"""SGIS 외부 데이터 로더 회귀 테스트."""

import pytest

from src.data import external, regions

pytestmark = pytest.mark.requires_data


@pytest.fixture(scope="module")
def census():
    return external.census_dong_panel().set_index("dong_cd")


def test_year_selection_is_explicit():
    """파일명에 포함된 연도로 원하는 통계 연도를 명시 선택한다."""
    f24 = external._find("*성연령별인구.csv", "2024")
    assert "2024" in f24.name
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


def test_population_is_plausible(census):
    """강남 약 54만, 춘천 약 28만 규모여야 한다."""
    by = census.groupby("sgg_name")["pop"].sum()
    assert 450_000 < by["서울 강남구"] < 620_000
    assert 220_000 < by["강원 춘천시"] < 330_000
