"""Prepara o dataset final para fine-tuning.

Lê tudo de `data/synthetic/`, aplica anonimização, converte para o formato
`messages` (ChatML), embaralha com seed=42, faz split estratificado 80/10/10
e salva em `data/processed/train.jsonl`, `val.jsonl`, `test.jsonl`.

Também emite um relatório em `data/processed/dataset_report.md` com:
- Total de exemplos por split
- Distribuição por tipo de fonte
- Comprimento médio em tokens (aproximação via tiktoken cl100k_base)
- Top 10 entidades anonimizadas
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import tiktoken

from anonymization import AnonymizationResult, anonymize_text

# ----- Caminhos -----
HERE = Path(__file__).parent
SYNTHETIC_DIR = HERE / "synthetic"
PROCESSED_DIR = HERE / "processed"
PROTOCOLS_DIR = SYNTHETIC_DIR / "protocols"
TEMPLATES_DIR = SYNTHETIC_DIR / "templates"
PATIENTS_CSV = SYNTHETIC_DIR / "patients.csv"
QA_JSONL = SYNTHETIC_DIR / "qa_pairs.jsonl"
REFUSALS_JSONL = SYNTHETIC_DIR / "refusals.jsonl"

REPORT_PATH = PROCESSED_DIR / "dataset_report.md"

SEED = 42
TRAIN_FRAC = 0.8
VAL_FRAC = 0.1
TEST_FRAC = 0.1

# Mensagens system padronizadas por tipo de fonte.
SYSTEM_PROTOCOL = (
    "Você é um assistente médico que responde com base em protocolos "
    "clínicos institucionais. Seja preciso, estruturado e cite a conduta passo a passo."
)
SYSTEM_TEMPLATE = (
    "Você é um assistente médico que ajuda a redigir documentos clínicos "
    "(laudos, receitas, atestados). Produza o documento solicitado em formato adequado."
)
SYSTEM_PATIENT = (
    "Você é um assistente médico que resume informações de prontuários "
    "para apoiar a tomada de decisão clínica."
)
SYSTEM_QA = (
    "Você é um assistente médico especializado em prática clínica. "
    "Responda dúvidas de médicos com base em condutas reconhecidas."
)
SYSTEM_REFUSAL = (
    "Você é um assistente médico que prioriza segurança e ética clínica. "
    "Quando o pedido está fora do escopo médico, recuse e aponte onde a "
    "pessoa pode buscar a resposta. Quando o pedido é clínico mas faltam "
    "dados ou exige avaliação presencial, NÃO entregue dose, diagnóstico "
    "definitivo ou conduta — enumere os dados que faltam ou oriente a "
    "buscar atendimento adequado."
)


# ----- Parsing utilities -----
def parse_md_with_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extrai frontmatter YAML simples (key: value) e corpo do markdown."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5 :]
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


# ----- Carregadores por fonte -----
def load_protocols() -> list[dict[str, Any]]:
    """Cada protocolo vira 1 exemplo: user pergunta, assistant retorna corpo."""
    if not PROTOCOLS_DIR.exists():
        return []
    items = []
    for path in sorted(PROTOCOLS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = parse_md_with_frontmatter(text)
        titulo = fm.get("titulo", path.stem)
        especialidade = fm.get("especialidade", "")
        # Remove a seção "## Perguntas relacionadas" do corpo (deixa só o protocolo)
        body_protocolo = re.split(r"\n##\s+Perguntas relacionadas", body, maxsplit=1)[0].strip()
        user_msg = f"Resuma o protocolo de {especialidade}: {titulo}."
        items.append({
            "source_type": "protocol",
            "source_file": path.name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROTOCOL},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": body_protocolo},
            ],
        })
    return items


def load_templates() -> list[dict[str, Any]]:
    if not TEMPLATES_DIR.exists():
        return []
    items = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = parse_md_with_frontmatter(text)
        tipo = fm.get("tipo", "documento clínico")
        titulo = fm.get("titulo", path.stem)
        user_msg = f"Gere um modelo de {tipo} ({titulo})."
        items.append({
            "source_type": "template",
            "source_file": path.name,
            "messages": [
                {"role": "system", "content": SYSTEM_TEMPLATE},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": body.strip()},
            ],
        })
    return items


def load_patients() -> list[dict[str, Any]]:
    if not PATIENTS_CSV.exists():
        return []
    items = []
    with PATIENTS_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            user_msg = f"Faça um resumo do prontuário do paciente {row['nome']}."
            assistant_msg = (
                f"Paciente: {row['nome']}\n"
                f"Sexo: {row['sexo']}\n"
                f"Data de nascimento: {row['data_nascimento']}\n"
                f"CPF: {row['cpf']}\n"
                f"Telefone: {row['telefone']}\n"
                f"Endereço: {row['endereco']}\n\n"
                f"Alergias: {row['alergias']}\n"
                f"Medicações em uso: {row['medicacoes_atuais']}\n\n"
                f"Histórico clínico:\n{row['historico_resumido']}"
            )
            items.append({
                "source_type": "patient",
                "source_file": f"patients.csv#{row['id']}",
                "messages": [
                    {"role": "system", "content": SYSTEM_PATIENT},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg},
                ],
            })
    return items


def load_qa() -> list[dict[str, Any]]:
    if not QA_JSONL.exists():
        return []
    items = []
    with QA_JSONL.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                pair = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append({
                "source_type": "qa",
                "source_file": f"qa_pairs.jsonl#{i}",
                "messages": [
                    {"role": "system", "content": SYSTEM_QA},
                    {"role": "user", "content": pair["pergunta"]},
                    {"role": "assistant", "content": pair["resposta"]},
                ],
            })
    return items


def load_refusals() -> list[dict[str, Any]]:
    """Lê refusals.jsonl (gerado por generate_synthetic.py --only refusals)."""
    if not REFUSALS_JSONL.exists():
        return []
    items = []
    with REFUSALS_JSONL.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append({
                "source_type": "refusal",
                "source_file": f"refusals.jsonl#{i}",
                "messages": [
                    {"role": "system", "content": SYSTEM_REFUSAL},
                    {"role": "user", "content": rec["pergunta"]},
                    {"role": "assistant", "content": rec["resposta"]},
                ],
            })
    return items


# ----- Anonimização do item inteiro -----
def anonymize_item(item: dict[str, Any]) -> AnonymizationResult:
    """Anonimiza todas as mensagens do item, mantendo consistência interna."""
    full_text = "\n\n".join(m["content"] for m in item["messages"])
    result = anonymize_text(full_text)

    # Re-aplica o anonimizador em cada mensagem individualmente para
    # garantir consistência ao reconstruir (mesmo mapping não é preservado
    # entre chamadas — então o jeito robusto é anonimizar cada msg, mas
    # isso perde consistência cross-message). Aqui usamos uma abordagem
    # simples: anonimizamos o concat e depois dividimos pelos delimitadores.
    parts = result.anonymized_text.split("\n\n")
    if len(parts) == len(item["messages"]):
        for msg, new_text in zip(item["messages"], parts):
            msg["content"] = new_text
    else:
        # Fallback: anonimiza cada msg isolada (perde consistência cross-msg
        # mas evita corrupção de estrutura).
        for msg in item["messages"]:
            r = anonymize_text(msg["content"])
            msg["content"] = r.anonymized_text
    return result


# ----- Split estratificado -----
# Ordem FIXA de categorias para o stratified_split. Manter "refusal" por
# ÚLTIMO preserva o estado do rng nas categorias anteriores — exemplos de
# protocol/template/patient/qa caem nos mesmos splits que caíam antes da
# introdução de recusas (comparabilidade com o modelo já treinado).
SOURCE_ORDER = ["patient", "protocol", "qa", "template", "refusal"]


def stratified_split(
    items: list[dict[str, Any]],
    train_frac: float = TRAIN_FRAC,
    val_frac: float = VAL_FRAC,
    seed: int = SEED,
) -> tuple[list, list, list]:
    """Split estratificado por source_type, com seed fixa.

    Itera as categorias em SOURCE_ORDER (não em ordem alfabética) para
    manter os splits das categorias antigas idênticos aos da Fase 1
    quando refusals é adicionada.
    """
    by_type: dict[str, list] = {}
    for item in items:
        by_type.setdefault(item["source_type"], []).append(item)

    # Sanity check: qualquer source_type fora do SOURCE_ORDER seria silenciado.
    unknown = set(by_type) - set(SOURCE_ORDER)
    if unknown:
        raise ValueError(
            f"source_type(s) desconhecido(s) em SOURCE_ORDER: {unknown}. "
            f"Adicione-os à constante SOURCE_ORDER em prepare_dataset.py."
        )

    rng = random.Random(seed)
    train, val, test = [], [], []
    for source_type in SOURCE_ORDER:
        group = by_type.get(source_type, [])
        if not group:
            continue
        rng.shuffle(group)
        n = len(group)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        train.extend(group[:n_train])
        val.extend(group[n_train : n_train + n_val])
        test.extend(group[n_train + n_val :])
    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


# ----- Tokenização aproximada -----
_TIKTOKEN_ENC = None


def _enc():
    global _TIKTOKEN_ENC
    if _TIKTOKEN_ENC is None:
        _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENC


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    return sum(len(_enc().encode(m["content"])) for m in messages)


# ----- Salvamento -----
def write_jsonl(items: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            # Salva apenas o que importa pro fine-tuning: messages
            f.write(json.dumps({"messages": item["messages"]}, ensure_ascii=False) + "\n")


# ----- Relatório -----
# Padrões textuais que indicam recusa — usados pra validar via conteúdo
# que as recusas chegaram aos splits (não dependem de metadado).
REFUSAL_GREP_PATTERNS = (
    "não posso", "fora do escopo", "fora do meu escopo",
    "preciso de mais", "consulte um", "procure um",
    "atendimento presencial", "samu", "192", "pronto-socorro",
)


def _count_refusal_patterns(items: list) -> dict[str, int]:
    """Conta quantos items contêm cada padrão de recusa no assistant."""
    counts = {p: 0 for p in REFUSAL_GREP_PATTERNS}
    for it in items:
        # Concatena conteúdo do assistant (último) — onde a recusa aparece.
        assistant_text = " ".join(
            m["content"].lower() for m in it["messages"]
            if m["role"] == "assistant"
        )
        for p in REFUSAL_GREP_PATTERNS:
            if p in assistant_text:
                counts[p] += 1
    return counts


def build_report(
    train: list, val: list, test: list, entities_counter: Counter
) -> str:
    def stats(items: list) -> dict[str, Any]:
        types = Counter(it["source_type"] for it in items)
        token_counts = [estimate_tokens(it["messages"]) for it in items]
        avg = sum(token_counts) / len(token_counts) if token_counts else 0
        return {
            "total": len(items),
            "by_type": dict(types),
            "avg_tokens": avg,
            "max_tokens": max(token_counts) if token_counts else 0,
            "min_tokens": min(token_counts) if token_counts else 0,
        }

    s_train, s_val, s_test = stats(train), stats(val), stats(test)
    total = s_train["total"] + s_val["total"] + s_test["total"]

    # Validação textual de recusas (independente de metadado).
    refusal_train = _count_refusal_patterns(train)
    refusal_val = _count_refusal_patterns(val)
    refusal_test = _count_refusal_patterns(test)

    lines = [
        "# Relatório do dataset",
        "",
        "> Dados sintéticos e fictícios gerados via OpenAI gpt-4o-mini, anonimizados via spaCy + regex.",
        "",
        f"**Total de exemplos:** {total}",
        "",
        "## Distribuição por split",
        "",
        "| Split | Total | Por tipo de fonte |",
        "|---|---|---|",
        f"| train | {s_train['total']} | {s_train['by_type']} |",
        f"| val   | {s_val['total']} | {s_val['by_type']} |",
        f"| test  | {s_test['total']} | {s_test['by_type']} |",
        "",
        "## Comprimento (tokens, aproximação via tiktoken cl100k_base)",
        "",
        "| Split | Médio | Mínimo | Máximo |",
        "|---|---|---|---|",
        f"| train | {s_train['avg_tokens']:.0f} | {s_train['min_tokens']} | {s_train['max_tokens']} |",
        f"| val   | {s_val['avg_tokens']:.0f} | {s_val['min_tokens']} | {s_val['max_tokens']} |",
        f"| test  | {s_test['avg_tokens']:.0f} | {s_test['min_tokens']} | {s_test['max_tokens']} |",
        "",
        "> Nota: tiktoken `cl100k_base` é uma aproximação do tokenizer do Qwen2.5 (~10-15% de margem).",
        "",
        "## Top 10 tipos de entidades anonimizadas",
        "",
        "| Tipo | Ocorrências |",
        "|---|---|",
    ]
    for ent_type, count in entities_counter.most_common(10):
        lines.append(f"| {ent_type} | {count} |")
    lines.append("")
    lines.append("## Validação textual de recusas")
    lines.append("")
    lines.append(
        "Contagem de exemplos cujo assistant contém cada padrão de "
        "recusa (verificação independente de metadado — confirma que "
        "as recusas geradas chegaram efetivamente aos splits)."
    )
    lines.append("")
    lines.append("| Padrão | train | val | test |")
    lines.append("|---|---|---|---|")
    for pat in REFUSAL_GREP_PATTERNS:
        lines.append(
            f"| `{pat}` | {refusal_train[pat]} | {refusal_val[pat]} | "
            f"{refusal_test[pat]} |"
        )
    lines.append("")
    lines.append(f"_Gerado a partir de `data/synthetic/` com seed = {SEED}_")
    return "\n".join(lines) + "\n"


# ----- Main -----
def main() -> int:
    print("=" * 60)
    print("Preparação do dataset final — medical-assistant")
    print("=" * 60)

    print("→ Carregando fontes...")
    protocols = load_protocols()
    templates = load_templates()
    patients = load_patients()
    qa = load_qa()
    refusals = load_refusals()
    print(f"  protocolos: {len(protocols)}")
    print(f"  templates:  {len(templates)}")
    print(f"  pacientes:  {len(patients)}")
    print(f"  Q&A:        {len(qa)}")
    print(f"  recusas:    {len(refusals)}")

    all_items = protocols + templates + patients + qa + refusals
    if not all_items:
        print("\n❌ Nenhum item encontrado em data/synthetic/. Rode antes:")
        print("   uv run python data/generate_synthetic.py")
        return 1

    print(f"\n→ Anonimizando {len(all_items)} itens (pode levar 1-3 min, "
          f"spaCy carrega na 1ª chamada)...")
    entities_counter: Counter = Counter()
    for i, item in enumerate(all_items, 1):
        result = anonymize_item(item)
        entities_counter.update(result.entities_found)
        if i % 50 == 0 or i == len(all_items):
            print(f"  {i}/{len(all_items)}")

    print("\n→ Dividindo em train/val/test (80/10/10, estratificado, seed=42)...")
    train, val, test = stratified_split(all_items)
    print(f"  train: {len(train)} | val: {len(val)} | test: {len(test)}")

    print("\n→ Salvando JSONL...")
    write_jsonl(train, PROCESSED_DIR / "train.jsonl")
    write_jsonl(val, PROCESSED_DIR / "val.jsonl")
    write_jsonl(test, PROCESSED_DIR / "test.jsonl")

    print("→ Gerando relatório...")
    report = build_report(train, val, test, entities_counter)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"  {REPORT_PATH.relative_to(HERE.parent)}")

    print("\n✅ Pronto. Inspecione com:")
    print("   uv run python data/inspect_dataset.py --split train --n 5")
    print(f"   cat data/processed/dataset_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
