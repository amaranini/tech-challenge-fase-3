"""Geração de dataset sintético via OpenAI gpt-4o-mini.

Estrutura de saída em `data/synthetic/`:
- protocols/*.md         — um protocolo clínico por arquivo (com frontmatter)
- templates/*.md         — modelos de laudo/receita/atestado
- patients.csv           — 50 pacientes (Faker pt_BR + histórico via OpenAI)
- qa_pairs.jsonl         — pares pergunta/resposta brutos (antes do split)
- _failures.jsonl        — itens que falharam validação (para debug)

Salvamento incremental: cada item bem-sucedido vai pro disco imediatamente.
Se o script morrer, ao rodar de novo ele pula o que já existe.

NÃO chama a API automaticamente: pede confirmação interativa de custo.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from faker import Faker
from openai import APIError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError, field_validator
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

# ----- Caminhos -----
HERE = Path(__file__).parent
SYNTHETIC_DIR = HERE / "synthetic"
PROTOCOLS_DIR = SYNTHETIC_DIR / "protocols"
TEMPLATES_DIR = SYNTHETIC_DIR / "templates"
PATIENTS_CSV = SYNTHETIC_DIR / "patients.csv"
QA_JSONL = SYNTHETIC_DIR / "qa_pairs.jsonl"
REFUSALS_JSONL = SYNTHETIC_DIR / "refusals.jsonl"
FAILURES_LOG = SYNTHETIC_DIR / "_failures.jsonl"

# ----- Config -----
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SEED = 42

# Preços gpt-4o-mini (USD por 1M tokens) — referência calibrada para 2026.
COST_INPUT_PER_1M = 0.15
COST_OUTPUT_PER_1M = 0.60

# Volumes alvo
N_PROTOCOLS = 35
N_TEMPLATES = 20
N_PATIENTS = 50
N_QA_PAIRS = 400
N_REFUSALS = 60
PATIENT_BATCH = 5
QA_BATCH = 5
REFUSAL_BATCH = 5

# Limite de re-tentativas do filtro de qualidade textual em recusas.
REFUSAL_QUALITY_RETRIES = 3

# Especialidades, tipos e categorias para variedade
SPECIALTIES = [
    "cardiologia", "pneumologia", "infectologia", "pediatria",
    "emergência", "neurologia", "endocrinologia", "ortopedia",
    "gastroenterologia", "dermatologia", "urologia", "oncologia",
    "psiquiatria", "geriatria", "ginecologia e obstetrícia",
]

TEMPLATE_TYPES = [
    "laudo radiológico", "laudo laboratorial",
    "receita simples", "receita controlada",
    "atestado médico", "encaminhamento",
    "sumário de alta", "solicitação de exame",
    "declaração de comparecimento", "prescrição de enfermagem",
]

QA_CATEGORIES = [
    "diagnóstico diferencial", "posologia",
    "interpretação de exame", "manejo de emergência",
    "indicação de exame", "contraindicação",
    "efeito colateral", "conduta inicial",
]

# Taxonomia de recusas: categoria -> [(subcategoria, n_exemplos, descrição
# do tipo de pedido). N_REFUSALS deve ser igual à soma de n_exemplos.
REFUSAL_TAXONOMY: dict[str, list[tuple[str, int, str]]] = {
    "refusal_out_of_scope": [
        ("non_medical_general", 6,
         "pedido fora da medicina (matemática, jurídico, finanças, "
         "receita culinária, programação simples)"),
        ("personal_subjective", 6,
         "opinião política, religiosa, moral ou estética não-médica"),
        ("creative_writing", 6,
         "escrita criativa (poema, redação escolar, letra de música, "
         "carta pessoal)"),
        ("tech_help", 6,
         "suporte técnico de computador, celular, internet ou rede social"),
        ("inappropriate_personal", 6,
         "perguntas pessoais sobre o assistente, flerte, role-play "
         "não-clínico"),
    ],
    "refusal_clinical": [
        ("prescription_without_context", 8,
         "pedido de prescrição sem dados do paciente (idade, peso, "
         "alergias, função renal, comorbidades, foco infeccioso); "
         "modelo deve PEDIR esses dados antes de qualquer dose"),
        ("pediatric_without_weight_age", 5,
         "dose pediátrica sem peso e idade da criança; modelo deve "
         "explicitamente recusar dar dose sem esses dados"),
        ("definitive_diagnosis_without_exam", 5,
         "pedido de diagnóstico definitivo só por sintomas, sem exame "
         "físico, laboratorial ou de imagem; modelo deve apontar quais "
         "exames são necessários e que diagnóstico definitivo exige "
         "avaliação presencial"),
        ("layperson_advice", 4,
         "leigo (paciente ou familiar) pedindo conduta médica; modelo "
         "deve orientar a procurar atendimento médico e NÃO indicar "
         "tratamento"),
        ("emergency_needs_in_person", 4,
         "situação que sugere emergência (dor torácica de início súbito, "
         "AVC, anafilaxia, sinais de choque) — modelo deve orientar a "
         "procurar PA/SAMU 192 imediatamente e NÃO conduzir por chat"),
        ("dangerous_self_medication", 4,
         "auto-medicação com risco real (interação medicamentosa grave, "
         "dose acima do seguro, mistura com álcool) — modelo deve "
         "recusar e orientar a consultar médico/farmacêutico"),
    ],
}

# Padrões textuais aceitáveis para validar que uma "recusa" gerada
# realmente é uma recusa (filtro de qualidade pós-geração).
REFUSAL_PATTERNS = (
    "não posso", "não devo", "não é apropriado", "fora do meu escopo",
    "fora do escopo", "consulte um", "consultar um", "procure um",
    "procurar um", "preciso de mais", "antes de", "requer",
    "depende de", "sem essas informações", "sem essas info",
    "atendimento presencial", "avaliação presencial", "buscar atendimento",
    "samu", "pronto-socorro", "pronto socorro", "pronto atendimento",
    "emergência", "192",
)


def _has_refusal_pattern(text: str) -> bool:
    """True se o texto contém pelo menos um padrão de recusa aceitável."""
    lower = text.lower()
    return any(p in lower for p in REFUSAL_PATTERNS)


# ----- Schemas Pydantic para validação das respostas -----
class Protocol(BaseModel):
    titulo: str = Field(min_length=10)
    especialidade: str
    conteudo: str = Field(min_length=200)
    perguntas_relacionadas: list[str] = Field(min_length=1)


class Template(BaseModel):
    tipo: str
    titulo: str = Field(min_length=5)
    conteudo: str = Field(min_length=100)
    variacao_descricao: str


class PatientHistory(BaseModel):
    id: str
    alergias: str
    medicacoes_atuais: str
    historico_resumido: str = Field(min_length=50)

    @field_validator("alergias", "medicacoes_atuais", "historico_resumido", mode="before")
    @classmethod
    def _coerce_to_string(cls, v):
        # gpt-4o-mini às vezes devolve esses campos como lista
        # (ex: ["penicilina"]). Normalizamos pra texto.
        if isinstance(v, list):
            return ", ".join(str(x).strip() for x in v if str(x).strip()) or "Nenhuma"
        if v is None:
            return "Nenhuma"
        return v


class PatientBatchResponse(BaseModel):
    pacientes: list[PatientHistory] = Field(min_length=1)


class QAPair(BaseModel):
    pergunta: str = Field(min_length=30)
    resposta: str = Field(min_length=50)


class QABatchResponse(BaseModel):
    pares: list[QAPair] = Field(min_length=1)


class RefusalPair(BaseModel):
    pergunta: str = Field(min_length=10)
    resposta: str = Field(min_length=40)


class RefusalBatchResponse(BaseModel):
    pares: list[RefusalPair] = Field(min_length=1)


# ----- Utilitários -----
def _log_failure(kind: str, identifier: Any, error: str) -> None:
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    with FAILURES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, "id": str(identifier), "error": error}) + "\n")


def _has_obvious_placeholder(s: str) -> bool:
    """Heurística pra descartar respostas que ficaram com placeholders soltos."""
    lower = s.lower()
    return any(token in lower for token in ("lorem", "xxx", "[nome]", "[data]", "[xx]"))


# Retry: 3 tentativas, backoff exponencial 1s → 2s → 4s.
_api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, json.JSONDecodeError)),
)


@_api_retry
def _chat_json(client: OpenAI, user_prompt: str) -> dict[str, Any]:
    """Chama a OpenAI com response_format=json_object e devolve o dict."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é um especialista médico ajudando a gerar dados "
                    "FICTÍCIOS para treinamento de uma IA acadêmica. Todos os "
                    "dados são sintéticos, sem ligação com pacientes reais. "
                    "Responda APENAS em JSON válido, sem texto fora do JSON."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)


