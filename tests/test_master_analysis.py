"""집계구 마스터 → 분석용 피처 테이블(이슈 #10) 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import master_analysis as ma

SGIS_SAMPLE = [
    "SGIS2024_cp2_bem_01",  # 제외: 중분류 종사자수
    "SGIS2024_cp_bem_001",  # 제외: 대분류 종사자수
    "SGIS2024_ho_yr_005",  # 유지: 2010년 이전 건축연도 구간
    "SGIS2024_ho_yr_006",  # 제외
    "SGIS2024_ho_yr_020",  # 제외
    "SGIS2024_ga_sd_004",  # 제외: 전부 공백
    "SGIS2024_ga_sd_005",  # 유지: 1인가구
    "SGIS2024_cp2_bnu_35",  # 제외: 대분류와 중복
    "SGIS2024_cp2_bnu_47",  # 유지: 소매업
    "SGIS2024_to_em_020",  # 유지: 총종사자수
]


class TestDropColumns:
    def test_sgis_drop_columns_follows_meeting_decision(self):
        assert ma.sgis_drop_columns(SGIS_SAMPLE) == [
            "SGIS2024_cp2_bem_01",
            "SGIS2024_cp_bem_001",
            "SGIS2024_ho_yr_006",
            "SGIS2024_ho_yr_020",
            "SGIS2024_ga_sd_004",
            "SGIS2024_cp2_bnu_35",
        ]

    def test_sgis_drop_columns_ignores_non_sgis(self):
        assert ma.sgis_drop_columns(["TMST_00_sum", "cp2_bem_01"]) == []

    def test_sk_mean_columns(self):
        cols = ["TMST_00_sum", "TMST_00_mean", "MAN_FLOW_POP_CNT_10G_mean"]
        assert ma.sk_mean_columns(cols) == ["TMST_00_mean", "MAN_FLOW_POP_CNT_10G_mean"]

    def test_sk_redundant_quality_columns_keeps_representatives(self):
        cols = [
            "TMST_00_n_valid",
            "TMST_00_missing_rate",
            "age_n_partial",
            "hour_n_complete",
            "hour_incomplete_rate",
        ]
        assert ma.sk_redundant_quality_columns(cols) == [
            "TMST_00_n_valid",
            "TMST_00_missing_rate",
            "age_n_partial",
        ]

    @pytest.mark.parametrize(
        ("col", "family"),
        [
            ("MAN_FLOW_POP_CNT_60GU_n_valid", "age"),
            ("WMAN_FLOW_POP_CNT_10G_missing_rate", "age"),
            ("TMST_23_n_valid", "hour"),
            ("FLOW_POP_CNT_SUN_missing_rate", "weekday"),
        ],
    )
    def test_quality_family(self, col, family):
        assert ma.quality_family(col) == family

    def test_quality_family_rejects_unknown(self):
        with pytest.raises(ValueError, match="N_GRID"):
            ma.quality_family("N_GRID")

    def test_drop_reasons_excludes_quality_by_default(self):
        cols = ["SGIS2024_ga_sd_004", "TMST_00_mean", "TMST_00_n_valid"]
        assert set(ma.drop_reasons(cols)) == {"SGIS2024_ga_sd_004", "TMST_00_mean"}
        assert set(ma.drop_reasons(cols, drop_sk_quality=True)) == set(cols)


@pytest.fixture(scope="module")
def master():
    from src.data import paths

    return pd.read_csv(paths.master_files()["master"], dtype=ma.READ_DTYPES)


@pytest.mark.requires_data
class TestDropColumnsOnMaster:
    def test_counts_match_issue(self, master):
        assert len(ma.sgis_drop_columns(master.columns)) == 113
        assert len(ma.sk_mean_columns(master.columns)) == 43
        assert len(ma.sk_redundant_quality_columns(master.columns)) == 89

    def test_mean_equals_sum_over_n_valid(self, master):
        for col in ma.sk_mean_columns(master.columns):
            base = col.removesuffix("_mean")
            expected = master[f"{base}_sum"] / master[f"{base}_n_valid"]
            assert np.allclose(master[col], expected, equal_nan=True), col

    def test_quality_columns_carry_no_extra_information(self, master):
        for col in ma.sk_redundant_quality_columns(master.columns):
            if col in ma.SK_PARTIAL_COLS:
                assert (master[col] == 0).all(), col
                continue
            family = ma.quality_family(col)
            rep = (
                f"{family}_n_complete"
                if col.endswith("_n_valid")
                else f"{family}_incomplete_rate"
            )
            assert master[col].equals(master[rep]) or np.allclose(
                master[col], master[rep], equal_nan=True
            ), col
