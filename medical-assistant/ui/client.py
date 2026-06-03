"""Cliente HTTP da UI para a API local (Fase 7).

Wrapper fino em torno de `httpx.Client`. Centraliza:
- base URL (env var `MEDICAL_API_URL`, default http://localhost:8000)
- header X-Doctor-Id (passado por argumento — nunca em variável global)
- tratamento uniforme de erro (devolve dict com chave 'error' ao invés de
  levantar — torna o uso na UI mais simples)
- timeout generoso (60s) pq o /consult pode levar segundos

A UI NUNCA importa `assistant.*` ou `api.*` — só este wrapper. Isso garante
que o desacoplamento HTTP fica enforced no código (regra final da Fase 7).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = os.environ.get("MEDICAL_API_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)


class APIClient:
    """Cliente HTTP da API. Mantenha 1 instância por sessão Streamlit."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: httpx.Timeout = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    # ─── Internals ─────────────────────────────────────────────────────

    def _get(self, path: str, **kwargs) -> dict | list:
        try:
            r = self._client.get(path, **kwargs)
            if r.status_code >= 400:
                return {"error": f"HTTP {r.status_code}", "detail": _safe_detail(r)}
            return r.json()
        except httpx.ConnectError:
            return {"error": "connect_error",
                    "detail": f"Não consegui conectar em {self.base_url}. "
                              "A API está rodando?"}
        except httpx.TimeoutException:
            return {"error": "timeout",
                    "detail": "API demorou muito pra responder."}
        except Exception as e:  # noqa: BLE001
            return {"error": "unknown", "detail": str(e)}

    def _post(self, path: str, json: dict, headers: dict | None = None) -> dict:
        try:
            r = self._client.post(path, json=json, headers=headers or {})
            if r.status_code >= 400:
                return {"error": f"HTTP {r.status_code}", "detail": _safe_detail(r)}
            return r.json()
        except httpx.ConnectError:
            return {"error": "connect_error",
                    "detail": f"Não consegui conectar em {self.base_url}."}
        except httpx.TimeoutException:
            return {"error": "timeout",
                    "detail": "API demorou muito pra responder."}
        except Exception as e:  # noqa: BLE001
            return {"error": "unknown", "detail": str(e)}

    # ─── Endpoints ─────────────────────────────────────────────────────

    def health(self) -> dict:
        return self._get("/health")  # type: ignore[return-value]

    def list_patients(self, limit: int = 100) -> list[dict] | dict:
        return self._get("/patients", params={"limit": limit})

    def get_patient(self, patient_id: str) -> dict:
        return self._get(f"/patients/{patient_id}")  # type: ignore[return-value]

    def consult(
        self,
        question: str,
        patient_id: str | None,
        doctor_id: str,
    ) -> dict:
        return self._post(
            "/consult",
            json={"question": question, "patient_id": patient_id},
            headers={"X-Doctor-Id": doctor_id},
        )

    def list_audit(
        self,
        limit: int = 50,
        has_alerts: bool = False,
        has_guardrail: bool = False,
        patient_id: str | None = None,
    ) -> list[dict] | dict:
        params: dict[str, Any] = {"limit": limit}
        if has_alerts:
            params["has_alerts"] = "true"
        if has_guardrail:
            params["has_guardrail"] = "true"
        if patient_id:
            params["patient_id"] = patient_id
        return self._get("/audit", params=params)

    def get_audit_detail(self, request_id: str) -> dict:
        return self._get(f"/audit/{request_id}")  # type: ignore[return-value]

    def close(self) -> None:
        self._client.close()


def _safe_detail(response: httpx.Response) -> str:
    """Extrai detail da resposta de erro do FastAPI, com fallback."""
    try:
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        return response.text[:500]
    except Exception:  # noqa: BLE001
        return response.text[:500]


def is_error(payload: dict | list) -> bool:
    """True se o retorno do client representa erro."""
    return isinstance(payload, dict) and "error" in payload
