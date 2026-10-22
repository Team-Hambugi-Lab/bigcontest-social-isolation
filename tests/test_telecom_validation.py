"""통신 관심집단 연관 검증(#25) 1단계 테스트."""

import struct
import unicodedata

import numpy as np
import pandas as pd
import pytest

from src.data import paths
from src.evaluation import telecom_validation as tv


def _cells(rows: list[tuple]) -> pd.DataFrame:
    """(ym, dong_cd, sex, age, pop, hh_single, n_isolated) 튜플로 long 테이블을 만든다."""
    cols = ["ym", "dong_cd", "sex", "age", "pop", "hh_single", "n_isolated"]
    df = pd.DataFrame(rows, columns=cols)
    return df.assign(dong_nm=df["dong_cd"].map({"A": "가동", "B": "나동"}))


def test_target_ratio_is_sum_over_sum_not_mean_of_cells():
    # 65세 셀: 1/10, 70세 셀: 90/100 -> 셀 평균은 0.5, 합 비율은 91/110
    df = _cells(
        [
            ("202507", "A", 1, 65, 100, 10, 1),
            ("202507", "A", 2, 70, 1000, 100, 90),
        ]
    )
    out = tv.target_ratios(df).set_index("dong_cd")
    assert out.loc["A", "ratio_1in_old65"] == pytest.approx(91 / 110)
    assert out.loc["A", "ratio_pop_old65"] == pytest.approx(91 / 1100)


def test_target_groups_filter_sex_and_age():
    df = _cells(
        [
            ("202507", "A", 1, 50, 100, 10, 2),  # male5064, all
            ("202507", "A", 2, 55, 100, 10, 4),  # 여성이라 male5064 아님
            ("202507", "A", 1, 65, 100, 10, 6),  # 65세라 male5064 아님, old65
        ]
    )
    out = tv.target_ratios(df).set_index("dong_cd")
    assert out.loc["A", "ratio_1in_male5064"] == pytest.approx(2 / 10)
    assert out.loc["A", "ratio_1in_old65"] == pytest.approx(6 / 10)
    assert out.loc["A", "ratio_1in_all"] == pytest.approx(12 / 30)


def test_six_month_value_is_mean_of_monthly_ratios():
    df = _cells(
        [
            ("202507", "A", 1, 65, 100, 10, 1),
            ("202508", "A", 1, 65, 100, 20, 6),
        ]
    )
    out = tv.target_ratios(df).set_index("dong_cd")
    assert out.loc["A", "ratio_1in_old65"] == pytest.approx((0.1 + 0.3) / 2)


def test_cell_ratios_average_months_per_cell():
    df = _cells(
        [
            ("202507", "A", 1, 20, 100, 10, 1),
            ("202508", "A", 1, 20, 300, 30, 9),
            ("202507", "B", 2, 20, 50, 5, 5),
        ]
    )
    out = tv.cell_ratios(df).set_index("dong_cd")
    assert out.loc["A", "n_months"] == 2
    assert out.loc["A", "ratio_1in"] == pytest.approx((0.1 + 0.3) / 2)
    assert out.loc["A", "ratio_pop"] == pytest.approx((0.01 + 0.03) / 2)
    assert out.loc["B", "ratio_1in"] == pytest.approx(1.0)


def test_functions_do_not_mutate_input():
    df = _cells([("202507", "A", 1, 65, 100, 10, 1)])
    before = df.copy()
    tv.cell_ratios(df)
    tv.target_ratios(df)
    pd.testing.assert_frame_equal(df, before)


def test_validate_rejects_wrong_dong_count():
    df = _cells([("202507", "A", 1, 65, 100, 10, 1)])
    with pytest.raises(ValueError, match="22"):
        tv.validate_gangnam(df)


def test_ym_from_file(tmp_path):
    assert tv.ym_from_file(tmp_path / "2025.07월_10개_관심집단수.xlsx") == "202507"


def test_interest_group_files_matches_nfd_names(tmp_path):
    folder = tmp_path / unicodedata.normalize("NFD", "서울_10개_관심집단수")
    folder.mkdir()
    for m in ("07", "08", "09", "10", "11", "12"):
        name = unicodedata.normalize("NFD", f"2025.{m}월_10개_관심집단수.xlsx")
        (folder / name).write_text("x")
    (folder / "other.xlsx").write_text("x")

    found = paths.interest_group_files(tmp_path)

    assert [tv.ym_from_file(p) for p in found] == list(paths.MONTHS)


def test_interest_group_files_rejects_missing_months(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "2025.07월_10개_관심집단수.xlsx").write_text("x")
    with pytest.raises(FileNotFoundError, match="found 1"):
        paths.interest_group_files(tmp_path)


def test_to_sgis_code_appends_zero_except_renamed_dong():
    out = tv.to_sgis_code(pd.Series(["1123051", "1123074"]))
    # 일원2동은 앞 7자리가 신사동과 겹치는 개포3동 코드로 간다
    assert out.tolist() == ["11230510", "11230511"]


def _telecom_names(pairs):
    return pd.DataFrame(pairs, columns=["dong_cd", "dong_nm"])


