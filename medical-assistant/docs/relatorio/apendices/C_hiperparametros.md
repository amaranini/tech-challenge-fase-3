# Apêndice C — Hiperparâmetros do fine-tuning

Configuração canônica `mlx-lm` usada no Treino #1 (2026-05-26).
Arquivo original: [`finetuning/configs/lora_config.yaml`](../../../finetuning/configs/lora_config.yaml).

## Modelo base

| Item | Valor |
|---|---|
| Identificador HuggingFace | `mlx-community/Qwen2.5-1.5B-Instruct-bf16` |
| Parâmetros totais | 1.54 B |
| Precisão | bfloat16 (full — necessário para LoRA no MLX) |
| Tamanho do download | ~3 GB |

## Modo de execução

| Item | Valor | Por quê |
|---|---|---|
| `fine_tune_type` | `lora` | Compromisso entre custo de treino e qualidade. Full fine-tuning não cabe em 16 GB de RAM unificada. |
| `optimizer` | `adamw` | Padrão para fine-tuning de LLMs. |
| `seed` | 42 | Reprodutibilidade — mesma seed da geração de dataset. |

## Quais camadas e quais matrizes

| Item | Valor | Por quê |
|---|---|---|
| `num_layers` | 16 (de 28) | Cobre as 16 camadas mais altas (mais semânticas). 28 = full custaria mais sem ganho mensurável em dataset pequeno. |
| `lora_parameters.keys` | `["self_attn.q_proj", "self_attn.v_proj"]` | Default mlx-lm. Adicionar `k_proj` + `o_proj` dobra parâmetros LoRA sem ganho aparente no nosso tamanho de dataset. |
| `lora_parameters.rank` | 8 | Pequeno o suficiente pra evitar overfitting em 406 exemplos, grande o suficiente pra aprender o registro PT-BR clínico. |
| `lora_parameters.scale` | 20.0 | Multiplicador da saída LoRA antes de somar ao peso original. |
| `lora_parameters.dropout` | 0.05 | Regularização leve. |

## Batch e iterações

| Item | Valor | Justificativa |
|---|---|---|
| `batch_size` | 1 | Físico = 1 para caber no M1 16 GB. |
| `grad_accumulation_steps` | 4 | Batch efetivo de 4 sem custo de memória. |
| `iters` | 300 | ≈ 3 epochs (406 train / 4 = 101 iters por epoch). |
| `max_seq_length` | 1024 | Cobre 100 % dos exemplos sem truncar (max real = 935 tokens). |

## Taxa de aprendizado

| Item | Valor | Notas de calibração |
|---|---|---|
| `learning_rate` | 5e-5 | Meio do range típico LoRA (1e-5 a 1e-4). Loss desceu monotonicamente; sem NaN. |

## Validação e checkpoints

| Item | Valor |
|---|---|
| `steps_per_eval` | 25 (12 medições de val loss no treino) |
| `val_batches` | 25 batches do `valid.jsonl` por avaliação |
| `steps_per_report` | 10 (linhas de progresso no terminal) |
| `save_every` | 100 (3 checkpoints intermediários + o final) |

## Resumo dos parâmetros treináveis

Com `num_layers=16`, `keys=["q_proj", "v_proj"]`, `rank=8`:

- Parâmetros LoRA por camada por matriz: `rank × (in_features + out_features)`
- Para `q_proj` e `v_proj` num modelo 1.5 B, `in_features = out_features = 1536`
- Por camada: 2 matrizes × 8 × (1536 + 1536) = **49.152** params
- Total em 16 camadas: **786.432 params** (≈ 0.05 % do modelo)

## Tempo e custo

| Métrica | Valor |
|---|---|
| Tempo real de treino | ~11 min (Mac M1, 16 GB) |
| Pico de memória (sob `mx.metal.device_info()`) | ~10 GB |
| Tamanho do adapter final | ~3.2 MB (safetensors) |
