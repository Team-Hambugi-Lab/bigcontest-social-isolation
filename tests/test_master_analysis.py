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


def _status_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TOT_OA_CD": ["A", "B"],
            "SGIS2024_cp2_bnu_47": ["no_record", "numeric"],
            "SGIS2024_cp_bnu_001": ["numeric", "no_record"],
            "SGIS2024_ga_sd_005": ["no_record", "source_na"],
        }
    )


class TestFillBusinessNoRecord:
    def _df(self) -> pd.DataFrame:
        # 같은 집계구가 두 달 반복되는 마스터 구조를 흉내 낸다
        return pd.DataFrame(
            {
                "STD_YM": ["202507", "202507", "202508"],
                "TOT_OA_CD": ["A", "B", "A"],
                "SGIS2024_cp2_bnu_47": [np.nan, 3.0, np.nan],
                "SGIS2024_cp_bnu_001": [5.0, np.nan, 5.0],
                "SGIS2024_ga_sd_005": [np.nan, np.nan, np.nan],
            }
        )

    def test_no_record_business_counts_become_zero(self):
        out = ma.fill_business_no_record(self._df(), _status_frame())
        assert out["SGIS2024_cp2_bnu_47"].tolist() == [0.0, 3.0, 0.0]
        assert out["SGIS2024_cp_bnu_001"].tolist() == [5.0, 0.0, 5.0]

    def test_non_business_columns_stay_missing(self):
        out = ma.fill_business_no_record(self._df(), _status_frame())
        assert out["SGIS2024_ga_sd_005"].isna().all()

    def test_input_is_not_modified(self):
        df = self._df()
        before = df.copy()
        ma.fill_business_no_record(df, _status_frame())
        pd.testing.assert_frame_equal(df, before)

    def test_business_count_columns(self):
        cols = ["SGIS2024_cp2_bnu_47", "SGIS2024_cp_bnu_001", "SGIS2024_cp2_bem_01"]
        assert ma.business_count_columns(cols) == cols[:2]


def _sk_frame() -> pd.DataFrame:
    """SK 매칭 집계구 1행 + 미매칭 1행 + 소표본 1행."""
    rows = {"N_GRID": [10, 0, 2], "HAS_SK_POINTS": [True, False, True]}
    for h in ma.HOURS:
        rows[f"TMST_{h}_sum"] = [1.0, np.nan, 1.0]
    rows["TMST_00_sum"] = [25.0, np.nan, 1.0]  # 첫 행 합계 = 25 + 23 = 48
    for d in ma.WEEKDAYS:
        rows[f"FLOW_POP_CNT_{d}_sum"] = [10.0, np.nan, 1.0]  # 첫 행 합계 = 70
    for g in ma.AGE_GROUPS:
        rows[f"MAN_FLOW_POP_CNT_{g}_sum"] = [5.0, np.nan, 1.0]
        rows[f"WMAN_FLOW_POP_CNT_{g}_sum"] = [5.0, np.nan, 1.0]  # 첫 행 합계 = 60
    return pd.DataFrame(rows)


class TestAddShareFeatures:
    def test_adds_40_columns(self):
        out = ma.add_share_features(_sk_frame())
        assert out.shape[1] == _sk_frame().shape[1] + 40

    def test_shares_sum_to_one_per_table(self):
        out = ma.add_share_features(_sk_frame()).iloc[[0, 2]]
        for prefix in ("share_hour_", "share_wkdy_", "share_age_"):
            assert np.allclose(out.filter(like=prefix).sum(axis=1), 1.0), prefix

    def test_share_values(self):
        out = ma.add_share_features(_sk_frame()).iloc[0]
        assert out["share_hour_00"] == pytest.approx(25 / 48)
        assert out["share_dawn"] == pytest.approx((25 + 5) / 48)
        assert out["share_weekend"] == pytest.approx(2 / 7)
        assert out["share_age_60GU"] == pytest.approx(10 / 60)

    def test_unmatched_row_has_missing_shares_not_zero(self):
        out = ma.add_share_features(_sk_frame()).iloc[1]
        shares = out.filter(like="share_")
        assert shares.isna().all()

    def test_zero_total_gives_missing_share(self):
        df = _sk_frame().iloc[[0]].copy()
        df[[f"TMST_{h}_sum" for h in ma.HOURS]] = 0.0
        out = ma.add_share_features(df)
        assert out.filter(like="share_hour_").isna().all(axis=None)
        assert np.isnan(out["share_dawn"].iloc[0])

    def test_small_sample_flag_only_for_matched_blocks(self):
        out = ma.add_share_features(_sk_frame())
        assert out["is_small_sample"].tolist() == [False, False, True]


def _mini_master() -> pd.DataFrame:
    sk = _sk_frame().iloc[[0, 1]].reset_index(drop=True)
    meta = pd.DataFrame(
        {
            "STD_YM": ["202507", "202507"],
            "TOT_OA_CD": ["B", "A"],  # 정렬 확인용으로 역순
            "TMST_00_mean": [1.0, np.nan],
            "TMST_00_n_valid": [3, 0],
            "SGIS2024_ga_sd_004": [np.nan, np.nan],
            "SGIS2024_cp2_bnu_47": [np.nan, 2.0],
            "SGIS2024_ga_sd_005": [7.0, np.nan],
        }
    )
    return pd.concat([meta, sk], axis=1)


