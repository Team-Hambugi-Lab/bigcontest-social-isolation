"""SGIS 집계구 통계 로더.

출처
    통계지리정보서비스(SGIS) 소지역 통계. 무료 공개, 신청 후 다운로드.
    `data/raw/external/` 아래에 원본 그대로 둔다.

구조
    CSV 컬럼은 [기준연도, 행정구역코드, 통계항목, 통계값] 순이다.
    행정구역코드는 시도(2자리)·시군구(5자리)·행정동(8자리)이 한 파일에 섞여 있다.
    행정동 8자리가 SK BLOCK_CD 앞 8자리와 같은 체계라 바로 조인된다
    (47개 중 46개 직접 일치, 1개는 코드 개편 대응).
"""

from fnmatch import fnmatch
from pathlib import Path
from unicodedata import normalize

import numpy as np
import pandas as pd

from src.data.paths import RAW_DIR
from src.data.regions import SGG_NAMES, TARGET_SGG

EXTERNAL_DIR = next(
    (path for path in RAW_DIR.iterdir() if path.is_dir() and "SGIS" in path.name),
    RAW_DIR / "external",
)

# SK에는 11230740(일원2동)이, SGIS에는 11230511(개포3동)이 있다. 같은 동의 이름만 바뀐
# 것이다. 강남구청이 행정동 명칭만 바꾸고 법정동은 유지한다고 안내했고, 서울시 통신정보
# 20세 이상 인구 / SGIS 총인구가 0.857로 다른 21개 동 범위(0.73~1.34) 안에 있다(#25).
# SK와 서울시 자료는 개칭 전 코드를 쓴다. SGIS 쪽을 SK 코드로 맞춘다.
DONG_CODE_FIX = {"11230511": "11230740"}

# 성·연령별 인구 항목 (전체, 성 미구분). 5세 단위 21구간 + 나이미상
AGE_ITEMS_ALL = [f"in_age_{i:03d}" for i in range(1, 23)]
AGE_YOUNG = [f"in_age_{i:03d}" for i in range(1, 4)]  # 0~14세
AGE_WORK = [f"in_age_{i:03d}" for i in range(4, 14)]  # 15~64세
AGE_OLD = [f"in_age_{i:03d}" for i in range(14, 22)]  # 65세 이상
AGE_OLDEST = [f"in_age_{i:03d}" for i in range(17, 22)]  # 80세 이상

CSV_COLS = ["year", "block_cd", "item", "value"]

# 2023·2024 두 해가 서로 다른 요청번호 폴더에 들어 있다. 폴더명 정렬이 연도 순서와
# 어긋나므로(458194가 398356보다 뒤) 연도를 반드시 명시해서 고른다.
# SK 데이터가 2025-07~12이므로 가장 가까운 2024를 기본값으로 둔다.
DEFAULT_YEAR = "2024"


def _find(pattern: str, year: str = DEFAULT_YEAR) -> Path:
    """NFD 한글 경로를 정규화해 비교하고 연도를 명시적으로 고른다."""
    normalized_pattern = normalize("NFC", pattern)
    hits = sorted(
        path
        for path in EXTERNAL_DIR.rglob("*")
        if path.is_file() and fnmatch(normalize("NFC", path.name), normalized_pattern)
    )
    if not hits:
        raise FileNotFoundError(f"{EXTERNAL_DIR} 아래에서 {pattern!r}를 찾지 못했다")
    if year is None:
        if len(hits) > 1:
            raise ValueError(
                f"{pattern!r}가 {len(hits)}개다. year를 지정할 것: {[h.name for h in hits]}"
            )
        return hits[0]
    matched = [h for h in hits if f"_{year}년" in normalize("NFC", h.name)]
    if len(matched) != 1:
        raise FileNotFoundError(
            f"{pattern!r}에서 {year}년 파일을 단일 특정하지 못했다: {[h.name for h in hits]}"
        )
    return matched[0]


def load_sgis_csv(pattern: str, year: str = DEFAULT_YEAR) -> pd.DataFrame:
    """SGIS 통계 CSV 하나를 읽어 대상 시군구만 남긴다."""
    df = pd.read_csv(_find(pattern, year), encoding="cp949", dtype={"행정구역코드": str})
    df.columns = CSV_COLS
    df = df[df.block_cd.str.len().eq(8) & df.block_cd.str[:5].isin(TARGET_SGG)].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["dong_cd"] = df.block_cd.str[:8].replace(DONG_CODE_FIX)
    df["sgg_cd"] = df.block_cd.str[:5]
    return df


def dong_names() -> pd.Series:
    """행정동 코드 -> 읍면동 이름. SGIS 행정동 경계 속성에서 만든다."""
    import geopandas as gpd

    adm = gpd.read_file(_find("bnd_dong_*.shp", year=None), columns=["ADM_CD", "ADM_NM"])
    key = adm.ADM_CD.replace(DONG_CODE_FIX)
    return pd.Series(adm.ADM_NM.to_numpy(), index=key.to_numpy(), name="dong_name")


def census_dong_panel(year: str = DEFAULT_YEAR) -> pd.DataFrame:
    """행정동 단위 외부 인구 지표.

    집계구 값을 행정동으로 합산하고, 파생 지표는 합산 후 재계산한다
    (비율의 평균이 아니라 합계의 비율이어야 한다).
    """
    age = load_sgis_csv("*성연령별인구.csv", year)
    piv = (
        age[age.item.isin(AGE_ITEMS_ALL)]
        .pivot_table(index="dong_cd", columns="item", values="value", aggfunc="sum")
        .reindex(columns=AGE_ITEMS_ALL)
        .fillna(0.0)
    )
    out = pd.DataFrame(
        {
            "pop": piv.sum(axis=1),
            "pop_young": piv[AGE_YOUNG].sum(axis=1),
            "pop_work": piv[AGE_WORK].sum(axis=1),
            "pop_old": piv[AGE_OLD].sum(axis=1),
            "pop_oldest": piv[AGE_OLDEST].sum(axis=1),
        }
    )
    out["senior_ratio"] = out.pop_old / out["pop"] * 100
    out["oldest_ratio"] = out.pop_oldest / out["pop"] * 100
    out["aging_index"] = out.pop_old / out.pop_young.replace(0, np.nan) * 100
    out["elderly_dependency"] = out.pop_old / out.pop_work.replace(0, np.nan) * 100

    # 현재 SGIS 파일은 행정동 값을 직접 제공한다.
    dens = load_sgis_csv("*인구총괄(인구밀도).csv", year)
    out = out.join(dens.set_index("dong_cd")["value"].rename("pop_density"))

    names = dong_names()
    out["dong_name"] = [names.get(d, "?") for d in out.index]
    out["sgg_name"] = [SGG_NAMES[d[:5]] for d in out.index]
    return out.reset_index()
