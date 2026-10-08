"""4축 지표와 합성 지수 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import isolation


def test_minmax_basic_range():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = isolation.minmax(s)
    assert out.min() == 0.0
    assert out.max() == 1.0
    assert out.iloc[1] == pytest.approx(1 / 3)


def test_minmax_invert_flips_direction():
    s = pd.Series([1.0, 2.0, 3.0])
    out = isolation.minmax(s, invert=True)
    assert out.iloc[0] == 1.0
    assert out.iloc[-1] == 0.0


def test_minmax_constant_series_returns_zeros():
    s = pd.Series([5.0, 5.0, 5.0])
    out = isolation.minmax(s)
    assert (out == 0.0).all()


def test_composite_equal_weights_is_mean():
    df = pd.DataFrame({"a": [0.0, 1.0], "b": [1.0, 0.0]})
    out = isolation.composite(df, ["a", "b"])
    assert out.tolist() == [0.5, 0.5]


def test_composite_custom_weights_normalized():
    df = pd.DataFrame({"a": [0.0, 1.0], "b": [1.0, 0.0]})
    out = isolation.composite(df, ["a", "b"], weights={"a": 3.0, "b": 1.0})
    assert out.iloc[0] == pytest.approx(0.25)
    assert out.iloc[1] == pytest.approx(0.75)


def test_composite_rejects_out_of_range_input():
    df = pd.DataFrame({"a": [0.0, 2.0], "b": [1.0, 0.0]})
    with pytest.raises(ValueError, match="0~1"):
        isolation.composite(df, ["a", "b"])


def test_sensitivity_is_reproducible():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.random((20, 3)), columns=["a", "b", "c"])
    r1 = isolation.sensitivity(df, ["a", "b", "c"], n_trials=50, seed=42)
    r2 = isolation.sensitivity(df, ["a", "b", "c"], n_trials=50, seed=42)
    pd.testing.assert_frame_equal(r1, r2)
    assert set(r1.columns) == {"rank_mean", "rank_std", "rank_min", "rank_max"}
    assert len(r1) == 20


def test_entropy_uniform_is_log_n():
    row = np.ones(24)
    assert isolation._entropy(row) == pytest.approx(np.log(24))


def test_entropy_all_zero_is_zero():
    assert isolation._entropy(np.zeros(24)) == 0.0


@pytest.mark.requires_data
def test_space_indicators_columns_and_range():
    from src.features import sk_dong

    panel = sk_dong.build_space_panel()
    ind = isolation.space_indicators(panel)
    assert ind["dong_cd"].nunique() == 47
    for c in ("wkdy_cv", "time_entropy", "night_share", "peak_ratio", "senior_share"):
        assert c in ind.columns
        assert ind[c].notna().all()
    assert ind["night_share"].between(0, 1).all()
    assert ind["senior_share"].between(0, 1).all()
    assert ind["peak_ratio"].between(0, 1).all()
    # 24개 구간 균등분포의 엔트로피 상한은 log(24)
    assert (ind["time_entropy"] <= np.log(24) + 1e-9).all()


@pytest.mark.requires_data
def test_cohort_indicators_columns():
    from src.features import card_cohort

    panel = card_cohort.cohort_panel(card_cohort.prepare_card(2))
    ind = isolation.cohort_indicators(panel)
    for c in ("social_share", "amount_per_use", "ry_diversity"):
        assert c in ind.columns
    assert ind["social_share"].between(0, 1).all()
    assert (ind["amount_per_use"] > 0).all()
    assert len(ind) == 2 * 2 * 9


def test_disclaimer_mentions_unvalidated():
    assert "외부검증" in isolation.DISCLAIMER
