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
