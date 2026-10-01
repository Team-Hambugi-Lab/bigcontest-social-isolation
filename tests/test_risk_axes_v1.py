"""위험 신호 변수 계산 단위 테스트 (1부: 월별 변수)."""

import numpy as np
import pytest
import pandas as pd

from src.features.risk_axes_v1 import (
    AGE_COLS,
    elderly_share,
    flatness_cv,
    night_share,
    reduce_to_block_level,
    total_flow,
    trend_slope,
    weekend_ratio,
)


def _panel_row(**overrides) -> dict:
    row = {f"TMST_{h:02d}": 1.0 for h in range(24)}
    row.update(
        {
            "MAN_FLOW_POP_CNT_10G": 1.0, "MAN_FLOW_POP_CNT_20G": 1.0,
            "MAN_FLOW_POP_CNT_30G": 1.0, "MAN_FLOW_POP_CNT_40G": 1.0,
            "MAN_FLOW_POP_CNT_50G": 1.0, "MAN_FLOW_POP_CNT_60GU": 1.0,
            "WMAN_FLOW_POP_CNT_10G": 1.0, "WMAN_FLOW_POP_CNT_20G": 1.0,
            "WMAN_FLOW_POP_CNT_30G": 1.0, "WMAN_FLOW_POP_CNT_40G": 1.0,
            "WMAN_FLOW_POP_CNT_50G": 1.0, "WMAN_FLOW_POP_CNT_60GU": 1.0,
            "FLOW_POP_CNT_MON": 1.0, "FLOW_POP_CNT_TUS": 1.0,
            "FLOW_POP_CNT_WED": 1.0, "FLOW_POP_CNT_THU": 1.0,
            "FLOW_POP_CNT_FRI": 1.0, "FLOW_POP_CNT_SAT": 1.0,
            "FLOW_POP_CNT_SUN": 1.0,
        }
    )
    row.update(overrides)
    return row


class TestTotalFlow:
    def test_sums_twelve_age_columns(self):
        panel = pd.DataFrame([_panel_row()])
        assert total_flow(panel).iloc[0] == 12.0


class TestFlatnessCv:
    def test_perfectly_flat_profile_is_zero(self):
        panel = pd.DataFrame([_panel_row()])
        assert flatness_cv(panel).iloc[0] == pytest.approx(0.0)

    def test_peaked_profile_has_positive_cv(self):
        row = _panel_row()
        row["TMST_09"] = 100.0
        panel = pd.DataFrame([row])
        assert flatness_cv(panel).iloc[0] > 0.0


class TestNightShare:
    def test_all_activity_at_night_gives_share_one(self):
        row = {f"TMST_{h:02d}": (1.0 if h < 6 else 0.0) for h in range(24)}
        panel = pd.DataFrame([row])
        assert night_share(panel).iloc[0] == pytest.approx(1.0)

    def test_no_night_activity_gives_share_zero(self):
        row = {f"TMST_{h:02d}": (0.0 if h < 6 else 1.0) for h in range(24)}
        panel = pd.DataFrame([row])
        assert night_share(panel).iloc[0] == pytest.approx(0.0)


class TestWeekendRatio:
    def test_equal_weekday_weekend_gives_one(self):
        panel = pd.DataFrame([_panel_row()])
        assert weekend_ratio(panel).iloc[0] == pytest.approx(1.0)

    def test_weekend_double_weekday_gives_two(self):
        row = _panel_row(FLOW_POP_CNT_SAT=2.0, FLOW_POP_CNT_SUN=2.0)
        panel = pd.DataFrame([row])
        assert weekend_ratio(panel).iloc[0] == pytest.approx(2.0)


class TestElderlyShare:
    def test_only_elderly_gives_share_one(self):
        zeroed = {
            c: 0.0
            for c in [
                "MAN_FLOW_POP_CNT_10G", "MAN_FLOW_POP_CNT_20G", "MAN_FLOW_POP_CNT_30G",
                "MAN_FLOW_POP_CNT_40G", "MAN_FLOW_POP_CNT_50G",
                "WMAN_FLOW_POP_CNT_10G", "WMAN_FLOW_POP_CNT_20G", "WMAN_FLOW_POP_CNT_30G",
                "WMAN_FLOW_POP_CNT_40G", "WMAN_FLOW_POP_CNT_50G",
            ]
        }
        panel = pd.DataFrame([_panel_row(**zeroed)])
        assert elderly_share(panel).iloc[0] == pytest.approx(1.0)


class TestTrendSlope:
    def test_declining_series_has_negative_slope(self):
        series = pd.Series([np.log(100.0), np.log(50.0), np.log(25.0)])
        assert trend_slope(series) < 0

    def test_single_observation_is_nan(self):
        series = pd.Series([np.log(100.0)])
        assert pd.isna(trend_slope(series))


class TestReduceToBlockLevel:
    def test_trend_is_negative_for_declining_flow(self):
        rows = []
        for i, month in enumerate(["202507", "202508", "202509"]):
            scale = 120.0 / (i + 1)
            row = _panel_row(
                **{c: scale / 12 for c in AGE_COLS}
            )
            row["STD_YM"] = month
            row["집계구"] = "B1"
            rows.append(row)
        panel = pd.DataFrame(rows)

        result = reduce_to_block_level(panel, months_order=["202507", "202508", "202509"])

        assert result.loc["B1", "추세"] < 0

    def test_single_month_trend_is_nan(self):
        row = _panel_row()
        row["STD_YM"] = "202507"
        row["집계구"] = "B1"
        panel = pd.DataFrame([row])

        result = reduce_to_block_level(panel, months_order=["202507"])

        assert pd.isna(result.loc["B1", "추세"])
