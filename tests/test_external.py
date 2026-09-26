"""SGIS 외부 데이터 로더와 방향성 검증 결과 회귀 테스트.

이 프로젝트에서 가장 오래 막혀 있던 것이 방향 가정의 외부 검증이었다.
SGIS 행정동 코드가 SK BLOCK_CD 앞 8자리와 같은 체계라는 사실이 그것을 풀었다.
검증 결과를 여기에 고정한다.
"""

import pytest

from src.data import external, regions
from src.features import isolation, sk_dong

AXES = ["wkdy_cv", "night_share", "peak_ratio"]


@pytest.fixture(scope="module")
def census():
    return external.census_dong_panel().set_index("dong_cd")


@pytest.fixture(scope="module")
def joined(census):
    panel = sk_dong.build_space_panel()
    ind = isolation.space_indicators(panel).set_index("dong_cd")
    norm = ind[[]].copy()
    for c in AXES:
        norm[c] = isolation.minmax(ind[c], invert=True)
    ind["score"] = isolation.composite(norm, AXES)
    return ind.join(census, how="inner")


def test_year_selection_is_explicit():
    """연도가 다른 두 파일이 있다. glob 정렬은 연도 순서와 어긋나므로 명시 선택해야 한다."""
    f24 = external._find("*성연령별인구.csv", "2024")
    f23 = external._find("*성연령별인구.csv", "2023")
    assert "2024년" in f24.name
    assert "2023년" in f23.name
    assert f24 != f23
    with pytest.raises(FileNotFoundError):
        external._find("*성연령별인구.csv", "2099")


def test_default_year_is_2024(census):
    """SK 데이터가 2025-07~12이므로 가장 가까운 2024를 쓴다. 강남 합계로 확인."""
    assert external.DEFAULT_YEAR == "2024"
    gn = census[census.sgg_name == "서울 강남구"]["pop"].sum()
    assert 515_000 < gn < 530_000, f"강남 합계 {gn:,.0f} — 2023년 파일을 읽었을 수 있다"


def test_sgis_codes_match_sk_at_dong_level(census):
    """SGIS 행정동 코드가 SK BLOCK_CD 앞 8자리와 같은 체계다."""
    assert len(census) == 47
    assert set(census.sgg_name) == set(regions.SGG_NAMES.values())
    assert (census.dong_name != "?").all(), "이름이 붙지 않은 동이 있다"


def test_join_covers_all_47_dongs(joined):
    assert len(joined) == 47


def test_population_is_plausible(census):
    """강남 약 54만, 춘천 약 28만 규모여야 한다."""
    by = census.groupby("sgg_name")["pop"].sum()
    assert 450_000 < by["서울 강남구"] < 620_000
    assert 220_000 < by["강원 춘천시"] < 330_000


def test_sk_senior_flow_tracks_census_senior_ratio(joined):
    """SK 60대+ 유동 비중이 통계청 65세+ 인구 비율과 강하게 맞는다.

    제공 데이터의 신뢰도 근거. 실측 춘천 +0.83 / 강남 +0.50.
    """
    for sgg, g in joined.groupby("sgg_name"):
        r = g.senior_share.corr(g.senior_ratio, method="spearman")
        assert r > 0.45, f"{sgg} 상관 {r:.3f}"


def test_night_share_direction_holds_in_chuncheon(joined):
    """night_share 방향 가정('낮을수록 위험')이 춘천에서 확인된다.

    원값과 고령비율이 음의 상관이면, invert 후 양이 되어 가정에 부합한다.
    """
    cc = joined[joined.sgg_name == "강원 춘천시"]
    assert cc.night_share.corr(cc.senior_ratio, method="spearman") < -0.5
    assert cc.night_share.corr(cc.elderly_dependency, method="spearman") < -0.6


def test_wkdy_cv_direction_is_rejected(joined):
    """wkdy_cv 방향 가정은 기각됐다.

    '낮을수록 위험'을 가정했으나 춘천에서 고령비율과 양의 상관이다.
    주말 관광 유입 때문으로 보인다. 이 사실을 고정해 둔다.
    """
    cc = joined[joined.sgg_name == "강원 춘천시"]
    assert cc.wkdy_cv.corr(cc.senior_ratio, method="spearman") > 0.3


def test_axes_do_not_work_in_gangnam(joined):
    """강남에서는 모든 축이 외부 지표와 무관하다. 한계를 고정한다."""
    gn = joined[joined.sgg_name == "서울 강남구"]
    for c in AXES + ["score"]:
        r = abs(gn[c].corr(gn.senior_ratio, method="spearman"))
        assert r < 0.45, f"{c} 상관 {r:.3f} — 강남에서 관계가 생겼다면 문서를 갱신할 것"


def test_gangnam_has_extreme_inflow(joined):
    """강남은 거주인구 대비 유동인구가 압도적이라 주민 신호가 묻힌다."""
    joined = joined.assign(ratio=joined.total / joined["pop"])
    gn = joined[joined.sgg_name == "서울 강남구"]
    cc = joined[joined.sgg_name == "강원 춘천시"]
    assert gn.ratio.max() > 40
    assert gn.ratio.median() > cc.ratio.median()
