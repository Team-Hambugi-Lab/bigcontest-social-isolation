"""SK 공간축 패널 테스트."""

import pytest

from src.features import sk_dong


@pytest.fixture(scope="module")
def panel():
    return sk_dong.build_space_panel()


def test_column_group_sizes():
    assert len(sk_dong.AGE_COLS) == 12
    assert len(sk_dong.TIME_COLS) == 24
    assert len(sk_dong.WKDY_COLS) == 7
    assert len(sk_dong.SENIOR_COLS) == 2
    assert len(sk_dong.NIGHT_COLS) == 8


def test_aggregate_dong_shape():
    agg = sk_dong.aggregate_dong("age")
    assert agg.index.names == ["dong_cd", "STD_YM"]
    assert agg.index.get_level_values("dong_cd").nunique() == 47
    assert len(agg) == 47 * 6
    assert list(agg.columns) == sk_dong.AGE_COLS


def test_all_three_tables_produce_same_47_dongs():
    dongs = {
        t: set(sk_dong.aggregate_dong(t).index.get_level_values("dong_cd"))
        for t in ("age", "time", "wkdy")
    }
    assert dongs["age"] == dongs["time"] == dongs["wkdy"]
    assert len(dongs["age"]) == 47


def test_space_panel_merges_without_loss(panel):
    assert len(panel) == 47 * 6
    assert panel.isnull().sum().sum() == 0
    for c in sk_dong.AGE_COLS + sk_dong.TIME_COLS + sk_dong.WKDY_COLS:
        assert c in panel.columns


def test_age_total_matches_time_total_at_dong_level(panel):
    """동 단위 AGE 총량과 TIME 총량 격차를 실측 범위 안에 고정한다.

    공통 격자에서는 두 총량이 정확히 일치하나(상관 1.000000),
    테이블별 격자 커버리지가 달라 동 단위에서는 격차가 남는다.
    격차는 춘천 면 지역 7개 동에 집중되며 TIME 격자가 AGE보다 6~15% 적다.
    """
    age_sum = panel[sk_dong.AGE_COLS].sum(axis=1)
    time_sum = panel[sk_dong.TIME_COLS].sum(axis=1)
    rel = (age_sum - time_sum).abs() / age_sum

    assert rel.median() < 0.001  # 실측 0.0055%
    assert rel.max() < 0.05  # 실측 3.33% (춘천 32010380)
    # 전체 총량 기준으로는 0.1% 미만
    assert abs(age_sum.sum() - time_sum.sum()) / age_sum.sum() < 0.001


def test_cross_table_gap_is_concentrated_in_chuncheon(panel):
    """격차가 춘천 저밀도 면 지역에 몰려 있는지 확인한다."""
    age_sum = panel[sk_dong.AGE_COLS].sum(axis=1)
    time_sum = panel[sk_dong.TIME_COLS].sum(axis=1)
    rel = (age_sum - time_sum).abs() / age_sum

    gangnam = rel[panel["dong_cd"].str.startswith("11230")]
    chuncheon = rel[panel["dong_cd"].str.startswith("32010")]
    assert gangnam.max() < 0.001  # 강남 실측 최대 0.028%
    assert chuncheon.max() > 0.01  # 춘천 실측 최대 3.33%


def test_wkdy_sum_is_about_seven_times_daily_average(panel):
    ratio = panel[sk_dong.WKDY_COLS].sum(axis=1).sum() / panel[sk_dong.AGE_COLS].sum(axis=1).sum()
    # WKDY 각 칸은 해당 요일의 일평균이므로 7칸 합은 일평균의 약 7배
    assert 6.5 < ratio < 7.5


def test_unit_tong_gives_more_units():
    agg = sk_dong.aggregate_dong("age", unit="tong_cd")
    assert agg.index.get_level_values("tong_cd").nunique() == 148
