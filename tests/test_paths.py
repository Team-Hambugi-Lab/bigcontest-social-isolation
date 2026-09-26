"""경로 모듈 테스트 — NFD 한글 파일명 접근이 핵심."""

import pytest

from src.data import paths


def test_raw_dirs_exist():
    assert paths.SK_DIR.is_dir()
    assert paths.CARD_DIR.is_dir()


def test_sk_file_returns_existing_path():
    p = paths.sk_file("age", "202507")
    assert p.exists()
    assert p.name == "flow_age_pop_202507.csv"


def test_sk_file_rejects_unknown_table():
    with pytest.raises(ValueError, match="table"):
        paths.sk_file("bogus", "202507")


def test_card_file_finds_nfd_korean_name():
    # 한글 파일명이 NFD로 저장되어 있어 문자열 리터럴로는 열리지 않는다
    p2 = paths.card_file(2)
    assert p2.exists()
    assert p2.stat().st_size > 100_000_000

    p1 = paths.card_file(1)
    assert p1.exists()
    assert p1 != p2


def test_all_18_sk_files_present():
    found = [paths.sk_file(t, m) for t in paths.SK_TABLES for m in paths.MONTHS]
    assert len(found) == 18
    assert all(p.exists() for p in found)


def test_list_raw_files_counts_20():
    inv = paths.list_raw_files()
    assert len(inv) == 20
    assert set(inv["group"]) == {"sk", "card"}
