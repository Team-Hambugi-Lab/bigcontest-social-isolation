"""발표자료 3번 배경 지도(M1) — 강남 집계구 1인가구 비율, 역삼2동 강조."""

# 2026-10-24, 이슈 #26. 원자료(SGIS 2024)만 쓰고 우리 지수·등급은 쓰지 않는다.
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap, to_rgb

from src.visualization.style import setup_style

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data/processed/master_sgis2024_selected_no_industry_counts.csv"
OA_SHP = ROOT / "data/raw/reference_data/강남_집계구경계/bnd_oa_11230_2025_2Q.shp"
DONG_SHP = (
    ROOT
    / "data/raw/국가데이터처_SGIS 행정구역 통계 및 경계/2. 경계"
    / "3. 2025년 2분기 기준 행정동 경계/bnd_dong_00_2025_2Q.shp"
)
OUT_DIR = ROOT / "docs/slides/figures"  # reports/figures는 gitignore 대상

GANGNAM_SGG = "11230"
FOCUS_DONG = "역삼2동"
BINS = [0, 10, 20, 30, 40, 50, 60, 70, 100]
NAVY_STEPS = [
    "#e8edf6",
    "#cdd8ec",
    "#a9bcdd",
    "#7f9bcb",
    "#5878b4",
    "#3a5998",
    "#243f78",
    "#142a55",
]
FADE = (
    0.35  # 역삼2동 밖은 흰색과 섞어 흐리게 (투명도 대신 실제 색으로 섞어 슬라이드 배경과 무관하게)
)
NO_DATA_COLOR = "#d9d9d9"


def fade(color: str, keep: float = FADE) -> tuple:
    """색을 흰색과 섞어 keep 비율만 남긴다."""
    return tuple(1 - keep * (1 - c) for c in to_rgb(color))


def load_oa() -> gpd.GeoDataFrame:
    """강남 집계구 경계에 1인가구 비율(%)을 붙인다."""
    cols = ["TOT_OA_CD", "ADM_CD", "SGIS2024_ga_sd_005", "SGIS2024_to_ga_001"]
    df = pd.read_csv(MASTER, usecols=cols, dtype={"TOT_OA_CD": str, "ADM_CD": str})
    df = df.drop_duplicates("TOT_OA_CD").copy()
    valid = df["SGIS2024_to_ga_001"] > 0
    df["solo_rate"] = (df["SGIS2024_ga_sd_005"] / df["SGIS2024_to_ga_001"] * 100).where(valid)

    oa = gpd.read_file(OA_SHP)
    oa["TOT_OA_CD"] = oa["TOT_OA_CD"].astype(str)
    return oa.merge(df.drop(columns="ADM_CD"), on="TOT_OA_CD", how="left")


def load_dong(crs) -> gpd.GeoDataFrame:
    """강남구 행정동 경계를 집계구 좌표계로 읽는다."""
    dong = gpd.read_file(DONG_SHP)
    return dong[dong["ADM_CD"].astype(str).str.startswith(GANGNAM_SGG)].to_crs(crs)


