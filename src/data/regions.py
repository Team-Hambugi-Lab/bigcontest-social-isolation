"""BLOCK_CD 파싱과 좌표계 변환.

BLOCK_CD 20자리는 구(舊) 행정구역코드 체계다.

    11230  510  10  1020000001
    시군구  행정동 통   일련번호

앞 5자리는 좌표를 WGS84로 변환해 역추적한 결과 시군구임을 확인했다.
  11230 -> 37.497N 127.062E, 관측면적 38.1km2 (서울 강남구, 실제 39.5km2)
  32010 -> 37.869N 127.716E (강원 춘천시)
6~8자리 개수는 강남구 행정동 22개, 춘천시 읍면동 25개와 정확히 일치한다.
"""

import pandas as pd
from pyproj import Transformer

SGG_NAMES = {"11230": "서울 강남구", "32010": "강원 춘천시"}
TARGET_SGG = ("11230", "32010")
GRID_AREA_M2 = 2500  # 50m x 50m 격자

_TRANSFORMER = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def add_region_codes(df: pd.DataFrame) -> pd.DataFrame:
    """BLOCK_CD에서 시군구·행정동·통 코드를 뽑아 컬럼으로 붙인다."""
    out = df.copy()
    code = out["BLOCK_CD"].astype(str)
    out["sgg_cd"] = code.str[:5]
    out["dong_cd"] = code.str[:8]
    out["tong_cd"] = code.str[:10]
    out["sgg_name"] = out["sgg_cd"].map(SGG_NAMES)
    return out


def filter_target_sgg(df: pd.DataFrame) -> pd.DataFrame:
    """대상 시군구(강남구·춘천시) 격자만 남긴다. 경계 격자는 제외된다."""
    if "sgg_cd" not in df.columns:
        df = add_region_codes(df)
    return df[df["sgg_cd"].isin(TARGET_SGG)].copy()


def add_wgs84(df: pd.DataFrame) -> pd.DataFrame:
    """UTM-K(EPSG:5179) 좌표를 WGS84 경위도로 변환해 붙인다."""
    out = df.copy()
    lon, lat = _TRANSFORMER.transform(out["X_COORD"].to_numpy(), out["Y_COORD"].to_numpy())
    out["lon"] = lon
    out["lat"] = lat
    return out
