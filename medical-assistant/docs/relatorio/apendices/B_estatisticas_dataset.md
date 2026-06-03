# Apêndice B — Estatísticas do dataset

Material reproduzido (com adaptação mínima) de
[`data/processed/dataset_report.md`](../../../data/processed/dataset_report.md),
gerado em 2026-05-26 pelo `data/prepare_dataset.py`.

> Dados sintéticos e fictícios gerados via OpenAI `gpt-4o-mini`, anonimizados
> via spaCy (NER PT-BR) + regex (CPF, CEP, telefone).

## Totais

| Item | Quantidade |
|---|---|
| Pacientes sintéticos (CSV) | 50 |
| Protocolos clínicos (Markdown) | 35 |
| Pares Q&A (JSONL) | 400 |
| Recusas (JSONL) | 3 |
| **Exemplos pós-processamento** | **508** |

## Distribuição por split

| Split | Total | Por tipo de fonte |
|---|---|---|
| `train` | 406 | qa: 320, patient: 40, template: 16, protocol: 28, refusal: 2 |
| `val`   | 50  | qa: 40, template: 2, patient: 5, protocol: 3 |
| `test`  | 52  | protocol: 4, qa: 40, refusal: 1, patient: 5, template: 2 |

## Comprimento em tokens (aproximação via `tiktoken cl100k_base`)

| Split | Médio | Mínimo | Máximo |
|---|---|---|---|
| `train` | 187 | 87  | 935 |
| `val`   | 183 | 96  | 893 |
| `test`  | 188 | 86  | 853 |

`tiktoken cl100k_base` é uma aproximação do tokenizer do Qwen2.5
(±10-15 % de margem). A escolha de `max_seq_length: 1024` no fine-tuning
cobre 100 % dos exemplos sem truncamento.

## Anonimização — entidades removidas

Top entidades substituídas por placeholders (`<PESSOA>`, `<LOCAL>`, etc.):

| Tipo | Ocorrências |
|---|---|
| PESSOA | 131 |
| LOCAL | 114 |
| CEP | 50 |
| CPF | 50 |
| DATA | 50 |
| TELEFONE | 28 |

## Verificação independente de recusas

Contagem por padrão textual (não confia em metadado — confirma que recusas
chegaram aos splits):

| Padrão | train | val | test |
|---|---|---|---|
| `não posso` | 0 | 0 | 0 |
| `fora do escopo` | 0 | 0 | 0 |
| `fora do meu escopo` | 1 | 0 | 0 |
| `preciso de mais` | 1 | 0 | 1 |
| `consulte um` | 0 | 0 | 0 |
| `procure um` | 0 | 0 | 0 |
| `atendimento presencial` | 0 | 0 | 0 |
| `pronto-socorro` | 0 | 0 | 0 |

**Diagnóstico desta tabela:** o dataset gerado na Fase 1 tem ≤ 4 exemplos
contendo qualquer padrão de recusa. Após o fine-tuning, isso se traduziu
em um modelo que **não recusa** prompts de prescrição direta. A correção
foi feita por outra camada — guardrails (Fase 6), §5.6 do corpo do
relatório.
