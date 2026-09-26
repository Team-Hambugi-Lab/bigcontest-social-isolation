"""SGIS 집계구 통계 로더.

출처
    통계지리정보서비스(SGIS) 소지역 통계. 무료 공개, 신청 후 다운로드.
    `data/raw/external/` 아래에 원본 그대로 둔다.

구조
    CSV에 **헤더가 없다**. 컬럼은 [기준연도, 코드(14자리), 통계항목코드, 값] 순이다.
    코드 14자리 = 시도(2) + 시군구(3) + 읍면동(3) + 집계구(6).
    **앞 8자리가 SK BLOCK_CD 앞 8자리와 같은 체계**라 행정동 수준에서 바로 조인된다
    (47개 중 46개 직접 일치, 1개는 코드 개편 대응).
    집계구 6자리는 SK 체계와 달라 집계구 단위 조인에는 경계 shapefile이 필요하다.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.paths import RAW_DIR
from src.data.regions import SGG_NAMES, TARGET_SGG

EXTERNAL_DIR = RAW_DIR / "external"

# SK에는 11230740이, SGIS에는 11230511(개포3동)이 있다. 행정동 코드 개편 시점 차이로
# 보이며 둘 다 실재하는 동 하나에 대응한다. SGIS 쪽을 SK 코드로 맞춘다.
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
    """NFD 한글 경로를 피해 glob으로 찾되 연도를 명시적으로 고른다."""
    hits = sorted(EXTERNAL_DIR.rglob(pattern))
    if not hits:
        raise FileNotFoundError(f"{EXTERNAL_DIR} 아래에서 {pattern!r}를 찾지 못했다")
    if year is None:
        if len(hits) > 1:
            raise ValueError(
                f"{pattern!r}가 {len(hits)}개다. year를 지정할 것: {[h.name for h in hits]}"
            )
        return hits[0]
    matched = [h for h in hits if f"_{year}년" in h.name]
    if len(matched) != 1:
        raise FileNotFoundError(
            f"{pattern!r}에서 {year}년 파일을 단일 특정하지 못했다: {[h.name for h in hits]}"
        )
    return matched[0]


def load_sgis_csv(pattern: str, year: str = DEFAULT_YEAR) -> pd.DataFrame:
    """SGIS 통계 CSV 하나를 읽어 대상 시군구만 남긴다."""
    df = pd.read_csv(
        _find(pattern, year),
        header=None,
        names=CSV_COLS,
        dtype={"year": str, "block_cd": str, "item": str},
    )
    df = df[df.block_cd.str[:5].isin(TARGET_SGG)].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["dong_cd"] = df.block_cd.str[:8].replace(DONG_CODE_FIX)
    df["sgg_cd"] = df.block_cd.str[:5]
    return df


def dong_names() -> pd.Series:
    """행정동 코드 -> 읍면동 이름. SGIS 행정구역 코드표에서 만든다."""
    adm = pd.read_excel(_find("*행정구역 코드*.xls", year=None), dtype=str, skiprows=1)
    adm.columns = ["sido_cd", "sido", "sgg_cd", "sgg", "dong_cd", "dong"]
    adm = adm.dropna(subset=["sido_cd"])
    key = (adm.sido_cd + adm.sgg_cd + adm.dong_cd).replace(DONG_CODE_FIX)
    return pd.Series(adm.dong.to_numpy(), index=key.to_numpy(), name="dong_name")


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

    # 인구밀도는 집계구별 값이라 인구 가중평균으로 올린다
    dens = load_sgis_csv("*인구총괄(인구밀도).csv", year)
    pop = load_sgis_csv("*인구총괄(총인구).csv", year)
    pop = pop[pop.item == "to_in_001"][["block_cd", "value"]].rename(columns={"value": "w"})
    m = dens.merge(pop, on="block_cd")
    out = out.join(
        m.groupby("dong_cd")
        .apply(
            lambda g: np.average(g.value, weights=g.w) if g.w.sum() > 0 else np.nan,
            include_groups=False,
        )
        .rename("pop_density")
    )

    names = dong_names()
    out["dong_name"] = [names.get(d, "?") for d in out.index]
    out["sgg_name"] = [SGG_NAMES[d[:5]] for d in out.index]
    return out.reset_index()
