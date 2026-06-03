"""UI Streamlit do assistente clínico (Fase 7).

Consome a API HTTP em `api/` via `httpx`. Não importa o grafo nem o audit
DB diretamente — toda comunicação passa pelo HTTP, simulando deployment
real e desacoplando front/back.
"""
