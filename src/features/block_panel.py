"""SK 유동인구 격자 데이터를 집계구(BLOCK_CD 앞 13자리) 단위 월별 패널로 집계.

BLOCK_CD는 보고서(진재언, 2026-09-26)에 따르면 통계청 집계구 코드 체계를
따르며 앞 5자리=시군구, 앞 13자리=집계구다. 원 코드는 공유되지 않아 이
전제를 그대로 가져왔다 — 검증이 필요하면 재언 님 코드와 대조한다.
"""

import pandas as pd

TARGET_SGG_PREFIXES = ("11230", "32010")  # 서울 강남구, 강원 춘천시
BLOCK_LEVEL_DIGITS = 13
KEY_COLS = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]


def aggregate_to_block(df: pd.DataFrame) -> pd.DataFrame:
    """격자 단위 SK 통합 데이터를 (기준월, 집계구) 단위로 합산한다.

    강남구·춘천시 외 시군구 접두는 제외한다. 값 컬럼이 그룹 내에서 전부
    결측이면 0이 아니라 결측으로 남긴다(min_count=1).
    """
    is_target = df["BLOCK_CD"].str.startswith(TARGET_SGG_PREFIXES)
    filtered = df.loc[is_target].copy()
    filtered["집계구"] = filtered["BLOCK_CD"].str.slice(0, BLOCK_LEVEL_DIGITS)

    value_cols = [c for c in filtered.columns if c not in (*KEY_COLS, "집계구")]
    grouped = filtered.groupby(["STD_YM", "집계구"], as_index=False)[value_cols].sum(min_count=1)
    return grouped
