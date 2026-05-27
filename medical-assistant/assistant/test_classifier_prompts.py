"""Teste empírico dos classificadores dos Nós 1 e 2 (Fase 5).

Rodar com:
    uv run python assistant/test_classifier_prompts.py

Não é um pytest — é um script de validação manual:
- Nó 1 (classify_intent): determinístico via keyword matching. Não precisa
  do LLM. Roda em milissegundos.
- Nó 2 (triage_urgency): LLM-based. Carrega o MedicalLLM.

Critério informal de aprovação: ≥ 4/5 em cada nó.
"""

from __future__ import annotations

import sys
import time

from assistant.config import ADAPTER_PATH, MODEL_PATH
from assistant.graph_nodes import classify_intent, make_triage_urgency_node
from assistant.graph_state import initial_state
from assistant.llm import MedicalLLM


def _make_classifier_llm() -> MedicalLLM:
    """Cria uma instância 'classificadora': temperatura 0.0, sem system clínico, max_tokens curto."""
    return MedicalLLM(
        model_path=MODEL_PATH,
        adapter_path=ADAPTER_PATH,
        system_prompt=None,    # Os nós passam o system explicitamente
        temperature=0.0,
        max_tokens=16,
        top_p=1.0,
    )


# ────────────────────────────────────────────────────────────────────────
# Casos de teste
# ────────────────────────────────────────────────────────────────────────

INTENT_CASES: list[tuple[str, str]] = [
    ("Qual o protocolo institucional para crise asmática em adulto?", "clinica"),
    ("Que horas começa o plantão da emergência amanhã?", "administrativa"),
    ("Você consegue me ajudar a planejar uma viagem pra Buenos Aires?", "fora_de_escopo"),
    ("Paciente P0001 está com taquicardia e dor torácica, o que considerar?", "clinica"),
    ("Quem é o responsável pelo fechamento do livro do plantão noturno?", "administrativa"),
]

TRIAGE_CASES: list[tuple[str, str]] = [
    ("Paciente em parada cardiorrespiratória, qual a sequência de RCP?", "alta"),
    ("Paciente com tosse seca há 2 semanas, sem febre, hígido", "baixa"),
    ("Recém-nascido com hipotonia e cianose central agora", "alta"),
    ("Paciente diabético com glicemia 280, sem cetose, sintomático leve", "media"),
    ("Qual a dose de paracetamol pra criança de 15kg pra dor leve?", "baixa"),
]


# ────────────────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────────────────

def _run_node(node_fn, question: str, expected: str, raw_field: str) -> dict:
    """Roda 1 nó com a pergunta e devolve resumo."""
    state = initial_state(question=question, patient_id=None)
    t0 = time.monotonic()
    out = node_fn(state)
    dt = time.monotonic() - t0

    trace_entry = out["node_trace"][0]
    parsed = out[raw_field]
    ok = (parsed == expected)
    return {
        "question": question,
        "expected": expected,
        "parsed": parsed,
        "ok": ok,
        "trace_summary": trace_entry["summary"],
        "latency_s": round(dt, 4),
        "error": trace_entry.get("error"),
    }


def _print_case(i: int, r: dict) -> None:
    status = "✅" if r["ok"] else "❌"
    print(f"  [{i}] {status}  esperado={r['expected']:<18s} → parsed={r['parsed']:<18s} ({r['latency_s']}s)")
    print(f"      pergunta: {r['question']}")
    print(f"      trace:    {r['trace_summary']}")
    if r["error"]:
        print(f"      erro:     {r['error']}")
    print()


def main() -> int:
    print("=" * 72)
    print("  Teste empírico dos classificadores dos Nós 1 e 2 (Fase 5)")
    print("=" * 72)
    print()

    # ─── Nó 1 — sem LLM ──────────────────────────────────────────────────
    print("-" * 72)
    print("Nó 1 — classify_intent (determinístico, sem LLM)")
    print("-" * 72)
    intent_results = []
    for i, (q, expected) in enumerate(INTENT_CASES, start=1):
        r = _run_node(classify_intent, q, expected, raw_field="intent")
        intent_results.append(r)
        _print_case(i, r)

    intent_acc = sum(1 for r in intent_results if r["ok"])
    print(f"  → acertos: {intent_acc}/{len(intent_results)}")
    print()

    # ─── Nó 2 — LLM ──────────────────────────────────────────────────────
    print("Carregando MedicalLLM pro Nó 2 (uma instância clean)...")
    t0 = time.monotonic()
    llm = _make_classifier_llm()
    llm._ensure_loaded()
    print(f"  ✓ modelo pronto em {time.monotonic() - t0:.1f}s")
    print()
    triage = make_triage_urgency_node(llm)

    print("-" * 72)
    print("Nó 2 — triage_urgency (LLM, classifier_llm)")
    print("-" * 72)
    triage_results = []
    for i, (q, expected) in enumerate(TRIAGE_CASES, start=1):
        r = _run_node(triage, q, expected, raw_field="urgency")
        triage_results.append(r)
        _print_case(i, r)

    triage_acc = sum(1 for r in triage_results if r["ok"])
    print(f"  → acertos: {triage_acc}/{len(triage_results)}")
    print()

    # ─── Resumo ──────────────────────────────────────────────────────────
    print("=" * 72)
    print("  Resumo")
    print("=" * 72)
    print(f"  Nó 1 (classify_intent, determinístico): {intent_acc}/{len(intent_results)}")
    print(f"  Nó 2 (triage_urgency, LLM):             {triage_acc}/{len(triage_results)}")
    print()

    threshold = 4
    if intent_acc >= threshold and triage_acc >= threshold:
        print("  ✅ Ambos os nós atingiram o threshold informal de aprovação.")
        return 0
    print("  ⚠ Pelo menos um nó ficou abaixo de 4/5. Revisar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
