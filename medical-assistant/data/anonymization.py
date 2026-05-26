"""Anonimização de PII em texto clínico em português.

Detecta entidades sensíveis (nomes, CPF, RG, CRM, CEP, telefone, e-mail,
data, número de prontuário, locais) e substitui por placeholders consistentes
do tipo `[CPF_1]`, `[PESSOA_1]`, etc.

Estratégia: regex para padrões estruturados (formatos fixos como CPF) +
spaCy NER (`pt_core_news_lg`) para padrões não estruturados (nomes,
locais). Em sobreposições, o regex tem prioridade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import spacy
from spacy.language import Language

SPACY_MODEL = "pt_core_news_lg"

# Padrões regex em ordem de prioridade. Tuplas: (regex, tipo, flags).
# Padrões mais específicos vêm primeiro para vencer em conflitos.
REGEX_PATTERNS: list[tuple[str, str, int]] = [
    # CPF formatado: 123.456.789-00
    (r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "CPF", 0),
    # CPF não formatado: exatamente 11 dígitos isolados
    (r"\b\d{11}\b", "CPF", 0),
    # RG: 12.345.678-9 ou 12.345.678-X
    (r"\b\d{1,2}\.\d{3}\.\d{3}-[\dxX]\b", "RG", 0),
    # CRM: CRM/SP 123456 ou CRM-SP 123456 ou CRMSP 123456
    (r"\bCRM[\s/\-]?[A-Z]{2}\s*\d{3,7}\b", "CRM", re.IGNORECASE),
    # CEP: 12345-678 ou 12345678 (8 dígitos exatos)
    (r"\b\d{5}-?\d{3}\b", "CEP", 0),
    # Telefone BR: aceita +55, parênteses opcionais, 9º dígito opcional
    (
        r"(?:\+55\s*)?(?:\(\d{2}\)|\d{2})\s*9?\d{4}[\s\-]?\d{4}\b",
        "TELEFONE",
        0,
    ),
    # E-mail
    (r"\b[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}\b", "EMAIL", 0),
    # Data DD/MM/AAAA
    (r"\b\d{1,2}/\d{1,2}/\d{4}\b", "DATA", 0),
    # Data por extenso: "12 de março de 2024"
    (
        r"\b\d{1,2}\s+de\s+"
        r"(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4}\b",
        "DATA",
        re.IGNORECASE,
    ),
    # Número de prontuário: rótulo + dígitos
    (
        r"\b(?:Prontu[áa]rio|Reg(?:istro)?|ID\s+do\s+paciente)\s*[:.\-]?\s*\d+",
        "PRONTUARIO",
        re.IGNORECASE,
    ),
]

# Labels do spaCy → placeholders. Mantemos apenas PER e LOC para reduzir
# falsos positivos (ORG marca demais coisa como hospital, doença etc).
_SPACY_LABEL_MAP = {"PER": "PESSOA", "LOC": "LOCAL"}


@dataclass
class AnonymizationResult:
    """Resultado de uma anonimização.

    - `anonymized_text`: texto já com placeholders.
    - `mapping`: dicionário original → placeholder (para auditoria/debug).
    - `entities_found`: lista de tipos detectados, ordenada.
    """

    anonymized_text: str
    mapping: dict[str, str] = field(default_factory=dict)
    entities_found: list[str] = field(default_factory=list)


@dataclass
class _Span:
    start: int
    end: int
    text: str
    type: str


@lru_cache(maxsize=1)
def _load_spacy() -> Language:
    """Carrega o modelo spaCy pt_core_news_lg (cacheado por processo)."""
    try:
        return spacy.load(SPACY_MODEL)
    except OSError as e:
        raise RuntimeError(
            f"Modelo spaCy '{SPACY_MODEL}' não encontrado. "
            f"Rode: uv run python -m spacy download {SPACY_MODEL}"
        ) from e


def _regex_spans(text: str) -> list[_Span]:
    spans: list[_Span] = []
    for pattern, ent_type, flags in REGEX_PATTERNS:
        for m in re.finditer(pattern, text, flags=flags):
            spans.append(_Span(m.start(), m.end(), m.group(), ent_type))
    return spans


def _spacy_spans(text: str) -> list[_Span]:
    nlp = _load_spacy()
    doc = nlp(text)
    return [
        _Span(ent.start_char, ent.end_char, ent.text, _SPACY_LABEL_MAP[ent.label_])
        for ent in doc.ents
        if ent.label_ in _SPACY_LABEL_MAP
    ]


def _resolve_overlaps(spans: list[_Span]) -> list[_Span]:
    """Remove spans sobrepostos. Em empate de início, span mais longo vence;
    quando regex e spaCy disputam, regex tende a vencer porque cobre o
    padrão estruturado completo."""
    if not spans:
        return []
    # (start asc, end desc) — o mais longo vence em conflito de início.
    spans = sorted(spans, key=lambda s: (s.start, -s.end))
    result = [spans[0]]
    for s in spans[1:]:
        if s.start >= result[-1].end:
            result.append(s)
    return result


def anonymize_text(text: str) -> AnonymizationResult:
    """Anonimiza PII no texto, mantendo consistência intra-documento.

    Mesma entidade (case-insensitive) → mesmo placeholder dentro do mesmo
    texto. Se "Maria Silva" aparece 3 vezes, vira `[PESSOA_1]` nas 3.
    """
    if not text:
        return AnonymizationResult(anonymized_text=text)

    spans = _regex_spans(text) + _spacy_spans(text)
    spans = _resolve_overlaps(spans)

    mapping: dict[str, str] = {}
    cache: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}

    def placeholder_for(original: str, ent_type: str) -> str:
        key = (ent_type, original.strip().lower())
        if key in cache:
            mapping.setdefault(original, cache[key])
            return cache[key]
        counters[ent_type] = counters.get(ent_type, 0) + 1
        ph = f"[{ent_type}_{counters[ent_type]}]"
        cache[key] = ph
        mapping[original] = ph
        return ph

    # Substitui de trás pra frente para preservar índices.
    result_text = text
    for s in sorted(spans, key=lambda s: -s.start):
        ph = placeholder_for(s.text, s.type)
        result_text = result_text[: s.start] + ph + result_text[s.end :]

    return AnonymizationResult(
        anonymized_text=result_text,
        mapping=mapping,
        entities_found=sorted({s.type for s in spans}),
    )


def anonymize_file(input_path: str | Path, output_path: str | Path) -> AnonymizationResult:
    """Anonimiza um arquivo de texto. Cria diretórios pai se preciso."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    text = input_path.read_text(encoding="utf-8")
    result = anonymize_text(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.anonymized_text, encoding="utf-8")
    return result


def anonymize_dataset(
    input_dir: str | Path, output_dir: str | Path
) -> dict[str, AnonymizationResult]:
    """Anonimiza recursivamente todos os .md/.txt de um diretório.

    Retorna dict {caminho_relativo → AnonymizationResult}.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    results: dict[str, AnonymizationResult] = {}
    for path in input_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            rel = path.relative_to(input_dir)
            results[str(rel)] = anonymize_file(path, output_dir / rel)
    return results
