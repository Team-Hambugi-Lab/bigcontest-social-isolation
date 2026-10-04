"""집계구 유동인구-기온 상관 검정 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features.flow_temperature import (
    flow_deviation,
    monthly_log_flow,
    temperature_deviation,
    correlate_flow_with_temperature,
)
from src.features.risk_axes_v1 import AGE_COLS


def _panel_row(집계구: str, STD_YM: str, total: float) -> dict:
    row = {c: total / len(AGE_COLS) for c in AGE_COLS}
    row["집계구"] = 집계구
    row["STD_YM"] = STD_YM
    return row


class TestMonthlyLogFlow:
    def test_computes_ln_flow_and_region(self):
        panel = pd.DataFrame(
            [
                _panel_row("1123051001", "202507", 100.0),
                _panel_row("3201051001", "202507", 50.0),
            ]
        )

        result = monthly_log_flow(panel)

        assert result.loc[result.집계구 == "1123051001", "ln유동인구"].iloc[0] == pytest.approx(
            np.log(100.0)
        )
        assert result.loc[result.집계구 == "1123051001", "지역"].iloc[0] == "서울"
        assert result.loc[result.집계구 == "3201051001", "지역"].iloc[0] == "춘천"


class TestFlowDeviation:
    def test_deviation_is_zero_mean_per_oa(self):
        monthly_flow = pd.DataFrame(
            {
                "집계구": ["A", "A", "B", "B"],
                "STD_YM": ["202507", "202508", "202507", "202508"],
                "ln유동인구": [4.0, 6.0, 1.0, 3.0],
                "지역": ["서울", "서울", "춘천", "춘천"],
            }
        )

        result = flow_deviation(monthly_flow)

        a = result[result.집계구 == "A"].set_index("STD_YM")["ln유동인구_편차"]
        assert a["202507"] == pytest.approx(-1.0)
        assert a["202508"] == pytest.approx(1.0)
        b = result[result.집계구 == "B"].set_index("STD_YM")["ln유동인구_편차"]
        assert b["202507"] == pytest.approx(-1.0)
        assert b["202508"] == pytest.approx(1.0)


class TestTemperatureDeviation:
    def test_deviation_is_zero_mean_per_region(self):
        monthly_temp = pd.DataFrame(
            {
                "지역": ["서울", "서울", "춘천", "춘천"],
                "STD_YM": ["202507", "202512", "202507", "202512"],
                "평균기온": [26.0, -3.0, 21.0, -7.0],
            }
        )

        result = temperature_deviation(monthly_temp)

        seoul = result[result.지역 == "서울"].set_index("STD_YM")["평균기온_편차"]
        assert seoul["202507"] == pytest.approx(14.5)
        assert seoul["202512"] == pytest.approx(-14.5)


class TestFlowTracksTemperature:
    def test_detects_perfect_correlation(self):
        flow_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "ln유동인구_편차": [5.0, 4.0, 3.0, 1.0, -4.0, -9.0],
            }
        )
        temp_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "평균기온_편차": [10.0, 9.0, 6.0, -1.0, -9.0, -17.0],
            }
        )

        result = correlate_flow_with_temperature(flow_dev, temp_dev)

        assert result.loc["서울", "correlation"] == pytest.approx(1.0)
        assert result.loc["서울", "n"] == 6

    def test_separates_regions(self):
        months = [f"2025{m:02d}" for m in range(7, 13)]
        flow_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6 + ["춘천"] * 6,
                "STD_YM": months * 2,
                "ln유동인구_편차": [5.0, 4.0, 3.0, 1.0, -4.0, -9.0]
                + [1.0, -3.0, 2.0, -1.0, 4.0, -2.0],
            }
        )
        temp_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6 + ["춘천"] * 6,
                "STD_YM": months * 2,
                "평균기온_편차": [10.0, 9.0, 6.0, -1.0, -9.0, -17.0] * 2,
            }
        )

        result = correlate_flow_with_temperature(flow_dev, temp_dev)

        assert set(result.index) == {"서울", "춘천"}
        assert result.loc["서울", "correlation"] == pytest.approx(1.0)
        assert abs(result.loc["춘천", "correlation"]) < 1.0

    def test_partial_missing_values_do_not_make_whole_region_nan(self):
        """scipy.spearmanr의 기본 nan_policy='propagate'는 행 하나만 결측이어도
        전체 상관·p-value를 NaN으로 만든다(리뷰 Important #4). 결측 달(예: 그
        집계구의 특정 월 데이터 누락, 또는 log(0)로 생긴 결측)이 하나 있어도
        나머지 유효한 달로는 상관을 계산할 수 있어야 하고, n도 유효한 행만
        세야 한다.
        """
        flow_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "ln유동인구_편차": [5.0, 4.0, float("nan"), 1.0, -4.0, -9.0],
            }
        )
        temp_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "평균기온_편차": [10.0, 9.0, 6.0, -1.0, -9.0, -17.0],
            }
        )

        result = correlate_flow_with_temperature(flow_dev, temp_dev)

        assert result.loc["서울", "n"] == 5
        assert not pd.isna(result.loc["서울", "correlation"])
