"""대면 접촉 기회 지표 테스트.

정의에서 도출한 축들이 하나의 개념을 재는지(내적 일관성)를 회귀로 고정한다.
기존 집단축은 alpha -4.22로 실패했다. 같은 실수를 반복하지 않도록 기준을 박아 둔다.
"""

import numpy as np
import pytest

from src.features import card_cohort, contact


@pytest.fixture(scope="module")
def card():
    return card_cohort.prepare_card(2)


@pytest.fixture(scope="module")
def panel(card):
    return contact.contact_indicators(card, keys=contact.PANEL_KEYS, min_cnt=1000)


@pytest.mark.requires_data
def test_every_category_is_classified(card):
    """90개 업종이 모두 5개 군 중 하나에 속한다. 미분류가 있으면 예외."""
    tagged = contact.tag_tier(card)
    assert tagged["tier"].notna().all()
    assert set(tagged["tier"]) == set(contact.TIERS)


def test_tier_definitions_do_not_overlap():
    seen = []
    for rys in contact.TIERS.values():
        seen.extend(rys)
    assert len(seen) == len(set(seen)), "업종이 두 군에 중복 배정됐다"


@pytest.mark.requires_data
def test_stay_tier_share_is_plausible(card):
    """체류형 대면은 전체 건수의 20% 안팎이어야 한다."""
    tagged = contact.tag_tier(card)
    share = tagged.loc[tagged.is_stay, "USE_CNT"].sum() / tagged["USE_CNT"].sum()
    assert 0.15 < share < 0.30


@pytest.mark.requires_data
def test_indicators_are_in_range(panel):
    assert panel["contact_share"].between(0, 1).all()
    assert panel["contact_breadth"].between(0, 1).all()
    # 24종 균등분포의 엔트로피 상한은 log(24)
    assert (panel["contact_entropy"] <= np.log(len(contact.CONTACT_STAY)) + 1e-9).all()


@pytest.mark.requires_data
def test_coherence_passes_threshold(panel):
    """핵심 검정 — 세 축이 하나의 개념을 잰다. 실측 alpha 0.72."""
    res = contact.coherence(panel, contact.PREDICTIONS)
    assert res["alpha"] >= 0.70
    assert res["min_inter_item"] > 0, "항목 간 음의 상관이 있으면 합산할 수 없다"


@pytest.mark.requires_data
def test_old_cohort_axes_still_fail(card):
    """기존 집단축은 여전히 실패한다. 왜 바꿨는지를 고정해 둔다."""
    from src.features import isolation

    old = isolation.cohort_indicators(card_cohort.cohort_panel(card))
    res = contact.coherence(old, ["social_share", "amount_per_use", "ry_diversity"])
    assert res["alpha"] < 0, f"기존 축 alpha가 {res['alpha']:.3f}로 예상과 다르다"


@pytest.mark.requires_data
def test_medical_inclusion_breaks_coherence(card):
    """의료를 대면 접촉에 넣으면 일관성이 무너진다. 분류 결정의 근거."""
    tagged = contact.tag_tier(card)
    tagged["is_stay"] = tagged.is_stay | tagged["tier"].eq("C_의료")
    d = tagged[tagged["tier"].isin(contact.DENOM_DAILY + ("C_의료",))]
    keys = contact.COHORT_KEYS
    tot = d.groupby(keys, observed=True)["USE_CNT"].sum().rename("total_cnt")
    st = d[d.is_stay]
    by = st.groupby(keys + ["MCT_RY_CD"], observed=True)["USE_CNT"].sum()
    out = (
        tot.to_frame()
        .join(st.groupby(keys, observed=True)["USE_CNT"].sum().rename("stay_cnt"))
        .join(
            by.groupby(keys, observed=True)
            .apply(lambda s: contact._entropy(s.to_numpy()))
            .rename("contact_entropy")
        )
        .join(by.groupby(keys, observed=True).size().rename("n"))
        .fillna(0)
    )
    out["contact_share"] = out.stay_cnt / out.total_cnt
    out["contact_breadth"] = out.n / (len(contact.CONTACT_STAY) + len(contact.CONTACT_CARE))
    res = contact.coherence(out.reset_index(), contact.PREDICTIONS)
    assert res["alpha"] < 0.5, "의료 포함 시 일관성이 무너져야 한다 (실측 0.18)"


@pytest.mark.requires_data
def test_monthly_reliability_is_high(panel):
    """월 간 순위가 유지된다. 지표가 안정적으로 무언가를 잰다는 뜻."""
    for col in ("contact_share", "contact_entropy"):
        piv = panel.pivot_table(
            index=["MCT_SGG_CD", "SEX_CCD", "age_band"], columns="ym", values=col
        )
        cm = piv.corr(method="spearman").to_numpy()
        tri = cm[np.triu_indices(len(cm), 1)]
        assert tri.mean() > 0.85, f"{col} 월간 신뢰도 {tri.mean():.3f}"


@pytest.mark.requires_data
def test_age_controlled_coherence_is_documented_as_weak(panel):
    """연령을 통제하면 일관성이 기준 미달로 떨어진다. 한계를 고정해 둔다."""
    rz = panel.copy()
    for c in contact.PREDICTIONS:
        rz[c] = panel[c] - panel.groupby("age_band")[c].transform("mean")
    res = contact.coherence(rz, contact.PREDICTIONS)
    assert res["alpha"] < 0.70, "연령 통제 후에도 통과한다면 문서를 갱신해야 한다"
