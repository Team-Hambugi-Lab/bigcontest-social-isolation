import numpy as np
import pandas as pd
import pytest

from src.features import risk_features_youth as rf


def test_feature_hits_all_needs_every_item_answered():
    df = pd.DataFrame({"a": [2, 2, 1, np.nan], "b": [2, 1, 2, 2]})
    hit, valid = rf.feature_hits(df, "all", {"a": [2], "b": [2]})
    assert hit.tolist() == [True, False, False, False]
    assert valid.tolist() == [True, True, True, False]


def test_feature_hits_any_and_empty_option_widens_denominator():
    # q14a1은 q14=1에게만 묻는다: q14=2인 사람도 분모에 들어가야 한다
    df = pd.DataFrame({"q14a1": [1, 2, np.nan, np.nan], "q14": [1, 1, 2, np.nan]})
    hit, valid = rf.feature_hits(df, "any", {"q14a1": [1], "q14": []})
    assert hit.tolist() == [True, False, False, False]
    assert valid.tolist() == [True, True, True, False]


def test_seoul_evidence_sums_rows_and_rejects_unknown_label(monkeypatch):
    tables = pd.DataFrame(
        {
            "GROUP": ["고립은둔"] * 3 + ["전체"] * 3,
            "TABLE_CODE": ["A1"] * 6,
            "TABLE_LABEL": ["노동"] * 6,
            "N_BASE": [486] * 3 + [5513] * 3,
            "ROW_LABEL": ["x", "y", "z"] * 2,
            "VALUE": [10.0, 20.0, 70.0, 1.0, 2.0, 97.0],
        }
    )
    monkeypatch.setattr(rf, "SEOUL_EVIDENCE", [("F", "A1", ["x", "y"], "")])
    out = rf.seoul_evidence_table(tables)
    assert out.loc[0, ["PCT", "COMPARE_PCT", "N_VALID"]].tolist() == [30.0, 3.0, 486]
    monkeypatch.setattr(rf, "SEOUL_EVIDENCE", [("F", "A1", ["없는 보기"], "")])
    with pytest.raises(KeyError):
        rf.seoul_evidence_table(tables)


def test_feature_supports_ranks_by_gap_from_everyone(monkeypatch):
    # s1은 모두가 많이 원하고(해당자 50%, 전체 50%), s2는 해당자만 더 원한다(해당자 50%, 전체 25%)
    df = pd.DataFrame({"f": [1, 1, 2, 2], "s1": [4, 1, 4, 1], "s2": [4, 1, 1, 1]})
    monkeypatch.setattr(rf, "MOHW_FEATURES", [("F", "", "", "any", {"f": [1]})])
    monkeypatch.setattr(rf, "TOP_SUPPORTS", 1)
    out = rf.feature_supports(df, {"s1": "지원1", "s2": "지원2"})
    assert out.loc[0, ["SUPPORT_TYPES", "SUPPORT_NEED_PCT"]].tolist() == ["지원2", "50.0"]


@pytest.mark.requires_data
def test_real_features_cover_all_codes_and_match_hand_count():
    out = rf.build_risk_features_youth()
    feat = out[(out["TABLE"] == "RISK_FEATURE") & (out["SOURCE"] == rf.MOHW_SOURCE)]
    assert set(feat["FEATURE_CODE"]) == {f[0] for f in rf.MOHW_FEATURES}
    assert len(feat) == 2 * len(rf.MOHW_FEATURES)  # 은둔·고립
    assert feat["PCT"].between(0, 100).all()
    # 은둔 자살 시도: q14a1=1 1,063명 / q14 응답 5,160명
    attempt = feat.set_index(["FEATURE_CODE", "GROUP"]).loc[("MIND_SUICIDE_ATTEMPT", "은둔")]
    assert attempt[["N", "N_VALID"]].tolist() == [1063, 5160]
    seoul = out[out["SOURCE"] == rf.SEOUL_SOURCE]
    assert len(seoul) == len(rf.SEOUL_EVIDENCE)
