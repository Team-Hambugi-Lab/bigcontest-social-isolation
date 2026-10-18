"""기대 유동 모델·신호 판정·행정동 집계 테스트 (#16)."""

import numpy as np
import pandas as pd
import pytest

from src.features import h4_age_panel as h4
from src.modeling import h4_activity_signal as sig

MONTHS = [f"2025{m:02d}" for m in range(7, 13)]
PLANTED = {f"OA{i:03d}" for i in range(5)}  # 60대 이상 유동을 기대보다 낮게 심은 집계구
DROP = -0.7


def synthetic_panel(n_oa: int = 80, seed: int = 0) -> pd.DataFrame:
    """로그 선형 모델로 유동을 만들고 PLANTED 집계구의 60대 이상에 낮은 잔차를 심는다."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_oa):
        code = f"OA{i:03d}"
        region = "강남구" if i % 2 else "춘천시"
        adm = f"D{i % 4}"
        emp = rng.uniform(5, 500)
        for band in h4.AGE_BANDS:
            res = rng.uniform(30, 300)
            for ym in MONTHS:
                other = rng.uniform(500, 5000)
                log_flow = 0.5 * np.log(res) + 0.1 * np.log1p(emp) + 0.8 * np.log(other)
                log_flow += rng.normal(0, 0.05)
                if code in PLANTED and band == "60GU":
                    log_flow += DROP
                rows.append(
                    {
                        "TOT_OA_CD": code,
                        "STD_YM": ym,
                        "AGE_BAND": band,
                        "FLOW": np.exp(log_flow),
                        "FLOW_OTHER": other,
                        "FLOW_TOTAL": other + np.exp(log_flow),
                        "RESIDENT": res,
                        "EMPLOYEES": emp,
                        "REGION": region,
                        "ADM_CD": adm,
                        "HOLD_REASON": np.nan,
                        "JUDGEMENT_STATUS": "judged",
                    }
                )
    return pd.DataFrame(rows)


def resid_rows(code: str, resids: list[float], status: str = "judged", adm: str = "D0"):
    """persistence 입력용 집계구 한 개의 월별 잔차 행."""
    return pd.DataFrame(
        {
            "TOT_OA_CD": code,
            "STD_YM": MONTHS[: len(resids)],
            "AGE_BAND": "60GU",
            "FLOW": 100.0,
            "FLOW_OTHER": 1000.0,
            "FLOW_TOTAL": 1100.0,
            "EXPECTED": 100.0,
            "RESID": resids,
            "RESIDENT": 50.0,
            "REGION": "강남구",
            "ADM_CD": adm,
            "JUDGEMENT_STATUS": status,
        }
    )


def test_planted_low_residuals_are_recovered():
    resid, fits = sig.residual_panel(synthetic_panel())
    signal = sig.persistence(resid)
    s60 = signal[signal["AGE_BAND"] == "60GU"].set_index("TOT_OA_CD")
    assert s60.loc[sorted(PLANTED), "SIGNAL"].all()
    assert s60.loc[sorted(PLANTED), "MEAN_RESID"].max() < s60.drop(PLANTED)["MEAN_RESID"].min()
    assert fits["40G"]["coef"]["log_resident"] == pytest.approx(0.5, abs=0.05)


def test_zero_resident_row_has_missing_residual():
    panel = synthetic_panel(n_oa=20).astype({"HOLD_REASON": object})
    zero = (panel["TOT_OA_CD"] == "OA010") & (panel["AGE_BAND"] == "40G")
    panel.loc[zero, ["RESIDENT", "JUDGEMENT_STATUS", "HOLD_REASON"]] = [
        0.0,
        "held",
        "zero_resident_band",
    ]
    resid, _ = sig.residual_panel(panel)
    assert resid.loc[zero, "RESID"].isna().all()
    assert resid.loc[~zero, "RESID"].notna().all()


def test_persistence_k_boundary():
    four_low = [-0.3, -0.3, -0.3, -0.3, 0.05, 0.05]
    rows = resid_rows("A", four_low)
    assert sig.persistence(rows, k=4)["SIGNAL"].iloc[0]
    assert not sig.persistence(rows, k=5)["SIGNAL"].iloc[0]
    assert sig.persistence(rows, k=4)["N_LOW_MONTHS"].iloc[0] == 4


def test_tau_ignores_small_negative_residuals():
    rows = resid_rows("A", [-0.05] * 6)  # 기대보다 약 5% 낮음: tau 0.1 미만
    assert sig.persistence(rows, tau=0.0)["SIGNAL"].iloc[0]
    assert not sig.persistence(rows, tau=0.1)["SIGNAL"].iloc[0]
    assert sig.persistence(rows, tau=0.1)["N_LOW_MONTHS"].iloc[0] == 0


def test_low_months_but_positive_mean_is_not_signal():
    rows = resid_rows("A", [-0.01, -0.01, -0.01, -0.01, 0.5, 0.5])
    assert not sig.persistence(rows, k=4)["SIGNAL"].iloc[0]


def test_held_rows_have_missing_signal():
    out = sig.persistence(resid_rows("A", [-0.5] * 6, status="held"))
    assert pd.isna(out["SIGNAL"].iloc[0])
    assert pd.isna(out["N_LOW_MONTHS"].iloc[0])
    assert out["MEAN_RESID"].iloc[0] == pytest.approx(-0.5)  # 참고값은 남긴다


def test_dong_with_no_judged_oa_has_missing_rate():
    resid = pd.concat(
        [
            resid_rows("A", [-0.5] * 6, adm="D0"),
            resid_rows("B", [0.1] * 6, adm="D0"),
            resid_rows("C", [-0.5] * 6, status="held", adm="D1"),
        ]
    )
    dong = sig.aggregate_dong(sig.persistence(resid), resid).set_index("ADM_CD")
    assert dong.loc["D0", "SIGNAL_RATE"] == 0.5
    assert pd.isna(dong.loc["D1", "SIGNAL_RATE"])
    assert dong.loc["D1", "N_HELD"] == 1
    assert dong.loc["D1", "DONG_POOLED_RESID"] == pytest.approx(0.0)  # FLOW = EXPECTED


def test_dong_pooled_resid_includes_held_oa():
    resid = pd.concat(
        [
            resid_rows("A", [0.0] * 6, adm="D0"),
            resid_rows("B", [0.0] * 6, status="held", adm="D0").assign(FLOW=50.0),
        ]
    )
    dong = sig.aggregate_dong(sig.persistence(resid), resid).set_index("ADM_CD")
    assert dong.loc["D0", "DONG_POOLED_RESID"] == pytest.approx(np.log(150 / 200))


@pytest.mark.requires_data
def test_real_data_outputs():
    master = pd.read_csv(sig.MASTER_PATH, dtype={"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str})
    status = pd.read_csv(sig.STATUS_PATH, dtype=str)
    result = sig.run(master, status)
    oa, dong = result["signal_oa"], result["signal_dong"]
    assert len(oa) == 1698 * len(h4.AGE_BANDS)
    assert len(dong) == 47 * len(h4.AGE_BANDS)
    assert oa["TOT_OA_CD"].str.len().eq(14).all()
    assert dong["ADM_CD"].str.len().eq(8).all()
    held = oa["JUDGEMENT_STATUS"].eq("held")
    assert oa.loc[held, "SIGNAL"].isna().all()
    assert oa.loc[~held, "SIGNAL"].notna().all()
    assert (dong["N_OA"] == dong["N_JUDGED"] + dong["N_HELD"]).all()
    assert dong["N_OA"].groupby(dong["AGE_BAND"]).sum().eq(1698).all()
