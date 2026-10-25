"""발표자료 STEP 1 — 테마 A·B 상위 20% 지도 (강남·춘천 집계구)."""

# 2026-10-25, 이슈 #26. 지수 v3.3 결과와 집계구·행정동 경계만 쓴다.
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from src.visualization.style import setup_style
from src.visualization.theme_ab_scatter import COLORS, INDEX, TOP

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "data/raw/reference_data"
OA_SHP = {
    "강남구": REF / "강남_집계구경계/bnd_oa_11230_2025_2Q.shp",
    "춘천시": REF / "춘천_집계구경계/bnd_oa_32010_2025_2Q.shp",
}
DONG_SHP = (
    ROOT
    / "data/raw/국가데이터처_SGIS 행정구역 통계 및 경계/2. 경계"
    / "3. 2025년 2분기 기준 행정동 경계/bnd_dong_00_2025_2Q.shp"
)
SGG = {"강남구": "11230", "춘천시": "32010"}
OUT = ROOT / "docs/slides/figures/theme_ab_map.png"
HOLD_COLOR = "#e9ebef"


def classify(d: pd.DataFrame) -> pd.Series:
    """테마 A·B 상위 20% 여부로 집계구를 나눈다. 보류(grade 0)는 따로 둔다."""
    a, b = d["theme_A_pct"] >= TOP, d["theme_B_pct"] >= TOP
    g = pd.Series("그 외", index=d.index)
    g[a & ~b] = "A만 상위"
    g[~a & b] = "B만 상위"
    g[a & b] = "둘 다 상위"
    g[d["grade"] == 0] = "보류"
    return g


def main() -> None:
    """두 지역 지도를 나란히 그리고 집계 수를 설계서 값과 대조한다."""
    setup_style()
    idx = pd.read_csv(INDEX, dtype={"TOT_OA_CD": str})
    idx["group"] = classify(idx)
    n = idx["group"].value_counts()
    print(n.to_dict())
    assert (n["A만 상위"], n["둘 다 상위"], n["B만 상위"]) == (159, 156, 159)

    dong = gpd.read_file(DONG_SHP)
    colors = {**COLORS, "보류": HOLD_COLOR}
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={"width_ratios": [1, 1.3]})
    for ax, (region, shp) in zip(axes, OA_SHP.items()):
        oa = gpd.read_file(shp)
        oa["TOT_OA_CD"] = oa["TOT_OA_CD"].astype(str)
        oa = oa.merge(idx[["TOT_OA_CD", "group"]], on="TOT_OA_CD", how="left")
        oa["color"] = oa["group"].map(colors).fillna(HOLD_COLOR)
        oa.plot(ax=ax, color=oa["color"], edgecolor="white", linewidth=0.1)
        d = dong[dong["ADM_CD"].astype(str).str.startswith(SGG[region])].to_crs(oa.crs)
        d.boundary.plot(ax=ax, color="white", linewidth=0.7)
        ax.set_title(region, fontsize=14)
        ax.set_axis_off()

    labels = ["둘 다 상위", "A만 상위", "B만 상위", "그 외", "보류"]
    handles = [Patch(color=colors[k], label=f"{k} {n[k]:,}곳") for k in labels]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=11)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", transparent=True)
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