# ----- Geração: Protocolos -----
def generate_protocols(client: OpenAI, n: int = N_PROTOCOLS) -> int:
    """Gera N protocolos clínicos. Salva um .md por protocolo, com frontmatter."""
    PROTOCOLS_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    for i in range(n):
        specialty = SPECIALTIES[i % len(SPECIALTIES)]
        round_idx = i // len(SPECIALTIES) + 1
        out_path = PROTOCOLS_DIR / f"protocol_{i:03d}_{specialty.replace(' ', '_')}.md"
        if out_path.exists():
            generated += 1
            print(f"  [{generated}/{n}] (pula, já existe) {out_path.name}")
            continue

        prompt = (
            f"Gere um PROTOCOLO CLÍNICO FICTÍCIO sobre {specialty}.\n"
            f"Esta é a rodada {round_idx} dessa especialidade — escolha um tema "
            f"clínico DISTINTO de protocolos anteriores (ex: para cardiologia "
            f"rodada 1 = dor torácica, rodada 2 = ICC descompensada, etc).\n\n"
            f"Responda em JSON com:\n"
            f'- "titulo": título do protocolo\n'
            f'- "especialidade": "{specialty}"\n'
            f'- "conteudo": markdown completo (300-500 palavras), com seções:\n'
            f"  Indicação, Critérios de inclusão/exclusão, Conduta inicial, "
            f"Conduta subsequente, Critérios de alta/encaminhamento\n"
            f'- "perguntas_relacionadas": lista de 2-3 perguntas em '
            f"português que um médico faria sobre este protocolo"
        )
        try:
            raw = _chat_json(client, prompt)
            proto = Protocol(**raw)
            if _has_obvious_placeholder(proto.conteudo):
                raise ValueError("conteúdo com placeholders óbvios")
        except (ValidationError, ValueError, Exception) as e:  # noqa: BLE001
            _log_failure("protocol", i, repr(e))
            print(f"  [{generated}/{n}] FALHOU protocol_{i:03d}: {e}")
            continue

        body = (
            f"---\n"
            f"especialidade: {proto.especialidade}\n"
            f'titulo: "{proto.titulo}"\n'
            f"data_geracao: {time.strftime('%Y-%m-%d')}\n"
            f"versao: 1\n"
            f"---\n\n"
            f"# {proto.titulo}\n\n"
            f"{proto.conteudo}\n\n"
            f"## Perguntas relacionadas\n\n"
            + "\n".join(f"- {q}" for q in proto.perguntas_relacionadas)
            + "\n"
        )
        out_path.write_text(body, encoding="utf-8")
        generated += 1
        print(f"  [{generated}/{n}] {out_path.name}")
    return generated


