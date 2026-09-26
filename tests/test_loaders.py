"""로더 테스트 — 12월 중복 제거와 타입 변환이 핵심."""

import pandas as pd

from src.data import loaders


def test_load_sk_age_july_shape():
    df = loaders.load_sk("age", "202507")
    assert len(df) == 98_129
    assert df.shape[1] == 16
    # pandas 3.0에서 dtype=str는 StringDtype을 만든다
    assert pd.api.types.is_string_dtype(df["STD_YM"])
    assert pd.api.types.is_string_dtype(df["BLOCK_CD"])
    assert df["BLOCK_CD"].str.len().eq(20).all()


def test_december_time_duplicates_removed():
    raw = loaders.load_sk("time", "202512", dedupe=False)
    dedup = loaders.load_sk("time", "202512", dedupe=True)
    assert len(raw) == 185_090
    assert len(dedup) == 92_545
    assert len(raw) == 2 * len(dedup)


def test_december_wkdy_duplicates_removed():
    dedup = loaders.load_sk("wkdy", "202512")
    assert len(dedup) == 121_267


def test_non_december_files_have_no_duplicates():
    for ym in ("202507", "202510"):
        df = loaders.load_sk("time", ym, dedupe=False)
        assert df.duplicated(subset=loaders.SK_PK).sum() == 0


def test_load_sk_all_months_concatenates():
    df = loaders.load_sk("age")
    assert len(df) == 596_252  # 6개월 합계
    assert sorted(df["STD_YM"].unique()) == list(loaders.MONTHS)


def test_sk_value_cols_counts():
    assert len(loaders.sk_value_cols(loaders.load_sk("age", "202507"))) == 12
    assert len(loaders.sk_value_cols(loaders.load_sk("time", "202507"))) == 24
    assert len(loaders.sk_value_cols(loaders.load_sk("wkdy", "202507"))) == 7


def test_sk_values_have_no_nulls():
    df = loaders.load_sk("age", "202507")
    cols = loaders.sk_value_cols(df)
    assert df[cols].isnull().sum().sum() == 0


def test_load_card_dataset2():
    df = loaders.load_card(2)
    assert len(df) == 1_806_800
    assert list(df.columns) == [
        "TA_YMD",
        "MCT_SGG_CD",
        "MCT_RY_CD",
        "CLN_SGG_CD",
        "SEX_CCD",
        "AGE_CCD",
        "TS_AT",
        "USE_CNT",
    ]
    assert pd.api.types.is_integer_dtype(df["TS_AT"])
    assert pd.api.types.is_integer_dtype(df["USE_CNT"])
    assert df["USE_CNT"].min() == 5
    assert df["TS_AT"].min() == 6
    assert df["TA_YMD"].nunique() == 184
    assert df["SEX_CCD"].nunique() == 2
    assert df["MCT_RY_CD"].nunique() == 90


def test_load_card_dataset1_has_corporate():
    df = loaders.load_card(1)
    assert len(df) == 1_044_710
    assert "TIME_GB" in df.columns
    assert "법인" in set(df["SEX_CCD"])


def test_dedupe_report_flags_only_december():
    rep = loaders.dedupe_report()
    assert len(rep) == 18
    dropped = rep[rep["dropped"] > 0]
    assert set(dropped["ym"]) == {"202512"}
    assert set(dropped["table"]) == {"time", "wkdy"}
    assert rep["rows_raw"].sum() == 2_101_675
    assert rep["rows_dedup"].sum() == 1_887_863
