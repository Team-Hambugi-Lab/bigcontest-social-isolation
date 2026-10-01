"""재언 보고서 재현용 위험 신호 5개 변수 계산.

원 코드가 공유되지 않아 보고서 서술(4·6·8장)만으로 재구성했다. 각 함수의
정의는 docstring에 그대로 남긴다 — 원 코드 확인 전까지는 가정이다.
"""

import numpy as np
import pandas as pd

AGE_COLS = [
    "MAN_FLOW_POP_CNT_10G", "MAN_FLOW_POP_CNT_20G", "MAN_FLOW_POP_CNT_30G",
    "MAN_FLOW_POP_CNT_40G", "MAN_FLOW_POP_CNT_50G", "MAN_FLOW_POP_CNT_60GU",
    "WMAN_FLOW_POP_CNT_10G", "WMAN_FLOW_POP_CNT_20G", "WMAN_FLOW_POP_CNT_30G",
    "WMAN_FLOW_POP_CNT_40G", "WMAN_FLOW_POP_CNT_50G", "WMAN_FLOW_POP_CNT_60GU",
]
ELDERLY_COLS = ["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]
TIME_COLS = [f"TMST_{h:02d}" for h in range(24)]
NIGHT_COLS = [f"TMST_{h:02d}" for h in range(0, 6)]
WEEKDAY_COLS = [
    "FLOW_POP_CNT_MON", "FLOW_POP_CNT_TUS", "FLOW_POP_CNT_WED",
    "FLOW_POP_CNT_THU", "FLOW_POP_CNT_FRI",
]
WEEKEND_COLS = ["FLOW_POP_CNT_SAT", "FLOW_POP_CNT_SUN"]


def total_flow(panel: pd.DataFrame) -> pd.Series:
    """성·연령 12칸 합(=해당 행의 월간 총 유동인구)."""
    return panel[AGE_COLS].sum(axis=1)


def flatness_cv(panel: pd.DataFrame) -> pd.Series:
    """시간대 비중(TMST를 그 행의 시간대 합으로 나눈 값)의 변동계수.

    값이 작을수록 평탄(오르내림 없음)하다 — "낮을수록 위험" 방향이다.
    """
    time_total = panel[TIME_COLS].sum(axis=1)
    share = panel[TIME_COLS].div(time_total, axis=0)
    return share.std(axis=1) / share.mean(axis=1)


def night_share(panel: pd.DataFrame) -> pd.Series:
    """야간(00~05시) 유동인구가 하루 시간대 합에서 차지하는 비중."""
    time_total = panel[TIME_COLS].sum(axis=1)
    return panel[NIGHT_COLS].sum(axis=1) / time_total


def weekend_ratio(panel: pd.DataFrame) -> pd.Series:
    """주말(토·일) 평균 ÷ 평일(월~금) 평균."""
    weekday_mean = panel[WEEKDAY_COLS].mean(axis=1)
    weekend_mean = panel[WEEKEND_COLS].mean(axis=1)
    return weekend_mean / weekday_mean


def elderly_share(panel: pd.DataFrame) -> pd.Series:
    """60대 이상(남+여) 유동인구가 성·연령 12칸 합에서 차지하는 비중."""
    return panel[ELDERLY_COLS].sum(axis=1) / total_flow(panel)
