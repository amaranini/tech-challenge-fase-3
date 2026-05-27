"""Testes de integração da chain end-to-end com mocks (rápidos)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from assistant.chain import build_medical_chain
from assistant.rag.retriever import RetrievedChunk
from assistant.tools.patient_records import PatientRecord


def _fake_chunk(text: str, source: str, section: str, score: float = 0.7) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        metadata={
            "source_file": source,
            "title": "T",
            "specialty": "geral",
            "section": section,
            "chunk_index": 0,
        },
        score=score,
    )


def _fake_patient(pid: str = "P0001") -> PatientRecord:
    return PatientRecord(
        id=pid,
        nome="Paciente Teste",
        idade=55,
        sexo="M",
        alergias="penicilina",
        medicacoes_atuais="losartana",
        historico_resumido="HAS controlada.",
    )


def _build_mocks(retriever_chunks=None, patient_record=None, llm_text="resposta"):
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=llm_text)

    retriever = MagicMock()
    retriever.retrieve.return_value = retriever_chunks or []

    patient_lookup = MagicMock()
    patient_lookup.return_value = patient_record

    return llm, retriever, patient_lookup


def test_chain_rag_only_path():
    """Pergunta sem ID: aciona RAG, NÃO consulta paciente."""
    llm, retriever, patient_lookup = _build_mocks(
        retriever_chunks=[_fake_chunk("trecho sobre sepse", "p1.md", "Conduta")],
        llm_text="Resposta sobre sepse.",
    )
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "Qual o protocolo de sepse?"})

    assert result["response"] == "Resposta sobre sepse."
    assert len(result["sources"]) == 1
    assert result["sources"][0]["source_file"] == "p1.md"
    assert result["routing"]["needs_patient"] is False
    assert result["patient_data"] == []
    retriever.retrieve.assert_called_once()
    patient_lookup.assert_not_called()


def test_chain_patient_only_path():
    """Pergunta com ID: consulta paciente, mas RAG também roda (sempre ativo)."""
    rec = _fake_patient("P0001")
    llm, retriever, patient_lookup = _build_mocks(
        retriever_chunks=[],  # RAG roda mas (no teste) retorna nada
        patient_record=rec,
        llm_text="Alergias: penicilina.",
    )
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "Quais alergias do P0001?"})

    assert result["routing"]["needs_patient"] is True
    assert result["routing"]["patient_ids"] == ["P0001"]
    assert len(result["patient_data"]) == 1
    assert result["patient_data"][0]["found"] is True
    assert result["patient_data"][0]["record"]["alergias"] == "penicilina"
    patient_lookup.assert_called_once_with("P0001")


def test_chain_combines_rag_and_patient():
    rec = _fake_patient("P0007")
    chunks = [_fake_chunk("tratamento de pneumonia comunitária", "pneu.md", "Conduta")]
    llm, retriever, patient_lookup = _build_mocks(
        retriever_chunks=chunks, patient_record=rec, llm_text="Conduta x."
    )
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "Para o P0007 com pneumonia, conduta?"})

    assert result["routing"]["needs_rag"] is True
    assert result["routing"]["needs_patient"] is True
    assert len(result["sources"]) == 1
    assert len(result["patient_data"]) == 1


def test_chain_handles_unknown_patient_gracefully():
    """ID inexistente: lookup retorna None; chain marca found=False."""
    llm, retriever, patient_lookup = _build_mocks(
        retriever_chunks=[], patient_record=None, llm_text="Paciente não encontrado."
    )
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "Quais alergias do P9999?"})

    assert len(result["patient_data"]) == 1
    assert result["patient_data"][0]["found"] is False
    assert result["patient_data"][0]["record"] is None


def test_chain_use_rag_false_skips_retrieval():
    """Flag use_rag=False desliga o RAG mesmo com router pedindo."""
    llm, retriever, patient_lookup = _build_mocks(
        retriever_chunks=[_fake_chunk("trecho", "x.md", "x")],
    )
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "Qual o protocolo de sepse?", "use_rag": False})

    assert result["sources"] == []
    retriever.retrieve.assert_not_called()


def test_chain_returns_latencies():
    llm, retriever, patient_lookup = _build_mocks()
    chain = build_medical_chain(llm=llm, retriever=retriever, patient_lookup=patient_lookup)
    result = chain.invoke({"question": "teste"})
    lat = result["latencies"]
    assert "router" in lat and "llm" in lat and "total" in lat
    assert lat["total"] >= 0
