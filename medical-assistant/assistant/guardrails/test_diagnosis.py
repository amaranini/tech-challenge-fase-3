"""Testes unitários do GUARDRAIL_DIAGNOSTICO_DEFINITIVO."""

from __future__ import annotations

import pytest

from assistant.guardrails.diagnosis import DiagnosisGuardrail


@pytest.fixture
def g():
    return DiagnosisGuardrail()


class TestPositivos:
    @pytest.mark.parametrize("text", [
        "Trata-se de um quadro de pneumonia bacteriana",
        "O diagnóstico definitivo é leucemia mielóide aguda",
        "Com certeza é um quadro de apendicite",
        "Definitivamente é uma crise asmática",
        "É um caso clássico de TEP",
        "Sem dúvida é uma sepse de origem urinária",
        "Trata-se de uma exacerbação de DPOC",
        "O diagnóstico fechado de IAM com supra de ST",
        "É um caso definitivo de pneumonia atípica",
    ])
    def test_dispara_em_marcadores_de_certeza(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"
        assert r.level == "block"


class TestNegativos:
    @pytest.mark.parametrize("text", [
        # Probabilístico
        "Provavelmente é pneumonia bacteriana, mas Rx confirmaria",
        "Considerar hipótese de TEP, principalmente se D-dímero alterado",
        "Diagnósticos diferenciais incluem pneumonia, asma e bronquite",
        "O paciente apresenta sintomas compatíveis com diabetes — solicitar HbA1c",
        "Histórico do paciente menciona diabetes tipo 2",
        "Avaliar possibilidade de TEP via TC de tórax",
        "Hipóteses diagnósticas: pneumonia, asma, TEP",
        # Referências ao prontuário
        "Paciente é portador de hipertensão controlada",
        "Comorbidades prévias: DM2 e HAS",
        # Casos onde "tem" aparece sem ser categórico
        "O paciente tem queixa de dispneia há 3 dias",
        "Tem indicação de avaliação cardiológica",
    ])
    def test_nao_dispara(self, g, text):
        r = g.detect(text)
        assert not r.triggered, f"NÃO deveria disparar: {text!r}"


class TestRewritePrompt:
    def test_prompt_pede_tom_probabilistico(self, g):
        text = "Trata-se de pneumonia"
        r = g.detect(text)
        prompt = g.rewrite_prompt(text, r)
        assert "probabil" in prompt.lower() or "hipótese" in prompt.lower()
        assert "TEXTO ORIGINAL" in prompt
