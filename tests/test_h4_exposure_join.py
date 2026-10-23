"""활동 저하 신호와 노출 지수 결합 테스트 (#16)."""

import pandas as pd
import pytest

from src.modeling import h4_exposure_join as ej


def test_join_keeps_unscored_rows_and_classifies_status():
    signal = pd.DataFrame(
        {
            "TOT_OA_CD": ["a", "b", "c", "d", "e", "a"],
            "REGION": "강남구",
            "ADM_CD": "1",
            "AGE_BAND": ["60GU"] * 5 + ["20G"],
            "JUDGEMENT_STATUS": ["judged", "judged", "held", "held", "judged", "judged"],
            "HOLD_REASON": [None, None, "work_area", "no_resident", None, None],
            "N_LOW_MONTHS": [5, 6, None, None, 0, 6],
            "MEAN_RESID": [-0.3, -0.4, None, None, 0.2, -0.5],
            "SIGNAL": [True, True, None, None, False, True],
        }
    )
    index = pd.DataFrame(
        {
            "TOT_OA_CD": ["a", "b", "c", "d"],
            "hold": [False, True, False, True],
            "grade": [3, 0, 5, 0],
            "theme_A_pct": [85.0, None, 10.0, None],
            "theme_B_pct": [10.0, None, 10.0, None],
            "type_label": ["고령 독거형", "보류", "일반", "보류"],
            "rental_est": [False, False, False, False],
            "hold_reason": [None, "업무지", None, "인구없음"],
            "watch": [True, False, True, False],
        }
    )
    out = ej.join(signal, index).set_index("TOT_OA_CD")

    assert list(out.index) == ["a", "b", "c", "d", "e"]  # 60GU만, 지수에 없는 e도 유지
    assert out["COMBINED_STATUS"].to_dict() == {
        "a": "judged_both",
        "b": "exposure_held",
        "c": "signal_held",
        "d": "double_held",
        "e": "exposure_held",
    }
    assert out["EXPOSURE_HIGH"].to_dict() == {
        "a": True,
        "b": False,
        "c": True,
        "d": False,
        "e": False,
    }
    assert out.loc["b", "EXPOSURE_HOLD_REASON"] == "no_exposure_score"
    assert out.loc["e", "INDEX_HOLD_REASON"] == "not_in_index"
    assert out.loc["b", "SIGNAL"]  # 지수 보류여도 H4 신호는 지우지 않음


def test_combine_dong_counts_joint_status_per_dong():
    joined = pd.DataFrame(
        {
            "ADM_CD": ["1", "1", "1", "2"],
            "SIGNAL": [True, True, None, False],
            "EXPOSURE_HIGH": [True, False, False, True],
            "COMBINED_STATUS": ["judged_both", "exposure_held", "double_held", "judged_both"],
        }
    )
    signal_dong = pd.DataFrame(
        {
            "ADM_CD": ["1", "2", "1"],
            "AGE_BAND": ["60GU", "60GU", "20G"],
            **{c: 0 for c in ["REGION", "N_OA", "N_JUDGED", "N_HELD", "N_SIGNAL"]},
            "SIGNAL_RATE": 0.0,
            "DONG_POOLED_RESID": 0.0,
        }
    )
    index_adm = pd.DataFrame({"ADM_CD": ["1", "2"], **{c: 1 for c in ej.INDEX_ADM_COLS}})
    out = ej.combine_dong(joined, signal_dong, index_adm).set_index("ADM_CD")

    assert len(out) == 2  # 60GU 행만
    assert out.loc["1", ["N_WATCH_SIGNAL", "N_SIGNAL_EXPOSURE_HELD", "N_DOUBLE_HELD"]].tolist() == [
        1,
        1,
        1,
    ]
    assert out.loc["2", "N_WATCH_SIGNAL"] == 0


def test_association_within_dong_removes_composition_effect():
    # 동 1은 관찰 후보·신호가 모두 많고 동 2는 모두 적다. 동 안에서는 연관이 없다
    rows = [("1", True, True)] * 4 + [("1", False, True)] * 4
    rows += [("1", True, False)] * 1 + [("1", False, False)] * 1
    rows += [("2", True, True)] * 1 + [("2", False, True)] * 1
    rows += [("2", True, False)] * 4 + [("2", False, False)] * 4
    joined = pd.DataFrame(rows, columns=["ADM_CD", "EXPOSURE_HIGH", "SIGNAL"]).assign(
        REGION="강남구", COMBINED_STATUS="judged_both"
    )
    out = ej.association(joined).iloc[0]
    assert out["MH_ODDS_RATIO_WITHIN_DONG"] == pytest.approx(1.0)