# ----- Geração: Templates -----
def generate_templates(client: OpenAI, n: int = N_TEMPLATES) -> int:
    """Gera N modelos de documentos clínicos (laudo/receita/atestado/etc)."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0
    for i in range(n):
        ttype = TEMPLATE_TYPES[i % len(TEMPLATE_TYPES)]
        variation = i // len(TEMPLATE_TYPES) + 1
        slug = ttype.replace(" ", "_")
        out_path = TEMPLATES_DIR / f"template_{i:03d}_{slug}_v{variation}.md"
        if out_path.exists():
            generated += 1
            print(f"  [{generated}/{n}] (pula) {out_path.name}")
            continue

        prompt = (
            f"Gere um MODELO/TEMPLATE FICTÍCIO de '{ttype}' para uso hospitalar.\n"
            f"Esta é a variação {variation} desse tipo — deve diferir de "
            f"versões anteriores em estrutura, especialidade ou contexto clínico.\n"
            f"Use placeholders entre colchetes para campos preenchidos no uso "
            f"real (ex: [NOME DO PACIENTE], [DATA], [MEDICAMENTO]).\n\n"
            f"Responda em JSON com:\n"
            f'- "tipo": "{ttype}"\n'
            f'- "titulo": título do modelo\n'
            f'- "conteudo": markdown do modelo (150-300 palavras)\n'
            f'- "variacao_descricao": 1 frase descrevendo como esta versão difere'
        )
        try:
            raw = _chat_json(client, prompt)
            tpl = Template(**raw)
            if _has_obvious_placeholder(tpl.titulo):
                raise ValueError("título com placeholder óbvio")
        except (ValidationError, ValueError, Exception) as e:  # noqa: BLE001
            _log_failure("template", i, repr(e))
            print(f"  [{generated}/{n}] FALHOU template_{i:03d}: {e}")
            continue

        body = (
            f"---\n"
            f"tipo: {tpl.tipo}\n"
            f'titulo: "{tpl.titulo}"\n'
            f"variacao: {variation}\n"
            f'descricao_variacao: "{tpl.variacao_descricao}"\n'
            f"data_geracao: {time.strftime('%Y-%m-%d')}\n"
            f"---\n\n"
            f"# {tpl.titulo}\n\n"
            f"{tpl.conteudo}\n"
        )
        out_path.write_text(body, encoding="utf-8")
        generated += 1
        print(f"  [{generated}/{n}] {out_path.name}")
    return generated


# ----- Geração: Pacientes -----
def generate_patients(client: OpenAI, n: int = N_PATIENTS) -> int:
    """Gera N pacientes sintéticos. Faker cria demográficos; OpenAI gera
    histórico/alergias/medicações coerentes em batches."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # Se já existe, retomar do tamanho atual
    existing_ids: set[str] = set()
    if PATIENTS_CSV.exists():
        with PATIENTS_CSV.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                existing_ids.add(row["id"])
        print(f"  ↳ {len(existing_ids)} pacientes já existem — retomando.")

    fake = Faker("pt_BR")
    Faker.seed(SEED)
    rng = random.Random(SEED + len(existing_ids))

    write_header = not PATIENTS_CSV.exists()
    fieldnames = [
        "id", "nome", "cpf", "data_nascimento", "sexo", "telefone",
        "endereco", "alergias", "medicacoes_atuais", "historico_resumido",
    ]

    with PATIENTS_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        generated = len(existing_ids)
        # Processa em batches: Faker gera demográficos, OpenAI completa o resto
        while generated < n:
            batch_size = min(PATIENT_BATCH, n - generated)
            batch_demographics = []
            for j in range(batch_size):
                pid = f"P{generated + j + 1:04d}"
                if pid in existing_ids:
                    continue
                sexo = rng.choice(["M", "F"])
                idade = rng.randint(2, 90)
                nome = fake.name_male() if sexo == "M" else fake.name_female()
                batch_demographics.append({
                    "id": pid,
                    "nome": nome,
                    "cpf": fake.cpf(),
                    "data_nascimento": fake.date_of_birth(
                        minimum_age=idade, maximum_age=idade
                    ).strftime("%d/%m/%Y"),
                    "sexo": sexo,
                    "idade": idade,
                    "telefone": fake.phone_number(),
                    "endereco": fake.address().replace("\n", ", "),
                })
            if not batch_demographics:
                break

            # Pede à OpenAI o histórico médico coerente com cada paciente
            ids_payload = [
                {"id": p["id"], "idade": p["idade"], "sexo": p["sexo"]}
                for p in batch_demographics
            ]
            prompt = (
                f"Para os pacientes a seguir (sintéticos, fictícios), gere "
                f"alergias, medicações em uso e um histórico clínico resumido "
                f"COERENTE com idade e sexo. Mantenha realismo médico mas SEM "
                f"copiar de pacientes reais.\n\n"
                f"Pacientes: {json.dumps(ids_payload, ensure_ascii=False)}\n\n"
                f"IMPORTANTE: cada campo (alergias, medicacoes_atuais, "
                f"historico_resumido) deve ser UMA STRING DE TEXTO CORRIDO, "
                f"NÃO um array. Se houver múltiplos itens, separe-os com vírgula "
                f"dentro da mesma string. Se não houver, use 'Nenhuma'.\n\n"
                f'Exemplo correto: "alergias": "penicilina, dipirona"\n'
                f'Exemplo errado:  "alergias": ["penicilina", "dipirona"]\n\n'
                f'Responda JSON: {{"pacientes": [{{"id": "...", "alergias": '
                f'"texto", "medicacoes_atuais": "texto", "historico_resumido": '
                f'"texto"}}, ...]}}'
            )
            try:
                raw = _chat_json(client, prompt)
                batch_response = PatientBatchResponse(**raw)
                histories = {p.id: p for p in batch_response.pacientes}
            except (ValidationError, ValueError, Exception) as e:  # noqa: BLE001
                _log_failure("patient_batch", generated, repr(e))
                print(f"  FALHOU batch de pacientes começando em {generated}: {e}")
                generated += batch_size  # avança pra não travar
                continue

            for demo in batch_demographics:
                hist = histories.get(demo["id"])
                if not hist:
                    _log_failure("patient", demo["id"], "sem histórico retornado")
                    continue
                row = {
                    "id": demo["id"],
                    "nome": demo["nome"],
                    "cpf": demo["cpf"],
                    "data_nascimento": demo["data_nascimento"],
                    "sexo": demo["sexo"],
                    "telefone": demo["telefone"],
                    "endereco": demo["endereco"],
                    "alergias": hist.alergias,
                    "medicacoes_atuais": hist.medicacoes_atuais,
                    "historico_resumido": hist.historico_resumido,
                }
                writer.writerow(row)
                f.flush()
                generated += 1
                print(f"  [{generated}/{n}] paciente {demo['id']} salvo")

    return generated


