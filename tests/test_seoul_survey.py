import pandas as pd
import pytest

from src.features import seoul_survey as ss

TOTAL = ss.TOTAL_HEADER


def _toy_rows():
    return [
        ["【0】 응답자 Profile", None, None],
        [None, None, TOTAL],  # 열 배치가 다른 프로필 블록은 제외된다
        ["성별", "남성", 46.7],
        [None, None, None],
        ["【A18_1】 외로움 척도▶부족하다", None, None],
        ["BASE : ALL", TOTAL, "성별"],
        [None, None, "남성"],
        [ss.N_ROW_LABEL, "(486)", "(227)"],
        ["전혀그렇지않다", 10.9, 14.1],
        ["항상그렇다", 30.2, 30.8],
        ["▣ 합  계 ▣", "100", "100"],
        ["▣ 평  균 ▣", 2.9, 2.9],
        ["Top2(③+④)", 70.0, 68.7],
        [None, None, None],
        ["【C8_6_1 TO C8_6_8】 불참 이유", None, None],
        ["BASE : C8_5=2", TOTAL, "성별"],
        [None, None, "남성"],
        [ss.N_ROW_LABEL, "(224)", "(108)"],
        ["지원절차가 까다로울 것 같아서", 30.4, 31.5],
    ]


def test_parse_table_rows_reads_blocks_and_skips_profile():
    out = ss.parse_table_rows(_toy_rows(), "고립은둔")
    assert list(out.columns) == ss.OUTPUT_COLUMNS
    assert out["TABLE_CODE"].unique().tolist() == ["A18_1", "C8_6_1 TO C8_6_8"]
    a18 = out[out["TABLE_CODE"] == "A18_1"]
    assert a18["ROW_LABEL"].tolist() == ["전혀그렇지않다", "항상그렇다", "▣ 평  균 ▣", "Top2(③+④)"]
    assert a18["VALUE"].tolist() == [10.9, 30.2, 2.9, 70.0]  # 합계 행은 제외
    assert a18["N_BASE"].unique().tolist() == [486]


def test_parse_table_rows_keeps_base_condition_and_last_block_without_blank_row():
    out = ss.parse_table_rows(_toy_rows(), "전체")
    c8 = out[out["TABLE_CODE"].str.startswith("C8_6")]
    assert c8["BASE"].tolist() == ["C8_5=2"]
    assert c8["N_BASE"].tolist() == [224]
    assert c8["GROUP"].tolist() == ["전체"]


def test_table_file_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        ss.table_file("전체", tmp_path)


@pytest.mark.requires_data
def test_real_tables_match_hand_checked_values():
    out = ss.build_seoul_tables()
    assert out.groupby("GROUP")["N_BASE"].max().to_dict() == {"고립은둔": 486, "전체": 5513}
    c4 = out[(out["GROUP"] == "고립은둔") & out["TABLE_CODE"].str.startswith("C4_1 TO")]
    assert c4.set_index("ROW_LABEL").loc["경제적 지원", "VALUE"] == pytest.approx(57.2, abs=0.05)
    assert c4["N_BASE"].unique().tolist() == [486]
    assert not out["VALUE"].isna().all()
    assert isinstance(out, pd.DataFrame)
