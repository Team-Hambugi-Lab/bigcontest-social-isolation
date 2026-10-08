"""BLOCK_CD 파싱과 좌표 변환 테스트."""

import pandas as pd
import pytest

from src.data import loaders, regions


def test_add_region_codes_splits_correctly():
    df = pd.DataFrame({"BLOCK_CD": ["11230510101020000001"]})
    out = regions.add_region_codes(df)
    assert out.loc[0, "sgg_cd"] == "11230"
    assert out.loc[0, "dong_cd"] == "11230510"
    assert out.loc[0, "tong_cd"] == "1123051010"
    assert out.loc[0, "sgg_name"] == "서울 강남구"


def test_unknown_sgg_gets_none_name():
    df = pd.DataFrame({"BLOCK_CD": ["99999510101020000001"]})
    out = regions.add_region_codes(df)
    assert pd.isna(out.loc[0, "sgg_name"])


@pytest.mark.requires_data
def test_target_dong_counts_match_admin_divisions():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    gangnam = df[df["sgg_cd"] == "11230"]
    chuncheon = df[df["sgg_cd"] == "32010"]
    assert gangnam["dong_cd"].nunique() == 22  # 강남구 행정동 22개
    assert chuncheon["dong_cd"].nunique() == 25  # 춘천시 1읍 9면 15동


@pytest.mark.requires_data
def test_filter_target_sgg_drops_border_grids():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    kept = regions.filter_target_sgg(df)
    assert set(kept["sgg_cd"]) == set(regions.TARGET_SGG)
    assert len(df) - len(kept) == 60  # 경계 격자 60행


@pytest.mark.requires_data
def test_add_wgs84_places_gangnam_and_chuncheon():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    df = regions.add_wgs84(regions.filter_target_sgg(df))
    gn = df[df["sgg_cd"] == "11230"]
    cc = df[df["sgg_cd"] == "32010"]
    # 강남구 중심 근방
    assert 37.45 < gn["lat"].mean() < 37.55
    assert 127.0 < gn["lon"].mean() < 127.12
    # 춘천시 중심 근방
    assert 37.7 < cc["lat"].mean() < 38.05
    assert 127.5 < cc["lon"].mean() < 127.95


@pytest.mark.requires_data
def test_gangnam_observed_area_near_actual():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    gn = df[df["sgg_cd"] == "11230"]
    area_km2 = len(gn) * regions.GRID_AREA_M2 / 1e6
    assert 35 < area_km2 < 42  # 실제 강남구 39.5 km2
