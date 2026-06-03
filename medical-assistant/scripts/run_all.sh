#!/usr/bin/env bash
# Sobe API (FastAPI/uvicorn) e UI (Streamlit) em paralelo.
# Ctrl+C derruba os dois processos (via trap).
#
# Uso:
#   bash scripts/run_all.sh
#
# Variáveis opcionais:
#   API_PORT=8000     porta do FastAPI
#   UI_PORT=8501      porta do Streamlit
#   API_URL=http://localhost:$API_PORT  URL completa que a UI consome
#
# Logs ficam em logging_/ (criado se não existir) — fora do controle do git.

set -euo pipefail

API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
API_URL="${API_URL:-http://localhost:${API_PORT}}"

# Garante que estamos na raiz do projeto (medical-assistant/), não no scripts/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

mkdir -p logging_

# ─── PIDs ─────────────────────────────────────────────────────────────
API_PID=""
UI_PID=""

cleanup() {
    echo ""
    echo "🛑 Encerrando serviços…"
    [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
    [[ -n "$UI_PID"  ]] && kill "$UI_PID"  2>/dev/null || true
    # Espera 1s e força se ainda vivo
    sleep 1
    [[ -n "$API_PID" ]] && kill -9 "$API_PID" 2>/dev/null || true
    [[ -n "$UI_PID"  ]] && kill -9 "$UI_PID"  2>/dev/null || true
    echo "✓ Tudo parado."
    exit 0
}

trap cleanup INT TERM

# ─── Banner ───────────────────────────────────────────────────────────
cat <<EOF

═══════════════════════════════════════════════════════════════════════
  Medical Assistant — Demo completa (Fase 7)
═══════════════════════════════════════════════════════════════════════
  API (FastAPI):     http://localhost:${API_PORT}
  API docs:          http://localhost:${API_PORT}/docs
  UI (Streamlit):    http://localhost:${UI_PORT}

  Aguarde ~30-60s pelo carregamento do modelo MLX na primeira vez.
  Ctrl+C derruba os dois serviços.
═══════════════════════════════════════════════════════════════════════

EOF

# ─── Sobe API ─────────────────────────────────────────────────────────
echo "▶ Iniciando API (FastAPI/uvicorn) na porta ${API_PORT}…"
uv run uvicorn api.server:app --port "${API_PORT}" --log-level info \
    > "logging_/api.log" 2>&1 &
API_PID=$!
echo "  PID=${API_PID} · log: logging_/api.log"

# ─── Espera health-check da API antes de subir a UI ──────────────────
echo "⏳ Esperando API ficar pronta (health check)…"
for i in $(seq 1 60); do
    if curl -sf "${API_URL}/health" > /dev/null 2>&1; then
        echo "✓ API pronta após ${i}s."
        break
    fi
    if ! kill -0 "${API_PID}" 2>/dev/null; then
        echo "❌ API caiu durante o startup. Veja logging_/api.log."
        tail -20 "logging_/api.log"
        cleanup
    fi
    sleep 1
done

if ! curl -sf "${API_URL}/health" > /dev/null 2>&1; then
    echo "❌ API não respondeu em 60s. Veja logging_/api.log."
    cleanup
fi

# ─── Sobe UI ──────────────────────────────────────────────────────────
echo ""
echo "▶ Iniciando UI (Streamlit) na porta ${UI_PORT}…"
MEDICAL_API_URL="${API_URL}" \
    uv run streamlit run ui/app.py \
    --server.port "${UI_PORT}" \
    --server.headless true \
    --browser.gatherUsageStats false \
    > "logging_/ui.log" 2>&1 &
UI_PID=$!
echo "  PID=${UI_PID} · log: logging_/ui.log"

echo ""
echo "✨ Tudo no ar. Abra http://localhost:${UI_PORT} no navegador."
echo "   (Ctrl+C aqui derruba os dois.)"
echo ""

# Mantém o script vivo até receber INT/TERM
wait
