"""위험 신호 변수 계산 단위 테스트 (1부: 월별 변수)."""

import pytest
import pandas as pd

from src.features.risk_axes_v1 import (
    elderly_share,
    flatness_cv,
    night_share,
    total_flow,
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
