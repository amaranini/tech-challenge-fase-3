# Dataset — medical-assistant

> ⚠️ **TODOS OS DADOS SÃO SINTÉTICOS E FICTÍCIOS.**
> Nenhum dado real de paciente foi utilizado. Os textos foram gerados via
> OpenAI `gpt-4o-mini` com prompts que pedem explicitamente "dados fictícios
> para treinamento de IA". Os demográficos (CPF, nome, telefone, endereço)
> dos prontuários são gerados pela biblioteca [Faker](https://faker.readthedocs.io/)
> com locale `pt_BR` — eles seguem o formato brasileiro mas **não correspondem
> a pessoas reais**.

## Origem dos dados

| Fonte | Como foi gerada | Saída |
|---|---|---|
| **Protocolos clínicos** | OpenAI `gpt-4o-mini`, prompts em PT-BR rotacionando 15 especialidades | `synthetic/protocols/*.md` |
| **Templates de documentos** | OpenAI `gpt-4o-mini`, 10 tipos × 2 variações | `synthetic/templates/*.md` |
| **Pacientes (50)** | Faker pt_BR (demográficos) + OpenAI (histórico, alergias, medicações) | `synthetic/patients.csv` |
| **Pares Q&A (400)** | OpenAI `gpt-4o-mini`, batches de 5, rotacionando especialidades × categorias | `synthetic/qa_pairs.jsonl` |

Total estimado: ~505 exemplos no dataset final.

## Como reproduzir (passo a passo)

1. **Configurar a chave OpenAI** (uma vez):

   ```bash
   cp .env.example .env
   ```
   Edite `.env` e cole sua chave em `OPENAI_API_KEY=sk-...` (pegue em
   https://platform.openai.com/api-keys).

2. **Instalar dependências e modelo de NLP**:

   ```bash
   uv sync --extra data --extra dev
   uv run python -m spacy download pt_core_news_lg
   ```

3. **Rodar testes da anonimização** (não gasta API, ~30s):

   ```bash
   uv run pytest data/test_anonymization.py -v
   ```

4. **Gerar o dataset sintético** (gasta API, ~US$ 0,50–0,80):

   ```bash
   uv run python data/generate_synthetic.py
   ```
   O script mostra a estimativa de custo e pede confirmação `s/N` antes
   de chamar a OpenAI. Salva incrementalmente em `data/synthetic/` —
   se cair no meio, é só rodar de novo (ele pula o que já existe).

5. **Anonimizar + dividir em train/val/test**:

   ```bash
   uv run python data/prepare_dataset.py
   ```

6. **Inspecionar amostras**:

   ```bash
   uv run python data/inspect_dataset.py --split train --n 5
   cat data/processed/dataset_report.md
   ```

## Estatísticas

Veja `processed/dataset_report.md` (gerado pelo passo 5) para:
- Total por split (train/val/test)
- Distribuição por tipo de fonte
- Comprimento médio em tokens
- Top entidades anonimizadas

## Anonimização

A anonimização (`anonymization.py`) detecta e substitui por placeholders
consistentes:

| Tipo | Método |
|---|---|
| Nome de pessoa | spaCy NER (entidade `PER`) |
| Local | spaCy NER (entidade `LOC`) |
| CPF (formatado e não formatado) | regex |
| RG, CRM, CEP | regex |
| Telefone, e-mail | regex |
| Data (DD/MM/AAAA e por extenso) | regex |
| Número de prontuário | regex contextual |

A função `anonymize_text(text)` retorna um `AnonymizationResult` com o
texto anonimizado, um mapeamento original → placeholder e a lista de
tipos detectados. Dentro de um mesmo documento, repetições da mesma
entidade ganham o mesmo placeholder (ex: "Maria Silva" mencionada 3
vezes vira `[PESSOA_1]` nas 3).

## Limitações conhecidas

- **Aproximação de tokens**: o relatório usa `tiktoken cl100k_base` em vez
  do tokenizer real do Qwen2.5 — esperar diferença de ~10-15%.
- **Falsos negativos de NER**: nomes pouco comuns ou grafados de forma
  atípica podem escapar do spaCy. Os testes cobrem casos típicos, não
  todos os edge cases.
- **Variabilidade da OpenAI**: como o modelo é estocástico (temperatura 0.7),
  duas execuções produzem datasets diferentes em conteúdo (mas mesmos
  volumes). Os splits, dado o mesmo input, são determinísticos (seed=42).
- **Coerência médica**: o GPT pode gerar condutas datadas ou simplificadas.
  Este dataset é para fim acadêmico, não para uso clínico real.

## Formato dos arquivos finais

Cada linha de `processed/{train,val,test}.jsonl` é um JSON no formato
*messages* (estilo ChatML / OpenAI fine-tuning):

```json
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

Esse é o formato esperado pelo template de chat do Qwen2.5-Instruct e
pelos scripts de fine-tuning padrão.
