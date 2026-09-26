"""카드 집단축 패널 테스트."""

import pytest

from src.features import card_cohort


@pytest.fixture(scope="module")
def card():
    return card_cohort.prepare_card(2)


@pytest.fixture(scope="module")
def panel(card):
    return card_cohort.cohort_panel(card)


def test_social_categories_all_exist_in_data(card):
    present = set(card["MCT_RY_CD"])
    assert set(card_cohort.SOCIAL_RY) <= present
    assert len(card_cohort.SOCIAL_RY) == 12


def test_excluded_categories_are_half_the_amount(card):
    share = card.loc[card["is_excluded"], "TS_AT"].sum() / card["TS_AT"].sum()
    assert 0.48 < share < 0.51  # 실측 49.58%


def test_age_band_parses_space_format(card):
    assert card["age_band"].between(10, 90).all()
    assert sorted(card["age_band"].unique()) == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_ym_derived_from_ta_ymd(card):
    assert sorted(card["ym"].unique()) == [
        "202507",
        "202508",
        "202509",
        "202510",
        "202511",
        "202512",
    ]


def test_cohort_panel_shape(panel):
    # 2지역 x 2성별 x 9연령 x 6개월 = 216, 빈 조합이 있을 수 있어 이하
    assert len(panel) <= 216
    assert panel["MCT_SGG_CD"].nunique() == 2
    assert panel["SEX_CCD"].nunique() == 2
    assert panel["age_band"].nunique() == 9
    for c in ("amount", "count", "amount_ex", "social_amount", "n_ry", "local_count"):
        assert c in panel.columns


def test_amount_ex_is_smaller_than_amount(panel):
    assert (panel["amount_ex"] <= panel["amount"]).all()
    assert panel["amount_ex"].sum() < panel["amount"].sum()


def test_panel_total_matches_raw_total(card, panel):
    assert panel["amount"].sum() == card["TS_AT"].sum()
    assert panel["count"].sum() == card["USE_CNT"].sum()


def test_truncation_stats_reports_near_cut_share(card):
    stats = card_cohort.truncation_stats(card, by=["age_band"])
    assert len(stats) == 9
    assert stats["near_cut_share"].between(0, 1).all()
    assert (stats["n_cells"] > 0).all()
    assert "observed_combos" in stats.columns
    assert stats["combo_coverage"].between(0, 1).all()


def test_dataset2_use_cnt_has_suppressed_integer_gaps(card):
    """데이터2는 5건 미만 절단에 더해 추가 비식별 처리를 받았다.

    7~10, 14~15, 20~21이 아예 등장하지 않고 등장 구간은 [5,6] [11,13] [16,19] [22~]다.
    이 때문에 절단선 근접도는 USE_CNT <= 6으로 정의해야 한다.
    """
    present = set(card["USE_CNT"].unique())
    for v in card_cohort.MISSING_USE_CNT:
        assert v not in present, f"USE_CNT={v}가 데이터2에 등장한다"
    for v in (5, 6, 11, 12, 13, 16, 17, 18, 19, 22):
        assert v in present
    # 22 이상은 연속이다
    assert set(range(22, 61)) <= present


def test_dataset1_lacks_the_extra_suppression(card):
    """데이터1은 1~4만 없고 7~10 등은 존재한다. 두 파일의 가공 수준이 다르다."""
    d1 = card_cohort.prepare_card(1)
    present = set(d1["USE_CNT"].unique())
    assert set(range(1, 5)).isdisjoint(present)
    assert {7, 8, 9, 10, 14, 15, 20, 21} <= present


def test_prepare_card_handles_corporate_rows():
    """데이터1의 법인카드 행은 AGE_CCD가 '법인'이라 age_band가 <NA>가 된다."""
    d1 = card_cohort.prepare_card(1)
    assert d1["age_band"].isna().sum() == 61_297
    assert d1.loc[d1["is_corporate"], "age_band"].isna().all()
    assert d1.loc[~d1["is_corporate"], "age_band"].notna().all()


def test_local_flag_only_set_for_chuncheon(card):
    # 강남은 CLN_SGG_CD가 시도 단위라 강남구민을 식별할 수 없다
    assert card_cohort.LOCAL_SIDO == {"강원 춘천시": "강원"}
    assert not card.loc[card["MCT_SGG_CD"] == "서울 강남구", "is_local"].any()
    assert card.loc[card["MCT_SGG_CD"] == "강원 춘천시", "is_local"].any()
