import numpy as np
import pandas as pd
import pytest

from src.features import mohw_survey as ms


def test_tidy_codebook_fills_down_variable_fields():
    raw = pd.DataFrame(
        {
            "변수명": ["q1", None, "q2"],
            "조사표": ["Q1", None, "Q2"],
            "변수값": [1, 2, 1],
            "내용": ["예", "아니오", "있음"],
            "비고": ["문항1", None, "문항2"],
        }
    )
    out = ms.tidy_codebook(raw)
    assert out["var"].tolist() == ["q1", "q1", "q2"]
    assert out["question"].tolist() == ["문항1", "문항1", "문항2"]
    assert list(out.columns) == ms.CODEBOOK_COLUMNS


def test_clean_survey_turns_dot_into_nan_and_numeric():
    raw = pd.DataFrame({"q1": [1, ".", 4], "pid": ["a", "b", "c"]})
    out = ms.clean_survey(raw)
    assert out["q1"].isna().tolist() == [False, True, False]
    assert pd.api.types.is_numeric_dtype(out["q1"])
    assert out["pid"].tolist() == ["a", "b", "c"]
    assert raw["q1"].tolist() == [1, ".", 4]  # 원본 유지


def test_variable_table_one_row_per_variable():
    codebook = pd.DataFrame(
        {
            "var": ["q1", "q1", "q2", "pid"],
            "qno": ["Q1", "Q1", "Q2", None],
            "value": [1, 2, 1, None],
            "label": ["예", "아니오", "있음", "개인id"],
            "question": ["문항1", "문항1", "문항2", "연동"],
        }
    )
    out = ms.variable_table(codebook)
    assert out["var"].tolist() == ["q1", "q2", "pid"]
    assert out["n_options"].tolist() == [2, 1, 1]
    assert out.loc[0, "options"] == "1=예 / 2=아니오"
    assert out.loc[2, "options"] == "=개인id"  # 보기 값이 없는 변수


def test_survey_file_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        ms.survey_file(tmp_path)


@pytest.mark.requires_data
@pytest.mark.parametrize(("sheet", "n_rows"), [("(데이터)은둔", 5161), ("(데이터)고립", 3713)])
def test_real_survey_shape_and_missing(sheet, n_rows):
    df = ms.load_survey(sheet)
    assert len(df) == n_rows
    assert df["pid"].is_unique
    assert pd.api.types.is_numeric_dtype(df["q211"])
    assert not (df.select_dtypes("object") == ms.MISSING_TOKEN).any().any()
    assert df["q211"].dropna().isin([1, 2, 3, 4]).all()


def _toy_codebook():
    return pd.DataFrame(
        {
            "var": ["q211", "q211", "q211"],
            "qno": ["Q21-1", "Q21-1", "Q21-1"],
            "value": [1, 2, 3],
            "label": ["전혀", "별로", "매우"],
            "question": ["은둔생활을 벗어나기위한 도움 필요도_공간"] * 3,
        }
    )


def test_distribution_table_excludes_missing_from_denominator():
    df = pd.DataFrame({"q211": [1.0, 1.0, 3.0, np.nan]})
    out = ms.distribution_table(df, "은둔", ["q211"], _toy_codebook(), "SUPPORT_NEED")
    assert out["N_VALID"].unique().tolist() == [3]
    assert out["N"].tolist() == [2, 0, 1]  # 응답 없는 보기도 0으로 남긴다
    assert out["PCT"].tolist() == [66.7, 0.0, 33.3]
    assert out["ITEM_LABEL"].unique().tolist() == ["공간"]
    assert list(out.columns) == ms.OUTPUT_COLUMNS


def test_distribution_table_all_missing_gives_nan_pct():
    df = pd.DataFrame({"q211": [np.nan, np.nan]})
    out = ms.distribution_table(df, "고립", ["q211"], _toy_codebook(), "SUPPORT_NEED")
    assert out["N_VALID"].eq(0).all()
    assert out["PCT"].isna().all()


@pytest.mark.requires_data
def test_real_support_need_matches_hand_count():
    out = ms.build_support_tables()
    q211 = out[(out["ITEM_CODE"] == "q211") & (out["OPTION_CODE"] == 4)].set_index("GROUP")
    assert q211.loc["은둔", ["N", "N_VALID", "PCT"]].tolist() == [2186, 5158, 42.4]
    assert q211.loc["고립", ["N", "N_VALID", "PCT"]].tolist() == [1602, 3713, 43.1]
    sums = out.groupby(["TABLE", "GROUP", "ITEM_CODE"])["N"].sum()
    valid = out.groupby(["TABLE", "GROUP", "ITEM_CODE"])["N_VALID"].first()
    assert (sums == valid).all()  # 보기별 N 합 = 유효 응답 수
