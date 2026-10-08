"""SK 수치값의 이산 구조 회귀 테스트.

초기 분석에서 양자를 0.025로 잘못 단정했다가 전수 검정으로 0.0254임을 확인했다.
같은 실수를 반복하지 않도록 사실을 여기에 고정한다.
"""

import numpy as np
import pytest

from src.data import loaders
from src.features import sk_dong

QUANTUM = 0.0254
TABLE_COLS = {
    "age": sk_dong.AGE_COLS,
    "time": sk_dong.TIME_COLS,
    "wkdy": sk_dong.WKDY_COLS,
}
pytestmark = pytest.mark.requires_data


def positives(table: str, ym: str) -> np.ndarray:
    df = loaders.load_sk(table, ym)
    v = df[TABLE_COLS[table]].to_numpy().ravel()
    return v[v > 0]


@pytest.mark.parametrize("table", ["age", "time", "wkdy"])
def test_all_values_are_multiples_of_quantum(table):
    """모든 양수값은 0.0254의 정수배를 소수 2자리로 반올림한 값이다."""
    v = positives(table, "202507")
    k = np.rint(v / QUANTUM)
    # 2자리 반올림 오차 한계 0.005. 대형 격자의 경계 타이를 위해 0.006으로 둔다.
    assert np.abs(k * QUANTUM - v).max() <= 0.006


@pytest.mark.parametrize("table", ["age", "time", "wkdy"])
def test_quantum_is_not_0_025(table):
    """0.025로는 설명되지 않는다. 초기 오판을 고정해 둔다."""
    v = positives(table, "202507")
    k = np.rint(v / 0.025)
    explained = (np.abs(k * 0.025 - v) <= 0.005).mean()
    assert explained < 0.95, f"0.025 설명률이 {explained:.2%}로 예상보다 높다"


def test_minimum_positive_is_one_quantum():
    """최소 양수는 k=1, 즉 0.0254를 반올림한 0.03이다."""
    for table in TABLE_COLS:
        for ym in loaders.MONTHS:
            v = positives(table, ym)
            assert v.min() == pytest.approx(0.03)
            assert (v < 0.03).sum() == 0


def test_sub_one_interval_has_39_distinct_values():
    """[0,1) 구간 고유값이 39종이다. 연속값을 2자리 반올림했다면 99종이어야 한다."""
    v = positives("time", "202507")
    assert len(np.unique(v[v < 1])) == 39


def test_quantum_does_not_depend_on_month_length():
    """31일 달과 30일 달의 최소 양수·고유값 수가 같다. '월합계/일수' 구조가 아니다."""
    jul = positives("time", "202507")  # 31일
    sep = positives("time", "202509")  # 30일
    assert jul.min() == sep.min()
    assert len(np.unique(jul[jul < 1])) == len(np.unique(sep[sep < 1]))
