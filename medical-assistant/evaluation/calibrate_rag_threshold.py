"""Calibração empírica do RAG_MIN_SCORE.

Roda 25 queries (10 PRESENT + 10 ABSENT + 5 BORDERLINE) contra o retriever
SEM filtro (min_score=None), coleta scores top-1/2/3 e source do top-1,
calcula estatísticas por grupo e mostra como o threshold atual (0.5) se
comporta empiricamente. Recomenda ajustes se houver evidência clara.

PRESENT: temas confirmados no dataset (inspeção direta dos .md).
ABSENT: temas confirmados FORA do dataset (grep -r retornou 0 matches).
BORDERLINE: temas vagamente relacionados, pra ver onde caem na fronteira.

Uso:
    uv run python evaluation/calibrate_rag_threshold.py
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from assistant.config import RAG_MIN_SCORE  # noqa: E402
from assistant.rag.retriever import ProtocolRetriever  # noqa: E402


# ─── Queries de calibração ──────────────────────────────────────────────────

# PRESENT (10) — cada query mapeia 1:1 com um tema confirmado no dataset.
# Cobre 10 das 15 especialidades pra evitar viés.
PRESENT_QUERIES: list[str] = [
    "Como manejar arritmias cardíacas em adulto?",                  # 000
    "Qual o tratamento da asma em adultos?",                        # 001/016/031
    "Como tratar pneumonia adquirida na comunidade?",               # 002/017
    "Conduta em AVC isquêmico agudo?",                              # 004/020
    "Como avaliar cefaleia crônica?",                               # 005
    "Tratamento de hipotireoidismo subclínico",                     # 006
    "Manejo da dermatite atópica em adulto",                        # 009
    "Como tratar hiperplasia prostática benigna?",                  # 010/025
    "Conduta na insuficiência cardíaca congestiva descompensada",   # 015
    "Manejo de hemorragia pós-parto",                               # 029
]

# ABSENT (10) — confirmados FORA do dataset via `grep -r` (0 matches).
# Originalmente "fibrose cística" e "doença de Crohn" estavam aqui, mas
# o grep mostrou que aparecem no dataset (provavelmente como diagnóstico
# diferencial); substituídos por hanseníase e leptospirose.
ABSENT_QUERIES: list[str] = [
    "Como tratar Doença de Lyme transmitida por carrapato?",
    "Manejo da Doença de Chagas em fase crônica",
    "Conduta em Lúpus eritematoso sistêmico",
    "Como diagnosticar esclerose múltipla?",
    "Tratamento da síndrome de Guillain-Barré",
    "Manejo da hanseníase paucibacilar",
    "Diagnóstico de leptospirose grave",
    "Conduta em hipertensão portal",
    "Tratamento de mononucleose infecciosa",
    "Diagnóstico de doença de Kawasaki em criança",
]

# BORDERLINE (5) — temas vagamente relacionados com temas presentes.
# Foram desenhados pra estressar a fronteira (o que conta como "presente"?).
BORDERLINE_QUERIES: list[str] = [
    "Alergia respiratória crônica",          # próximo de asma
    "Infecção pulmonar viral",                # próximo de PAC (bacteriana)
    "Dor torácica de origem indeterminada",   # vago em cardiologia
    "Câncer broncogênico",                    # sinônimo direto de CPNPC
    "Ansiedade situacional aguda",            # próximo de TAG
]


@dataclass
class QueryResult:
    group: str
    query: str
    scores: list[float]  # top-1, top-2, top-3
    top1_source: str

    @property
    def top1(self) -> float:
        return self.scores[0] if self.scores else 0.0


# ─── Coleta ─────────────────────────────────────────────────────────────────


def collect(retriever: ProtocolRetriever, queries: list[str], group: str) -> list[QueryResult]:
    results: list[QueryResult] = []
    for q in queries:
        # SEM filtro: queremos os 3 brutos pra ver a distribuição completa
        chunks = retriever.retrieve(q, top_k=3, min_score=None)
        scores = [c.score for c in chunks]
        top1_src = chunks[0].source_file if chunks else "—"
        results.append(QueryResult(group=group, query=q, scores=scores, top1_source=top1_src))
    return results


# ─── Apresentação ───────────────────────────────────────────────────────────


def print_table(group: str, results: list[QueryResult]) -> None:
    print(f"\n{'═' * 78}")
    print(f"  GRUPO {group}  ({len(results)} queries)")
    print(f"{'═' * 78}")
    print(
        f"  {'#':>2}  {'top-1':>6}  {'top-2':>6}  {'top-3':>6}  "
        f"{'fonte top-1':<35}  query"
    )
    print(f"  {'-' * 76}")
    for i, r in enumerate(results, start=1):
        s = r.scores + [0.0] * (3 - len(r.scores))
        src = r.top1_source[:34]
        q = r.query[:30] + ("…" if len(r.query) > 30 else "")
        print(f"  {i:>2}  {s[0]:>6.3f}  {s[1]:>6.3f}  {s[2]:>6.3f}  {src:<35}  {q}")


def group_stats(results: list[QueryResult]) -> dict:
    top1s = [r.top1 for r in results]
    return {
        "n": len(top1s),
        "mean": statistics.mean(top1s),
        "median": statistics.median(top1s),
        "min": min(top1s),
        "max": max(top1s),
        "stdev": statistics.stdev(top1s) if len(top1s) > 1 else 0.0,
    }


def print_stats(name: str, stats: dict) -> None:
    print(
        f"  {name:<12} n={stats['n']:<3} "
        f"mean={stats['mean']:.3f}  median={stats['median']:.3f}  "
        f"min={stats['min']:.3f}  max={stats['max']:.3f}  "
        f"σ={stats['stdev']:.3f}"
    )


def histogram(name: str, scores: list[float], bins: list[tuple[float, float]]) -> None:
    """Histograma ASCII simples por bin de score."""
    print(f"\n  Histograma do top-1 — {name}:")
    for lo, hi in bins:
        count = sum(1 for s in scores if lo <= s < hi)
        bar = "█" * count
        print(f"    [{lo:.2f}-{hi:.2f})  {bar:<10}  ({count})")


def analyze_threshold(
    present: list[QueryResult],
    absent: list[QueryResult],
    borderline: list[QueryResult],
    threshold: float,
) -> dict:
    """Calcula como o threshold se comporta empiricamente."""
    present_pass = [r for r in present if r.top1 >= threshold]
    absent_filtered = [r for r in absent if r.top1 < threshold]

    return {
        "threshold": threshold,
        "present_recall": len(present_pass) / len(present) if present else 0.0,
        "absent_specificity": len(absent_filtered) / len(absent) if absent else 0.0,
        "present_failures": [r for r in present if r.top1 < threshold],
        "absent_failures": [r for r in absent if r.top1 >= threshold],
        "borderline_by_side": {
            "above": [r for r in borderline if r.top1 >= threshold],
            "below": [r for r in borderline if r.top1 < threshold],
        },
    }


def recommend(analysis: dict, present: list[QueryResult], absent: list[QueryResult]) -> str:
    """Recomendação textual baseada na análise."""
    th = analysis["threshold"]
    recall = analysis["present_recall"]
    spec = analysis["absent_specificity"]

    lines = []
    lines.append(f"\nThreshold atual: {th}")
    lines.append(
        f"  Recall (PRESENT passa): {recall*100:.0f}%  "
        f"({len(present) - len(analysis['present_failures'])}/{len(present)})"
    )
    lines.append(
        f"  Specificity (ABSENT filtra): {spec*100:.0f}%  "
        f"({len(analysis['absent_failures']) and len(absent) - len(analysis['absent_failures']) or len(absent)}/{len(absent)})"
    )

    if analysis["present_failures"]:
        lines.append(f"  ⚠ PRESENT falhos (recall < 100%):")
        for r in analysis["present_failures"]:
            lines.append(f"     score={r.top1:.3f} | {r.query[:60]}")

    if analysis["absent_failures"]:
        lines.append(f"  ⚠ ABSENT falhos (specificity < 100%):")
        for r in analysis["absent_failures"]:
            lines.append(f"     score={r.top1:.3f} | {r.query[:60]}")

    # Recomendação
    lines.append("")
    if recall == 1.0 and spec == 1.0:
        lines.append("✅ Threshold 0.5 está bem calibrado para este dataset.")
    elif recall < 1.0:
        # Algum PRESENT caiu — threshold pode estar alto
        worst_present = min(r.top1 for r in present)
        suggested = max(0.3, round(worst_present - 0.02, 2))
        lines.append(
            f"⚠ {len(analysis['present_failures'])} PRESENT(s) abaixo do threshold."
        )
        lines.append(
            f"   Pior PRESENT: {worst_present:.3f}. Sugestão: baixar threshold "
            f"pra ~{suggested:.2f} (margem 0.02 abaixo). Trade-off: ABSENT podem subir."
        )
    elif spec < 1.0:
        worst_absent = max(r.top1 for r in absent)
        suggested = round(worst_absent + 0.02, 2)
        lines.append(
            f"⚠ {len(analysis['absent_failures'])} ABSENT(s) passando o filtro."
        )
        lines.append(
            f"   Maior ABSENT: {worst_absent:.3f}. Sugestão: subir threshold "
            f"pra ~{suggested:.2f} (margem 0.02 acima)."
        )

    return "\n".join(lines)


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 78)
    print("  Calibração empírica do RAG_MIN_SCORE")
    print("=" * 78)

    retriever = ProtocolRetriever()

    print("\n→ Coletando scores (25 queries, sem filtro)...")
    present = collect(retriever, PRESENT_QUERIES, "PRESENT")
    absent = collect(retriever, ABSENT_QUERIES, "ABSENT")
    borderline = collect(retriever, BORDERLINE_QUERIES, "BORDERLINE")
    print("✓ pronto.")

    # Tabelas
    print_table("PRESENT (temas confirmados no dataset)", present)
    print_table("ABSENT (temas confirmados FORA — grep retornou 0)", absent)
    print_table("BORDERLINE (vagamente relacionados)", borderline)

    # Estatísticas
    print(f"\n{'═' * 78}")
    print("  ESTATÍSTICAS — score top-1")
    print(f"{'═' * 78}")
    s_present = group_stats(present)
    s_absent = group_stats(absent)
    s_border = group_stats(borderline)
    print_stats("PRESENT", s_present)
    print_stats("ABSENT", s_absent)
    print_stats("BORDERLINE", s_border)

    # Histogramas
    bins = [(0.0, 0.30), (0.30, 0.40), (0.40, 0.45), (0.45, 0.50),
            (0.50, 0.55), (0.55, 0.60), (0.60, 0.70), (0.70, 1.01)]
    histogram("PRESENT", [r.top1 for r in present], bins)
    histogram("ABSENT", [r.top1 for r in absent], bins)
    histogram("BORDERLINE", [r.top1 for r in borderline], bins)

    # Análise vs threshold atual
    print(f"\n{'═' * 78}")
    print(f"  ANÁLISE vs threshold atual ({RAG_MIN_SCORE})")
    print(f"{'═' * 78}")
    analysis = analyze_threshold(present, absent, borderline, RAG_MIN_SCORE)
    print(recommend(analysis, present, absent))

    # BORDERLINE breakdown
    above = analysis["borderline_by_side"]["above"]
    below = analysis["borderline_by_side"]["below"]
    print(f"\n  BORDERLINE (5 queries) — separação pelo threshold {RAG_MIN_SCORE}:")
    print(f"    Acima ({len(above)}): {[r.query for r in above]}")
    print(f"    Abaixo ({len(below)}): {[r.query for r in below]}")

    # Sugestões alternativas
    print(f"\n{'═' * 78}")
    print("  COMPORTAMENTO PARA THRESHOLDS ALTERNATIVOS")
    print(f"{'═' * 78}")
    for alt in [0.40, 0.45, 0.50, 0.55, 0.60]:
        a = analyze_threshold(present, absent, borderline, alt)
        marker = "  ←atual" if abs(alt - RAG_MIN_SCORE) < 0.001 else ""
        print(
            f"  th={alt:.2f}:  recall={a['present_recall']*100:>3.0f}%  "
            f"specificity={a['absent_specificity']*100:>3.0f}%{marker}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
