"""FastAPI app — expõe o grafo médico via HTTP (Fase 7).

Endpoints:
- GET  /health                   — diagnóstico do servidor
- GET  /patients                 — lista de pacientes (dropdown da UI)
- GET  /patients/{patient_id}    — detalhe + exames pendentes
- POST /consult                  — roda o grafo e persiste audit
- GET  /audit                    — lista paginada com filtros
- GET  /audit/{request_id}       — detalhe completo (events + alerts + rag)

Carregamento do modelo: 1x no startup, via lifespan. Lifespan loga tempo
de carregamento e seta `app.state.model_loaded`.

Como rodar (dev):
    uv run uvicorn api.server:app --reload --port 8000

Docs interativas: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import (
    GraphRunner,
    get_audit_reader,
    require_doctor_id,
    run_graph_callable,
)
from api.schemas import (
    AlertEvent,
    AuditDetail,
    AuditListItem,
    ConsultRequest,
    ConsultResponse,
    GuardrailEvent,
    HealthResponse,
    PatientDetail,
    PatientSummary,
    PendingExam,
    RagRetrieval,
)
from assistant.audit.reader import AuditReader
from assistant.audit.schema import AUDIT_DB_PATH
from assistant.explainability import build_explanation
from assistant.tools.patient_records import (
    DB_PATH as PATIENTS_DB_PATH,
    get_patient_by_id,
    get_pending_exams,
    list_patients,
)

logger = logging.getLogger(__name__)

API_VERSION = "0.7.0"


# ────────────────────────────────────────────────────────────────────────
# Lifespan: carrega o grafo uma única vez no startup
# ────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carrega grafo (modelo MLX + retriever Chroma) no startup.

    Em testes, defina app.state.skip_warmup = True ANTES de fazer requests
    pra pular o warmup pesado.
    """
    app.state.model_loaded = False
    app.state.startup_seconds = None

    if getattr(app.state, "skip_warmup", False):
        logger.info("skip_warmup=True — pulando carregamento do grafo")
        app.state.model_loaded = True
        yield
        return

    t0 = time.monotonic()
    logger.info("Carregando grafo (modelo MLX + retriever Chroma)…")
    try:
        from assistant.graph import _get_graph
        _get_graph()  # força lazy build do singleton
        elapsed = time.monotonic() - t0
        app.state.startup_seconds = round(elapsed, 2)
        app.state.model_loaded = True
        logger.info("Grafo pronto em %.1fs", elapsed)
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha ao carregar grafo no startup: %s", e)
        # Servidor sobe mesmo em modo degradado — /health vai sinalizar.
        app.state.model_loaded = False

    yield
    # Shutdown: nada a fazer (o grafo não tem cleanup explícito).


app = FastAPI(
    title="Medical Assistant API",
    description=(
        "API de demonstração para assistente clínico com guardrails, "
        "auditoria e explainability. Dados sintéticos — não usar em "
        "decisões clínicas reais."
    ),
    version=API_VERSION,
    lifespan=lifespan,
)

# UI Streamlit roda em 8501; libera CORS pra ela.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────────────────────────────────
# /health
# ────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Status do servidor. Útil pro UI desenhar indicador verde/vermelho."""
    model_loaded = bool(getattr(app.state, "model_loaded", False))
    db_ok = PATIENTS_DB_PATH.exists()
    audit_ok = AUDIT_DB_PATH.exists()
    status = "ok" if (model_loaded and db_ok) else "degraded"
    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        db_accessible=db_ok,
        audit_db_accessible=audit_ok,
        version=API_VERSION,
        startup_seconds=getattr(app.state, "startup_seconds", None),
    )


# ────────────────────────────────────────────────────────────────────────
# /patients
# ────────────────────────────────────────────────────────────────────────

@app.get("/patients", response_model=list[PatientSummary], tags=["patients"])
def patients_list(limit: int = Query(100, ge=1, le=500)) -> list[PatientSummary]:
    """Lista resumida de pacientes — dropdown da UI."""
    rows = list_patients(limit=limit)
    return [PatientSummary(**r) for r in rows]


