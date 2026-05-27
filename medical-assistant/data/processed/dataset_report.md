# Relatório do dataset

> Dados sintéticos e fictícios gerados via OpenAI gpt-4o-mini, anonimizados via spaCy + regex.

**Total de exemplos:** 508

## Distribuição por split

| Split | Total | Por tipo de fonte |
|---|---|---|
| train | 406 | {'qa': 320, 'patient': 40, 'template': 16, 'protocol': 28, 'refusal': 2} |
| val   | 50 | {'qa': 40, 'template': 2, 'patient': 5, 'protocol': 3} |
| test  | 52 | {'protocol': 4, 'qa': 40, 'refusal': 1, 'patient': 5, 'template': 2} |

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
| PESSOA | 131 |
| LOCAL | 114 |
| CEP | 50 |
| CPF | 50 |
| DATA | 50 |
| TELEFONE | 28 |

## Validação textual de recusas

Contagem de exemplos cujo assistant contém cada padrão de recusa (verificação independente de metadado — confirma que as recusas geradas chegaram efetivamente aos splits).

| Padrão | train | val | test |
|---|---|---|---|
| `não posso` | 0 | 0 | 0 |
| `fora do escopo` | 0 | 0 | 0 |
| `fora do meu escopo` | 1 | 0 | 0 |
| `preciso de mais` | 1 | 0 | 1 |
| `consulte um` | 0 | 0 | 0 |
| `procure um` | 0 | 0 | 0 |
| `atendimento presencial` | 0 | 0 | 0 |
| `samu` | 0 | 0 | 0 |
| `192` | 0 | 0 | 0 |
| `pronto-socorro` | 0 | 0 | 0 |

_Gerado a partir de `data/synthetic/` com seed = 42_
