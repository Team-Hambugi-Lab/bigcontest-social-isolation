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
NO_EXTRA = pd.DataFrame({"FEATURE_CODE": pd.Series(dtype="str")})


def test_merge_keeps_youth_rows_and_labels_age_groups():
    out, conflicts = rd.merge_dictionary(_youth(), _senior(), RATES, NO_EXTRA)
    assert out["FEATURE_CODE"].tolist() == ["A_X", "B_Y"]
    assert out.columns.tolist() == rd.rf.DICTIONARY_COLUMNS
    assert out.loc[0, "EVIDENCE_VALUE"] == "[청년] yv1 [고령·중장년] sv"
    assert out.loc[0, "AGE_PATTERN"] == "[청년] ra [고령·중장년] sp"
    assert out.loc[1, "AGE_PATTERN"] == "[청년] rb [고령·중장년] 근거 자료 없음"
    assert out.loc[1, "DETECT_RULE"] == "[청년] yr2"
    assert out.loc[0, "FEATURE_NAME"] == "가"
    assert conflicts == ["A_X FEATURE_NAME: 청년 '가' / 고령 '가'' -> 청년 값"]


def test_merge_rejects_crisis_mismatch_and_unknown_code():
    with pytest.raises(ValueError):
        rd.merge_dictionary(_youth(), _senior(crisis=1), RATES, NO_EXTRA)
    unknown = _senior().assign(FEATURE_CODE="Z_NEW")
    with pytest.raises(KeyError):
        rd.merge_dictionary(_youth(), unknown, RATES, NO_EXTRA)
    with pytest.raises(KeyError):
        rd.merge_dictionary(_youth(), _senior(), RATES, pd.DataFrame({"FEATURE_CODE": ["A_X"]}))


def test_proposed_rows_go_after_their_category_and_use_youth_evidence():
    proposed = pd.DataFrame(
        {
            "FEATURE_CODE": ["A_NEW", "B_NEW"],
            "FEATURE_NAME": ["새가", "새나"],
            "DEFINITION": ["d1", "d2"],
            "EVIDENCE": ["S1 p.14(PDF18) 예시; S5 p.56~57(PDF6~7) 85.2%", "S3 p.6(PDF6) 외출"],
            "DETECT_RULE": ["r1", "r2"],
        }
    )
    evidence = pd.DataFrame(
        {
            "TABLE": ["RISK_FEATURE"],
            "SOURCE": ["서울시 2022"],
            "FEATURE_CODE": ["A_NEW"],
            "GROUP": ["고립은둔"],
            "ITEM_CODE": ["A11"],
            "PCT": [26.8],
            "COMPARE_PCT": [3.4],
            "NOTE": [""],
        }
    )
    extra = rd.proposed_rows(proposed, evidence)
    out, _ = rd.merge_dictionary(_youth(), _senior(), RATES, extra)
    assert out["FEATURE_CODE"].tolist() == ["A_X", "A_NEW", "B_Y", "B_NEW"]
    a, b = out.loc[1], out.loc[3]
    assert (
        a["EVIDENCE_SOURCE"]
        == "[청년] 서울시 2022 (A11) [고령·중장년] S1 p.14(PDF18); S5 p.56~57(PDF6~7)"
    )
    assert a["AGE_PATTERN"].startswith("[청년] 서울시 2022 A11: 고립·은둔 26.8% 대 전체 청년 3.4%")
    assert b["AGE_PATTERN"].startswith("[청년] 청년 실태조사 근거 없음 [고령·중장년] 제안 코드")
    assert b["IS_CRISIS"] == "N" and b["DETECT_DATA"] == "감지 불가"
    assert pd.isna(b["SUPPORT_NEED_PCT"])


def test_index_rule_appends_to_senior_detect_rule(monkeypatch):
    monkeypatch.setattr(rd, "INDEX_RULES", {"A_X": "idx", "B_Y": "idx2"})
    monkeypatch.setattr(rd.rf, "DETECT", {"A_X": ("SGIS", "yr"), "B_Y": ("SGIS", "yr")})
    out, _ = rd.merge_dictionary(_youth(), _senior(), RATES, NO_EXTRA)
    assert out.loc[0, "DETECT_RULE"] == "[청년] yr [고령·중장년] sr idx"
    assert out.loc[1, "DETECT_RULE"] == "[청년] yr [고령·중장년] idx2"


def test_apply_institution_tags_orders_candidates_and_preserves_other_columns():
    risk = pd.DataFrame(
        {
            "FEATURE_CODE": ["A", "B"],
            "IS_CRISIS": ["N", "Y"],
            "DEFINITION": ["관계", "위기"],
            "INSTITUTION_TAGS": [pd.NA, pd.NA],
        }
    )
    mapping = pd.DataFrame(
        [
            ("A", "ISOLATION_CARE", 2, "서울"),
            ("A", "SOCIAL_PART", 1, "참여"),
            ("B", "CRISIS_LINE", 1, "이관"),
        ],
        columns=["FEATURE_CODE", "TAG", "PRIORITY", "NOTE"],
    )
    out = rd.apply_institution_tags(risk, mapping)
    assert out["INSTITUTION_TAGS"].tolist() == ["SOCIAL_PART;ISOLATION_CARE", "CRISIS_LINE"]
    assert out["DEFINITION"].tolist() == risk["DEFINITION"].tolist()
    assert risk["INSTITUTION_TAGS"].isna().all()


def test_apply_institution_tags_rejects_invalid_mapping_before_write():
    risk = pd.DataFrame({"FEATURE_CODE": ["A"], "IS_CRISIS": ["N"]})
    mapping = pd.DataFrame(
        [("A", "SOCIAL_PART", 1, "참여")],
        columns=["FEATURE_CODE", "TAG", "PRIORITY", "NOTE"],
    )
    for bad, error in [
        (mapping.assign(FEATURE_CODE="UNKNOWN"), "코드 불일치"),
        (mapping.assign(TAG="UNKNOWN"), "미등록 서비스 태그"),
        (mapping.assign(PRIORITY=2), "우선순위"),
        (pd.concat([mapping, mapping]), "중복"),
    ]:
        with pytest.raises(ValueError, match=error):
            rd.apply_institution_tags(risk, bad)