@app.get("/patients/{patient_id}", response_model=PatientDetail, tags=["patients"])
def patients_detail(patient_id: str) -> PatientDetail:
    """Detalhe do paciente + exames pendentes da tabela exames_pendentes."""
    try:
        rec = get_patient_by_id(patient_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Paciente {patient_id} não encontrado.")

    try:
        exams = get_pending_exams(patient_id)
    except FileNotFoundError:
        exams = []

    return PatientDetail(
        id=rec.id,
        nome=rec.nome,
        idade=rec.idade,
        sexo=rec.sexo,
        alergias=rec.alergias,
        medicacoes_atuais=rec.medicacoes_atuais,
        historico_resumido=rec.historico_resumido,
        pending_exams=[PendingExam(**e) for e in exams],
    )


# ────────────────────────────────────────────────────────────────────────
# /consult
# ────────────────────────────────────────────────────────────────────────

@app.post("/consult", response_model=ConsultResponse, tags=["consult"])
def consult(
    payload: ConsultRequest,
    doctor_id: Annotated[str, Depends(require_doctor_id)],
    runner: Annotated[GraphRunner, Depends(run_graph_callable)],
) -> ConsultResponse:
    """Roda o grafo completo numa pergunta. Persiste no audit DB.

    Header obrigatório: `X-Doctor-Id: <string>`. Esse valor é gravado em
    `interactions.doctor_id` (audit DB).
    """
    t0 = time.monotonic()
    try:
        state = runner(payload.question, payload.patient_id, doctor_id)
    except Exception as e:  # noqa: BLE001 — defensivo, último recurso
        logger.exception("Erro inesperado ao rodar grafo: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}") from e
    latency_ms = int((time.monotonic() - t0) * 1000)

    explanation = build_explanation(state)
    output_guards = state.get("output_guardrails_triggered") or []
    was_rewritten = any(r.get("action_taken") == "rewritten" for r in output_guards)
    has_alert = bool(state.get("alerts_emitted"))

    return ConsultResponse(
        request_id=state.get("request_id", ""),
        final_response=state.get("final_response", ""),
        explanation=explanation,
        latency_ms=latency_ms,
        urgency=state.get("urgency"),
        intent=state.get("intent"),
        was_rewritten=was_rewritten,
        has_alert=has_alert,
    )


# ────────────────────────────────────────────────────────────────────────
# /audit
# ────────────────────────────────────────────────────────────────────────

def _row_to_list_item(row, has_guard: bool, has_alert: bool) -> AuditListItem:
    return AuditListItem(
        request_id=row.request_id,
        ts=row.ts,
        question=row.question,
        patient_id=row.patient_id,
        doctor_id=row.doctor_id,
        intent=row.intent,
        urgency=row.urgency,
        bypass_detected=row.bypass_detected,
        has_guardrail=has_guard,
        has_alert=has_alert,
        latency_ms=row.latency_ms,
    )


def _enrich_with_flags(
    reader: AuditReader,
    rows,
) -> list[AuditListItem]:
    """Junta cada interaction com flags has_guardrail / has_alert.

    Faz 1 query agregada por flag — evita N+1.
    """
    if not rows:
        return []
    ids = [r.request_id for r in rows]
    placeholders = ",".join(["?"] * len(ids))
    conn = reader._connect()
    try:
        guard_set = {
            row[0] for row in conn.execute(
                f"SELECT DISTINCT request_id FROM guardrail_events "
                f"WHERE request_id IN ({placeholders}) AND triggered = 1",
                ids,
            ).fetchall()
        }
        alert_set = {
            row[0] for row in conn.execute(
                f"SELECT DISTINCT request_id FROM alerts "
                f"WHERE request_id IN ({placeholders})",
                ids,
            ).fetchall()
        }
    finally:
        conn.close()
    return [
        _row_to_list_item(r, r.request_id in guard_set, r.request_id in alert_set)
        for r in rows
    ]


@app.get("/audit", response_model=list[AuditListItem], tags=["audit"])
def audit_list(
    reader: Annotated[AuditReader, Depends(get_audit_reader)],
    limit: int = Query(50, ge=1, le=500),
    has_alerts: bool = Query(False),
    has_guardrail: bool = Query(False),
    patient_id: Optional[str] = Query(None, pattern=r"^P\d{4}$"),
) -> list[AuditListItem]:
    """Lista paginada de interações.

    Filtros são exclusivos entre si na prioridade abaixo (1 escolhido por vez):
    - `has_alerts` → só com alerta
    - `has_guardrail` → só com guardrail disparado
    - `patient_id` → só do paciente
    - sem filtro → mais recentes
    """
    if has_alerts:
        rows = reader.filter_has_alerts(limit=limit)
    elif has_guardrail:
        rows = reader.filter_has_guardrail(limit=limit)
    elif patient_id:
        rows = reader.filter_by_patient(patient_id, limit=limit)
    else:
        rows = reader.list_recent(limit=limit)
    return _enrich_with_flags(reader, rows)


@app.get("/audit/{request_id}", response_model=AuditDetail, tags=["audit"])
def audit_detail(
    request_id: str,
    reader: Annotated[AuditReader, Depends(get_audit_reader)],
) -> AuditDetail:
    """Detalhe completo de uma interação."""
    detail = reader.get_by_id(request_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"request_id {request_id} não encontrado.")

    snap = None
    if detail.interaction.state_snapshot:
        try:
            snap = json.loads(detail.interaction.state_snapshot)
        except json.JSONDecodeError:
            snap = None

    return AuditDetail(
        request_id=detail.interaction.request_id,
        ts=detail.interaction.ts,
        question=detail.interaction.question,
        patient_id=detail.interaction.patient_id,
        doctor_id=detail.interaction.doctor_id,
        intent=detail.interaction.intent,
        urgency=detail.interaction.urgency,
        bypass_detected=detail.interaction.bypass_detected,
        response=detail.interaction.response,
        latency_ms=detail.interaction.latency_ms,
        rag_has_sources=detail.interaction.rag_has_sources,
        state_snapshot=snap,
        guardrail_events=[
            GuardrailEvent(
                guardrail_name=e.guardrail_name,
                level=e.level,
                applies_to=e.applies_to,
                triggered=e.triggered,
                matched_patterns=e.matched_patterns,
                severity=e.severity,
                message=e.message,
                action_taken=e.action_taken,
            )
            for e in detail.guardrail_events
        ],
        alerts=[
            AlertEvent(
                request_id=a.request_id,
                ts=a.ts,
                patient_id=a.patient_id,
                urgency=a.urgency,
                summary=a.summary,
                acknowledged=a.acknowledged,
            )
            for a in detail.alerts
        ],
        rag_retrievals=[
            RagRetrieval(
                query=r.get("query", ""),
                top_k_results=r.get("top_k_results", []),
                had_sources=r.get("had_sources", False),
            )
            for r in detail.rag_retrievals
        ],
    )
