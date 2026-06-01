"""Testes unitários do GUARDRAIL_PRESCRICAO_DIRETA."""

from __future__ import annotations

import pytest

from assistant.guardrails.prescription import PrescriptionGuardrail


@pytest.fixture
def g():
    return PrescriptionGuardrail()


class TestPositivos:
    """Inputs que DEVEM disparar o guardrail."""

    @pytest.mark.parametrize("text", [
        "Prescreva amoxicilina 500mg de 8/8h",
        "Recomendo 1g de paracetamol a cada 6 horas",
        "Administre dipirona 1 grama IM",
        "Tome dois comprimidos de 500mg ao dia",
        "Prescrevo dexametasona 4mg",
    ])
    def test_pattern_verb_dose(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"
        assert r.severity > 0.5
        assert r.level == "block"

    @pytest.mark.parametrize("text", [
        "Amoxicilina 500mg a cada 8 horas é a posologia padrão",
        "Paracetamol 750mg a cada 6 horas",
        "Insulina 10UI a cada 12 horas",
    ])
    def test_pattern_drug_dose_posology(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"

    @pytest.mark.parametrize("text", [
        "Quinhentos miligramas de amoxicilina para essa pneumonia",
        "Um grama de paracetamol via oral",
        "Cem miligramas de dipirona",
        "Dois gramas de cefalexina a cada 12 horas",
        "Mil miligramas de paracetamol",
    ])
    def test_pattern_dose_extenso(self, g, text):
        r = g.detect(text)
        assert r.triggered, f"DEVERIA disparar: {text!r}"

    def test_multiplos_padroes_em_um_texto(self, g):
        text = ("Prescreva amoxicilina 500mg de 8/8h. "
                "Tome também quinhentos miligramas de dipirona.")
        r = g.detect(text)
        assert r.triggered
        # Pelo menos 2 patterns diferentes
        assert len(r.matched_patterns) >= 2


class TestNegativos:
    """Inputs que NÃO devem disparar."""

    @pytest.mark.parametrize("text", [
        "A dose de referência da amoxicilina é 500mg, mas a prescrição é decisão do médico",
        "O protocolo institucional sugere amoxicilina em dose padrão; consulte o médico assistente",
        "Paciente tem alergia a penicilinas registrada no prontuário",
        "Considerar antibioticoterapia empírica conforme protocolo de pneumonia comunitária",
        "Avaliar resposta clínica em 48-72h e ajustar conduta",
        "O paciente está estável e bem-orientado",
        "Discutir necessidade de antibiótico com o médico assistente",
        "Em pneumonia comunitária leve, a literatura recomenda amoxicilina como primeira linha",
        # Casos borderline que NÃO devem disparar
        "Caso seja necessário, considerar dose de manutenção",
        "Paciente em uso de medicação contínua sem interrupção",
    ])
    def test_nao_dispara(self, g, text):
        r = g.detect(text)
        assert not r.triggered, f"NÃO deveria disparar: {text!r}"
        assert r.severity == 0.0


class TestRewritePrompt:
    def test_inclui_padroes_no_prompt(self, g):
        text = "Prescreva amoxicilina 500mg"
        r = g.detect(text)
        prompt = g.rewrite_prompt(text, r)
        assert "prescrição" in prompt.lower() or "prescricao" in prompt.lower()
        assert "TEXTO ORIGINAL" in prompt
        assert text in prompt

    def test_prompt_menciona_padrao_detectado(self, g):
        text = "Prescreva amoxicilina 500mg"
        r = g.detect(text)
        prompt = g.rewrite_prompt(text, r)
        # Algum dos patterns matched deve aparecer no prompt
        assert any(p[:15] in prompt for p in r.matched_patterns) or "verb_dose" in prompt


class TestResultStructure:
    def test_result_quando_dispara_tem_message(self, g):
        r = g.detect("Prescreva amoxicilina 500mg")
        assert r.message
        assert r.guardrail_name == "prescricao_direta"
        assert r.applies_to == "output"
        assert r.level == "block"

    def test_result_quando_nao_dispara(self, g):
        r = g.detect("Texto normal sem prescrição")
        assert not r.triggered
        assert r.matched_patterns == []
        assert r.message == ""

    def test_to_dict_serializa(self, g):
        r = g.detect("Prescreva amoxicilina 500mg")
        d = r.to_dict()
        assert d["guardrail_name"] == "prescricao_direta"
        assert d["triggered"] is True
        assert isinstance(d["matched_patterns"], list)
