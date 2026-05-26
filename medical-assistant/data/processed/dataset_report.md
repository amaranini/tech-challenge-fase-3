# Relatório do dataset

> Dados sintéticos e fictícios gerados via OpenAI gpt-4o-mini, anonimizados via spaCy + regex.

**Total de exemplos:** 505

## Distribuição por split

| Split | Total | Por tipo de fonte |
|---|---|---|
| train | 404 | {'qa': 320, 'patient': 40, 'protocol': 28, 'template': 16} |
| val   | 50 | {'qa': 40, 'template': 2, 'patient': 5, 'protocol': 3} |
| test  | 51 | {'protocol': 4, 'qa': 40, 'patient': 5, 'template': 2} |

## Comprimento (tokens, aproximação via tiktoken cl100k_base)

| Split | Médio | Mínimo | Máximo |
|---|---|---|---|
| train | 187 | 87 | 935 |
| val   | 183 | 96 | 893 |
| test  | 188 | 86 | 853 |

> Nota: tiktoken `cl100k_base` é uma aproximação do tokenizer do Qwen2.5 (~10-15% de margem).

## Top 10 tipos de entidades anonimizadas

| Tipo | Ocorrências |
|---|---|
| PESSOA | 130 |
| LOCAL | 114 |
| CEP | 50 |
| CPF | 50 |
| DATA | 50 |
| TELEFONE | 28 |

_Gerado a partir de `data/synthetic/` com seed = 42_
