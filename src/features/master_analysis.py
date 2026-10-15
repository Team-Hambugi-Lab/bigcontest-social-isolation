"""집계구 마스터(SK 2025.07~12 + SGIS 2024)를 분석용 피처 테이블로 정리한다 (이슈 #10).

마스터 원본은 수정하지 않는다. 열 제외 기준은 10/11 팀 회의 결정(SGIS 113열)과
이슈 #10 본문(`*_mean` 43열, 팀 확인 전인 SK 품질 89열은 옵션)을 따른다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

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
