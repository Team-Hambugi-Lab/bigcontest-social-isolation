"""서울 통신정보 대조 테스트 (#16)."""

import pandas as pd
import pytest

from src.evaluation import h4_external_validation as ev


def test_code_mapping_appends_zero_with_exception():
    out = ev.to_sgis_code(pd.Series(["1123051", "1123074"]))
    assert out.tolist() == ["11230510", "11230511"]


def test_dong_metrics_weights_by_population():
    telecom = pd.DataFrame(
        {
            "ADM_CD": ["11230510"] * 3,
            "연령대": ["60", "75", "20"],
            "총인구수": [100.0, 300.0, 50.0],
            **{m: [1.0, 3.0, 9.0] for m in ev.METRICS.values()},
        }
    )
    out = ev.dong_metrics(telecom).set_index("AGE_BAND")
    assert out.loc["60GU", "MOVES_WEEKDAY"] == pytest.approx((100 * 1 + 300 * 3) / 400)
    assert out.loc["20G", "MOVES_WEEKDAY"] == 9.0


def test_correlate_flags_expected_sign():
    signal = pd.DataFrame(
        {
            "ADM_CD": [f"D{i}" for i in range(5)],
            "AGE_BAND": "60GU",
            "SIGNAL_RATE": [0.1, 0.2, 0.3, 0.4, 0.5],
            "DONG_POOLED_RESID": [0.2, 0.1, 0.0, -0.1, -0.2],
        }
    )
    metrics = signal[["ADM_CD", "AGE_BAND"]].assign(
        HOME_STAY_WEEKDAY=[1, 2, 3, 4, 5],
        HOME_STAY_HOLIDAY=[1, 2, 3, 4, 5],
        MOVES_WEEKDAY=[5, 4, 3, 2, 1],
        MOVES_HOLIDAY=[5, 4, 3, 2, 1],
    )
    out = ev.correlate(signal, metrics)
    assert out.loc[out["SCOPE"] == "all", "SIGN_MATCH"].all()


@pytest.mark.requires_data
def test_real_telecom_covers_all_gangnam_dongs():
    metrics = ev.dong_metrics(ev.load_telecom(sorted(ev.TELECOM_DIR.glob("*.xlsx"))[:1]))
    signal = pd.read_csv(ev.SIGNAL_DONG_PATH, dtype={"ADM_CD": str})
    gangnam = set(signal.loc[signal["ADM_CD"].str.startswith(ev.GANGNAM_PREFIX), "ADM_CD"])
    assert gangnam == set(metrics["ADM_CD"])
    assert len(gangnam) == 22
