"""Map July 2025 SKT points to Gangnam-gu and Chuncheon-si boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


KEYS = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]
TARGETS = ["강남구", "춘천시"]
SKT_CRS = "EPSG:5179"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skt-csv", type=Path, required=True)
    parser.add_argument("--boundary-shp", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def run(skt_csv: Path, boundary_shp: Path, output_dir: Path) -> pd.DataFrame:
    dtype = {col: "string" for col in KEYS}
    df = pd.read_csv(
        skt_csv,
        encoding="utf-8-sig",
        dtype=dtype,
        na_values=["NULL"],
    )

    age_cols = [
        col for col in df.columns if col.startswith(("MAN_FLOW_POP_CNT_", "WMAN_FLOW_POP_CNT_"))
    ]
    if len(age_cols) != 12:
        raise ValueError(f"성·연령 지표 12개가 필요하지만 {len(age_cols)}개입니다.")

    points_df = df.loc[df[age_cols].notna().all(axis=1), KEYS].copy()
    if points_df.duplicated(KEYS).any():
        raise ValueError("STD_YM + BLOCK_CD + X_COORD + Y_COORD 중복이 있습니다.")
    if points_df.duplicated(["X_COORD", "Y_COORD"]).any():
        raise ValueError("분석 입력에 중복 좌표가 있습니다.")

    points_df["X_NUM"] = pd.to_numeric(points_df["X_COORD"], errors="raise")
    points_df["Y_NUM"] = pd.to_numeric(points_df["Y_COORD"], errors="raise")

    boundary = gpd.read_file(boundary_shp)
    if boundary.crs is None:
        raise ValueError("경계 파일 좌표계가 없습니다. .prj 파일을 확인하세요.")
    boundary = boundary.to_crs(SKT_CRS)
    boundary = boundary.loc[
        boundary["SIGUNGU_NM"].isin(TARGETS),
        ["BASE_DATE", "SIGUNGU_CD", "SIGUNGU_NM", "geometry"],
    ]
    if set(boundary["SIGUNGU_NM"]) != set(TARGETS):
        raise ValueError("경계 파일에서 강남구와 춘천시를 모두 찾지 못했습니다.")

    points = gpd.GeoDataFrame(
        points_df,
        geometry=gpd.points_from_xy(points_df["X_NUM"], points_df["Y_NUM"]),
        crs=SKT_CRS,
    )
    joined = gpd.sjoin(points, boundary, how="left", predicate="intersects")
    if joined.index.duplicated().any():
        raise ValueError("한 지점이 둘 이상의 대상 경계에 배정됐습니다.")

    region = joined["SIGUNGU_NM"].fillna("경계 밖")
    summary = region.value_counts().rename_axis("지역").rename("지점수").reset_index()
    summary = pd.concat(
        [pd.DataFrame({"지역": ["전체"], "지점수": [len(joined)]}), summary],
        ignore_index=True,
    )
    mapped = joined["SIGUNGU_NM"].notna().sum()
    summary["매핑성공률"] = pd.NA
    summary.loc[summary["지역"] == "전체", "매핑성공률"] = mapped / len(joined)

    output_dir.mkdir(parents=True, exist_ok=True)
    mapping = joined.drop(columns=["geometry", "index_right"])
    mapping.to_csv(
        output_dir / "202507_SKT_시군구_매핑.csv",
        index=False,
        encoding="utf-8-sig",
        na_rep="NULL",
    )
    mapping.loc[mapping["SIGUNGU_NM"].isna()].to_csv(
        output_dir / "202507_경계밖_62개.csv",
        index=False,
        encoding="utf-8-sig",
        na_rep="NULL",
    )
    summary.to_csv(
        output_dir / "202507_공간조인_요약.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return summary


if __name__ == "__main__":
    args = parse_args()
    result = run(args.skt_csv, args.boundary_shp, args.output_dir)
    print(result.to_string(index=False))