# ----- Geração: Q&A -----
def generate_qa_pairs(client: OpenAI, n: int = N_QA_PAIRS, batch_size: int = QA_BATCH) -> int:
    """Gera N pares pergunta/resposta médicos, em batches de `batch_size`."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # Conta os já existentes para retomada
    existing = 0
    if QA_JSONL.exists():
        with QA_JSONL.open("r", encoding="utf-8") as f:
            for _ in f:
                existing += 1
        print(f"  ↳ {existing} Q&A já existem — retomando.")

    rng = random.Random(SEED + existing)
    generated = existing

    with QA_JSONL.open("a", encoding="utf-8") as f:
        while generated < n:
            specialty = rng.choice(SPECIALTIES)
            category = rng.choice(QA_CATEGORIES)
            this_batch = min(batch_size, n - generated)

            prompt = (
                f"Gere {this_batch} pares pergunta-resposta sobre {specialty}, "
                f"categoria '{category}'. Cada par deve ser medicamente coerente, "
                f"realista, e útil para um médico em formação consultar.\n"
                f"Use condutas baseadas em prática clínica reconhecida; dados de "
                f"paciente, quando aparecerem, devem ser fictícios.\n"
                f'Responda JSON: {{"pares": [{{"pergunta": "...", "resposta": "..."}}, ...]}}'
            )
            try:
                raw = _chat_json(client, prompt)
                batch = QABatchResponse(**raw)
            except (ValidationError, ValueError, Exception) as e:  # noqa: BLE001
                _log_failure("qa_batch", generated, repr(e))
                print(f"  FALHOU batch Q&A começando em {generated}: {e}")
                continue

            for pair in batch.pares:
                if _has_obvious_placeholder(pair.pergunta) or _has_obvious_placeholder(pair.resposta):
                    _log_failure("qa_pair", generated, "placeholder óbvio")
                    continue
                line = json.dumps(
                    {
                        "pergunta": pair.pergunta,
                        "resposta": pair.resposta,
                        "especialidade": specialty,
                        "categoria": category,
                    },
                    ensure_ascii=False,
                )
                f.write(line + "\n")
                f.flush()
                generated += 1
                if generated >= n:
                    break
            print(f"  [{generated}/{n}] Q&A acumulados ({specialty} / {category})")

    return generated


# ----- Geração: Recusas -----
def _refusal_prompt(category: str, subcat: str, subcat_desc: str, n: int) -> str:
    """Constrói o prompt para geração de N exemplos de recusa numa subcategoria."""
    if category == "refusal_out_of_scope":
        objetivo = (
            "O ASSISTENTE deve RECUSAR responder no mérito porque o pedido "
            "está fora do escopo médico. A recusa precisa: (1) explicitar "
            "que está fora do escopo, (2) NÃO entregar a resposta substantiva "
            "do que foi pedido (não calcule, não escreva o poema, não dê o "
            "conselho jurídico — só aponte onde a pessoa pode buscar), e "
            "(3) opcionalmente oferecer ajuda no domínio clínico."
        )
        exemplar = (
            "Exemplo do padrão desejado (NÃO copie literalmente):\n"
            '{"pergunta": "Pode me ajudar a calcular a média ponderada de '
            'três notas pra fechar a disciplina?", "resposta": "Esse pedido '
            "está fora do meu escopo — sou um assistente focado em apoio à "
            "decisão clínica e não respondo dúvidas acadêmicas. Pra esse "
            "cálculo, vale consultar uma calculadora científica ou o material "
            'da disciplina. Posso ajudar com alguma dúvida clínica?"}'
        )
    else:  # refusal_clinical
        objetivo = (
            "O ASSISTENTE deve RECUSAR responder no mérito por motivo "
            "CLÍNICO/SEGURANÇA. A recusa precisa: (1) explicar concretamente "
            "QUE dados faltam (ou por que esse pedido exige atendimento "
            "presencial / avaliação médica direta), (2) NÃO entregar dose, "
            "diagnóstico definitivo ou conduta prescritiva, (3) ser técnica "
            "(linguagem médica) e respeitosa — não moralizar, não infantilizar. "
            "Se a pergunta vier com contexto parcial, a recusa deve ENUMERAR "
            "os dados específicos que ainda faltam (idade, peso, alergias, "
            "função renal, comorbidades, gravidade, etc) — não apenas dizer "
            '"preciso de mais informações" genericamente.'
        )
        exemplar = (
            "Exemplo do padrão desejado (NÃO copie literalmente):\n"
            '{"pergunta": "Prescreva amoxicilina para essa pneumonia.", '
            '"resposta": "Antes de sugerir um esquema, preciso de mais '
            "informações sobre o paciente: idade e peso (especialmente se "
            "for pediátrico), alergia a beta-lactâmicos, função renal, "
            "comorbidades relevantes (DPOC, diabetes, ICC) e gravidade do "
            "quadro (critérios CURB-65 ou equivalente). A escolha do "
            "antibiótico, dose e duração dependem desses dados. Pode me "
            'fornecer essas informações?"}'
        )

    return (
        f"Gere {n} pares pergunta-resposta SINTÉTICOS para treinar um "
        f"assistente médico a RECUSAR adequadamente.\n\n"
        f"Categoria: {category}\n"
        f"Subcategoria: {subcat}\n"
        f"Tipo do pedido: {subcat_desc}\n\n"
        f"{objetivo}\n\n"
        f"VARIE o formato das perguntas dentro do batch: misture pelo menos "
        f"DOIS dos formatos abaixo, sem repetir o mesmo formato em todos os "
        f"pares:\n"
        f"  - imperativo curto (ex: 'Prescreva X.')\n"
        f"  - pergunta direta curta (ex: 'Que dose de X?')\n"
        f"  - permissivo (ex: 'Pode prescrever X?')\n"
        f"  - auto-referente (ex: 'Quero prescrever X, qual a dose?')\n"
        f"  - pergunta longa com contexto fake mas insuficiente\n"
        f"  - registro informal (ex: 'tô com paciente com X, o que faço?')\n"
        f"  - registro formal (ex: 'Solicito orientação sobre...')\n\n"
        f"As respostas devem variar em tamanho conforme o pedido: curtas "
        f"quando o pedido é curto, mais detalhadas quando o pedido já vem "
        f"com contexto parcial.\n\n"
        f"{exemplar}\n\n"
        f'Responda JSON: {{"pares": [{{"pergunta": "...", "resposta": "..."}}, ...]}}'
    )


def generate_refusals(client: OpenAI, n: int = N_REFUSALS) -> int:
    """Gera N exemplos de recusa, distribuídos conforme REFUSAL_TAXONOMY.

    Cada par sai com `categoria` e `subcategoria` no JSONL. A categoria
    também serve como tag textual de busca depois.

    Filtro de qualidade: descarta respostas que NÃO contenham padrões
    de recusa (ver REFUSAL_PATTERNS). Re-tenta até REFUSAL_QUALITY_RETRIES
    vezes por batch que cair abaixo do esperado.
    """
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # Conta os já existentes para retomada (mesma estratégia do qa_pairs).
    existing_by_subcat: dict[str, int] = {}
    if REFUSALS_JSONL.exists():
        with REFUSALS_JSONL.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    key = rec.get("subcategoria", "")
                    existing_by_subcat[key] = existing_by_subcat.get(key, 0) + 1
                except json.JSONDecodeError:
                    continue
        total_existing = sum(existing_by_subcat.values())
        if total_existing:
            print(f"  ↳ {total_existing} recusas já existem — retomando.")

    # Sanity check: soma da taxonomia bate com N.
    declared = sum(
        cnt for subs in REFUSAL_TAXONOMY.values() for _, cnt, _ in subs
    )
    if declared != n:
        print(f"  ⚠ taxonomia declara {declared} exemplos, mas n={n}. "
              f"Usando o que a taxonomia diz ({declared}).")
        n = declared

    generated = sum(existing_by_subcat.values())
    with REFUSALS_JSONL.open("a", encoding="utf-8") as f:
        for category, subcats in REFUSAL_TAXONOMY.items():
            for subcat, target, desc in subcats:
                already = existing_by_subcat.get(subcat, 0)
                remaining = target - already
                if remaining <= 0:
                    print(f"  [skip] {category}/{subcat}: já temos {already}")
                    continue

                # Gera em batches de REFUSAL_BATCH dentro de cada subcat.
                while remaining > 0:
                    this_batch = min(REFUSAL_BATCH, remaining)
                    pairs_accepted: list[RefusalPair] = []

                    for attempt in range(REFUSAL_QUALITY_RETRIES):
                        prompt = _refusal_prompt(
                            category, subcat, desc, this_batch
                        )
                        try:
                            raw = _chat_json(client, prompt)
                            batch = RefusalBatchResponse(**raw)
                        except (ValidationError, ValueError, Exception) as e:  # noqa: BLE001
                            _log_failure(
                                "refusal_batch", f"{subcat}#{attempt}", repr(e)
                            )
                            print(f"  FALHOU {subcat} (tent {attempt+1}): {e}")
                            continue

                        # Filtro de qualidade: aceita apenas pares cuja
                        # resposta contenha padrão de recusa.
                        for pair in batch.pares:
                            if _has_obvious_placeholder(pair.pergunta) \
                                    or _has_obvious_placeholder(pair.resposta):
                                _log_failure(
                                    "refusal_pair", subcat,
                                    f"placeholder óbvio: {pair.pergunta!r}",
                                )
                                continue
                            if not _has_refusal_pattern(pair.resposta):
                                _log_failure(
                                    "refusal_pair", subcat,
                                    f"sem padrão de recusa: {pair.resposta[:80]!r}",
                                )
                                continue
                            pairs_accepted.append(pair)
                            if len(pairs_accepted) >= this_batch:
                                break

                        if len(pairs_accepted) >= this_batch:
                            break
                        # senão, tenta de novo (gerar mais pra completar batch)

                    if not pairs_accepted:
                        print(f"  ⚠ {subcat}: zero pares aceitos após "
                              f"{REFUSAL_QUALITY_RETRIES} tentativas. Seguindo.")
                        remaining = 0  # evita loop infinito
                        continue

                    # Pega só os primeiros `this_batch` aceitos.
                    for pair in pairs_accepted[:this_batch]:
                        line = json.dumps(
                            {
                                "pergunta": pair.pergunta,
                                "resposta": pair.resposta,
                                "categoria": category,
                                "subcategoria": subcat,
                            },
                            ensure_ascii=False,
                        )
                        f.write(line + "\n")
                        f.flush()
                        generated += 1
                        remaining -= 1
                    print(f"  [{generated}/{n}] {category}/{subcat} "
                          f"(+{len(pairs_accepted[:this_batch])})")
    return generated


# ----- Estimativa de custo + confirmação -----
def estimate_cost(only: str = "all") -> tuple[int, float]:
    """Retorna (chamadas_totais, custo_estimado_usd) para o subset selecionado."""
    # tokens médios por chamada (estimativa calibrada)
    ALL_ITEMS: dict[str, tuple[int, int, int]] = {
        "protocols":  (N_PROTOCOLS, 500, 2500),
        "templates":  (N_TEMPLATES, 400, 1200),
        "patients":   (N_PATIENTS // PATIENT_BATCH, 400, 1500),
        "qa":         (N_QA_PAIRS // QA_BATCH, 400, 1500),
        # Recusas: prompt mais longo (descrição + exemplar) e saída
        # média ~250 tokens por par × 5 por batch ≈ 1250.
        "refusals":   (N_REFUSALS // REFUSAL_BATCH, 700, 1300),
    }
    if only == "all":
        selected = ALL_ITEMS.values()
    else:
        selected = [ALL_ITEMS[only]] if only in ALL_ITEMS else []
    total_calls = sum(c for c, _, _ in selected)
    total_cost = 0.0
    for n_calls, in_tok, out_tok in selected:
        total_cost += n_calls * (
            in_tok * COST_INPUT_PER_1M / 1_000_000
            + out_tok * COST_OUTPUT_PER_1M / 1_000_000
        )
    # buffer de 30% para retries
    return total_calls, total_cost * 1.3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera dataset sintético via OpenAI gpt-4o-mini."
    )
    parser.add_argument(
        "--only",
        choices=["all", "protocols", "templates", "patients", "qa", "refusals"],
        default="all",
        help="gera só o subset selecionado (default: all)",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="pula a confirmação interativa de custo (CUIDADO).",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERRO: OPENAI_API_KEY não está definida.")
        print("   Crie um arquivo .env (ou copie de .env.example) com a chave.")
        return 1

    total_calls, estimated_cost = estimate_cost(args.only)
    print("=" * 60)
    print("Geração de dataset sintético — medical-assistant")
    print("=" * 60)
    print(f"Modelo: {MODEL}")
    print(f"Subset: {args.only}")
    if args.only in ("all", "protocols"):
        print(f"  protocolos: {N_PROTOCOLS}")
    if args.only in ("all", "templates"):
        print(f"  templates:  {N_TEMPLATES}")
    if args.only in ("all", "patients"):
        print(f"  pacientes:  {N_PATIENTS}")
    if args.only in ("all", "qa"):
        print(f"  Q&A:        {N_QA_PAIRS}")
    if args.only in ("all", "refusals"):
        print(f"  recusas:    {N_REFUSALS}")
    print(f"Chamadas estimadas: ~{total_calls}")
    print(f"Custo estimado: ~US$ {estimated_cost:.2f} (com buffer de retries)")
    print("=" * 60)
    if not args.yes:
        answer = input("Prosseguir? [s/N] ").strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            print("Cancelado.")
            return 0

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    t0 = time.monotonic()
    p_count = t_count = pa_count = qa_count = r_count = None
    if args.only in ("all", "protocols"):
        print("\n→ Gerando protocolos...")
        p_count = generate_protocols(client)
    if args.only in ("all", "templates"):
        print("\n→ Gerando templates...")
        t_count = generate_templates(client)
    if args.only in ("all", "patients"):
        print("\n→ Gerando pacientes...")
        pa_count = generate_patients(client)
    if args.only in ("all", "qa"):
        print("\n→ Gerando pares Q&A...")
        qa_count = generate_qa_pairs(client)
    if args.only in ("all", "refusals"):
        print("\n→ Gerando recusas...")
        r_count = generate_refusals(client)

    elapsed = time.monotonic() - t0
    print("\n" + "=" * 60)
    print(f"Concluído em {elapsed:.1f}s.")
    if p_count is not None:
        print(f"  Protocolos: {p_count}/{N_PROTOCOLS}")
    if t_count is not None:
        print(f"  Templates:  {t_count}/{N_TEMPLATES}")
    if pa_count is not None:
        print(f"  Pacientes:  {pa_count}/{N_PATIENTS}")
    if qa_count is not None:
        print(f"  Q&A:        {qa_count}/{N_QA_PAIRS}")
    if r_count is not None:
        print(f"  Recusas:    {r_count}/{N_REFUSALS}")
    if FAILURES_LOG.exists():
        with FAILURES_LOG.open() as f:
            fail_count = sum(1 for _ in f)
        if fail_count:
            print(f"  ⚠ Falhas:   {fail_count} (ver {FAILURES_LOG.relative_to(HERE)})")
    print("\nPróximo passo: uv run python data/prepare_dataset.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
