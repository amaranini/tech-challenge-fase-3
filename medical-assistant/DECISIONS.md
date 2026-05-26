# Log de Decisões Técnicas

Cada decisão deste projeto fica registrada aqui, em português e linguagem
simples. A ideia é que você consiga reler depois e entender **por que** as
coisas estão como estão — não só **o que** foi feito.

Formato: número, título, contexto, decisão, alternativas consideradas e
por que rejeitadas.

---

## 1. Gerenciador de pacotes: `uv` em vez de `pip + venv`

**Contexto.** Todo projeto Python precisa de dois ingredientes:
(1) um ambiente isolado, para que as bibliotecas deste projeto não
"contaminem" outros projetos do seu Mac, e (2) um gerenciador que
instale, atualize e trave versões dessas bibliotecas.

Historicamente isso era feito com `venv` (cria o ambiente) + `pip`
(instala) + `pip-tools` ou `poetry` (trava versões). Funciona, mas é
lento e propenso a confusão (qual `venv` está ativo agora? por que esse
pacote está em conflito?).

**Decisão.** Usar [`uv`](https://github.com/astral-sh/uv), um gerenciador
escrito em Rust pela Astral (mesmo time do `ruff`). Ele faz tudo em um só
comando, é ~10 a 100× mais rápido que pip, lê o `pyproject.toml` direto e
ativa o ambiente automaticamente para cada comando — você não precisa
lembrar de "ativar o venv".

**Alternativas consideradas.**
- `pip + venv` puro: padrão, mas lento e exige passos manuais.
- `poetry`: bom, mas mais lento que `uv` e adiciona um arquivo `poetry.lock` próprio.
- `conda`: ótimo para ciência de dados com binários pesados, mas exagero aqui.

**Por que rejeitadas.** `uv` é mais rápido, mais simples para quem está
começando em Python e já virou padrão de fato em projetos novos da
comunidade em 2025–2026.

---

## 2. Treino no Google Colab, inferência local no Mac

**Contexto.** O projeto tem duas fases distintas de execução:
- **Fine-tuning**: pegar o modelo base (Qwen2.5-3B-Instruct) e ajustá-lo
  com dados médicos. Isso exige muita VRAM (memória de GPU), tipicamente
  16–24 GB, e bibliotecas que dependem de **CUDA** (a stack da NVIDIA).
- **Inferência**: rodar o modelo já treinado para responder perguntas.
  Esta etapa é leve — um modelo de 3B parâmetros cabe em ~6 GB de RAM
  depois de quantizado.

Seu Mac é Apple Silicon (M-series). Ele não tem GPU NVIDIA, então CUDA
não roda nele. Em compensação, a Apple oferece o **MLX**, um framework
nativo otimizado para a memória unificada do M-series, e o **Ollama**,
um runtime local fácil de usar.

**Decisão.**
- **Treino**: rodar no **Google Colab** (GPU T4 gratuita ou A100 com
  Colab Pro). Lá vivem `transformers`, `peft` (técnica de fine-tuning
  eficiente chamada LoRA — *Low-Rank Adaptation* — que treina só um
  pedaço pequeno do modelo) e `bitsandbytes` (quantização em 4/8 bits).
- **Inferência**: rodar **localmente no Mac** com MLX (preferido) ou
  Ollama (fallback). Isso permite gravar a demonstração de 15 min offline,
  sem depender de internet ou conta paga.

**Por que separar.** Manter dependências CUDA fora do `pyproject.toml`
deixa a instalação local mais leve e evita erros confusos em quem tenta
rodar em Mac. O notebook de treino é autossuficiente: você abre no Colab,
roda, baixa o resultado, e ele entra em `finetuning/outputs/`.

---

## 3. Modelo base: Qwen2.5-3B-Instruct

**Contexto.** Para fazer fine-tuning a gente precisa partir de um modelo
pré-treinado. As opções variam em tamanho (1B, 3B, 7B, 13B+ parâmetros),
licença, qualidade e formato.

**Decisão.** Usar [`Qwen/Qwen2.5-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
da Alibaba como ponto de partida.

**Por quê.**
- **Tamanho ideal para o Mac.** 3B parâmetros, depois de quantizado para
  4 bits, ocupa ~2 GB de RAM. Cabe folgado em qualquer Apple Silicon com
  8 GB+ de memória unificada e roda em tempo real.
- **Licença Apache 2.0.** Permite uso comercial e fine-tuning sem
  restrição — sem dor de cabeça jurídica num projeto acadêmico que pode
  virar portfólio.
- **Performance acima do tamanho.** Em benchmarks gerais (MMLU, HumanEval,
  GSM8K), Qwen2.5-3B-Instruct chega perto e às vezes supera modelos de 7B
  de gerações anteriores. Ótima relação qualidade/custo.
- **Variante "Instruct".** Já foi pós-treinada para seguir instruções e
  conversar — não precisamos ensinar isso do zero, só especializar em
  domínio médico.
- **Família escalável.** Se um dia decidirmos subir para 7B ou 14B, é só
  trocar o ID do modelo; toda a stack continua igual.

**Alternativas consideradas.**
- **Llama-3.2-3B-Instruct (Meta)**: muito bom, mas licença
  "Community License" tem restrições (>700M usuários, branding).
- **Phi-3.5-mini (Microsoft)**: ótimo para tamanho (3.8B), mas mais
  focado em raciocínio matemático/código que em diálogo geral.
- **Gemma-2-2B (Google)**: licença permissiva, mas qualidade um pouco
  abaixo do Qwen2.5 no mesmo tamanho.
- **Modelos médicos prontos (Meditron, BioMistral)**: já especializados,
  mas o ponto do Tech Challenge é demonstrar o processo de fine-tuning —
  partir de um genérico mostra mais.

**Por que rejeitadas.** Qwen2.5-3B-Instruct empata ou ganha em todos os
critérios que importam para a gente: tamanho, licença, qualidade,
disponibilidade em MLX/Ollama e capacidade de instruct.

---

## 4. Geração sintética com OpenAI `gpt-4o-mini`

**Contexto.** Precisamos de centenas de exemplos médicos para fine-tuning,
sem usar dados reais de pacientes (privacidade) e sem coletar de literatura
livre (qualidade e licença). A solução prática é gerar tudo sinteticamente
via um LLM mais forte que o nosso modelo base.

**Decisão.** Usar **OpenAI `gpt-4o-mini`** como "professor sintético":
- ~145 chamadas totais (protocolos, templates, pacientes em batches,
  Q&A em batches).
- Custo real: **US$ 0,06** com buffer para retries.
- Validação de schema com Pydantic + descarte de respostas com
  placeholders literais.

**Por quê `gpt-4o-mini` e não outro:**
- Custo baixíssimo: ~$0,15/$0,60 por 1M tokens (input/output).
- Qualidade suficiente para texto clínico didático (não precisamos de
  GPT-4o full).
- Suporte nativo a `response_format=json_object` — parsing confiável.
- Limites de rate confortáveis no tier gratuito.

**Alternativas consideradas.**
- **Claude Haiku**: qualidade comparável, mas custo similar e setup
  extra (chave Anthropic, biblioteca extra).
- **Gemini Flash**: barato, mas JSON mode menos maduro.
- **LLM local (Llama-3 8B)**: zero custo, mas qualidade abaixo e
  geração lenta no Mac da Ana — 145 chamadas levariam horas.

**Mitigação de risco:** o script `generate_synthetic.py` mostra a
estimativa de custo e pede confirmação `s/N` antes de qualquer
chamada paga. Salva incremental para nada se perder se cair no meio.

---

## 5. Formato `messages` (ChatML) em vez de Alpaca

**Contexto.** Há dois formatos comuns para datasets de fine-tuning de LLMs
de chat:

- **Alpaca** (clássico): `{"instruction": "...", "input": "...", "output": "..."}`.
- **`messages`** (ChatML, estilo OpenAI/Qwen/Claude):
  `{"messages": [{"role": "system", "content": "..."}, {"role": "user", ...}, ...]}`.

**Decisão.** Usar o formato `messages`.

**Por quê.**
- O Qwen2.5-Instruct foi pré-treinado com o template
  `system/user/assistant` (ChatML). Fine-tuning no mesmo formato
  **preserva o comportamento de chat** que o modelo já tem.
- É o formato esperado pelo método `apply_chat_template()` da biblioteca
  `transformers` e pelos scripts modernos de fine-tuning (Axolotl,
  TRL, MLX-LM).
- Alpaca é legado — conviria converter pra `messages` na hora do
  fine-tuning, então melhor já nascer assim.
- Permite múltiplos turnos no futuro (RAG com contexto recuperado, por exemplo).

---

## 6. Anonimização híbrida: spaCy NER + regex

**Contexto.** Precisamos remover/substituir dados pessoais (PII) dos
prontuários e exemplos antes de treinar. Mesmo sendo dados sintéticos,
o pipeline tem que funcionar de verdade — esse é um entregável demonstrável.

**Decisão.** Combinar **spaCy `pt_core_news_lg`** (modelo grande de
português) para detectar nomes/locais via NER, com **regex** para
detectar padrões estruturados (CPF, CEP, telefone, e-mail, etc).

**Por quê o híbrido:**
- **Regex puro perde nomes**: nome de pessoa não tem padrão de caracteres,
  só contexto.
- **NER puro perde formatos estruturados**: spaCy não foi treinado pra
  capturar CPF como entidade — ele veria "123.456.789-00" como número
  qualquer.
- **Híbrido cobre os dois lados**: regex pega os formatos exatos (rápido
  e infalível); NER pega o resto.

**Detalhes de implementação:**
- spaCy: usamos só labels `PER` (pessoa) e `LOC` (local). `ORG` foi
  excluído por dar muito falso positivo em texto médico (tipo
  "Hospital São Lucas" virando ORG OK, mas "Diabetes Mellitus" também).
- Em conflito de spans (regex e NER cobrindo o mesmo trecho), o regex
  vence — geralmente é mais específico.
- **Consistência**: dentro do mesmo documento, mesma entidade ganha
  mesmo placeholder. "Maria Silva" mencionada 3 vezes vira `[PESSOA_1]`
  nas 3.

**Por que `pt_core_news_lg` (e não `_md` ou `_sm`):**
- F1 de NER em pessoas ~92% (vs ~85% no `_md`, ~78% no `_sm`).
- Custa 568 MB de download e ~1,5s pra carregar — aceitável.

---

## 7. Dataset processado vai pro git; dados sintéticos brutos ficam ignored

**Contexto.** Onde gravamos o quê?

**Decisão.**
- ✅ `data/processed/*.jsonl` (train/val/test **já anonimizados**) **vai
  pro git**. É o entregável final do Tech Challenge — qualquer pessoa
  precisa conseguir reproduzir o fine-tuning sem rodar a OpenAI de novo.
- ✅ `data/processed/dataset_report.md` também vai (transparência).
- ❌ `data/synthetic/*` (intermediário, **antes** da anonimização) fica
  **gitignored**. Mesmo sendo dados gerados por Faker, eles aparentam ser
  reais (CPF formato válido, nome próprio, endereço estruturado) —
  manter ignored é boa prática defensiva.

**Por quê.** Se alguém clonar o repo, deve conseguir treinar direto
(reprodutibilidade); mas não deve ter acesso aos dados pré-anonimização
(prática defensiva, mesmo com dados fictícios).

---

## 8. Modelo de fine-tuning: Qwen2.5-1.5B (em vez do 3B planejado na Fase 0)

**Contexto.** Na Fase 0 escolhemos `Qwen2.5-3B-Instruct` como modelo base.
Ao chegar na Fase 2 (fine-tuning local no M1 16 GB), refizemos as contas
de memória pro treino e o 3B ficou apertado demais.

**Decisão.** Trocar para **`mlx-community/Qwen2.5-1.5B-Instruct-bf16`**
para a Fase 2 (fine-tuning).

**Por quê.**
- 3B em bf16 ocupa ~6 GB de RAM só com os pesos. Somando ativações,
  gradientes e otimizador, treino com seq_len=1024 ficaria em ~13 GB —
  sem margem segura num Mac com 16 GB que ainda precisa rodar o sistema.
- 1.5B em bf16 ocupa ~3 GB de RAM. Mesma configuração de treino:
  uso total ~10 GB com margem confortável.
- Tempo por iteração no M1 também é ~2× mais rápido com 1.5B → treino de
  30-60 min em vez de 1-3 h.
- Qualidade da família Qwen2.5 nessa escala (1.5B) é boa para texto
  médico didático em PT-BR; a perda de qualidade vs 3B é pequena para
  o nosso caso (estilo/formato, não conhecimento).

**Por que `bf16` e não `4bit` ou `8bit`:** versões quantizadas (`4bit`,
`8bit`) só servem para inferência — não dá pra treinar LoRA em cima
delas via mlx-lm. Precisamos da versão `bf16` para treinar.

**Alternativas consideradas.**
- **Manter o 3B**: caberia se rodássemos com seq_len=512 e
  `grad_checkpoint=true`, mas o treino dobraria de tempo e o risco de
  OOM por outros processos do macOS seria alto.
- **Cair pra 0.5B**: muito conservador. Reservado como plano B (B em
  `finetuning/README.md` troubleshooting).
- **Trocar de família (Phi-3.5-mini, Llama-3.2-1B)**: perderíamos a
  decisão #3, que fundamentava muita coisa. 1.5B Qwen2.5 mantém a
  família e atende os limites de hardware.

---

## 9. Framework de fine-tuning: mlx-lm

**Contexto.** Para fazer LoRA local no Mac, três caminhos práticos:

**Decisão.** Usar **`mlx-lm`** (Apple). Versão estável atual no PyPI: 0.31.x.

**Por quê.**
- **Único framework de treino com aceleração GPU real no M1.** Hugging
  Face `transformers` no Mac roda em CPU (não tem CUDA) → 50-100× mais
  lento. `mlx-lm` usa Metal, a stack gráfica da Apple, e treina em
  minutos onde transformers levaria horas.
- **API CLI e Python**: `mlx_lm.lora --config x.yaml` faz tudo, e dá
  pra carregar adapter via Python pra inferência (`mlx_lm.load`,
  `mlx_lm.generate`).
- **Comunidade ativa**: muitos modelos prontos em `mlx-community/`
  (versões bf16/4bit/8bit pré-convertidas no Hugging Face).
- **Formato de dataset compatível com o nosso**: aceita o formato
  `chat` (linhas `{"messages": [...]}`) que já produzimos na Fase 1 —
  sem conversão de schema, só rename `val.jsonl → valid.jsonl`.

**Alternativas consideradas.**
- **Axolotl / LLaMA-Factory**: ferramentas modernas mas exigem CUDA.
- **TRL + transformers (CPU)**: tecnicamente possível, mas tempo
  inviável no Mac.
- **Treinar no Colab e baixar adapter**: contraria a decisão #2 de
  manter a inferência local e independente.

---

## 10. Hiperparâmetros LoRA

**Contexto.** LoRA tem vários hiperparâmetros sensíveis a dataset/hardware.
Documentamos os escolhidos e o raciocínio para que possam ser
revisitados se a curva de loss indicar problema.

**Decisão (final, em `finetuning/configs/lora_config.yaml`):**

| Parâmetro | Valor | Justificativa curta |
|---|---|---|
| `rank` | 8 | Default mlx-lm; bom equilíbrio capacidade × memória pra 404 exemplos. |
| `scale` | 20.0 | Default mlx-lm. Multiplicador da saída LoRA. |
| `dropout` | 0.05 | Leve regularização contra overfit em dataset pequeno. |
| `keys` | `q_proj`, `v_proj` | Default. Cobre o suficiente; k/o dobra parâmetros sem ganho relevante aqui. |
| `num_layers` | 16 | Top 16 das 28 camadas do Qwen2.5-1.5B — cobre as mais semânticas. |
| `learning_rate` | 5e-5 | Meio do range típico (1e-5 a 1e-4). |
| `batch_size` | 1 | M1 16 GB não comporta mais. |
| `grad_accumulation_steps` | 4 | Batch efetivo = 4, igual ao default do mlx-lm. |
| `iters` | 300 | ≈ 3 epochs (404 train / batch 4 → 101 iters/epoch). |
| `max_seq_length` | 1024 | Cobre o máximo real do dataset (935 tokens). |
| `steps_per_eval` | 25 | 12 medições de val durante o treino — bom pra ver overfitting cedo. |

**Por que NÃO usamos as alternativas comuns:**
- **rank=16**: dobraria memória e probabilidade de overfittar em 404 exemplos.
- **LR=1e-4**: bom em treinos longos com batch grande; com nossa config
  pode ficar instável.
- **seq_len=2048**: dobraria memória sem ganho (nosso máximo é 935).

**Filosofia complementar:** estamos fazendo fine-tuning para **ensinar
estilo/formato** (jargão médico, estrutura de laudo, registro PT-BR), e
**não** para incutir conhecimento factual. Conhecimento factual virá do
RAG na Fase 4 — por isso parâmetros conservadores são apropriados.

---

## 11. Avaliação: perplexity + 10 prompts qualitativos

**Contexto.** Como medir se o fine-tuning "funcionou"? Loss de treino
sozinha não basta — pode estar baixa por overfitting.

**Decisão.** Dupla camada de avaliação:

1. **Quantitativa: perplexity no test set** (50+ exemplos held-out, não
   vistos no treino). Calculada com `mlx_lm.lora --test`. Comparamos
   `ppl_base` vs `ppl_fine_tuned`. Esperamos queda de 30-50% no domínio.
2. **Qualitativa: 10 prompts fixos** em PT-BR cobrindo 5 categorias
   (clínica geral, formato, conduta, segurança/ética, fora de escopo).
   Rodados em base e fine-tuned, salvos lado-a-lado em
   `evaluation/comparison.md` — leitura humana é o que valida estilo,
   adequação clínica e cuidado ético.

**Por quê.**
- Só perplexity esconde regressões qualitativas (modelo pode aprender
  formato e perder o cuidado ético, por exemplo).
- Só qualitativa é subjetiva — perplexity dá número objetivo.
- 10 prompts cabem confortavelmente num PDF/relatório técnico e no
  vídeo de 15 min sem virar uma enxurrada.

---

## 12. Wrapper LangChain: `BaseChatModel` (não `LLM` cru)

**Contexto.** Pra integrar o modelo fine-tuned a chains, agentes e
guardrails do LangChain nas próximas fases, precisamos de uma classe
Python compatível com a interface deles. O LangChain expõe duas raízes:
`BaseLLM` (modelos de completar texto, single-turn) e `BaseChatModel`
(modelos de chat com `messages`, multi-turn).

**Decisão.** A classe `MedicalLLM` herda de `BaseChatModel`.

**Por quê.**
- O Qwen2.5-Instruct **é um modelo de chat** — foi treinado com o template
  `messages` (system/user/assistant), e nosso fine-tuning manteve esse
  formato. Encapsular como `BaseLLM` (single-prompt text completion)
  exigiria converter messages → string e perderia o template do tokenizer.
- A maioria das integrações modernas do LangChain (RAG via
  `create_retrieval_chain`, agentes, `RunnableWithMessageHistory`) assume
  `BaseChatModel`. Usar `BaseLLM` complicaria a Fase 4 em diante.
- `BaseChatModel` preserva a noção de SystemMessage/HumanMessage/AIMessage
  até o fim do pipeline, o que casa com nossos guardrails (Fase 6) que
  vão inspecionar/filtrar por papel.

**Implementação:** apenas `_generate` (sync) implementado nesta fase.
Streaming (`_stream`) e async (`_agenerate`/`_astream`) ficam para a
Fase 6 (UI Streamlit), usando `mlx_lm.stream_generate` já disponível.

---

## 13. System prompt clínico aplicado na Fase 3 (antes de RAG/guardrails)

**Contexto.** A Fase 2 entregou um modelo que **aprendeu formato/estilo
médico**, mas mostrou regressão clara em comportamento de segurança:
respondia "Prescreva amoxicilina" diretamente em vez de pedir contexto
clínico (documentado em `finetuning/README.md`, seção
*Histórico de treinamento*).

**Decisão.** Aplicar um **system prompt clínico forte** já na Fase 3,
antes de qualquer guardrail externo, e medir empiricamente quanto o
prompt sozinho consegue corrigir do comportamento. O system prompt vive
em `assistant/prompts.py` como constante `MEDICAL_SYSTEM_PROMPT` e é
aplicado automaticamente pelo `MedicalLLM.build_default_llm()`.

**Por quê fazer isso aqui em vez de esperar a Fase 6 (guardrails)?**
- O system prompt é o "guardrail mais barato" — não custa nem latência
  nem inferência extra, e o efeito pode ser mensurado em isolamento.
- Saber **quanto** do problema o system prompt resolve evita
  super-engenharia: se ele já cobrir 80% dos casos, a Fase 6 foca nos
  20% que escaparem; se cobrir 30%, ajustamos a estratégia da Fase 6.
- O comparativo gerado por `evaluation/eval_system_prompt.py` produz
  evidência empírica em `evaluation/comparison_phase3.md` — material
  direto pro relatório e pro vídeo.

**Como o system prompt é gerenciado:**
- Default da instância (`MedicalLLM(system_prompt=...)`).
- Se o input do `.invoke()` já contém `SystemMessage`, o do usuário
  ganha (princípio: chain do usuário > default da instância).
- No `demo_chat.py`, o comando `/system "..."` permite trocar ao vivo —
  útil pra demonstrar no vídeo que o mesmo modelo se comporta diferente
  com prompts diferentes.

**Versão `STRICT` reservada para a Fase 6:** por enquanto idêntica ao
default; será endurecida quando construirmos os guardrails (ex: refusal
mais agressivo, formato JSON obrigatório, regras pra emergência).

