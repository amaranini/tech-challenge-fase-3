"""Chain LangChain principal: roteia → recupera → enriquece prompt → gera → anexa fontes.

`build_medical_chain(...)` retorna um `Runnable` que aceita
`{"question": str, "use_rag": bool (opcional, default True)}` e devolve um dict:

    {
        "response": str,
        "sources": list[dict],          # fontes RAG com score (Estratégia B)
        "patient_data": list[dict],      # pacientes consultados (ou marcador de não-encontrado)
        "routing": dict,                 # decisão do roteador
        "latencies": dict,               # tempos de cada etapa em segundos
    }

A chain NÃO usa tool calling nativo do modelo. A decisão de chamar RAG ou
consultar paciente é tomada pelo `router.route()` ANTES do LLM ser chamado.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda

from assistant.rag.retriever import ProtocolRetriever, RetrievedChunk
from assistant.router import route
from assistant.tools.patient_records import PatientRecord, get_patient_by_id

logger = logging.getLogger(__name__)


# Template enriquecido. Sem placeholders se o bloco estiver vazio (sem RAG / sem paciente).
_USER_PROMPT_TEMPLATE = """{protocols_block}{patient_block}=== PERGUNTA ===
{question}

Use o contexto acima APENAS se for relevante para a pergunta. Se faltar algum dado clínico essencial (idade, peso, alergias, comorbidades, sinais vitais), peça antes de orientar."""


def _format_chunks_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines = ["=== CONTEXTO RECUPERADO DOS PROTOCOLOS INSTITUCIONAIS ===", ""]
    for i, c in enumerate(chunks, start=1):
        lines.append(
            f"[Trecho {i}] Fonte: {c.source_file} • Seção: {c.section}"
        )
        lines.append(c.text)
        lines.append("")
    return "\n".join(lines) + "\n"


def _format_patient_block(patients: list[dict]) -> str:
    if not patients:
        return ""
    lines = ["=== DADOS DO(S) PACIENTE(S) ===", ""]
    for p in patients:
        if p["record"] is None:
            lines.append(f"Paciente {p['id']}: NÃO ENCONTRADO no banco.")
            lines.append("")
            continue
        r = p["record"]
        lines.append(f"Paciente {r.id}: {r.nome} (sintético)")
        lines.append(f"Idade: {r.idade} anos | Sexo: {r.sexo}")
        lines.append(f"Alergias: {r.alergias or '(nenhuma registrada)'}")
        lines.append(f"Medicações em uso: {r.medicacoes_atuais or '(nenhuma)'}")
        lines.append(f"Histórico: {r.historico_resumido}")
        if r.exames_pendentes:
            lines.append(f"Exames pendentes: {', '.join(r.exames_pendentes)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _chunk_to_source_dict(c: RetrievedChunk) -> dict:
    return {
        "source_file": c.source_file,
        "title": c.title,
        "section": c.section,
        "specialty": c.specialty,
        "score": round(c.score, 4),
        "text_preview": c.text[:300] + (" […]" if len(c.text) > 300 else ""),
    }


def _patient_to_dict(record: PatientRecord | None, pid: str) -> dict:
    if record is None:
        return {"id": pid, "found": False, "record": None}
    return {"id": pid, "found": True, "record": record.to_dict()}


def build_medical_chain(
    llm: BaseChatModel,
    retriever: ProtocolRetriever | None = None,
    patient_lookup: Callable[[str], PatientRecord | None] | None = None,
    system_prompt: str | None = None,
    top_k: int = 3,
    min_score: float | None = None,
) -> Runnable:
    """Constrói a chain principal.

    Parâmetros:
        llm: instância de BaseChatModel (ex: MedicalLLM).
        retriever: ProtocolRetriever; se None, RAG é desligado.
        patient_lookup: função que aceita ID e devolve PatientRecord|None;
            default = get_patient_by_id.
        system_prompt: se None, usa o system_prompt da instância do llm
            (passa via SystemMessage só se o llm não tiver um próprio).
        top_k: quantos chunks recuperar do RAG (antes da filtragem).
        min_score: threshold cosseno; chunks abaixo são descartados.
            Quando o filtro zera tudo, a chain injeta um AVISO no prompt
            indicando "sem contexto relevante encontrado".
    """
    if patient_lookup is None:
        patient_lookup = get_patient_by_id

    def orchestrate(inputs: dict[str, Any]) -> dict[str, Any]:
        question = inputs["question"]
        use_rag = inputs.get("use_rag", True)

        # 1) Roteamento
        t = time.monotonic()
        routing = route(question)
        t_router = time.monotonic() - t

        # 2) RAG (opcional)
        chunks: list[RetrievedChunk] = []
        rag_attempted = False
        t_rag = 0.0
        if use_rag and routing.needs_rag and retriever is not None:
            rag_attempted = True
            t = time.monotonic()
            chunks = retriever.retrieve(question, top_k=top_k, min_score=min_score)
            t_rag = time.monotonic() - t

        # 3) Lookup de paciente (opcional)
        patient_block_data: list[dict] = []
        t_patient = 0.0
        if routing.needs_patient:
            t = time.monotonic()
            for pid in routing.patient_ids:
                try:
                    rec = patient_lookup(pid)
                except FileNotFoundError as e:
                    logger.warning("Banco de pacientes ausente: %s", e)
                    rec = None
                patient_block_data.append({"id": pid, "record": rec})
            t_patient = time.monotonic() - t

        # 4) Prompt enriquecido
        protocols_block = _format_chunks_block(chunks)

        # Quando o RAG foi tentado mas a filtragem (min_score) zerou os chunks,
        # injetamos um aviso transparente pro LLM. Sem isso, o modelo
        # "responde do nada" sem saber que não há respaldo dos protocolos.
        if rag_attempted and not chunks:
            protocols_block = (
                "=== ATENÇÃO ===\n"
                "Nenhum protocolo institucional claramente relevante foi "
                "encontrado para esta pergunta. Responda com base apenas "
                "no seu conhecimento geral, sinalize a incerteza explicitamente, "
                "e prefira pedir mais contexto a inventar conduta.\n\n"
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            protocols_block=protocols_block,
            patient_block=_format_patient_block(patient_block_data),
            question=question,
        )

        # 5) LLM
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_prompt))

        t = time.monotonic()
        ai_msg = llm.invoke(messages)
        t_llm = time.monotonic() - t

        response_text = (
            ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
        ).strip()

        # 6) Resultado estruturado (fontes anexadas programaticamente — Estratégia B)
        return {
            "response": response_text,
            "sources": [_chunk_to_source_dict(c) for c in chunks],
            "patient_data": [
                _patient_to_dict(p["record"], p["id"]) for p in patient_block_data
            ],
            "routing": routing.to_dict(),
            "latencies": {
                "router": round(t_router, 4),
                "rag": round(t_rag, 4),
                "patient": round(t_patient, 4),
                "llm": round(t_llm, 4),
                "total": round(t_router + t_rag + t_patient + t_llm, 4),
            },
            "prompt": user_prompt,  # útil pra debug / eval
        }

    return RunnableLambda(orchestrate)


def build_default_chain() -> Runnable:
    """Constrói a chain com defaults do projeto: MedicalLLM + ProtocolRetriever + SQLite."""
    from assistant.config import RAG_MIN_SCORE
    from assistant.llm import build_default_llm

    llm = build_default_llm()
    # llm já tem system_prompt aplicado via build_default_llm.
    # A chain NÃO duplica o system; o llm cuida disso ao receber HumanMessage.
    retriever = ProtocolRetriever()
    return build_medical_chain(
        llm=llm,
        retriever=retriever,
        patient_lookup=get_patient_by_id,
        system_prompt=None,  # delegado ao MedicalLLM
        top_k=3,
        min_score=RAG_MIN_SCORE,
    )
