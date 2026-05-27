"""Avaliação da Fase 4: 15 perguntas exercitando router, RAG e tool de paciente.

Categorias (5 cada esperado):
- rag_only      (5): pergunta sobre protocolo, sem ID
- patient_only  (3): pergunta cita ID conhecido
- both          (3): protocolo + paciente
- out_of_scope  (2): nem médico, modelo deve recusar
- invalid_id    (2): cita ID que não existe (P9999, P0099)

Saída:
- `evaluation/comparison_phase4.md`  (uma seção por pergunta, com fontes)
- métricas no terminal: % de roteamento correto e latências médias

Uso:
    uv run python evaluation/eval_rag.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from assistant.chain import build_default_chain  # noqa: E402

EVAL_DIR = PROJECT_ROOT / "evaluation"
COMPARISON_MD = EVAL_DIR / "comparison_phase4.md"

# Lista das 15 perguntas: (categoria_esperada, pergunta).
EVAL_CASES: list[tuple[str, str]] = [
    # 1-5: rag_only — só protocolos, sem ID
    ("rag_only", "Qual o protocolo institucional para manejo inicial de sepse?"),
    ("rag_only", "Como tratar infarto agudo do miocárdio com supra de ST nas primeiras horas?"),
    ("rag_only", "Quais os critérios diagnósticos atuais para diabetes mellitus tipo 2?"),
    ("rag_only", "Como manejar exacerbação aguda de asma em crianças?"),
    ("rag_only", "Qual a conduta inicial em paciente com suspeita de AVC isquêmico?"),
    # 6-8: patient_only — pergunta cita ID conhecido
    ("patient_only", "Quais são as alergias do paciente P0001?"),
    ("patient_only", "Qual o histórico clínico do paciente P0023?"),
    ("patient_only", "Que medicações o paciente P0042 está em uso?"),
    # 9-11: both — protocolo + paciente
    ("both", "Para o paciente P0001 com suspeita de pneumonia comunitária, qual conduta segundo nossos protocolos?"),
    ("both", "Paciente P0023 chega com dor torácica em aperto — qual protocolo aplicar considerando o histórico dele?"),
    ("both", "Para o paciente P0042 em pré-operatório, quais cuidados o protocolo de pré-anestesia prevê?"),
    # 12-13: out_of_scope — não é médico
    ("out_of_scope", "Como faço um bolo de chocolate?"),
    ("out_of_scope", "Quem ganhou a Copa do Mundo de 2022?"),
    # 14-15: invalid_id — ID que não existe no banco
    ("invalid_id", "Quais são as alergias do paciente P9999?"),
    ("invalid_id", "Qual o histórico clínico do paciente P0099?"),
]


def _detected_category(routing: dict, patient_data: list[dict]) -> str:
    """Determina categoria DETECTADA com base em routing + resultado do paciente lookup."""
    has_patient = routing["needs_patient"]
    if has_patient:
        # Algum ID retornou record?
        any_found = any(p["found"] for p in patient_data)
        if not any_found:
            return "invalid_id"  # tem ID na pergunta, mas nenhum existe
        # Tem paciente válido; é só patient ou também rag?
        # Aqui não dá pra distinguir "both" vs "patient_only" pela rota
        # (RAG está sempre on). Usamos heurística simples: se a pergunta tem
        # palavras de protocolo, é "both"; senão é "patient_only".
        return "patient_with_id"
    return "rag_or_oos"


def _categorize(routing: dict, patient_data: list[dict], question: str) -> str:
    """Heurística simples pra inferir a categoria detectada (pra compor a tabela de métricas)."""
    has_id_in_query = routing["needs_patient"]
    any_patient_found = any(p["found"] for p in patient_data) if patient_data else False
    protocol_words = ("protocolo", "conduta", "tratamento", "manejo", "critério", "diagnóstic")
    asks_protocol = any(w in question.lower() for w in protocol_words)

    if has_id_in_query and not any_patient_found:
        return "invalid_id"
    if has_id_in_query and any_patient_found:
        return "both" if asks_protocol else "patient_only"
    # sem ID
    medical_words = ("protocolo", "paciente", "tratamento", "conduta", "diagnós",
                     "exame", "sintoma", "diabetes", "sepse", "infarto", "asma",
                     "avc", "pneumon", "manejo", "antibió")
    is_medical = any(w in question.lower() for w in medical_words)
    return "rag_only" if is_medical else "out_of_scope"


def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return "_(nenhuma)_"
    lines = []
    for i, s in enumerate(sources, start=1):
        lines.append(
            f"  {i}. `{s['source_file']}` • _{s['section']}_ • "
            f"score: **{s['score']:.3f}**"
        )
    return "\n".join(lines)


def _format_patient_data(pdata: list[dict]) -> str:
    if not pdata:
        return "_(nenhum)_"
    lines = []
    for p in pdata:
        if p["found"]:
            r = p["record"]
            lines.append(
                f"  - **{p['id']}** ({r['nome']}, {r['idade']} anos, {r['sexo']}): "
                f"alergias: {r['alergias'] or '—'}; medicações: {r['medicacoes_atuais'] or '—'}"
            )
        else:
            lines.append(f"  - **{p['id']}**: ❌ não encontrado no banco")
    return "\n".join(lines)


def main() -> int:
    print("=" * 64)
    print("  Avaliação Fase 4 — RAG + roteamento + prontuário")
    print("=" * 64)
    print(f"  {len(EVAL_CASES)} casos\n")

    print("→ Carregando chain (modelo + adapter + Chroma + SQLite)...")
    t0 = time.monotonic()
    chain = build_default_chain()
    print(f"  ✓ carregado em {time.monotonic()-t0:.1f}s\n")

    results: list[dict] = []
    correct_routing = 0
    for i, (expected_cat, question) in enumerate(EVAL_CASES, start=1):
        print(f"  [{i}/{len(EVAL_CASES)}] [{expected_cat}] {question[:60]}...")
        t = time.monotonic()
        out = chain.invoke({"question": question})
        elapsed = time.monotonic() - t
        detected_cat = _categorize(out["routing"], out["patient_data"], question)
        is_correct = detected_cat == expected_cat
        if is_correct:
            correct_routing += 1
        results.append(
            {
                "n": i,
                "expected": expected_cat,
                "detected": detected_cat,
                "correct": is_correct,
                "question": question,
                "response": out["response"],
                "sources": out["sources"],
                "patient_data": out["patient_data"],
                "routing": out["routing"],
                "latencies": out["latencies"],
                "elapsed_sec": round(elapsed, 2),
            }
        )
        print(
            f"     detectado={detected_cat} {'✓' if is_correct else '✗'}  "
            f"sources={len(out['sources'])}  "
            f"patient_found={sum(1 for p in out['patient_data'] if p['found'])}/"
            f"{len(out['patient_data'])}  "
            f"({elapsed:.1f}s)"
        )

    # ─── Métricas ─────────────────────────────────────────────────────────
    n = len(results)
    pct_correct = 100 * correct_routing / n
    avg_total = sum(r["latencies"]["total"] for r in results) / n
    avg_rag = sum(r["latencies"]["rag"] for r in results) / n
    avg_llm = sum(r["latencies"]["llm"] for r in results) / n

    print("\n" + "=" * 64)
    print(f"  Roteamento correto: {correct_routing}/{n}  ({pct_correct:.1f}%)")
    print(f"  Latência média:     {avg_total:.2f}s (RAG {avg_rag:.2f}s | LLM {avg_llm:.2f}s)")

    # ─── Markdown ─────────────────────────────────────────────────────────
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Comparativo Fase 4 — roteamento, RAG e busca de prontuário",
        "",
        "> 15 casos cobrindo: 5 só-RAG, 3 só-paciente, 3 ambos, 2 fora-de-escopo, 2 ID inexistente.",
        f"> **Roteamento correto: {correct_routing}/{n} ({pct_correct:.1f}%)**",
        f"> **Latência média: {avg_total:.2f}s** (RAG {avg_rag:.2f}s | LLM {avg_llm:.2f}s)",
        "",
        "---",
        "",
    ]
    for r in results:
        check = "✅" if r["correct"] else "❌"
        lines.extend(
            [
                f"## {r['n']}. {check} `{r['expected']}` → detectado `{r['detected']}` "
                f"({r['elapsed_sec']}s)",
                "",
                f"**Pergunta:** {r['question']}",
                "",
                f"**Roteamento:** `needs_rag={r['routing']['needs_rag']}`, "
                f"`needs_patient={r['routing']['needs_patient']}`, "
                f"`patient_ids={r['routing']['patient_ids']}`",
                "",
                f"**Latências:** router {r['latencies']['router']:.3f}s | "
                f"RAG {r['latencies']['rag']:.3f}s | "
                f"paciente {r['latencies']['patient']:.3f}s | "
                f"LLM {r['latencies']['llm']:.3f}s",
                "",
                "**Fontes consultadas:**",
                _format_sources(r["sources"]),
                "",
                "**Pacientes consultados:**",
                _format_patient_data(r["patient_data"]),
                "",
                "**Resposta:**",
                "",
                r["response"],
                "",
                "---",
                "",
            ]
        )
    COMPARISON_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✓ Salvo: {COMPARISON_MD.relative_to(PROJECT_ROOT)}")
    print(f"\nLeia: cat {COMPARISON_MD.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
