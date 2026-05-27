"""Testes do roteador determinístico (rápidos, sem modelo)."""

from __future__ import annotations

from assistant.router import RoutingDecision, route


def test_route_simple_question_triggers_rag_only():
    r = route("Qual o protocolo para sepse?")
    assert r.needs_rag is True
    assert r.needs_patient is False
    assert r.patient_ids == []


def test_route_with_single_patient_id():
    r = route("Quais as alergias do paciente P0042?")
    assert r.needs_patient is True
    assert r.patient_ids == ["P0042"]


def test_route_with_multiple_patient_ids():
    r = route("Compare os históricos do P0001 e P0050.")
    assert r.patient_ids == ["P0001", "P0050"]


def test_route_deduplicates_repeated_ids():
    r = route("Para P0010, considerando que P0010 é diabético, qual conduta?")
    assert r.patient_ids == ["P0010"]


def test_route_ignores_non_matching_p_pattern():
    """Regex exige EXATAMENTE 4 dígitos após o P."""
    r = route("Falamos sobre P, ou P12, ou P123, ou P123456.")
    assert r.patient_ids == []


def test_route_lowercase_p_is_not_matched():
    """IDs no formato P0001 são maiúsculos; minúsculo p0001 não é ID."""
    r = route("paciente p0001 está bem")
    assert r.patient_ids == []


def test_route_always_needs_rag_even_for_off_topic():
    """RAG sempre ativo. Quem decide relevância é o retriever/LLM."""
    r = route("Como faço um bolo de chocolate?")
    assert r.needs_rag is True


def test_routing_decision_to_dict():
    r = route("Para o P0007, qual conduta?")
    d = r.to_dict()
    assert d == {"needs_rag": True, "needs_patient": True, "patient_ids": ["P0007"]}