def _mini_status() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TOT_OA_CD": ["A", "B"],
            "SGIS2024_cp2_bnu_47": ["numeric", "no_record"],
            "SGIS2024_ga_sd_005": ["no_record", "numeric"],
        }
    )


class TestBuildMasterAnalysis:
    def test_drops_agreed_columns_and_keeps_quality_by_default(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status())
        assert "SGIS2024_ga_sd_004" not in out.columns
        assert "TMST_00_mean" not in out.columns
        assert "TMST_00_n_valid" in out.columns

    def test_drop_sk_quality_option(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status(), drop_sk_quality=True)
        assert "TMST_00_n_valid" not in out.columns

    def test_keys_first_and_sorted(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status())
        assert out.columns[:2].tolist() == ma.KEY_COLS
        assert out["TOT_OA_CD"].tolist() == ["A", "B"]

    def test_input_is_not_modified(self):
        master = _mini_master()
        before = master.copy()
        ma.build_master_analysis(master, _mini_status())
        pd.testing.assert_frame_equal(master, before)


class TestBuildDictionary:
    def test_lists_kept_derived_and_dropped_columns(self):
        master = _mini_master()
        out = ma.build_master_analysis(master, _mini_status())
        sgis_dict = pd.DataFrame(
            {
                "OUTPUT_COLUMN": ["SGIS2024_ga_sd_005", "SGIS2024_cp2_bnu_47"],
                "VARIABLE_NAME": ["1인가구", "소매업"],
            }
        )

        d = ma.build_dictionary(master.columns, out, sgis_dict).set_index("COLUMN")

        assert d.columns.tolist() == ["STATUS", "SOURCE", "DESCRIPTION", "FORMULA_OR_REASON"]
        assert set(d.index) == set(out.columns) | {"SGIS2024_ga_sd_004", "TMST_00_mean"}
        assert d.loc["SGIS2024_ga_sd_005", "DESCRIPTION"] == "1인가구"
        assert d.loc["share_hour_00", "STATUS"] == "파생"
        assert d.loc["TMST_00_mean", "STATUS"] == "제외"
        assert "no_record" in d.loc["SGIS2024_cp2_bnu_47", "FORMULA_OR_REASON"]

    def test_derived_definition_rejects_unknown(self):
        with pytest.raises(KeyError):
            ma.derived_definition("TMST_00_sum")


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


@pytest.fixture(scope="module")
def status():
    from src.data import paths

    return pd.read_csv(paths.master_files()["status"], dtype={"TOT_OA_CD": str})


@pytest.mark.requires_data
class TestFillBusinessNoRecordOnMaster:
    def test_business_sums_match_total_after_fill(self, master, status):
        out = ma.fill_business_no_record(master, status)
        for pattern in (r"^SGIS2024_cp_bnu_\d+$", r"^SGIS2024_cp2_bnu_\d+$"):
            total = out.filter(regex=pattern).sum(axis=1)
            assert np.allclose(total, out["SGIS2024_to_fa_010"]), pattern

    def test_one_person_household_missing_is_kept(self, master, status):
        out = ma.fill_business_no_record(master, status)
        missing = out.loc[out["SGIS2024_ga_sd_005"].isna(), "TOT_OA_CD"].nunique()
        assert missing == 59


@pytest.fixture(scope="module")
def analysis(master, status):
    return ma.build_master_analysis(master, status)


@pytest.mark.requires_data
class TestMasterAnalysisOnMaster:
    def test_shape_and_keys(self, analysis):
        assert analysis.shape == (10_188, 375)  # 491 - 113 - 43 + 40
        assert not analysis.duplicated(ma.KEY_COLS).any()
        assert analysis["TOT_OA_CD"].str.len().eq(14).all()
        assert analysis["TOT_OA_CD"].nunique() == 1_698

    def test_drop_sk_quality_shape(self, master, status):
        out = ma.build_master_analysis(master, status, drop_sk_quality=True)
        assert out.shape == (10_188, 286)

    def test_shares_sum_to_one_for_matched_blocks(self, analysis):
        matched = analysis[analysis["HAS_SK_POINTS"]]
        for prefix in ("share_hour_", "share_wkdy_", "share_age_"):
            assert np.allclose(matched.filter(like=prefix).sum(axis=1), 1.0), prefix

    def test_unmatched_blocks_kept_with_missing_shares(self, analysis):
        unmatched = analysis[~analysis["HAS_SK_POINTS"]]
        assert unmatched["TOT_OA_CD"].nunique() == 3
        assert unmatched.filter(like="share_").isna().all(axis=None)

    def test_small_sample_blocks(self, analysis):
        assert analysis.loc[analysis["is_small_sample"], "TOT_OA_CD"].nunique() == 150

    def test_master_not_modified(self, master, status):
        before = master.copy()
        ma.build_master_analysis(master, status)
        pd.testing.assert_frame_equal(master, before)
