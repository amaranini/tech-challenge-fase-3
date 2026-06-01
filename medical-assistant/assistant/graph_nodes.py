"""Funções dos nós do grafo LangGraph (Fase 5).

Cada nó tem assinatura `(state: MedicalState) -> dict`:
- Recebe o State completo.
- Devolve APENAS as chaves que mudaram (LangGraph faz merge).
- Sempre adiciona 1 entrada em `node_trace`.
- Captura exceções e registra em `errors` (não propaga — grafo não crasha).

Convenção: nós que precisam de recursos externos (LLM, retriever, DB) são
construídos via fábricas `make_*_node(...)` que capturam o recurso em
closure. Nós sem dependências (ex: classify_intent, refuse_node) são
funções normais.

Justificativa dos try/except defensivos: o grafo PRECISA chegar até o
finalize_response em qualquer cenário, pra que o usuário sempre receba
alguma resposta. Erros internos vão pra `state.errors` e aparecem no
`/trace` do demo, mas não interrompem o fluxo.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from assistant.graph_prompts import (
    GENERATE_USER_TEMPLATE,
    REFUSE_TEMPLATE,
    TRIAGE_DEFAULT_FALLBACK,
    TRIAGE_SYSTEM_PROMPT,
    TRIAGE_USER_TEMPLATE,
    TRIAGE_VALID,
)
from assistant.graph_state import AlertEntry, MedicalState, NodeTraceEntry
from assistant.guardrails.bypass import REFUSE_MESSAGE as BYPASS_REFUSE_MESSAGE
from assistant.guardrails.registry import (
    OUTPUT_GUARDRAILS,
    run_input_guardrails,
    run_output_guardrails,
)
from assistant.guardrails.scope import SCOPE_NOTE
from assistant.intent_classifier import classify_intent_rules
from assistant.rag.retriever import ProtocolRetriever, RetrievedChunk
from assistant.router import PATIENT_ID_RE
from assistant.tools.patient_records import (
    PatientRecord,
    get_patient_by_id,
    get_pending_exams,
)

logger = logging.getLogger(__name__)

# Path do log estruturado de alertas (jsonl — uma linha por alerta).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALERTS_LOG_PATH = _PROJECT_ROOT / "logging_" / "alerts.jsonl"


# ────────────────────────────────────────────────────────────────────────
# Utilitários compartilhados
# ────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _make_trace(node: str, t_start: float, summary: str, error: str | None = None) -> NodeTraceEntry:
    return NodeTraceEntry(
        node=node,
        timestamp=_now_iso(),
        latency_s=round(time.monotonic() - t_start, 4),
        summary=summary,
        error=error,
    )


def _parse_label(raw_output: str, valid: tuple[str, ...]) -> str | None:
    """Procura uma das labels válidas no output bruto do LLM (lowercase + sem acento)."""
    text = raw_output.strip().lower()
    text = (text
            .replace("í", "i").replace("á", "a").replace("é", "e")
            .replace("ó", "o").replace("ú", "u").replace("ã", "a")
            .replace("ç", "c"))
    for label in valid:
        if re.search(rf"\b{re.escape(label)}\b", text):
            return label
    return None


def _call_llm(
    llm: BaseChatModel,
    system_prompt: str | None,
    user_prompt: str,
    max_tokens: int | None = None,
) -> str:
    """Invoca o LLM com system explícito (sobrepõe o system_prompt da instância).

    Importante: o MedicalLLM aceita SystemMessage no input e prioriza ele
    sobre o `self.system_prompt`. Por isso a gente passa o system aqui via
    SystemMessage, mesmo quando o llm já tem um default.
    """
    messages: list = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=user_prompt))

    kwargs = {}
    if max_tokens is not None:
        kwargs["config"] = {"max_tokens": max_tokens}
    try:
        result = llm.invoke(messages, **kwargs)
    except TypeError:
        result = llm.invoke(messages)
    return (result.content if hasattr(result, "content") else str(result)).strip()


# ────────────────────────────────────────────────────────────────────────
# Nó 1 — classify_intent (determinístico, sem LLM)
# ────────────────────────────────────────────────────────────────────────

def classify_intent(state: MedicalState) -> dict:
    """Classifica a intenção da pergunta por keyword matching.

    Roteador determinístico, coerente com `router.py` da Fase 4. Por que
    não LLM: o MedicalLLM (Qwen 1.5B + LoRA) é enviesado a classificar
    tudo como `clinica`. Validado em test_classifier_prompts.py.
    """
    t0 = time.monotonic()
    node = "classify_intent"
    question = state["question"]
    logger.info("[%s] question=%r", node, question[:80])

    try:
        intent, matched_kw = classify_intent_rules(question)
        logger.info("[%s] → %s (matched=%r)", node, intent, matched_kw)
        summary = (
            f"{intent} (kw={matched_kw!r})" if matched_kw
            else f"{intent} (nenhuma kw casou)"
        )
        trace = _make_trace(node, t0, summary=summary)
        return {"intent": intent, "node_trace": [trace]}

    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] exceção", node)
        trace = _make_trace(node, t0, summary=f"exceção: {e!s}", error=str(e))
        return {
            "intent": "clinica",
            "node_trace": [trace],
            "errors": [f"{node}: {e!s}"],
        }


# ────────────────────────────────────────────────────────────────────────
# Nó 2 — triage_urgency (LLM)
# ────────────────────────────────────────────────────────────────────────

def make_triage_urgency_node(classifier_llm: BaseChatModel) -> Callable[[MedicalState], dict]:
    """Fábrica do Nó 2. Capta o `classifier_llm` numa closure."""

    def triage_urgency(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "triage_urgency"
        question = state["question"]
        logger.info("[%s] question=%r", node, question[:80])

        try:
            raw = _call_llm(
                classifier_llm,
                TRIAGE_SYSTEM_PROMPT,
                TRIAGE_USER_TEMPLATE.format(question=question),
                max_tokens=8,
            )
            parsed = _parse_label(raw, TRIAGE_VALID)
            if parsed is None:
                logger.warning("[%s] parsing falhou raw=%r → fallback %r",
                               node, raw, TRIAGE_DEFAULT_FALLBACK)
                trace = _make_trace(
                    node, t0,
                    summary=f"raw={raw!r} → fallback={TRIAGE_DEFAULT_FALLBACK}",
                    error=f"parse_failed: raw={raw!r}",
                )
                return {
                    "urgency": TRIAGE_DEFAULT_FALLBACK,
                    "node_trace": [trace],
                    "errors": [f"{node}: parsing falhou, raw={raw!r}"],
                }
            logger.info("[%s] → %s", node, parsed)
            trace = _make_trace(node, t0, summary=f"raw={raw!r} → {parsed}")
            return {"urgency": parsed, "node_trace": [trace]}

        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] exceção", node)
            trace = _make_trace(node, t0, summary=f"exceção: {e!s}", error=str(e))
            return {
                "urgency": TRIAGE_DEFAULT_FALLBACK,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

    return triage_urgency


# ────────────────────────────────────────────────────────────────────────
# Nó 3 — fetch_patient_data
# Extrai ID via regex se não foi passado explicitamente. Consulta o DB.
# Skip gracioso se nenhum ID encontrado. Erros não-fatais → state.errors.
# ────────────────────────────────────────────────────────────────────────

def make_fetch_patient_data_node(
    patient_lookup: Callable[[str], Optional[PatientRecord]] = get_patient_by_id,
) -> Callable[[MedicalState], dict]:
    """Fábrica do Nó 3."""

    def fetch_patient_data(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "fetch_patient_data"
        question = state["question"]
        pid_from_state: Optional[str] = state.get("patient_id")

        # 1) Determinar patient_id (explícito > extraído via regex)
        if pid_from_state:
            pid = pid_from_state
            source = "argumento"
        else:
            matches = PATIENT_ID_RE.findall(question)
            if not matches:
                logger.info("[%s] sem patient_id → skip", node)
                trace = _make_trace(node, t0, summary="skip (sem patient_id)")
                return {"node_trace": [trace]}
            pid = matches[0]
            source = "regex"
            if len(matches) > 1:
                # Mais de um ID → loga warning, usa o primeiro
                logger.warning("[%s] múltiplos IDs %s — usando %s", node, matches, pid)

        # 2) Consultar DB
        try:
            rec = patient_lookup(pid)
        except FileNotFoundError as e:
            logger.warning("[%s] banco ausente: %s", node, e)
            trace = _make_trace(node, t0, summary=f"DB ausente para {pid}",
                                error=str(e))
            return {
                "patient_id": pid,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] erro no lookup", node)
            trace = _make_trace(node, t0, summary=f"erro lookup {pid}", error=str(e))
            return {
                "patient_id": pid,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

        if rec is None:
            logger.info("[%s] %s não encontrado", node, pid)
            trace = _make_trace(node, t0,
                                summary=f"{pid} ({source}) → NÃO ENCONTRADO",
                                error=f"patient_not_found:{pid}")
            return {
                "patient_id": pid,
                "patient_data": None,
                "node_trace": [trace],
                "errors": [f"{node}: paciente {pid} não encontrado"],
            }

        logger.info("[%s] %s → %s, %d anos", node, pid, rec.nome, rec.idade)
        trace = _make_trace(node, t0,
                            summary=f"{pid} ({source}) → {rec.nome}, {rec.idade}a")
        return {
            "patient_id": pid,
            "patient_data": rec.to_dict(),
            "node_trace": [trace],
        }

    return fetch_patient_data


# ────────────────────────────────────────────────────────────────────────
# Nó 4 — check_pending_exams
# Skip se sem patient_id. Não levanta exceção em paciente inexistente.
# ────────────────────────────────────────────────────────────────────────

def make_check_pending_exams_node(
    pending_exams_lookup: Callable[[str], list[dict]] = get_pending_exams,
) -> Callable[[MedicalState], dict]:
    """Fábrica do Nó 4."""

    def check_pending_exams(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "check_pending_exams"
        pid: Optional[str] = state.get("patient_id")

        if not pid:
            logger.info("[%s] sem patient_id → skip", node)
            trace = _make_trace(node, t0, summary="skip (sem patient_id)")
            return {"node_trace": [trace]}

        try:
            exams = pending_exams_lookup(pid)
            logger.info("[%s] %s → %d exame(s)", node, pid, len(exams))
            trace = _make_trace(node, t0,
                                summary=f"{pid} → {len(exams)} exame(s) pendente(s)")
            return {"pending_exams": exams, "node_trace": [trace]}
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] erro", node)
            trace = _make_trace(node, t0,
                                summary=f"erro consultando exames de {pid}",
                                error=str(e))
            return {
                "pending_exams": [],
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

    return check_pending_exams


# ────────────────────────────────────────────────────────────────────────
# Nó 5 — retrieve_protocol
# RAG com threshold; popula rag_chunks e rag_has_sources.
# ────────────────────────────────────────────────────────────────────────

def make_retrieve_protocol_node(
    retriever: ProtocolRetriever,
    top_k: int = 3,
    min_score: float = 0.55,
) -> Callable[[MedicalState], dict]:
    """Fábrica do Nó 5."""

    def retrieve_protocol(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "retrieve_protocol"
        question = state["question"]

        try:
            chunks: list[RetrievedChunk] = retriever.retrieve(
                question, top_k=top_k, min_score=min_score,
            )
            chunks_dict = [
                {
                    "text": c.text,
                    "source_file": c.source_file,
                    "section": c.section,
                    "specialty": c.specialty,
                    "score": round(c.score, 4),
                }
                for c in chunks
            ]
            has_sources = bool(chunks)
            logger.info("[%s] %d chunk(s) >= %.2f", node, len(chunks), min_score)
            scores = [round(c.score, 2) for c in chunks]
            trace = _make_trace(node, t0,
                                summary=f"{len(chunks)} chunk(s), scores={scores}")
            return {
                "rag_chunks": chunks_dict,
                "rag_has_sources": has_sources,
                "node_trace": [trace],
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] erro", node)
            trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
            return {
                "rag_chunks": [],
                "rag_has_sources": False,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

    return retrieve_protocol


# ────────────────────────────────────────────────────────────────────────
# Nó 6 — generate_response
# Monta prompt enriquecido (paciente + exames + protocolo) e chama LLM.
# ────────────────────────────────────────────────────────────────────────

def _format_patient_block(patient_data: Optional[dict]) -> str:
    if not patient_data:
        return ""
    p = patient_data
    lines = [
        "=== DADOS DO PACIENTE ===",
        f"ID: {p['id']} | {p['nome']} (sintético)",
        f"Idade: {p['idade']} anos | Sexo: {p['sexo']}",
        f"Alergias: {p.get('alergias') or '(nenhuma registrada)'}",
        f"Medicações em uso: {p.get('medicacoes_atuais') or '(nenhuma)'}",
        f"Histórico: {p.get('historico_resumido') or '(sem histórico relevante)'}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _format_exams_block(pending_exams: Optional[list[dict]]) -> str:
    if not pending_exams:
        return ""
    lines = ["=== EXAMES PENDENTES (em ordem de prioridade) ==="]
    for e in pending_exams:
        lines.append(
            f"- [{e['prioridade']}] {e['tipo_exame']} "
            f"(solicitado em {e['data_solicitacao']})"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _format_protocols_block(rag_chunks: Optional[list[dict]], rag_has_sources: bool) -> str:
    if rag_has_sources and rag_chunks:
        lines = ["=== CONTEXTO RECUPERADO DOS PROTOCOLOS INSTITUCIONAIS ===", ""]
        for i, c in enumerate(rag_chunks, start=1):
            lines.append(f"[Trecho {i}] Fonte: {c['source_file']} • Seção: {c['section']}")
            lines.append(c["text"])
            lines.append("")
        return "\n".join(lines) + "\n"
    # rag rodou mas não trouxe nada relevante → aviso explícito
    return (
        "=== ATENÇÃO ===\n"
        "Nenhum protocolo institucional claramente relevante foi encontrado. "
        "Responda com base no seu conhecimento geral, sinalize a incerteza, "
        "e prefira pedir mais contexto a inventar conduta.\n\n"
    )


def make_generate_response_node(
    llm: BaseChatModel,
) -> Callable[[MedicalState], dict]:
    """Fábrica do Nó 6 — usa o `llm` clínico (com system prompt da instância)."""

    def generate_response(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "generate_response"
        question = state["question"]
        patient_data = state.get("patient_data")
        pending_exams = state.get("pending_exams")
        rag_chunks = state.get("rag_chunks")
        rag_has_sources = state.get("rag_has_sources", False)

        try:
            user_prompt = GENERATE_USER_TEMPLATE.format(
                patient_block=_format_patient_block(patient_data),
                exams_block=_format_exams_block(pending_exams),
                protocols_block=_format_protocols_block(rag_chunks, rag_has_sources),
                question=question,
            )
            logger.info("[%s] prompt size=%d chars", node, len(user_prompt))
            # system=None → o MedicalLLM aplica o MEDICAL_SYSTEM_PROMPT default.
            response_text = _call_llm(llm, system_prompt=None, user_prompt=user_prompt)
            preview = response_text[:80].replace("\n", " ")
            trace = _make_trace(node, t0,
                                summary=f"{len(response_text)} chars: {preview!r}")
            return {"draft_response": response_text, "node_trace": [trace]}
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] erro", node)
            fallback = (
                "Não foi possível gerar uma resposta agora. Tente reformular "
                "a pergunta. Em emergências, encaminhe imediatamente para "
                "avaliação presencial."
            )
            trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
            return {
                "draft_response": fallback,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

    return generate_response


# ────────────────────────────────────────────────────────────────────────
# Nó 0 — input_guardrail_check (Fase 6)
# Roda guardrails input-side ANTES do classify_intent. Se bypass dispara,
# o grafo curto-circuita pro refuse_node (com mensagem específica de segurança).
# ────────────────────────────────────────────────────────────────────────

def input_guardrail_check(state: MedicalState) -> dict:
    """Aplica guardrails input-side na pergunta original.

    Hoje só o `BypassAttemptGuardrail` é input-side. Quando ele dispara,
    seta `bypass_detected=True` pra o roteamento do grafo encaminhar
    direto pro refuse_node, pulando classify_intent + RAG + LLM.
    """
    t0 = time.monotonic()
    node = "input_guardrail_check"
    question = state["question"]
    logger.info("[%s] question=%r", node, question[:80])

    try:
        results = run_input_guardrails(question)
        triggered = [r for r in results if r.triggered]
        bypass = any(r.guardrail_name == "bypass_attempt" and r.triggered for r in results)

        if bypass:
            logger.warning("[%s] BYPASS DETECTADO: %s", node, triggered[0].matched_patterns)
            summary = f"BYPASS: {triggered[0].message}"
        elif triggered:
            summary = f"{len(triggered)} input guardrail(s) triggered"
        else:
            summary = "nenhum disparo"

        trace = _make_trace(node, t0, summary=summary)
        # Sempre armazena TODOS os results (triggered ou não) pra audit completo
        return {
            "input_guardrails_triggered": [r.to_dict() for r in results],
            "bypass_detected": bypass,
            "node_trace": [trace],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] erro", node)
        trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
        return {
            "input_guardrails_triggered": [],
            "bypass_detected": False,
            "node_trace": [trace],
            "errors": [f"{node}: {e!s}"],
        }


# ────────────────────────────────────────────────────────────────────────
# Nó 7 — guardrail_check (Fase 6, refatorado)
# Roda os 4 output-side guardrails. Anexa NOTAS de warnings ao draft.
# Roteamento (conditional edge no graph.py): se algum BLOCK triggered →
# rewrite_node; senão → emit_alert.
# ────────────────────────────────────────────────────────────────────────

def guardrail_check(state: MedicalState) -> dict:
    """Aplica guardrails output-side ao draft_response.

    Substitui a versão simplista da Fase 5. Agora:
    - Roda 4 output guardrails (prescrição, diagnóstico, decisão, escopo).
    - Para WARNINGS triggered: anexa nota ao draft (sem chamar LLM).
    - Para BLOCKS triggered: NÃO reescreve aqui — só sinaliza. Quem reescreve
      é o rewrite_node, acessado via conditional edge.
    """
    t0 = time.monotonic()
    node = "guardrail_check"
    draft = state.get("draft_response", "") or ""

    try:
        results = run_output_guardrails(draft)
        triggered = [r for r in results if r.triggered]

        # Anexa notas de warnings (já que warnings não precisam de LLM)
        new_draft = draft
        for r in triggered:
            if r.level == "warning" and r.guardrail_name == "fora_escopo_residual":
                if SCOPE_NOTE.strip() not in new_draft:
                    new_draft = new_draft + SCOPE_NOTE
                r.action_taken = "note_appended"

        blocks_triggered = [r for r in triggered if r.level == "block"]
        if blocks_triggered:
            summary = f"{len(blocks_triggered)} block(s) triggered: {blocks_triggered[0].guardrail_name}"
            logger.warning("[%s] %s", node, summary)
        elif triggered:
            summary = f"{len(triggered)} warning(s) triggered"
            logger.info("[%s] %s", node, summary)
        else:
            summary = "sem disparos"
            logger.info("[%s] %s", node, summary)

        trace = _make_trace(node, t0, summary=summary)
        return {
            "draft_response": new_draft,
            "output_guardrails_triggered": [r.to_dict() for r in results],
            "node_trace": [trace],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] erro", node)
        trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
        return {
            "output_guardrails_triggered": [],
            "node_trace": [trace],
            "errors": [f"{node}: {e!s}"],
        }


# ────────────────────────────────────────────────────────────────────────
# Nó 8 — emit_alert_if_needed
# Se urgency == "alta", grava entrada em logging_/alerts.jsonl.
# ────────────────────────────────────────────────────────────────────────

def _ensure_alerts_log() -> None:
    ALERTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def emit_alert_if_needed(state: MedicalState) -> dict:
    """Emite alerta se urgência for alta. Caso contrário, no-op."""
    t0 = time.monotonic()
    node = "emit_alert_if_needed"
    urgency = state.get("urgency")
    question = state.get("question", "")
    pid = state.get("patient_id")
    draft = state.get("draft_response", "") or ""

    if urgency != "alta":
        logger.info("[%s] urgency=%s → no-op", node, urgency)
        trace = _make_trace(node, t0, summary=f"no-op (urgency={urgency})")
        return {"node_trace": [trace]}

    try:
        entry: AlertEntry = AlertEntry(
            timestamp=_now_iso(),
            patient_id=pid,
            question=question,
            urgency="alta",
            summary=(draft[:200] + " […]") if len(draft) > 200 else draft,
        )
        _ensure_alerts_log()
        with ALERTS_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Print visível pro vídeo
        print(f"⚠️  ALERTA EMITIDO: urgência alta para paciente {pid or '<sem ID>'} "
              f"(notificação simulada — alerts.jsonl)")
        logger.warning("[%s] ALERTA emitido pid=%s", node, pid)
        trace = _make_trace(node, t0, summary=f"ALERTA emitido pid={pid}")
        return {"alerts_emitted": [entry], "node_trace": [trace]}
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] erro ao gravar alerta", node)
        trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
        return {"node_trace": [trace], "errors": [f"{node}: {e!s}"]}


# ────────────────────────────────────────────────────────────────────────
# Nó 9 — finalize_response
# Monta resposta final: draft + fontes + disclaimer + (se alta) aviso.
# ────────────────────────────────────────────────────────────────────────

_DISCLAIMER = "*Esta orientação é apoio à decisão; a conduta final cabe ao médico assistente.*"


def finalize_response(state: MedicalState) -> dict:
    """Monta `final_response` formatada."""
    t0 = time.monotonic()
    node = "finalize_response"
    draft = state.get("draft_response", "") or ""
    rag_has_sources = state.get("rag_has_sources", False)
    rag_chunks = state.get("rag_chunks") or []
    alerts = state.get("alerts_emitted") or []

    try:
        parts: list[str] = [draft.strip()]

        # 1) Fontes (se RAG trouxe)
        if rag_has_sources and rag_chunks:
            parts.append("")
            parts.append("**Fontes consultadas:**")
            for c in rag_chunks:
                parts.append(f"- {c['source_file']} · _{c['section']}_ (score {c['score']})")

        # 2) Disclaimer (só se a resposta não terminar com algo similar)
        if "conduta final cabe" not in draft.lower():
            parts.append("")
            parts.append(_DISCLAIMER)

        # 3) Aviso de alerta
        if alerts:
            parts.append("")
            parts.append("🚨 **Alerta de urgência alta foi notificado à equipe.**")

        final = "\n".join(parts)
        logger.info("[%s] final size=%d chars", node, len(final))
        trace = _make_trace(node, t0, summary=f"final={len(final)} chars")
        return {"final_response": final, "node_trace": [trace]}
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] erro", node)
        # Mesmo se a formatação der errado, devolve o draft cru.
        trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
        return {
            "final_response": draft or "(sem resposta gerada)",
            "node_trace": [trace],
            "errors": [f"{node}: {e!s}"],
        }


# ────────────────────────────────────────────────────────────────────────
# Nó auxiliar — refuse_node
# Vira de classify_intent quando intent == "fora_de_escopo".
# Resposta fixa, sem chamar LLM.
# ────────────────────────────────────────────────────────────────────────

def refuse_node(state: MedicalState) -> dict:
    """Gera resposta de recusa. Mensagem depende do motivo:

    - `bypass_detected=True` → mensagem firme de segurança (BYPASS_REFUSE_MESSAGE)
    - senão (intent=fora_de_escopo) → mensagem educada padrão (REFUSE_TEMPLATE)
    """
    t0 = time.monotonic()
    node = "refuse_node"
    question = state.get("question", "")
    short = (question[:60] + " […]") if len(question) > 60 else question

    if state.get("bypass_detected"):
        text = BYPASS_REFUSE_MESSAGE
        summary = "recusa por bypass detectado"
        logger.warning("[%s] %s", node, summary)
    else:
        text = REFUSE_TEMPLATE.format(question_short=short)
        summary = "recusa por fora_de_escopo (template fixo)"
        logger.info("[%s] %s", node, summary)

    trace = _make_trace(node, t0, summary=summary)
    return {"draft_response": text, "node_trace": [trace]}


# ────────────────────────────────────────────────────────────────────────
# Nó auxiliar — rewrite_node
# Vira de guardrail_check quando alguma flag foi detectada.
# Reescreve via LLM sem prescrição direta.
# ────────────────────────────────────────────────────────────────────────

def make_rewrite_node(llm: BaseChatModel) -> Callable[[MedicalState], dict]:
    """Fábrica do rewrite_node — usa o `llm` clínico.

    Versão Fase 6: lê os `output_guardrails_triggered` do state, filtra os
    BLOCKs, monta UM prompt combinado (1 chamada ao LLM) endereçando todos
    os problemas detectados. Marca cada result com `action_taken="rewritten"`.
    """

    def rewrite_node(state: MedicalState) -> dict:
        t0 = time.monotonic()
        node = "rewrite_node"
        draft = state.get("draft_response", "") or ""
        results_dicts = state.get("output_guardrails_triggered") or []

        # Reconstrói GuardrailResult a partir dos dicts e filtra blocks
        from assistant.guardrails.base import GuardrailResult
        triggered_blocks = []
        for d in results_dicts:
            if d.get("triggered") and d.get("level") == "block":
                # Pega a instância do guardrail registrado pra acessar rewrite_prompt
                gr = next(
                    (g for g in OUTPUT_GUARDRAILS if g.name == d["guardrail_name"]),
                    None,
                )
                if gr is None:
                    continue
                triggered_blocks.append((gr, GuardrailResult(
                    guardrail_name=d["guardrail_name"],
                    triggered=True,
                    level=d.get("level", "block"),
                    applies_to=d.get("applies_to", "output"),
                    matched_patterns=list(d.get("matched_patterns", [])),
                    severity=d.get("severity", 0.0),
                    message=d.get("message", ""),
                )))

        if not triggered_blocks:
            # Não devia chegar aqui via conditional edge, mas defensivo
            logger.info("[%s] sem blocks pra reescrever — no-op", node)
            trace = _make_trace(node, t0, summary="sem blocks pra reescrever")
            return {"node_trace": [trace]}

        logger.info("[%s] reescrevendo (%d blocks)", node, len(triggered_blocks))

        try:
            # Constrói prompt combinado (registry helper)
            from assistant.guardrails.registry import _build_combined_rewrite_prompt
            prompt = _build_combined_rewrite_prompt(draft, triggered_blocks)
            rewritten = _call_llm(llm, system_prompt=None, user_prompt=prompt)

            # Atualiza action_taken nos dicts do state
            for d in results_dicts:
                if d.get("triggered") and d.get("level") == "block":
                    d["action_taken"] = "rewritten"

            trace = _make_trace(
                node, t0,
                summary=f"reescrito ({len(rewritten)} chars, {len(triggered_blocks)} block(s))",
            )
            # Substitui a lista inteira (não usa o reducer add) — voltamos o
            # state com a lista atualizada (1 forma de "overwrite": passar a
            # mesma lista com mudanças).
            return {
                "draft_response": rewritten,
                "output_guardrails_triggered": results_dicts,
                "node_trace": [trace],
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] erro no rewrite", node)
            # Marca action_taken="rewrite_failed" pra audit
            for d in results_dicts:
                if d.get("triggered") and d.get("level") == "block":
                    d["action_taken"] = f"rewrite_failed: {e!s}"
            trace = _make_trace(node, t0, summary=f"erro: {e!s}", error=str(e))
            return {
                "output_guardrails_triggered": results_dicts,
                "node_trace": [trace],
                "errors": [f"{node}: {e!s}"],
            }

    return rewrite_node
