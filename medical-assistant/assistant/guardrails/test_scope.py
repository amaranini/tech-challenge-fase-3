"""Testes unitários do GUARDRAIL_FORA_ESCOPO_RESIDUAL (warning)."""

from __future__ import annotations

import pytest

from assistant.guardrails.scope import SCOPE_NOTE, ScopeResidualGuardrail


@pytest.fixture
def g():
    return ScopeResidualGuardrail()


class TestPositivos:
    @pytest.mark.parametrize("text", [
        "Aqui está uma receita de bolo saudável para acompanhar a dieta",
        "Receita de pizza pra esses dias",
        "Vou citar a letra da música que ele estava ouvindo",
        "O time dele perdeu o jogo do campeonato brasileiro",
        "Esse filme da Netflix sobre médicos é bom",
        "Em uma novela sobre a vida hospitalar",
        "Receita para sopa de legumes",
    ])
    def test_dispara_fora_escopo(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"
        assert r.level == "warning"

    def test_codigo_python_dispara(self, g):
        text = "Em Python: import os para listar"
        r = g.detect(text)
        assert r.triggered

    def test_def_python_dispara(self, g):
        text = "Use def calcular() para isso"
        r = g.detect(text)
        assert r.triggered

    def test_code_fence_python_dispara(self, g):
        text = "```python\ndef f():\n    pass\n```"
        r = g.detect(text)
        assert r.triggered

    def test_ingredientes_lista_dispara(self, g):
        text = "Ingredientes:\n- 2 ovos\n- 1 xícara de farinha"
        r = g.detect(text)
        assert r.triggered


class TestNegativos:
    @pytest.mark.parametrize("text", [
        # "receita" em contexto clínico
        "Receita simples: amoxicilina é prescrita em dose padrão",
        "Receita médica deve ser feita pelo médico",
        "Receita para emergência hipertensiva: nitroprussiato em bomba",
        # "importante" começa com "import" mas sem keyword Python
        "É importante avaliar o paciente",
        "Importante: solicitar exames de imagem",
        # "ingredientes" sem ser lista culinária
        "Os ingredientes ativos do medicamento são paracetamol e cafeína",
        # Pacientes mencionando esporte/filme não disparam (contexto correto)
        "O paciente foi liberado para retomar atividades físicas",
        "Avaliar resposta clínica em 48-72h",
        "Discutir condutas com a equipe assistente",
    ])
    def test_nao_dispara(self, g, text):
        r = g.detect(text)
        assert not r.triggered, f"NÃO deveria disparar: {text!r}"


class TestNoteFormat:
    def test_scope_note_constante_curta_e_legivel(self):
        assert "escopo" in SCOPE_NOTE.lower()
        assert len(SCOPE_NOTE) < 300

    def test_warning_severity_baixa(self, g):
        r = g.detect("Receita de bolo")
        assert r.triggered
        assert r.severity < 0.6  # warning não deve ter severidade alta