def _sgis_names(pairs):
    return pd.DataFrame(pairs, columns=["ADM_CD", "ADM_NM"])


def _gangnam22():
    """신사동(1123051)·일원2동(1123074)과 가상 동 20개로 22개 동을 만든다."""
    telecom = [("1123051", "신사동"), ("1123074", "일원2동")]
    sgis = [("11230510", "신사동"), ("11230511", "개포3동"), ("32010110", "춘천동")]
    for i in range(20):
        telecom.append((f"11230{i:02d}", f"동{i}"))
        sgis.append((f"11230{i:02d}0", f"동{i}"))
    return _telecom_names(telecom), _sgis_names(sgis)


def test_dong_code_table_matches_22_and_flags_exception():
    telecom, sgis = _gangnam22()
    table = tv.dong_code_table(telecom, sgis).set_index("dong_cd")
    assert len(table) == 22
    assert table.loc["1123074", "ADM_CD"] == "11230511"
    assert table.loc["1123074", "code_exception"]
    assert not table.loc["1123074", "name_match"]
    assert table.loc["1123051", "ADM_CD"] == "11230510"


def test_dong_code_table_rejects_unmatched_dong():
    telecom, sgis = _gangnam22()
    with pytest.raises(ValueError, match="미매칭"):
        tv.dong_code_table(telecom, sgis[sgis["ADM_CD"] != "11230511"])


def test_dong_code_table_rejects_name_mismatch_outside_exceptions():
    telecom, sgis = _gangnam22()
    sgis.loc[sgis["ADM_CD"] == "11230510", "ADM_NM"] = "다른동"
    with pytest.raises(ValueError, match="이름"):
        tv.dong_code_table(telecom, sgis)


def _write_dbf(path, fields, records, deleted=()):
    """문자 필드만 있는 최소 dBASE III 파일을 쓴다."""
    header_len = 32 + 32 * len(fields) + 1
    record_len = 1 + sum(n for _, n in fields)
    out = bytearray(b"\x03" + bytes(3))
    out += struct.pack("<IHH", len(records), header_len, record_len) + bytes(20)
    for name, length in fields:
        out += name.encode().ljust(11, b"\0") + b"C" + bytes(4) + bytes([length]) + bytes(15)
    out += b"\x0d"
    for i, rec in enumerate(records):
        out += b"*" if i in deleted else b" "
        for (_, length), value in zip(fields, rec, strict=True):
            out += value.encode("utf-8").ljust(length, b" ")
    path.write_bytes(bytes(out))


def test_read_dbf_reads_utf8_fields_and_skips_deleted(tmp_path):
    f = tmp_path / "t.dbf"
    fields = [("ADM_CD", 8), ("ADM_NM", 12)]
    _write_dbf(f, fields, [("11230510", "신사동"), ("11230511", "개포3동"), ("x", "y")], {2})
    out = tv.read_dbf(f)
    assert out.to_dict("list") == {
        "ADM_CD": ["11230510", "11230511"],
        "ADM_NM": ["신사동", "개포3동"],
    }


@pytest.fixture(scope="module")
def gangnam():
    return tv.load_interest_groups()


@pytest.mark.requires_data
def test_load_gangnam_shape(gangnam):
    assert len(gangnam) == 22 * 2 * 12 * 6
    assert sorted(gangnam["ym"].unique()) == list(paths.MONTHS)
    assert gangnam["dong_cd"].str.len().eq(7).all()


@pytest.mark.requires_data
def test_numerator_is_not_subset_of_single_households(gangnam):
    # 분자가 1인가구 부분집합이 아니라는 설계 전제를 고정한다 (실측 84셀)
    assert (gangnam["n_isolated"] > gangnam["hh_single"]).sum() == 84
    assert (gangnam["n_isolated"] <= gangnam["pop"]).all()


@pytest.mark.requires_data
def test_dong_table_has_22_rows_and_valid_ranges(gangnam):
    dong = tv.target_ratios(gangnam)
    assert len(dong) == 22
    assert dong.notna().all().all()
    pop_cols = [c for c in dong.columns if c.startswith("ratio_pop_")]
    assert ((dong[pop_cols] > 0) & (dong[pop_cols] < 1)).all().all()


@pytest.mark.requires_data
def test_real_code_map_is_one_to_one_with_v33_adm(gangnam):
    table = tv.dong_code_table(gangnam, tv.read_dbf(paths.sgis_dong_dbf()))
    assert table["code_exception"].sum() == 1
    assert (~table["name_match"]).sum() == 1  # 일원2동 ↔ 개포3동만 이름이 다르다

    adm = pd.read_csv(
        paths.INTERIM_DIR / "v3.3" / "isolation_index_v3_adm.csv", dtype={"ADM_CD": str}
    )
    assert set(table["ADM_CD"]) == set(adm.loc[adm["REGION"] == "강남구", "ADM_CD"])


# --- 2단계: 연관 검증 ---


