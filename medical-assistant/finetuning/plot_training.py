"""Gera gráficos do treino a partir de `finetuning/output/training_log.json`.

Saídas em `finetuning/output/`:
- loss_curve.png  — train e val loss por iteração
- lr_schedule.png — taxa de aprendizado por iteração (constante na nossa config)

Uso:
    uv run python finetuning/plot_training.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).parent
LOG_PATH = HERE / "output" / "training_log.json"
LOSS_PNG = HERE / "output" / "loss_curve.png"
LR_PNG = HERE / "output" / "lr_schedule.png"


def main() -> int:
    if not LOG_PATH.exists():
        print(f"❌ {LOG_PATH} não existe. Rode antes:")
        print("   uv run python finetuning/train.py")
        return 1

    entries = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    if not entries:
        print("⚠ training_log.json está vazio.")
        return 1

    train_pts = [(e["iter"], e["train_loss"]) for e in entries if e["type"] == "train"]
    val_pts = [(e["iter"], e["val_loss"]) for e in entries if e["type"] == "val"]
    lr_pts = [(e["iter"], e["lr"]) for e in entries if e["type"] == "train"]

    if not train_pts:
        print("⚠ Nenhum ponto de train loss encontrado.")
        return 1

    # ── Loss curve ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    train_iters, train_losses = zip(*train_pts)
    ax.plot(train_iters, train_losses, label="Train loss", linewidth=1.2,
            marker=".", markersize=4, color="#1f77b4")
    if val_pts:
        val_iters, val_losses = zip(*val_pts)
        ax.plot(val_iters, val_losses, label="Val loss", linewidth=2,
                marker="o", markersize=6, color="#d62728")
        best_iter, best_loss = min(val_pts, key=lambda p: p[1])
        ax.scatter([best_iter], [best_loss], s=120, facecolors="none",
                   edgecolors="green", linewidths=2,
                   label=f"melhor val ({best_loss:.3f} @ iter {best_iter})")
    ax.set_xlabel("Iteração")
    ax.set_ylabel("Loss")
    ax.set_title("Fine-tuning LoRA — curva de loss")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(LOSS_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {LOSS_PNG.relative_to(HERE.parent)}")

    # ── LR schedule ─────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    lr_iters, lrs = zip(*lr_pts)
    ax.plot(lr_iters, lrs, linewidth=1.5, color="#2ca02c")
    ax.set_xlabel("Iteração")
    ax.set_ylabel("Learning rate")
    ax.set_title("Schedule de learning rate")
    ax.grid(alpha=0.3)
    # Se LR é constante, força eixo y mais informativo
    if max(lrs) - min(lrs) < 1e-12:
        center = lrs[0]
        ax.set_ylim(center * 0.5, center * 1.5)
    fig.tight_layout()
    fig.savefig(LR_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {LR_PNG.relative_to(HERE.parent)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
