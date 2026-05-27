"""Classificador de intenção determinístico (Nó 1 do grafo, Fase 5).

Não usa LLM. Faz match por palavras-chave / expressões em 3 categorias:
- "administrativa": ops/gestão hospitalar (plantão, agenda, escala, ...)
- "clinica":       prática clínica (paciente, sintoma, protocolo, ...)
- "fora_de_escopo": qualquer outra coisa

Decisão arquitetural (Fase 5): o MedicalLLM fine-tuned em diálogos clínicos
tem viés forte para enxergar tudo como "clinica", mesmo com few-shot
reforçado. Validado empiricamente em `test_classifier_prompts.py` (3/5 na v1
e na v2 dos prompts LLM-based). Trocar pra Qwen base aumentaria pressão de
RAM no M1 16GB. A classificação é binária-ish, então um roteador
determinístico (estilo `router.py` da Fase 4) é a ferramenta certa pro
problema.

Ordem das checagens:
1. ADMIN_KEYWORDS — checadas primeiro porque vocabulário admin pode
   coexistir com termos médicos contextuais ("plantão da emergência" deve
   classificar como admin).
2. MEDICAL_KEYWORDS — se não foi admin.
3. Fallback: "fora_de_escopo".

Para auditoria: a função retorna também a palavra-chave que disparou o
match (em `node_trace` no graph_nodes.py).
"""

from __future__ import annotations

from typing import Literal

Intent = Literal["clinica", "administrativa", "fora_de_escopo"]


# ────────────────────────────────────────────────────────────────────────
# Vocabulários
# ────────────────────────────────────────────────────────────────────────

# Frases multi-palavra MUST vir antes das palavras simples na busca,
# porque alguma das simples ("plantão") aparece dentro das frases.
ADMIN_KEYWORDS: tuple[str, ...] = (
    # Frases (mais específicas, checadas antes)
    "que horas",
    "fechamento do livro",
    "livro do plantão", "livro do plantao",
    "sistema interno",
    "sistema de prontuário", "sistema de prontuario",
    "marcar consulta", "marcar exame", "remarcar consulta",
    "recursos humanos",
    # Palavras simples (operações hospitalares)
    "plantão", "plantao",
    "agenda", "agendar", "agendamento",
    "horário", "horario",
    "cadastro", "cadastrar",
    "fila",
    "diretor", "diretoria", "gestão", "gestao",
    "papelada", "burocracia",
    "turno", "escala", "expediente",
)

MEDICAL_KEYWORDS: tuple[str, ...] = (
    # Atores
    "paciente", "pacientes",
    "médico", "medico", "enfermeira", "enfermeiro",
    # Sintomas / sinais
    "sintoma", "sintomas", "dor", "febre", "tosse", "dispneia", "cianose",
    "taquicardia", "bradicardia",
    "hipertensão", "hipertensao", "hipotensão", "hipotensao",
    "convulsão", "convulsao", "convulsionando",
    "hipotonia", "hipóxia", "hipoxia",
    "anafilaxia", "choque",
    "parada cardiorrespiratória", "parada cardiorrespiratoria",
    "parada cardíaca", "parada cardiaca",
    # Diagnósticos / condições
    "sepse", "asma", "asmática", "asmatica",
    "diabetes", "diabético", "diabetico",
    "iam", "avc", "tev", "embolia", "pneumonia",
    "infecção", "infeccao",
    "emergência", "emergencia", "urgência", "urgencia",
    # Conduta / processo clínico
    "protocolo", "protocolos",
    "diagnóstico", "diagnostico",
    "tratamento", "tratamentos",
    "conduta", "condutas",
    "dose", "doses", "posologia",
    "medicação", "medicacao", "medicamento", "remédio", "remedio",
    "prescrição", "prescricao", "prescrever", "prescreva", "prescrevo",
    "recomendo",
    "exame", "exames", "gasometria", "hemograma", "glicemia",
    "raio-x", "tomografia", "ecg", "holter",
    "crise",
    "pressão arterial", "pressao arterial",
    "rcp", "manejo", "manejar",
)


# ────────────────────────────────────────────────────────────────────────
# API
# ────────────────────────────────────────────────────────────────────────

def classify_intent_rules(question: str) -> tuple[Intent, str | None]:
    """Classifica a intenção da mensagem.

    Retorna (intent, matched_keyword).
    `matched_keyword` é a primeira palavra-chave que disparou o match (útil
    pra trace/auditoria) ou None quando caiu em fora_de_escopo.
    """
    q = question.lower()

    for kw in ADMIN_KEYWORDS:
        if kw in q:
            return "administrativa", kw

    for kw in MEDICAL_KEYWORDS:
        if kw in q:
            return "clinica", kw

    return "fora_de_escopo", None
