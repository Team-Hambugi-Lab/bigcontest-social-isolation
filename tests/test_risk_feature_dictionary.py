import pandas as pd
import pytest

from src.features import risk_feature_dictionary as rd


def _youth():
    return pd.DataFrame(
        {
            "FEATURE_CODE": ["A_X", "B_Y"],
            "FEATURE_NAME": ["가", "나"],
            "DETECT_DATA": ["SK", "감지 불가"],
            "EVIDENCE_SOURCE": ["ys1", "ys2"],
            "EVIDENCE_VALUE": ["yv1", "yv2"],
            "DETECT_RULE": ["yr1", "yr2"],
            "IS_CRISIS": ["N", "Y"],
        }
    )


def _senior(crisis=0):
    return pd.DataFrame(
        {
            "FEATURE_CODE": ["A_X"],
            "FEATURE_NAME": ["가'"],
            "DETECT_DATA": ["SK"],
            "AGE_PATTERN": ["sp"],
            "EVIDENCE_SOURCE": ["ss"],
            "EVIDENCE_VALUE": ["sv"],
            "DETECT_RULE": ["sr"],
            "IS_CRISIS": [crisis],
        }
    )


RATES = pd.Series({"A_X": "ra", "B_Y": "rb"})


def test_merge_keeps_youth_rows_and_labels_age_groups():
    out, conflicts = rd.merge_dictionary(_youth(), _senior(), RATES)
    assert out["FEATURE_CODE"].tolist() == ["A_X", "B_Y"]
    assert out.columns.tolist() == rd.DICTIONARY_COLUMNS
    assert out.loc[0, "EVIDENCE_VALUE"] == "[청년] yv1 [고령·중장년] sv"
    assert out.loc[0, "AGE_PATTERN"] == "[청년] ra [고령·중장년] sp"
    assert out.loc[1, "AGE_PATTERN"] == "[청년] rb [고령·중장년] A-2 근거 없음"
    assert out.loc[1, "DETECT_RULE"] == "[청년] yr2"
    assert out.loc[0, "FEATURE_NAME"] == "가"
    assert conflicts == ["A_X FEATURE_NAME: 청년 '가' / 고령 '가'' -> 청년 값"]


def test_merge_rejects_crisis_mismatch_and_unknown_code():
    with pytest.raises(ValueError):
        rd.merge_dictionary(_youth(), _senior(crisis=1), RATES)
    unknown = _senior().assign(FEATURE_CODE="Z_NEW")
    with pytest.raises(KeyError):
        rd.merge_dictionary(_youth(), unknown, RATES)
