"""Config central do pacote `assistant`.

Lê variáveis do `.env` na raiz do projeto e expõe constantes para o
restante do código. Para validar o adapter no filesystem, usar
`validate_adapter_path()` — não validamos no import-time pra não
quebrar testes que rodam sem o adapter.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega .env da raiz do projeto (medical-assistant/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Modelo base — versão bf16 é a única que permite LoRA no MLX.
MODEL_PATH: str = os.getenv("MODEL_PATH", "mlx-community/Qwen2.5-1.5B-Instruct-bf16")

# Adapter LoRA treinado na Fase 2.
ADAPTER_PATH: str = os.getenv("ADAPTER_PATH", "./finetuning/output/adapters")

# Defaults de geração.
DEFAULT_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
DEFAULT_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
DEFAULT_TOP_P: float = float(os.getenv("LLM_TOP_P", "0.95"))


def validate_adapter_path() -> Path:
    """Resolve e valida `ADAPTER_PATH`. Levanta erro claro se não existir.

    Útil em scripts que precisam falhar cedo (antes de baixar 3 GB de
    modelo só pra descobrir que o adapter não está lá).
    """
    path = Path(ADAPTER_PATH).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Adapter LoRA não encontrado em '{path}'.\n"
            f"Como resolver:\n"
            f"  1) Treinar: uv run python finetuning/train.py\n"
            f"  2) Ou ajustar ADAPTER_PATH no .env apontando pro path correto."
        )
    return path
