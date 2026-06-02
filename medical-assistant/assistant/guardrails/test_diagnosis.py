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

    @pytest.mark.parametrize("text", [
        # Novo padrão Fase 6.1: "paciente tem [doença grave]"
        "O paciente tem câncer de pulmão não pequenas células",
        "Paciente apresenta tumor cerebral",
        "Tem sepse de origem urinária",
        "O paciente tem AVC isquêmico",
        "Apresenta IAM com supra de ST",
        "O paciente tem insuficiência renal crônica",
    ])
    def test_dispara_em_doencas_graves(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"

    @pytest.mark.parametrize("text", [
        # "diagnóstico [adj]* confirmado de [X]"
        "Paciente com diagnóstico histopatológico confirmado de câncer",
        "Diagnóstico confirmado de TEP",
        "Paciente com diagnóstico laboratorial confirmado de HIV",
        # "paciente com [doença grave]" sem qualificador
        "Paciente com câncer de pulmão estágio IIIB",
        "Caso com sepse de origem desconhecida",
        "Paciente com IAM em evolução",
    ])
    def test_dispara_em_diagnostico_confirmado(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"


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
        # Casos onde "tem" aparece sem ser categórico (palavras NÃO graves)
        "O paciente tem queixa de dispneia há 3 dias",
        "Tem indicação de avaliação cardiológica",
        "O paciente tem alergia a penicilinas",
        "Histórico patológico inclui diabetes",
        "Tem dor abdominal há 24 horas",
        # Qualificadores que devem anular "paciente com [doença grave]"
        "Paciente com suspeita de câncer de pulmão",
        "Caso com hipótese de TEP",
        "Paciente com histórico de IAM prévio",
        "Paciente com antecedente de AVC",
        "Paciente com risco de sepse — monitorar",
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
