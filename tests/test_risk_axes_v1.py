"""위험 신호 변수 계산 단위 테스트 (1부: 월별 변수)."""

import numpy as np
import pytest
import pandas as pd

from src.features.risk_axes_v1 import (
    AGE_COLS,
    align_risk_direction,
    cronbach_alpha_standardized,
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
            "MAN_FLOW_POP_CNT_10G": 1.0,
            "MAN_FLOW_POP_CNT_20G": 1.0,
            "MAN_FLOW_POP_CNT_30G": 1.0,
            "MAN_FLOW_POP_CNT_40G": 1.0,
            "MAN_FLOW_POP_CNT_50G": 1.0,
            "MAN_FLOW_POP_CNT_60GU": 1.0,
            "WMAN_FLOW_POP_CNT_10G": 1.0,
            "WMAN_FLOW_POP_CNT_20G": 1.0,
            "WMAN_FLOW_POP_CNT_30G": 1.0,
            "WMAN_FLOW_POP_CNT_40G": 1.0,
            "WMAN_FLOW_POP_CNT_50G": 1.0,
            "WMAN_FLOW_POP_CNT_60GU": 1.0,
            "FLOW_POP_CNT_MON": 1.0,
            "FLOW_POP_CNT_TUS": 1.0,
            "FLOW_POP_CNT_WED": 1.0,
            "FLOW_POP_CNT_THU": 1.0,
            "FLOW_POP_CNT_FRI": 1.0,
            "FLOW_POP_CNT_SAT": 1.0,
            "FLOW_POP_CNT_SUN": 1.0,
        }
    )
    row.update(overrides)
    return row


class TestTotalFlow:
    def test_sums_twelve_age_columns(self):
        panel = pd.DataFrame([_panel_row()])
        assert total_flow(panel).iloc[0] == 12.0

    def test_all_missing_age_cols_stay_nan_not_zero(self):
        """12칸이 전부 결측이면 0이 아니라 결측이어야 한다.

        0으로 새면 이후 ln(0)=-inf가 되어 해당 집계구의 추세 전체가 깨진다
        (리뷰 Important #2).
        """
        row = _panel_row(**{c: float("nan") for c in AGE_COLS})
        panel = pd.DataFrame([row])
        assert pd.isna(total_flow(panel).iloc[0])


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
                "MAN_FLOW_POP_CNT_10G",
                "MAN_FLOW_POP_CNT_20G",
                "MAN_FLOW_POP_CNT_30G",
                "MAN_FLOW_POP_CNT_40G",
                "MAN_FLOW_POP_CNT_50G",
                "WMAN_FLOW_POP_CNT_10G",
                "WMAN_FLOW_POP_CNT_20G",
                "WMAN_FLOW_POP_CNT_30G",
                "WMAN_FLOW_POP_CNT_40G",
                "WMAN_FLOW_POP_CNT_50G",
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
            row = _panel_row(**{c: scale / 12 for c in AGE_COLS})
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

    def test_trend_uses_actual_month_rank_not_dropna_position(self):
        """관측월 사이에 빈 달이 있으면 dropna 이후 순번이 아니라 실제
        월 위치(months_order 기준 순서)를 x값으로 써야 한다 (리뷰 Important #1).

        202507(순서 0)·202508(순서 1)·202512(순서 5)만 관측되고 실제
        기울기가 -0.1/월이면, 순번(0,1,2)으로 잘못 피팅하면 -0.25가 나오고
        실제 월 위치(0,1,5)로 올바르게 피팅하면 -0.1이 나온다.
        """
        months_order = ["202507", "202508", "202509", "202510", "202511", "202512"]
        true_slope = -0.1
        observed = {"202507": 0, "202508": 1, "202512": 5}

        rows = []
        for month, rank in observed.items():
            flow = np.exp(np.log(100.0) + true_slope * rank)
            row = _panel_row(**{c: flow / 12 for c in AGE_COLS})
            row["STD_YM"] = month
            row["집계구"] = "B1"
            rows.append(row)
        panel = pd.DataFrame(rows)

        result = reduce_to_block_level(panel, months_order=months_order)

        assert result.loc["B1", "추세"] == pytest.approx(true_slope, abs=1e-6)


class TestAlignRiskDirection:
    def test_flatness_and_trend_are_negated(self):
        block_level = pd.DataFrame(
            {
                "평탄도": [0.5],
                "야간비중": [0.3],
                "주말비": [1.2],
                "고령비중": [0.4],
                "추세": [-0.1],
            },
            index=pd.Index(["B1"], name="집계구"),
        )

        aligned = align_risk_direction(block_level)

        assert aligned.loc["B1", "평탄도_위험"] == -0.5
        assert aligned.loc["B1", "추세_위험"] == pytest.approx(0.1)
        assert aligned.loc["B1", "야간비중_위험"] == 0.3
        assert aligned.loc["B1", "고령비중_위험"] == 0.4
        assert aligned.loc["B1", "주말비_위험"] == 1.2


class TestCronbachAlphaStandardized:
    def test_perfectly_correlated_items_give_alpha_near_one(self):
        base = np.arange(100, dtype=float)
        items = pd.DataFrame({"a": base, "b": base * 2, "c": base + 5})

        alpha = cronbach_alpha_standardized(items)

        assert alpha == pytest.approx(1.0, abs=1e-6)

    def test_independent_items_give_low_alpha(self):
        rng = np.random.default_rng(42)
        items = pd.DataFrame(
            {
                "a": rng.normal(size=500),
                "b": rng.normal(size=500),
                "c": rng.normal(size=500),
            }
        )

        alpha = cronbach_alpha_standardized(items)

        assert alpha < 0.3

    def test_raises_on_constant_column(self):
        items = pd.DataFrame({"a": [1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0]})

        with pytest.raises(ValueError, match="결측"):
            cronbach_alpha_standardized(items)

    def test_pearson_is_default_method(self):
        base = np.arange(100, dtype=float)
        items = pd.DataFrame({"a": base, "b": base * 2, "c": base + 5})

        assert cronbach_alpha_standardized(items) == cronbach_alpha_standardized(
            items, method="pearson"
        )

    def test_spearman_method_is_invariant_to_monotonic_transform(self):
        """x와 x**3은 선형관계는 아니지만 완전한 단조관계라 순위상관은 1.0이다.

        분포가 심하게 치우친 항목(예: 주말비, 최대 68)이 있을 때 Pearson은
        이상치에 민감하지만 Spearman은 순위만 보므로 덜 흔들린다 (리뷰 Important #3).
        """
        x = np.arange(1, 21, dtype=float)
        items = pd.DataFrame({"a": x, "b": x**3})

        alpha_spearman = cronbach_alpha_standardized(items, method="spearman")

        assert alpha_spearman == pytest.approx(1.0, abs=1e-6)
