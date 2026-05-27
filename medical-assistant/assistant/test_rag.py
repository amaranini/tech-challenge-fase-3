"""Testes do retriever real. Pulam se o índice ainda não foi construído."""

from __future__ import annotations

from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CHROMA_DIR = HERE / "data" / "chroma_db"

_skip = pytest.mark.skipif(
    not CHROMA_DIR.exists(),
    reason=f"Índice RAG não construído em {CHROMA_DIR}. "
    f"Rode: uv run python assistant/rag/build_index.py",
)


@_skip
def test_retriever_returns_top_k_chunks():
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    chunks = retriever.retrieve("Como manejar sepse?", top_k=3)
    assert len(chunks) == 3
    for c in chunks:
        assert c.text
        assert c.source_file
        assert 0.0 <= c.score <= 1.0


@_skip
def test_retriever_finds_pneumonia_protocol():
    """Recupera o protocolo certo quando a pergunta é sobre tema PRESENTE no dataset.

    Por que essa pergunta: `protocol_002_infectologia.md` é o protocolo de
    Pneumonia Adquirida na Comunidade (PAC) — confirmado por inspeção direta
    do arquivo. Tema com vocabulário específico (PAC, antibioticoterapia
    empírica, CURB-65) que NÃO se confunde com outros temas do dataset.

    Critérios de aprovação:
    - Pelo menos 1 dos 3 chunks retornados vem de `protocol_002_infectologia.md`.
    - Top-1 score > 0.5 (similaridade do cosseno).
    """
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    chunks = retriever.retrieve(
        "Como tratar pneumonia adquirida na comunidade em adulto?", top_k=3
    )

    assert len(chunks) == 3, f"Esperava 3 chunks, veio {len(chunks)}"

    sources = [c.source_file for c in chunks]
    assert "protocol_002_infectologia.md" in sources, (
        f"Esperava o protocolo de PAC entre os top-3, veio: {sources}"
    )

    top_score = chunks[0].score
    assert top_score > 0.5, (
        f"Top-1 score baixo demais ({top_score:.3f}) para tema presente no "
        f"dataset. Ou o embedding/chunking degradou, ou o protocolo de PAC "
        f"não está indexado."
    )


@_skip
def test_retriever_distinguishes_present_vs_absent_topics():
    """Tema ausente deve ter score top-1 menor que tema presente por margem >= 0.10.

    Comparativa em vez de absoluta porque scores absolutos dependem da
    calibração do embedding/Chroma e podem flutuar entre versões — mas a
    separação relativa deve se manter.

    Pneumonia Adquirida na Comunidade está no `protocol_002_infectologia.md`;
    Doença de Lyme não está em nenhum protocolo do dataset. Lyme tem
    manifestação dermatológica (eritema migrans), então é um teste FORTE de
    discriminação: o retriever precisa distinguir "tema central" de "tema
    vagamente relacionado por sintoma compartilhado".
    """
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    present = retriever.retrieve(
        "Como tratar pneumonia adquirida na comunidade?", top_k=1
    )[0]
    absent = retriever.retrieve(
        "Como tratar Doença de Lyme transmitida por carrapato?", top_k=1
    )[0]

    diff = present.score - absent.score
    assert diff >= 0.10, (
        f"Discriminação insuficiente: PAC={present.score:.3f} "
        f"(de {present.source_file}), Lyme={absent.score:.3f} "
        f"(de {absent.source_file}), diferença={diff:.3f}. Esperado >= 0.10."
    )


@_skip
def test_retriever_filters_irrelevant_results():
    """Pergunta sobre tema AUSENTE deve ser filtrada na configuração de produção.

    Usa o `RAG_MIN_SCORE` que a chain de produção aplica (lido do `.env`,
    default 0.5). Sem essa filtragem, a chain injetaria chunks ruins no
    prompt como contexto autoritativo — risco de o LLM ancorar em
    conteúdo irrelevante.

    Regressão: este teste só passa enquanto o retriever respeitar
    `min_score`. Se alguém remover o parâmetro, ele volta a falhar.
    """
    from assistant.config import RAG_MIN_SCORE
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    chunks = retriever.retrieve(
        "Como tratar Doença de Lyme transmitida por carrapato?",
        top_k=3,
        min_score=RAG_MIN_SCORE,
    )

    # Todos os chunks que sobreviveram devem ter score >= threshold.
    # (Se o filtro zerou, lista vazia também passa.)
    assert all(c.score >= RAG_MIN_SCORE for c in chunks), (
        f"Filtragem falhou: algum chunk passou com score < {RAG_MIN_SCORE}.\n"
        + "\n".join(f"  - {c.source_file} score={c.score:.3f}" for c in chunks)
    )


@_skip
def test_retriever_metadata_completeness():
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    chunks = retriever.retrieve("conduta inicial pneumonia", top_k=3)
    assert chunks
    for c in chunks:
        assert "source_file" in c.metadata
        assert "section" in c.metadata
        assert "title" in c.metadata


@_skip
def test_retriever_top_k_parameter():
    from assistant.rag.retriever import ProtocolRetriever

    retriever = ProtocolRetriever()
    assert len(retriever.retrieve("teste", top_k=1)) == 1
    assert len(retriever.retrieve("teste", top_k=5)) == 5
