# Apêndice D — Calibração do threshold RAG

Arquivo-fonte completo:
[`evaluation/rag_threshold_calibration_results.md`](../../../evaluation/rag_threshold_calibration_results.md).
Reproduzido aqui apenas os dados essenciais para o relatório.

## Setup

| Item | Valor |
|---|---|
| Data | 2026-05-26 |
| Embedding model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Distância | cosseno (Chroma com `hnsw:space="cosine"`) |
| Top-k | 3 (sem filtro durante coleta) |
| Total de queries | 25 (10 PRESENT + 10 ABSENT + 5 BORDERLINE) |

PRESENT = temas confirmados no dataset (inspeção direta dos 35 protocolos).
ABSENT = temas confirmados fora (grep retornou 0 matches).
BORDERLINE = queries vagamente relacionadas a temas presentes.

## Estatísticas — score top-1

| Grupo | n  | média | mediana | min   | max   | σ     |
|---|----|-------|---------|-------|-------|-------|
| PRESENT    | 10 | 0.711 | 0.735   | 0.495 | 0.840 | 0.117 |
| ABSENT     | 10 | 0.441 | 0.460   | 0.158 | 0.601 | 0.131 |
| BORDERLINE | 5  | 0.562 | 0.580   | 0.272 | 0.721 | 0.178 |

## Trade-off por threshold

Tabela 1 — Comportamento esperado por threshold candidato.

| Threshold | Recall (PRESENT passa) | Specificity (ABSENT filtra) | Observação |
|---|---|---|---|
| 0.40 | 100 % (10/10) | 30 % (3/10) | pega tudo, deixa lixo passar |
| 0.45 | 100 % (10/10) | 40 % (4/10) | — |
| 0.50 | 90 % (9/10) | 70 % (7/10) | sacrifica AVC isquêmico (0.495) |
| **0.55** ← escolhido | 90 % (9/10) | 80 % (8/10) | Pareto-domina 0.50 |
| 0.60 | 80 % (8/10) | 90 % (9/10) | perde também HPB (0.564) |

## Falhas conhecidas com `min_score = 0.55`

### PRESENT que caem abaixo do threshold

- `Conduta em AVC isquêmico agudo?` → 0.495 → mapeou pro `protocol_004_emergência.md`
  (que **é** sobre AVC). A formulação com qualificador temporal ("agudo")
  parece degradar o embedding multilíngue. Cai na faixa "sem fonte" e a
  chain instrui o LLM a pedir mais contexto.

### ABSENT que passam mesmo com 0.55

- `Doença de Chagas em fase crônica` → 0.601 → mapeou pro
  `protocol_023_gastroenterologia.md` (Doença Inflamatória Intestinal).
  Há sobreposição semântica legítima (megacólon), mas o protocolo NÃO
  trata de Chagas. **Falso positivo persistente** — nenhum threshold
  absoluto resolve.

## BORDERLINE — separação com 0.55

| Query | top-1 | Lado |
|---|---|---|
| alergia respiratória crônica | 0.721 | passa |
| câncer broncogênico | 0.691 | passa |
| ansiedade situacional aguda | 0.580 | passa |
| infecção pulmonar viral | 0.546 | filtra |
| dor torácica de origem indeterminada | 0.272 | filtra |

Filtrar "infecção pulmonar viral" é o **trade-off aceito** do projeto: o
único protocolo de pneumonia trata de PAC (bacteriana). Sugerir antibiótico
para infecção viral seria clinicamente inadequado.

## Limitações da calibração

1. **Dataset pequeno (35 protocolos)** — em produção, redistribuição de
   scores pode mudar; necessário recalibrar.
2. **Falso positivo por sobreposição semântica legítima** (Chagas/DII) —
   solução futura: combinar com filtro lexical ou re-ranking.
3. **Instabilidade com qualificadores temporais** — embedding MiniLM-L12
   é sensível a "agudo"/"crônico".
4. **Trocar embedding exige recalibrar tudo** — os números acima são
   específicos do `paraphrase-multilingual-MiniLM-L12-v2`.

## Reprodução

```bash
cd medical-assistant
uv run python evaluation/calibrate_rag_threshold.py
```

O script é determinístico — diferenças esperadas ≤ 0.001.
