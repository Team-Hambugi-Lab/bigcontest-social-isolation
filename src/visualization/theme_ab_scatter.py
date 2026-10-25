"""발표자료 STEP 1 — 테마 A·B 백분위 산점도 (상위 20% 사분면)."""

# 2026-10-25, 이슈 #26. 지수 v3.3 결과(isolation_index_v3.csv)만 쓴다.
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.visualization.style import setup_style

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data/interim/v3.3/isolation_index_v3.csv"
OUT = ROOT / "docs/slides/figures/theme_ab_scatter.png"

TOP = 80  # 테마 상위 20%
COLORS = {"A만 상위": "#0072B2", "B만 상위": "#E69F00", "둘 다 상위": "#14264f", "그 외": "#c8ccd4"}


def main() -> None:
    """테마 A·B 백분위를 사분면으로 나눠 그리고 집계 수를 설계서 값과 대조한다."""
    setup_style()
    d = pd.read_csv(INDEX)
    d = d[d["grade"] > 0].copy()  # 보류 제외
    a, b = d["theme_A_pct"] >= TOP, d["theme_B_pct"] >= TOP
    d["group"] = "그 외"
    d.loc[a & ~b, "group"] = "A만 상위"
    d.loc[~a & b, "group"] = "B만 상위"
    d.loc[a & b, "group"] = "둘 다 상위"
    n = d["group"].value_counts()
    print(n.to_dict())
    assert (n["A만 상위"], n["둘 다 상위"], n["B만 상위"]) == (159, 156, 159), (
        "설계서 8번 수치와 다르다"
    )

    fig, ax = plt.subplots(figsize=(7, 7))
    for g in ["그 외", "A만 상위", "B만 상위", "둘 다 상위"]:
        s = d[d["group"] == g]
        ax.scatter(
            s["theme_A_pct"],
            s["theme_B_pct"],
            s=10,
            c=COLORS[g],
            label=f"{g} {len(s)}곳",
            alpha=0.85,
            linewidths=0,
        )
    for v in (TOP,):
        ax.axvline(v, color="#555", lw=0.8, ls="--")
        ax.axhline(v, color="#555", lw=0.8, ls="--")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("테마 A 고령 독거 (지역 안 백분위)")
    ax.set_ylabel("테마 B 중장년 독거·주거취약 (지역 안 백분위)")
    ax.set_title("두 테마의 상위 20%는 절반만 겹친다")
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    ax.grid(False)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", transparent=True)
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
