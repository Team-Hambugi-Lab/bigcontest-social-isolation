"""발표자료 STEP 1 — 테마별 상위 20% 지도 (테마 A·B 각각 한 장)."""

# 2026-10-25, 이슈 #26. 지수 v3.3 결과와 집계구·행정동 경계만 쓴다.
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from src.visualization.style import setup_style
from src.visualization.theme_ab_map import DONG_SHP, HOLD_COLOR, OA_SHP, ROOT, SGG
from src.visualization.theme_ab_scatter import COLORS, INDEX, TOP

THEMES = {"A": ("theme_A_pct", COLORS["A만 상위"]), "B": ("theme_B_pct", COLORS["B만 상위"])}
OTHER_COLOR = "#c8ccd4"


def main() -> None:
    """테마마다 상위 20% 집계구만 테마 색으로 칠한 지도를 저장하고 지역별 수를 출력한다."""
    setup_style()
    idx = pd.read_csv(INDEX, dtype={"TOT_OA_CD": str})
    dong = gpd.read_file(DONG_SHP)
    oas = {
        r: gpd.read_file(p).assign(TOT_OA_CD=lambda g: g["TOT_OA_CD"].astype(str))
        for r, p in OA_SHP.items()
    }
    for theme, (col, color) in THEMES.items():
        top = (idx[col] >= TOP) & (idx["grade"] > 0)
        print(theme, idx[top].groupby("REGION").size().to_dict(), "합계", int(top.sum()))
        fig, axes = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw={"width_ratios": [1, 1.3]})
        for ax, (region, oa) in zip(axes, oas.items()):
            g = oa.merge(idx[["TOT_OA_CD", "grade", col]], on="TOT_OA_CD", how="left")
            c = pd.Series(OTHER_COLOR, index=g.index)
            c[g["grade"].fillna(0) == 0] = HOLD_COLOR
            c[(g[col] >= TOP) & (g["grade"] > 0)] = color
            g.plot(ax=ax, color=c, edgecolor="white", linewidth=0.1)
            d = dong[dong["ADM_CD"].astype(str).str.startswith(SGG[region])].to_crs(g.crs)
            d.boundary.plot(ax=ax, color="white", linewidth=0.7)
            ax.set_axis_off()
        out = ROOT / f"docs/slides/figures/theme_{theme}_map.png"
        fig.savefig(out, dpi=300, bbox_inches="tight", transparent=True)
        plt.close(fig)
        print(f"저장: {out}")


if __name__ == "__main__":
    main()
