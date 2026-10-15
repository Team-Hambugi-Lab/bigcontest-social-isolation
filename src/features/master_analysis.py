"""집계구 마스터(SK 2025.07~12 + SGIS 2024)를 분석용 피처 테이블로 정리한다 (이슈 #10).

마스터 원본은 수정하지 않는다. 열 제외 기준은 10/11 팀 회의 결정(SGIS 113열)과
이슈 #10 본문(`*_mean` 43열, 팀 확인 전인 SK 품질 89열은 옵션)을 따른다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd

KEY_COLS = ["STD_YM", "TOT_OA_CD"]
SGIS_PREFIX = "SGIS2024_"

# 10/11 회의 결정: 분석용 사본에서 제외할 SGIS 열(113열)
SGIS_DROP_PATTERNS = (r"cp2_bem_\d+", r"cp_bem_\d+")  # 업종별 종사자수 → to_em_020으로 대체
SGIS_DROP_CODES = frozenset(
    [f"ho_yr_{i:03d}" for i in range(6, 21)]  # 2010~2024 건축연도별 주택수
    + ["ga_sd_004", "in_age_050", "in_age_051", "in_age_081"]  # 전부 공백
    + ["cp2_bnu_35", "cp2_bnu_68", "cp2_bnu_84", "cp2_bnu_85"]  # 대분류 사업체수와 동일
)
SK_PARTIAL_COLS = ("age_n_partial", "hour_n_partial", "weekday_n_partial")
READ_DTYPES = {"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str, "BASE_DATE": str}
BUSINESS_COUNT_PATTERN = r"cp2?_bnu_\d+"
HOURS = [f"{h:02d}" for h in range(24)]
DAWN_HOURS = HOURS[:6]  # 00~05시
WEEKDAYS = ["MON", "TUS", "WED", "THU", "FRI", "SAT", "SUN"]  # 마스터 표기 그대로(TUS)
WEEKEND = ["SAT", "SUN"]
AGE_GROUPS = ["10G", "20G", "30G", "40G", "50G", "60GU"]
SMALL_SAMPLE_MAX_GRID = 2  # 격자 1~2개짜리 집계구는 비율이 쉽게 튄다


def sgis_drop_columns(columns: Iterable[str]) -> list[str]:
    """10/11 회의에서 분석용 사본에서 빼기로 한 SGIS 열을 입력 순서대로 반환한다."""
    drop = []
    for col in columns:
        if not col.startswith(SGIS_PREFIX):
            continue
        code = col.removeprefix(SGIS_PREFIX)
        if code in SGIS_DROP_CODES or any(re.fullmatch(p, code) for p in SGIS_DROP_PATTERNS):
            drop.append(col)
    return drop


def sk_mean_columns(columns: Iterable[str]) -> list[str]:
    """`sum ÷ n_valid`와 같은 값이라 중복인 SK 평균 열을 반환한다."""
    return [c for c in columns if c.endswith("_mean")]


def sk_redundant_quality_columns(columns: Iterable[str]) -> list[str]:
    """테이블별 대표 품질 열과 값이 같은 변수별 품질 열과, 항상 0인 `*_n_partial` 열.

    같은 SK 테이블 안에서는 격자가 통째로 있거나 없어서(all-or-nothing) 변수별
    `n_valid`·`missing_rate`가 `{age,hour,weekday}_n_complete`·`_incomplete_rate`와 같다.
    """
    return [
        c for c in columns if c.endswith(("_n_valid", "_missing_rate")) or c in SK_PARTIAL_COLS
    ]


def quality_family(column: str) -> str:
    """변수별 SK 열이 속한 원본 테이블(age·hour·weekday)을 반환한다."""
    if column.startswith(("MAN_", "WMAN_")):
        return "age"
    if column.startswith("TMST_"):
        return "hour"
    if column.startswith("FLOW_POP_CNT_"):
        return "weekday"
    raise ValueError(f"not a per-variable SK column: {column}")


def drop_reasons(columns: Iterable[str], drop_sk_quality: bool = False) -> dict[str, str]:
    """분석 테이블에서 뺄 열과 그 사유를 반환한다."""
    columns = list(columns)
    reasons = {c: "SGIS 제외(10/11 회의 결정)" for c in sgis_drop_columns(columns)}
    reasons |= {c: "sum과 중복(mean = sum / n_valid)" for c in sk_mean_columns(columns)}
    if drop_sk_quality:
        reasons |= {
            c: "대표 품질 열과 값이 같거나 항상 0"
            for c in sk_redundant_quality_columns(columns)
        }
    return reasons


def business_count_columns(columns: Iterable[str]) -> list[str]:
    """업종별 사업체수 SGIS 열(대분류 `cp_bnu_*`, 중분류 `cp2_bnu_*`)을 반환한다."""
    return [
        c
        for c in columns
        if c.startswith(SGIS_PREFIX)
        and re.fullmatch(BUSINESS_COUNT_PATTERN, c.removeprefix(SGIS_PREFIX))
    ]


def fill_business_no_record(df: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """사업체수 열에서 SGIS 원본에 기록이 없는(`no_record`) 값을 0으로 채운다.

    업종별 사업체수를 no_record=0으로 합하면 1,698개 집계구 전부 총사업체수(to_fa_010)와
    일치한다. 그래서 '기록 없음'을 '해당 업종 사업체 없음'으로 본다. 1인가구 등 다른 SGIS
    열의 no_record는 이런 근거가 없어 결측으로 둔다(이슈 #6: ga_sd_005를 0으로 덮지 않음).
    """
    out = df.copy()
    cols = business_count_columns(out.columns)
    no_record = (
        status.set_index("TOT_OA_CD")[cols].reindex(out["TOT_OA_CD"]).eq("no_record").to_numpy()
    )
    out[cols] = np.where(no_record, 0.0, out[cols].to_numpy(dtype=float))
    return out


def _shares(values: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """행 합계로 나눈 구성비. 합계가 결측이거나 0이면 결측으로 둔다."""
    total = values.sum(axis=1, min_count=1)
    total = total.where(total > 0)
    return values.div(total, axis=0).set_axis(names, axis=1)


def add_share_features(df: pd.DataFrame) -> pd.DataFrame:
    """시간대·요일·연령 구성비, 새벽·주말 비중, 소표본 플래그를 덧붙인다.

    구성비는 같은 SK 테이블 안에서만 계산한다. 같은 테이블 안에서는 격자가 통째로
    빠지므로 분자와 분모가 같은 격자 집합에서 나온다. SK 미매칭 집계구는 분모가
    결측이라 구성비도 결측이다(0으로 채우지 않는다).
    """
    hour = _shares(
        df[[f"TMST_{h}_sum" for h in HOURS]], [f"share_hour_{h}" for h in HOURS]
    )
    wkdy = _shares(
        df[[f"FLOW_POP_CNT_{d}_sum" for d in WEEKDAYS]], [f"share_wkdy_{d}" for d in WEEKDAYS]
    )
    age_total = pd.DataFrame(
        {
            g: df[f"MAN_FLOW_POP_CNT_{g}_sum"] + df[f"WMAN_FLOW_POP_CNT_{g}_sum"]
            for g in AGE_GROUPS
        }
    )
    age = _shares(age_total, [f"share_age_{g}" for g in AGE_GROUPS])
    extra = pd.DataFrame(
        {
            "share_dawn": hour[[f"share_hour_{h}" for h in DAWN_HOURS]].sum(
                axis=1, min_count=1
            ),
            "share_weekend": wkdy[[f"share_wkdy_{d}" for d in WEEKEND]].sum(
                axis=1, min_count=1
            ),
            "is_small_sample": df["HAS_SK_POINTS"] & (df["N_GRID"] <= SMALL_SAMPLE_MAX_GRID),
        }
    )
    return pd.concat([df, hour, wkdy, age, extra], axis=1)
