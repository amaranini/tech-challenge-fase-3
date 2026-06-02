"""Testes unitários do GUARDRAIL_DECISAO_CLINICA_FINAL."""

from __future__ import annotations

import pytest

from assistant.guardrails.clinical_decision import ClinicalDecisionGuardrail


@pytest.fixture
def g():
    return ClinicalDecisionGuardrail()


class TestAlta:
    @pytest.mark.parametrize("text", [
        "O paciente pode receber alta hospitalar",
        "Pode receber alta amanhã se estável",
        "Está apto para alta",
        "Paciente é liberado para alta",
    ])
    def test_dispara_alta(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"


class TestInternacao:
    @pytest.mark.parametrize("text", [
        "Deve ser internado em UTI",
        "Indicar internação imediata",
        "Encaminhar para hospitalização",
        "Não precisa internar, basta observação domiciliar",
        "Não precisa de UTI",
    ])
    def test_dispara_internacao(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"


class TestManutencaoStatus:
    @pytest.mark.parametrize("text", [
        # Novos padrões Fase 6.1
        "O paciente deve permanecer em observação",
        "Deve permanecer internado por mais 24h",
        "Manter em jejum até amanhã",
        "Deve continuar hospitalizado",
        "Manter em isolamento de contato",
        "Contraindicada a alta hospitalar",
        "Contraindicada alta nesse momento",
    ])
    def test_dispara_manutencao(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"

    @pytest.mark.parametrize("text", [
        # Com qualificador "considerar/avaliar" não dispara
        "Considerar manter em observação se sinais persistirem",
        "Avaliar manter em jejum a depender da evolução",
        # Contexto temporal passado
        "Em internações prévias o paciente permaneceu em observação",
    ])
    def test_nao_dispara_com_qualificador(self, g, text):
        r = g.detect(text)
        assert not r.triggered, f"NÃO deveria disparar: {text!r}"


class TestCirurgia:
    @pytest.mark.parametrize("text", [
        "Indicar cirurgia de apendicectomia urgente",
        "Encaminhar para cirurgia",
        "Encaminhar pra cirurgia laparoscópica",
    ])
    def test_dispara_cirurgia(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"


class TestSuspensaoMedicacao:
    @pytest.mark.parametrize("text", [
        "Suspender a metformina hoje",
        "Suspender warfarina imediatamente",
        "Interromper aspirina agora",
        "Descontinuar omeprazol agora",
    ])
    def test_dispara_suspensao(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"


class TestNegativos:
    @pytest.mark.parametrize("text", [
        # Sugestões / linguagem indireta
        "Avaliar critérios de alta e considerar liberação se estáveis",
        "Considerar internação se houver piora hemodinâmica",
        "Discutir indicação cirúrgica com o cirurgião plantonista",
        "Reavaliar metformina à luz da função renal — médico assistente pode considerar suspensão",
        # Referências contextuais
        "Hipóteses diagnósticas que podem internar incluem sepse e pneumonia grave",
        "Em internações prévias o paciente apresentou broncoespasmo",
        "Avaliar resposta clínica antes de qualquer decisão de alta",
        "Sinais de gravidade que indicariam internação: hipotensão, taquipneia",
        # Casos onde "suspender" aparece mas com qualificador "considerar"
        "Considerar suspensão da insulina se hipoglicemia",
        # Drogas raras NÃO listadas — falso negativo aceitável
        "Discutir suspensão de medicamento específico com a equipe",
    ])
    def test_nao_dispara(self, g, text):
        r = g.detect(text)
        assert not r.triggered, f"NÃO deveria disparar: {text!r}"


class TestSeveridade:
    def test_severidade_alta_quando_dispara(self, g):
        r = g.detect("Deve ser internado em UTI")
        assert r.severity > 0.5
