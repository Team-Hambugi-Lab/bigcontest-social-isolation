"""#15 동 집계에서 분모·가중치·제외 사유가 바뀌지 않게 확인한다."""

import pandas as pd
import pytest

from src.features import seoul_comm as sc


def test_exclusion_keeps_all_failed_conditions_and_one_primary_reason():
    master = pd.DataFrame(
        {
            "TOT_OA_CD": [f"{i:014d}" for i in range(sc.N_MISSING + 1)],
            "SGIS2024_to_in_001": [10] + [0] + [10] * 48,
            "SGIS2024_to_ga_001": [5] + [0] * 2 + [5] * 47,
            "SGIS2024_to_ho_001": [4] + [0] * 3 + [4] * 46,
            "HAS_SK_POINTS": [True] * 4 + [False] * 46,
        }
    )
    prototype = master.iloc[[0]]
    out = sc.excluded_oa(master, prototype).set_index("TOT_OA_CD")
    assert len(out) == sc.N_MISSING
    assert out.loc[f"{1:014d}", "primary_reason"] == "no_population"
    assert out.loc[f"{1:014d}", "no_households"]
    assert out.loc[f"{2:014d}", "primary_reason"] == "no_households"
    assert out.loc[f"{3:014d}", "primary_reason"] == "no_housing"
    assert out.loc[f"{4:014d}", "primary_reason"] == "no_sk"


def test_prototype_dong_uses_household_weights_and_keeps_coverage():
    base = pd.DataFrame(
        {
            "TOT_OA_CD": ["a", "b"],
            "ADM_CD": ["d", "d"],
            "SGIS2024_to_ga_001": [1, 9],
            "score": [0.0, 10.0],
            "grade": [1, 5],
        }
    )
    without = base.assign(score=[10.0, 0.0], grade=[5, 1])
    master = pd.DataFrame(
        {"TOT_OA_CD": ["a", "b", "c"], "ADM_CD": ["d"] * 3, "SGIS2024_to_ga_001": [1, 9, 10]}
    )
    out = sc.prototype_dong(master, base, without).iloc[0]
    assert out["score_with_oldho"] == pytest.approx(9.0)
    assert out["score_no_oldho"] == pytest.approx(1.0)
    assert out["grade5_hh_share_with_oldho"] == pytest.approx(0.9)
    assert out["n_oa_missing"] == 1
    assert out["share_hh_eval"] == pytest.approx(0.5)


def test_interest_ratio_uses_sum_over_sum_then_month_mean_and_separates_60s():
    data = pd.DataFrame(
        {
            "ADM_CD": ["d"] * 4,
            "ym": ["202507", "202507", "202508", "202508"],
            "age": [60, 65, 60, 65],
            "pop": [100, 10, 10, 100],
            "low_out": [10, 9, 0, 10],
        }
    )
    assert sc.monthly_ratio(data, "low_out", "old65")["d"] == pytest.approx((0.9 + 0.1) / 2)
    assert sc.monthly_ratio(data, "low_out", "old60")["d"] == pytest.approx(
        (19 / 110 + 10 / 110) / 2
    )


def test_telecom_weight_excludes_unestimated_and_missing_cells():
    data = pd.DataFrame(
        {
            "ADM_CD": ["d", "d", "d"],
            "ym": ["202507"] * 3,
            "age": [65, 70, 75],
            "pop": [100, 100, 100],
            "value": [10.0, 20.0, float("nan")],
            "missing": [50, 0, 0],
        }
    )
    out = sc.weighted_monthly(data, "value", "missing", "old65").loc["d"]
    assert out["value"] == pytest.approx((10 * 50 + 20 * 100) / 150)
    assert out["coverage"] == pytest.approx(0.5)
    data.loc[0, "missing"] = 101
    with pytest.raises(ValueError, match="negative"):
        sc.weighted_monthly(data, "value", "missing", "old65")
