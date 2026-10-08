"""SK 유동인구를 공간축 패널(행정동 x 월)로 집계한다.

3테이블의 격자 커버리지가 다르지만(AGE 98,129 / TIME 94,099 / WKDY 117,825)
동 단위로 올리면 47개 동이 동일하게 나오고 총량 차이도 중앙값 0.000%다.
따라서 공통 격자로 제한하지 않고 각 테이블 전체 격자를 쓴다.
"""

import pandas as pd

from src.data import loaders, regions

AGE_COLS = [
    f"{sex}_FLOW_POP_CNT_{grp}"
    for sex in ("MAN", "WMAN")
    for grp in ("10G", "20G", "30G", "40G", "50G", "60GU")
]
TIME_COLS = [f"TMST_{h:02d}" for h in range(24)]
WKDY_COLS = [f"FLOW_POP_CNT_{d}" for d in ("MON", "TUS", "WED", "THU", "FRI", "SAT", "SUN")]

SENIOR_COLS = ["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]
# 야간은 22시~익일 05시로 정의한다
NIGHT_COLS = [f"TMST_{h:02d}" for h in (22, 23, 0, 1, 2, 3, 4, 5)]

_TABLE_COLS = {"age": AGE_COLS, "time": TIME_COLS, "wkdy": WKDY_COLS}


def aggregate_dong(table: str, unit: str = "dong_cd") -> pd.DataFrame:
    """SK 테이블 한 종을 지정 공간 단위 x 월로 합산한다."""
    if table not in _TABLE_COLS:
        raise ValueError(f"table must be one of {tuple(_TABLE_COLS)}, got {table!r}")
    df = loaders.load_sk(table)
    df = regions.filter_target_sgg(regions.add_region_codes(df))
    cols = _TABLE_COLS[table]
    return df.groupby([unit, "STD_YM"], observed=True)[cols].sum().sort_index()


def build_space_panel(unit: str = "dong_cd") -> pd.DataFrame:
    """3테이블을 지정 공간 단위 x 월로 결합한 wide 패널을 만든다."""
    parts = [aggregate_dong(t, unit=unit) for t in ("age", "time", "wkdy")]
    panel = pd.concat(parts, axis=1)
    if panel.isnull().any().any():
        n = int(panel.isnull().sum().sum())
        raise ValueError(f"패널 결합 후 결측 {n}건 발생 — 단위별 커버리지를 확인할 것")
    return panel.reset_index()
