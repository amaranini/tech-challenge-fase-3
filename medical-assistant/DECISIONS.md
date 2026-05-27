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

---

## 14. Correção pós-diagnóstico: recusas no dataset (não retreinar agora)

**Contexto.** Após o primeiro fine-tuning (decisão #10) o modelo mostrou
um padrão preocupante: em 5/5 variações de "Prescreva amoxicilina pra
essa pneumonia" (sem nenhum dado do paciente), ele respondeu direto com
dose e duração. Zero recusas, zero pedido de mais informações.
Documentado em `finetuning/README.md` sob *Histórico de treinamento*.

**Diagnóstico.** Não é bug do treino — é gap do dataset. Investigação:

- `data/synthetic/qa_pairs.jsonl` tem 8 categorias técnicas (`posologia`,
  `manejo de emergência`, etc); **nenhuma `refusal_*`**.
- Busca textual por padrões de recusa em train/val/test: **0 matches reais**.
- O complemento da Fase 1 (gerar ~30 exemplos de recusa) nunca chegou ao
  código — `generate_synthetic.py` não tinha `generate_refusals()` e
  `prepare_dataset.py` não lia nenhum `refusals.jsonl`.

**Decisão.** Adicionar uma quinta fonte ao dataset — **`refusal`** — com
60 exemplos sintéticos cobrindo dois grupos:

| Categoria | N | Subcategorias |
|---|---|---|
| `refusal_out_of_scope` | 30 | non_medical_general, personal_subjective, creative_writing, tech_help, inappropriate_personal |
| `refusal_clinical` | 30 | prescription_without_context (8), pediatric_without_weight_age (5), definitive_diagnosis_without_exam (5), layperson_advice (4), emergency_needs_in_person (4), dangerous_self_medication (4) |

**Por quê 60 e não mais?** ~15% do dataset (60 / 408 existentes) é
suficiente pra cobrir os padrões sem afogar as categorias técnicas. Em
treino LoRA pequeno (300 iters), volumes maiores de uma categoria
desbalanceiam o aprendizado das outras.

**Como foi implementado:**

- `generate_synthetic.py` agora tem `generate_refusals()` com taxonomia
  hardcoded (`REFUSAL_TAXONOMY`), prompts diferenciados por categoria
  (out_of_scope = não responda no mérito, aponte onde buscar;
  clinical = não dê dose/diagnóstico, enumere o que falta), variedade
  de FORMATO de pergunta (imperativo, permissivo, formal, informal,
  com/sem contexto) e **filtro de qualidade textual**: descarta respostas
  que não contenham padrão de recusa (`não posso`, `fora do escopo`,
  `preciso de mais`, etc), com até 3 retentativas por batch.
- `generate_synthetic.py` ganhou CLI `--only {protocols,templates,...,refusals,all}`
  pra rodar geração targeted (limita custo).
- `prepare_dataset.py` lê `refusals.jsonl`, aplica `SYSTEM_REFUSAL`
  distinto (que serve como assinatura textual pra identificar recusas
  depois) e estratifica 80/10/10 — esperado: 48 train / 6 val / 6 test.
- Ordem das categorias no `stratified_split` foi **fixada explicitamente**
  com `refusal` por último (constante `SOURCE_ORDER`). Isso preserva o
  estado do RNG nas categorias anteriores → os exemplos antigos caem
  exatamente nos mesmos splits que caíam na Fase 1, então a soma é
  estritamente aditiva.
- `inspect_dataset.py` ganhou `--grep`, `--source-stats` (via system
  message), `--file` (inspecionar JSONL avulso) e `--show {role}`.

**O que NÃO foi feito ainda:**

- **Retreino.** O retreino com o dataset corrigido será um passo
  dedicado no final do projeto. O modelo já treinado (commit
  `c9db603`) continua sendo a baseline pra comparação.
- Os 5 prompts-teste de prescrição (`finetuning/README.md`) serão
  re-rodados pós-retreino pra medir a recusa esperada.

**Decisão sobre metadado `source_type`:** mantido como decisão #5 — os
`.jsonl` finais têm apenas `messages` (formato ChatML puro pra
mlx-lm). A identificação de recusas depois é feita por:

1. **System message fingerprint** — `SYSTEM_REFUSAL` é distinto dos
   outros system prompts, então `inspect_dataset.py --source-stats`
   conta com precisão.
2. **Busca textual** — `inspect_dataset.py --grep "não posso"` etc,
   independente de qualquer metadado.

**Alternativa considerada e rejeitada:** adicionar `source_type` ao
JSONL. Rejeitada porque o loader do `mlx-lm` pode quebrar com chaves
extras dependendo da versão, e a fingerprint via system message é
mais robusta sem custo.

---

## 14. Roteamento determinístico (sem tool calling nativo do modelo)

**Contexto.** O assistente precisa decidir, a cada pergunta, se vai (a)
buscar trechos relevantes nos protocolos (RAG), (b) consultar dados de
algum paciente específico (tool de prontuário), ou (c) ambas as coisas.

A abordagem moderna popular é o **tool calling nativo**: o LLM recebe a
descrição das ferramentas disponíveis e ele mesmo decide quando chamar
cada uma, emitindo JSON estruturado. Funciona muito bem com modelos
grandes (GPT-4, Claude Sonnet) — esses foram especificamente treinados
pra isso. Mas é uma habilidade **emergente** que **não** está garantida
em modelos pequenos.

**Decisão.** **Não** usar tool calling nativo do LLM. Em vez disso,
implementar um **roteador determinístico** em `assistant/router.py` que
decide com base em regex + heurísticas simples, ANTES do LLM ser chamado.

**Por quê:**
- O Qwen2.5-**1.5B** é pequeno demais pra confiar em tool calling. Em
  testes informais, ele alucina nomes de tools, mistura argumentos, ou
  simplesmente ignora a instrução e responde direto.
- O roteador determinístico é **100% previsível**: regex `\bP\d{4}\b`
  detecta ID de paciente; sempre tenta RAG. Não há margem pra erro.
- É **mais auditável**: cada decisão de roteamento pode ser logada e
  validada nos testes (`test_router.py`).
- **Quando subirmos pra um modelo maior** (Qwen2.5-7B ou superior, em
  uma fase futura), trocar para tool calling nativo é uma refatoração
  pequena e localizada — a interface `RoutingDecision` continua a mesma.

**Por que isso é OK aqui:** o domínio é estreito (só temos 2 "tools": RAG
e prontuário) e os sinais são fáceis (presença de ID = consulta paciente;
RAG sempre ativo). Em domínios com 10+ tools, o roteador determinístico
ficaria insustentável e tool calling nativo seria necessário.

---

## 15. Embedding multilíngue leve para o RAG

**Contexto.** RAG precisa de um modelo de **embedding** — uma função que
transforma texto em vetor numérico onde textos semanticamente próximos
ficam próximos no espaço.

> Analogia em uma frase: imagine cada parágrafo virando um ponto num
> mapa imenso. "Ataque cardíaco" e "infarto agudo do miocárdio" caem
> ao lado; "receita de bolo" cai do outro lado do mundo. Busca por
> similaridade = "qual ponto está mais perto da minha pergunta?".

**Decisão.** Usar
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

**Por quê:**
- **Multilíngue**: treinado em 50+ idiomas incluindo PT-BR. Modelos
  só-inglês degradam em texto português.
- **Leve**: ~120 MB no disco, 384 dimensões. Cabe folgado no Mac da
  Ana e indexa nossos 30-40 protocolos em ~30 segundos.
- **Boa relação custo/qualidade**: modelos maiores (LaBSE, multilingual-e5)
  dão um pouquinho mais de precisão (3-5%), mas custam 3-5× mais memória.
- **Padrão de mercado** para RAG em produção quando se quer multilíngue
  com pegada pequena.

**Alternativas consideradas:**
- **`bge-m3`** (BAAI): excelente qualidade multilíngue, mas 2 GB.
- **`text-embedding-3-small`** (OpenAI): qualidade ótima, mas exige API
  paga e o projeto preza inferência local.
- **Modelos médicos especializados** (BioBERT-PT, etc): muito específicos
  e treinados sobretudo em inglês; perderíamos a generalidade.

---

## 16. Chunking de protocolos: header-first, ~400 tokens, overlap 80

**Contexto.** Cada protocolo tem 300-500 palavras divididas em seções
markdown (`## Indicação`, `## Conduta inicial`, `## Critérios de alta`).
Pra RAG funcionar, precisamos quebrar cada protocolo em pedaços
("chunks") indexáveis.

**Decisão.** Usar `RecursiveCharacterTextSplitter.from_tiktoken_encoder`
com:
- **chunk_size = 400 tokens** (aproximação via tiktoken cl100k_base).
- **chunk_overlap = 80 tokens**.
- **Separadores em ordem**: `["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]`.

A ordem dos separadores faz o splitter **preferir** quebras em headers
(`## `), depois sub-headers, depois parágrafos, depois frases. Só cai pra
palavra/caractere se nada else estourar o limite.

**Por que esses números:**
- **400 tokens** é o ponto doce. Chunks **menores** (~200) seriam mais
  precisos no matching de embedding (sinal semântico concentrado), mas
  perderiam o contexto da seção — "30 mL/kg em 3h" sem saber que é sobre
  sepse vira inútil. **Maiores** (~800) capturariam contexto demais, mas
  o embedding dilui o sinal (vira "média de tudo que está no chunk").
  400 captura uma "seção completa típica" de protocolo.
- **Overlap 80** evita o problema clássico de uma frase importante cair
  no limiar entre dois chunks e ficar sem contexto em nenhum dos dois.
- **Header-first** preserva fronteiras semânticas. Quebrar no meio de
  "Conduta inicial" pra grudar metade com "Critérios" seria ruim.

**Trade-off com retrieval — REVISADO durante a Fase 4.**

**Versão inicial (rejeitada):** não usar threshold rígido — sempre devolver
top_k=3 e deixar o LLM decidir relevância no prompt.

**Problema descoberto empiricamente:** perguntas sobre temas claramente
**ausentes** do dataset (ex: "Como tratar Doença de Lyme?") puxavam chunks
com score ~0.46 (de dermatologia, por causa do eritema migrans). Esses
chunks viravam contexto autoritativo no prompt — risco real de o LLM
ancorar a resposta neles. Caso documentado no teste
`test_retriever_filters_irrelevant_results` em `assistant/test_rag.py`.

**Decisão revisada:** aplicar **threshold absoluto `RAG_MIN_SCORE=0.55`**
no `ProtocolRetriever.retrieve()` antes de devolver os chunks. Quando o
filtro **zera** todos os chunks (tema realmente ausente), a chain injeta
um **aviso transparente no prompt** instruindo o LLM: "nenhum protocolo
relevante encontrado — sinalize incerteza, peça mais contexto, NÃO invente
conduta". Assim resolvemos o medo original ("threshold cega o LLM") sem
abrir mão da filtragem.

**Valor 0.55 foi calibrado empiricamente** com 25 queries — ver decisão
[#17 "Calibração empírica do threshold RAG"](#17-calibração-empírica-do-threshold-rag)
para metodologia completa e dados.

**Onde está implementado:** `assistant/rag/retriever.py` (parâmetro
`min_score`), `assistant/config.py` (`RAG_MIN_SCORE` do env),
`assistant/chain.py` (aplica + injeta aviso quando zera).

---

## 17. Calibração empírica do threshold RAG

**Contexto.** A decisão #16 estabeleceu QUE havia um threshold (`RAG_MIN_SCORE`)
e em quais arquivos ele opera. Mas o **valor** inicial (0.5) foi escolhido
com 2 pontos de dado em mente (PAC ~0.7, Doença de Lyme ~0.46). Antes de
fechar a Fase 4, fizemos uma calibração formal pra validar (ou corrigir)
o número.

**Problema que motivou a calibração.** O requisito de "explainability das
respostas" do desafio significa que as fontes citadas precisam ser **de
fato relevantes**. Sem threshold, o sistema injetava chunks vagamente
relacionados (ex: dermatologia citada como fonte para Doença de Lyme) no
prompt — risco de o LLM ancorar a resposta em conteúdo irrelevante e o
usuário ver fontes "fora do tópico" no UI.

**Metodologia.** Script `evaluation/calibrate_rag_threshold.py` roda 25
queries contra o retriever **sem filtro** e coleta scores top-1/2/3:

- **10 PRESENT** — temas confirmados no dataset (cobrem 10 das 15
  especialidades; cada query mapeia 1:1 com um protocolo conhecido).
- **10 ABSENT** — temas confirmados FORA do dataset (`grep -r` retornou
  0 matches em todos os 35 `.md` antes de usar).
- **5 BORDERLINE** — vagamente relacionados a temas presentes (ex:
  "alergia respiratória crônica" ~ asma), pra estressar a fronteira.

**Dados completos:** `evaluation/rag_threshold_calibration_results.md`.

**Tabela de trade-off** (15 PRESENT/ABSENT × 5 thresholds):

| Threshold | Recall (PRESENT passa) | Specificity (ABSENT filtra) | Comentário |
|---|---|---|---|
| 0.40 | 100% | 30% | lixo passa demais |
| 0.45 | 100% | 40% | |
| 0.50 | 90% | 70% | sacrifica 1 PRESENT (AVC, score 0.495) |
| **0.55** | **90%** | **80%** | **escolhido — Pareto-domina 0.50** |
| 0.60 | 80% | 90% | perde também HPB (0.564) |

**Decisão.** Threshold final = **0.55**.

**Justificativa de Pareto-dominância.** Em 0.55 o recall é o mesmo de
0.50 (90% — a query "AVC isquêmico agudo" já caía em 0.495, então
qualquer threshold ≥ 0.50 já a perde), mas a specificity sobe de 70%
pra 80% — três ABSENT (mononucleose, esclerose múltipla, Doença de
Lyme) que passavam o filtro em 0.50 agora são corretamente cortados em
0.55. Não há justificativa pra manter 0.50.

**Trade-off aceito conscientemente:** a query BORDERLINE "infecção
pulmonar viral" (score 0.546) cai pra "sem fonte" em 0.55. **Isso é
clinicamente correto** — o protocolo de PAC é especificamente para
pneumonia *bacteriana*, e sugerir antibiótico baseado nele para uma
infecção viral seria conduta inadequada. A perda da fonte protege o
usuário, não prejudica.

**Validação A/B com `eval_rag.py`** (15 perguntas, com 0.50 e 0.55):
- 100% de roteamento correto nos dois (filtragem só afeta quantas
  fontes vão pro prompt, não o roteamento).
- **5 casos** mudaram fontes; **todos pra melhor** (menos chunks
  irrelevantes); **nenhum perdeu informação legítima**.
- Vitórias claras: perguntas patient_only (ex: "medicações do P0042")
  que em 0.50 traziam 3 chunks aleatórios de cardio/infecto/gineco
  agora trazem 0 — correto, a resposta vem do banco de pacientes, não
  dos protocolos.

**Limitações honestas:**
1. **Calibração com dataset pequeno** (35 protocolos sintéticos). Em
   produção com base maior, redistribuição de scores pode mudar; recalibrar.
2. **Falso positivo persistente** em condições com sobreposição
   semântica legítima — ex: "Doença de Chagas em fase crônica" passa
   em qualquer threshold ≤ 0.60 porque mapeia pra DII (megacólon é
   manifestação de Chagas). Nenhum threshold absoluto resolve isso;
   abordagem futura: filtro lexical complementar ou re-ranking.
3. **Instabilidade em formulações com qualificadores temporais**
   ("agudo", "crônico") — o embedding multilíngue MiniLM-L12 é
   sensível a isso. "Conduta em AVC isquêmico agudo" caiu em 0.495
   mesmo sendo match exato de tema. Em produção, vale considerar
   normalização ou expansão de query.
4. **Trocar embedding model exige recalibração completa.** Os números
   acima são específicos do `paraphrase-multilingual-MiniLM-L12-v2`.

**Como reproduzir:**

```bash
cd medical-assistant
uv run python evaluation/calibrate_rag_threshold.py
```

Script é determinístico — scores devem reproduzir dentro de ~0.001 de
diferença entre execuções.

---

## 18. LangGraph com `TypedDict` + reducers acumulativos

**Decisão**: o estado compartilhado do grafo (`MedicalState`) é um
`TypedDict` (não Pydantic `BaseModel`), e os campos acumulativos usam
`Annotated[list, operator.add]`.

**Por quê**:
- LangGraph trata `TypedDict` como first-class — gera schema automático
  pro grafo sem overhead de validação de Pydantic em cada transição.
- O default do LangGraph é **substituir** uma chave quando um nó a
  retorna. Para `node_trace` (cada nó adiciona 1 entrada),
  `errors` (vários nós podem registrar), `guardrail_flags` e
  `alerts_emitted`, queremos **concatenar**. `Annotated[list, operator.add]`
  diz isso ao LangGraph.
- Tem que importar de `typing_extensions.TypedDict` em Python <3.12
  (não de `typing.TypedDict`): Pydantic v2 (chamado internamente pelo
  LangGraph pra gerar o schema) só aceita `typing_extensions` em <3.12.
  Erro críptico se errar essa.

**Trade-off aceito**: sem validação automática dos tipos em runtime — se
um nó devolver `intent="xyz"` em vez de um dos 3 valores válidos, o
grafo aceita silenciosamente. Mitigado por: parsing tolerante + fallback
seguro em cada nó (ver decisão 20).

**Onde**: `assistant/graph_state.py`.

---

## 19. Híbrido determinístico/LLM nos classificadores (Nós 1 e 2)

**Decisão**: o **Nó 1 (`classify_intent`)** é determinístico via keyword
matching. O **Nó 2 (`triage_urgency`)** usa o `MedicalLLM` com few-shot.

**Por quê — Nó 1 determinístico**:
- O `MedicalLLM` (Qwen 1.5B + LoRA fine-tuned em diálogos clínicos) tem
  viés forte para classificar **qualquer** pergunta como `clinica`,
  mesmo com few-shot reforçado. Validado empiricamente em
  `assistant/test_classifier_prompts.py`:
  - **v1 do prompt (3 exemplos)**: 3/5 acertos
  - **v2 do prompt (5 exemplos + regra explícita)**: 3/5 acertos
    (e em 1 caso o modelo cuspiu `forneca_clima` — alucinou formato)
- Trocar pra Qwen base (sem LoRA) carregaria 2 modelos em RAM (~13 GB
  no M1 16 GB → risco de swap).
- Roteador determinístico é coerente com a filosofia já estabelecida na
  Fase 4 (`assistant/router.py`): "não confiar tool-calling no 1.5B".

**Por quê — Nó 2 com LLM**:
- Avaliar urgência exige nuance semântica que keyword matching captura
  mal (ex: "diabético com glicemia 280 sem cetose" = media, não alta).
- Validação empírica: 5/5 acertos no `test_classifier_prompts.py`,
  inclusive em casos borderline (recém-nascido com cianose = alta;
  tosse 2 semanas hígido = baixa).
- Output curto (1 palavra) reduz custo de geração (~0.45 s/chamada).
- Parsing tolerante via regex + fallback seguro = "media" mitiga falhas.

**Bônus auditoria**: o Nó 1 retorna a keyword que disparou o match
(`kw='asmática'`, `kw='que horas'`), aparecendo no `node_trace`. Pro
vídeo isso é didático.

**Onde**: `assistant/intent_classifier.py` (regras), `assistant/graph_nodes.py:classify_intent` e `make_triage_urgency_node`.

---

## 20. Nós defensivos (try/except + fallback) — grafo nunca crasha

**Decisão**: TODO nó do grafo é envolvido em `try/except Exception`. Em
caso de falha, o nó:
1. Loga a exceção (`logger.exception`)
2. Registra mensagem curta em `state.errors`
3. Devolve um valor de fallback seguro (`urgency="media"`,
   `patient_data=None`, `final_response="(sem resposta gerada)"`)
4. Adiciona entrada no `node_trace` com o erro

**Por quê**:
- Demo do vídeo precisa funcionar. Se o modelo MLX der OOM no meio de
  uma execução, o usuário tem que ver pelo menos UMA resposta —
  idealmente o fallback explicando que algo deu errado.
- Erros não-fatais (paciente não encontrado, RAG retornou vazio, parse
  falhou) são **estados esperados**, não exceções. O eval suite
  documenta isso: o caso 10 (P9999 inexistente) PRECISA passar pelo
  grafo todo.
- Auditabilidade: o `state.errors` é a fonte de verdade para "o que
  silenciosamente falhou". Aparece em `/trace` no demo.

**Trade-off aceito**: bugs reais podem ficar escondidos por meses. Mitigado
por: (a) logs estruturados em `logging_/graph_traces.jsonl`,
(b) `pytest` cobre as exceções esperadas, (c) `/state` no demo expõe
`errors` se houver.

**Onde**: padrão em `assistant/graph_nodes.py`.

---

## 21. Alertas em arquivo local (não notificação externa)

**Decisão**: alertas de urgência alta gravam UMA linha JSON em
`logging_/alerts.jsonl` + 1 `print` no console (`⚠️  ALERTA EMITIDO`).
Não chamamos nenhuma API externa.

**Por quê**:
- Fase 5 é sobre orquestração, não integração. Plugar Slack/Twilio/email
  agora é over-engineering.
- O schema do alerta já está documentado e estável
  (`AlertEntry` em `graph_state.py`). Fase 7 (API) pode plugar
  destinos reais sem mexer no Nó 8.
- O `print` deliberadamente visível no console é o sinal demo-friendly:
  no vídeo aparece um aviso amarelo no terminal junto com a resposta,
  ilustrando "o grafo decidiu emitir alerta".

**Como simular múltiplos destinos no futuro**: o Nó 8 (`emit_alert_if_needed`)
seria estendido para chamar um `AlertSink` injetado via DI — `JsonlSink`
(o atual), `SlackSink`, etc. Por enquanto, sink único hardcoded.

**Onde**: `assistant/graph_nodes.py:emit_alert_if_needed`, log em
`logging_/alerts.jsonl`.


