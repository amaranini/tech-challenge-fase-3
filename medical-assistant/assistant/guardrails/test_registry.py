"""Testes do registry (Fase 6) — orquestração de detect + ação."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from assistant.guardrails.registry import (
    apply_guardrails_to_response,
    list_guardrails,
    run_input_guardrails,
    run_output_guardrails,
)


class TestRunFunctions:
    def test_input_roda_so_o_bypass(self):
        results = run_input_guardrails("texto qualquer")
        assert len(results) == 1
        assert results[0].guardrail_name == "bypass_attempt"

    def test_output_roda_os_4(self):
        results = run_output_guardrails("texto qualquer")
        assert len(results) == 4
        names = [r.guardrail_name for r in results]
        assert "prescricao_direta" in names
        assert "diagnostico_definitivo" in names
        assert "decisao_clinica_final" in names
        assert "fora_escopo_residual" in names
        assert "bypass_attempt" not in names

    def test_list_guardrails(self):
        names = list_guardrails()
        assert len(names) == 5
        assert "bypass_attempt" in names


class TestApplyGuardrailsBlock:
    def _mock_llm(self, content: str) -> MagicMock:
        m = MagicMock()
        resp = MagicMock()
        resp.content = content
        m.invoke.return_value = resp
        return m

    def test_sem_disparo_devolve_texto_original_intacto(self):
        llm = self._mock_llm("never called")
        draft = "Considerar hipótese de pneumonia. Avaliar com Rx de tórax."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        assert out == draft
        assert not was_rewritten
        llm.invoke.assert_not_called()
        assert all(not r.triggered for r in results)

    def test_um_block_reescreve(self):
        llm = self._mock_llm("Versão reescrita sem prescrição direta.")
        draft = "Prescreva amoxicilina 500mg de 8/8h."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        assert was_rewritten
        assert out == "Versão reescrita sem prescrição direta."
        llm.invoke.assert_called_once()
        # O guardrail de prescrição deve estar triggered + action_taken="rewritten"
        prescr = next(r for r in results if r.guardrail_name == "prescricao_direta")
        assert prescr.triggered
        assert prescr.action_taken == "rewritten"

    def test_multiplos_blocks_uma_chamada_apenas(self):
        llm = self._mock_llm("Texto reescrito.")
        draft = "Trata-se de pneumonia. Deve ser internado em UTI."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        assert was_rewritten
        # Apenas 1 chamada ao LLM mesmo com 2 disparos
        assert llm.invoke.call_count == 1
        # Os 2 blocks que dispararam devem ter action_taken="rewritten"
        triggered = [r for r in results if r.triggered]
        assert len(triggered) >= 2
        for r in triggered:
            if r.level == "block":
                assert r.action_taken == "rewritten"

    def test_falha_no_rewrite_preserva_draft(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("modelo morreu")
        draft = "Prescreva amoxicilina 500mg de 8/8h."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        # Texto original preservado, was_rewritten = False
        assert out == draft
        assert not was_rewritten
        prescr = next(r for r in results if r.guardrail_name == "prescricao_direta")
        assert prescr.triggered
        assert prescr.action_taken and "rewrite_failed" in prescr.action_taken


class TestApplyGuardrailsWarning:
    def _mock_llm(self) -> MagicMock:
        return MagicMock()

    def test_warning_anexa_nota_sem_chamar_llm(self):
        llm = self._mock_llm()
        draft = "Aqui está uma receita de bolo de chocolate para o paciente."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        assert not was_rewritten
        assert out != draft
        assert "escopo" in out.lower()
        llm.invoke.assert_not_called()
        scope = next(r for r in results if r.guardrail_name == "fora_escopo_residual")
        assert scope.triggered
        assert scope.action_taken == "note_appended"

    def test_warning_nao_duplica_nota(self):
        from assistant.guardrails.scope import SCOPE_NOTE
        llm = self._mock_llm()
        draft = f"Texto com receita de bolo. {SCOPE_NOTE}"
        out, _, _ = apply_guardrails_to_response(draft, llm)
        assert out.count(SCOPE_NOTE.strip()) == 1


class TestCombinacaoBlockEWarning:
    def _mock_llm(self, content: str) -> MagicMock:
        m = MagicMock()
        resp = MagicMock()
        resp.content = content
        m.invoke.return_value = resp
        return m

    def test_block_e_warning_juntos(self):
        from assistant.guardrails.scope import SCOPE_NOTE
        llm = self._mock_llm("Versão reescrita sem prescrição.")
        # prescrição (block) + receita culinária (warning) juntos
        draft = "Prescreva amoxicilina 500mg. Aqui está uma receita de bolo."
        out, results, was_rewritten = apply_guardrails_to_response(draft, llm)
        # Block executou: was_rewritten=True
        assert was_rewritten
        # E a nota de warning foi anexada DEPOIS do rewrite (sobre o texto reescrito)
        assert out.startswith("Versão reescrita sem prescrição.")
        assert SCOPE_NOTE.strip() in out
        # Ambos os results triggered têm action_taken
        prescr = next(r for r in results if r.guardrail_name == "prescricao_direta")
        scope = next(r for r in results if r.guardrail_name == "fora_escopo_residual")
        assert prescr.action_taken == "rewritten"
        assert scope.action_taken == "note_appended"