def draw(oa: gpd.GeoDataFrame, dong: gpd.GeoDataFrame, focus_only: bool, out: Path) -> None:
    """전체를 흐리게, 역삼2동만 진하게 그린다. focus_only면 역삼2동 주변만 확대한다."""
    cmap = ListedColormap(NAVY_STEPS)
    faded = ListedColormap([fade(c) for c in NAVY_STEPS])
    norm = BoundaryNorm(BINS, cmap.N)
    focus = dong[dong["ADM_NM"] == FOCUS_DONG]
    in_focus = oa["ADM_CD"] == focus["ADM_CD"].iloc[0]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_axis_off()
    for part, cm, na in (
        (oa[~in_focus], faded, fade(NO_DATA_COLOR)),
        (oa[in_focus], cmap, NO_DATA_COLOR),
    ):
        part.plot(
            ax=ax,
            column="solo_rate",
            cmap=cm,
            norm=norm,
            edgecolor="white",
            linewidth=0.15,
            missing_kwds={"color": na},
        )
    dong.boundary.plot(ax=ax, color="white", linewidth=0.8, alpha=0.8)
    focus.boundary.plot(ax=ax, color="#142a55", linewidth=2.2)

    if focus_only:
        minx, miny, maxx, maxy = focus.total_bounds
        pad = max(maxx - minx, maxy - miny) * 0.35
        ax.set_xlim(minx - pad, maxx + pad)
        ax.set_ylim(miny - pad, maxy + pad)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cax = ax.inset_axes([0.04, 0.03, 0.4, 0.025])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal", ticks=[0, 20, 40, 60, 100])
    cb.set_label("집계구 1인가구 비율 (%)  ·  SGIS 2024", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    fig.savefig(out, dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)


def draw_explain(oa: gpd.GeoDataFrame, dong: gpd.GeoDataFrame, out: Path) -> None:
    """역삼2동만 그려 동 경계·집계구·두 덩어리(50% 이상 / 20% 미만)를 표시한다."""
    cmap = ListedColormap(NAVY_STEPS)
    norm = BoundaryNorm(BINS, cmap.N)
    focus = dong[dong["ADM_NM"] == FOCUS_DONG]
    f = oa[oa["ADM_CD"] == focus["ADM_CD"].iloc[0]]

    fig, ax = plt.subplots(figsize=(9, 10))
    ax.set_axis_off()
    f.plot(
        ax=ax,
        column="solo_rate",
        cmap=cmap,
        norm=norm,
        edgecolor="white",
        linewidth=0.6,
        missing_kwds={"color": NO_DATA_COLOR},
    )
    focus.boundary.plot(ax=ax, color="#E69F00", linewidth=3)

    groups = (
        (f[f["solo_rate"] >= 50], "A: 1인가구 50% 이상", "다세대·원룸 주택가", "#D55E00"),
        (f[f["solo_rate"] < 20], "B: 1인가구 20% 미만", "아파트 단지", "#009E73"),
    )
    for part, title, kind, color in groups:
        hh = part["SGIS2024_to_ga_001"].sum()
        rate = part["SGIS2024_ga_sd_005"].sum() / hh * 100
        blob = part.dissolve()
        blob.boundary.plot(ax=ax, color=color, linewidth=1.5, linestyle="--")
        p = blob.representative_point().iloc[0]
        text = f"덩어리 {title}\n집계구 {len(part)}곳 · {hh:,.0f}가구 · 평균 {rate:.1f}%\n({kind})"
        ax.annotate(
            text,
            (p.x, p.y),
            ha="center",
            fontsize=12,
            color="white",
            weight="bold",
            bbox={"boxstyle": "round", "fc": color, "alpha": 0.9},
        )

    one = f.dropna(subset=["solo_rate"]).iloc[[0]]
    one.boundary.plot(ax=ax, color="black", linewidth=2.5)
    c = one.centroid.iloc[0]
    minx, miny, _, maxy = focus.total_bounds
    ax.annotate(
        "집계구 하나 (검은 테두리)\n= 흰 가는 선으로 나뉜 칸 하나",
        (c.x, c.y),
        xytext=(minx, maxy + (maxy - miny) * 0.02),
        fontsize=11,
        arrowprops={"arrowstyle": "->"},
    )
    valid = f.dropna(subset=["solo_rate"])
    dong_rate = valid["SGIS2024_ga_sd_005"].sum() / valid["SGIS2024_to_ga_001"].sum() * 100
    ax.set_title(
        f"{FOCUS_DONG} — 주황 굵은 선이 동 경계, 그 안의 칸 {len(f)}개가 집계구\n"
        f"동 전체 1인가구 {dong_rate:.1f}% · 회색은 원자료 결측",
        fontsize=14,
        pad=40,
    )
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    """M1 지도 세 장(강남 전체, 역삼2동 확대, 역삼2동 설명)을 저장하고 수치를 확인한다."""
    setup_style()
    oa = load_oa()
    dong = load_dong(oa.crs)
    focus_cd = dong.loc[dong["ADM_NM"] == FOCUS_DONG, "ADM_CD"].iloc[0]
    f = oa[(oa["ADM_CD"] == focus_cd) & oa["solo_rate"].notna()]
    dong_rate = f["SGIS2024_ga_sd_005"].sum() / f["SGIS2024_to_ga_001"].sum() * 100
    p10, p90 = f["solo_rate"].quantile([0.1, 0.9])
    print(
        f"{FOCUS_DONG}: 집계구 {len(f)}곳, 동 전체 {dong_rate:.1f}%, P10~P90 {p10:.1f}~{p90:.1f}%"
    )
    assert len(f) == 72 and round(dong_rate, 1) == 36.5, "설계서 3번 수치와 다르다"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    draw(oa, dong, False, OUT_DIR / "map_M1_oneperson_gangnam.png")
    draw(oa, dong, True, OUT_DIR / "map_M1_oneperson_yeoksam2.png")
    draw_explain(oa, dong, OUT_DIR / "map_M1_oneperson_yeoksam2_explain.png")
    print(f"저장: {OUT_DIR}")


if __name__ == "__main__":
    main()