def _table22(theme_b_sign: int = 1) -> pd.DataFrame:
    """22개 동 검증 표. 테마 A와 대조 지표는 완전 단조, 테마 B는 부호를 고를 수 있다."""
    x = np.arange(22, dtype=float)
    return pd.DataFrame(
        {
            "dong_cd": [f"{i:02d}" for i in range(22)],
            "ADM_CD": [f"112307{i:02d}" for i in range(22)],
            "theme_A_pct_w": x,
            "theme_B_pct_w": theme_b_sign * x,
            "score_w": x,
            "single_share": x,
            "watch_share": x,
            "theme_A_hold": x,
            "theme_B_hold": x,
            "ratio_pop_all": x * 0.01,
            "ratio_1in_all": x * 0.1,
        }
    )


def test_target_columns_put_ratio_pop_first():
    assert tv.target_columns(_table22()) == ["ratio_pop_all", "ratio_1in_all"]


def test_spearman_table_perfect_monotone():
    out = tv.spearman_table(_table22()).set_index(["predictor", "target"])
    row = out.loc[("theme_A", "ratio_pop_all")]
    assert row["rho"] == pytest.approx(1.0)
    assert row["ci_low"] == pytest.approx(1.0)
    assert row["loo_min"] == pytest.approx(1.0)
    assert row["rho_no_rental"] == pytest.approx(1.0)
    assert len(out) == len(tv.predictor_columns()) * 2


def test_theme_diff_is_a_minus_b():
    out = tv.theme_diff(_table22(theme_b_sign=-1)).set_index("target")
    assert out.loc["ratio_pop_all", "diff_A_minus_B"] == pytest.approx(2.0)
    assert out.loc["ratio_pop_all", "ci_low"] == pytest.approx(2.0)


def test_bootstrap_is_reproducible_with_seed():
    table = _table22().assign(ratio_pop_all=np.random.default_rng(0).random(22))
    preds = {"theme_A": "theme_A_pct_w"}
    a = tv.bootstrap_rho(table, preds, ["ratio_pop_all"], n_boot=50)
    b = tv.bootstrap_rho(table, preds, ["ratio_pop_all"], n_boot=50)
    pd.testing.assert_frame_equal(a, b)


def test_leave_one_out_finds_influential_dong():
    table = _table22()
    table.loc[0, "ratio_pop_all"] = 1.0  # 첫 동만 순위를 뒤집는 이상값
    out = tv.leave_one_out_rho(table, {"theme_A": "theme_A_pct_w"}, ["ratio_pop_all"])
    row = out.loc[("theme_A", "ratio_pop_all")]
    assert row["loo_max"] == pytest.approx(1.0)
    assert row["loo_max_drop"] == table.loc[0, "ADM_CD"]


def test_sgis_dong_scores_adds_baseline_and_hold_included():
    adm = pd.DataFrame(
        {
            "ADM_CD": ["11230510", "32010110"],
            "hh_eval": [100.0, 50.0],
            "hh_single_eval": [40.0, 10.0],
            "hh_watch": [25.0, 5.0],
        }
    )
    oa = pd.DataFrame(
        {
            "ADM_CD": ["11230510", "11230510", "11230510"],
            "hh_total": [100.0, 300.0, 10.0],
            "theme_A_score": [1.0, 3.0, None],  # 세 번째는 점수 없음
            "theme_B_score": [0.0, 1.0, None],
            "hold": [False, True, True],  # 보류 행도 포함해 가중평균한다
        }
    )
    out = tv.sgis_dong_scores(adm, oa).set_index("ADM_CD")
    assert list(out.index) == ["11230510"]
    assert out.loc["11230510", "single_share"] == pytest.approx(0.4)
    assert out.loc["11230510", "watch_share"] == pytest.approx(0.25)
    assert out.loc["11230510", "theme_A_hold"] == pytest.approx((100 + 900) / 400)


def test_validation_table_rejects_missing_dong():
    dong = pd.DataFrame({"dong_cd": ["1123051"], "ratio_pop_all": [0.1]})
    code_map = pd.DataFrame({"dong_cd": ["1123051"], "ADM_CD": ["11230510"], "ADM_NM": ["신사동"]})
    sgis = pd.DataFrame({"ADM_CD": ["11230510"], "score_w": [50.0]})
    with pytest.raises(ValueError, match="22"):
        tv.validation_table(dong, code_map, sgis)


@pytest.mark.requires_data
def test_v33_adm_weighted_means_match_oa_recompute():
    oa = pd.read_csv(tv.V33_DIR / tv.V33_OA_NAME, dtype={"ADM_CD": str})
    adm = pd.read_csv(tv.V33_DIR / tv.V33_ADM_NAME, dtype={"ADM_CD": str}).set_index("ADM_CD")
    ev = oa[~oa["hold"] & oa["score"].notna()]
    for col in ("score", "theme_A_pct", "theme_B_pct"):
        weighted = (ev[col] * ev["hh_total"]).groupby(ev["ADM_CD"]).sum()
        recomputed = weighted / ev.groupby("ADM_CD")["hh_total"].sum()
        diff = (recomputed - adm.loc[recomputed.index, f"{col}_w"]).abs().max()
        assert diff < 1e-9
