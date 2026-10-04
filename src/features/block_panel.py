"""SK 유동인구 격자 데이터를 SGIS 공식 집계구 단위 월별 패널로 집계.

집계구는 BLOCK_CD 앞자리를 잘라 추정하지 않는다 — 재언 님의 EDA v4 노트북
(notebooks/261001_EDA_skt_isolation_jhj.ipynb, Cell 8)이 실제로 대조해보니
코드 절단(`[:13]`)과 공식 집계구 경계가 13.2%만 일치했다. 통계청 집계구는
지리적 포함관계가 아니라 인구 수 등 별도 기준으로 획정되기 때문이다. 대신
격자 좌표를 SGIS 공식 집계구 경계(data/raw/reference_data/{강남,춘천}_
집계구경계/bnd_oa_*.shp)에 공간조인(point-in-polygon)한다.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

OA_SHP_PATHS = (
    "강남_집계구경계/bnd_oa_11230_2025_2Q.shp",
    "춘천_집계구경계/bnd_oa_32010_2025_2Q.shp",
)
KEY_COLS = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]


def load_oa_boundaries(reference_dir: Path) -> gpd.GeoDataFrame:
    """강남·춘천 SGIS 집계구 경계를 하나로 합쳐 반환한다. 코드는 TOT_OA_CD(14자리)."""
    parts = [gpd.read_file(reference_dir / p)[["TOT_OA_CD", "geometry"]] for p in OA_SHP_PATHS]
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)


def assign_oa(df: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """격자 좌표를 집계구 경계에 공간조인해 '집계구' 컬럼을 추가한다.

    어느 집계구 폴리곤에도 속하지 않는 격자(경계 근처 잔차, 또는 강남·춘천
    외 지역)는 버린다 — 가장 가까운 폴리곤에 강제로 배정하지 않는다.
    """
    points = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["X_COORD"], df["Y_COORD"]), crs=boundaries.crs
    )
    joined = gpd.sjoin(points, boundaries, how="inner", predicate="within")
    joined = joined.drop(columns=["geometry", "index_right"]).rename(
        columns={"TOT_OA_CD": "집계구"}
    )
    return pd.DataFrame(joined)


def aggregate_to_block(df: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """격자 단위 SK 통합 데이터를 (기준월, 집계구) 단위로 합산한다.

    값 컬럼이 그룹 내에서 전부 결측이면 0이 아니라 결측으로 남긴다(min_count=1).
    """
    assigned = assign_oa(df, boundaries)
    value_cols = [c for c in assigned.columns if c not in (*KEY_COLS, "집계구")]
    grouped = assigned.groupby(["STD_YM", "집계구"], as_index=False)[value_cols].sum(min_count=1)
    return grouped
