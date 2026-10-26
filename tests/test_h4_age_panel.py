"""연령대별 거주 인구·유동·판단 보류 패널 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import h4_age_panel as h4

AGE_CELLS = list(range(1, 22))


def make_oa(code: str, cells: dict[int, float | str], total: float, **extra) -> tuple[dict, dict]:
    """집계구 하나의 SGIS 값 행과 상태 행을 만든다. 칸 값이 문자열이면 그 상태로 결측 처리한다."""
    values = {"TOT_OA_CD": code, "SGIS2024_to_in_001": total}
    status = {"TOT_OA_CD": code}
    for i in AGE_CELLS:
        v = cells.get(i, 10.0)
        col = h4.age_col(i)
        values[col] = np.nan if isinstance(v, str) else v
        status[col] = v if isinstance(v, str) else "numeric"
    values.update(
        {
            "REGION": "강남구",
            "ADM_CD": "11230510",
            "HAS_SK_POINTS": True,
            "is_small_sample": False,
            "SGIS2024_to_em_020": 10.0,
            "SGIS2024_to_ga_001": 100.0,
            "SGIS2024_to_ga_002": total / 100.0 if total else 0.0,
        }
    )
    values.update(extra)
    return values, status


def build(*oas: tuple[dict, dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """make_oa 결과들을 SGIS 값 표와 상태 표로 묶는다."""
    return pd.DataFrame([v for v, _ in oas]), pd.DataFrame([s for _, s in oas])


def band(res: pd.DataFrame, code: str, age_band: str) -> pd.Series:
    """결과에서 집계구 × 연령대 한 행을 꺼낸다."""
    return res.set_index(["TOT_OA_CD", "AGE_BAND"]).loc[(code, age_band)]


def test_band_maps_two_five_year_cells():
    master, status = build(make_oa("A", {5: 30.0, 6: 40.0}, total=210.0))
    res = h4.resident_by_band(master, status)
    assert band(res, "A", "20G")["RESIDENT"] == 70.0
    assert set(res["AGE_BAND"]) == set(h4.AGE_BANDS)


def test_masked_and_no_record_cells():
    master, status = build(make_oa("A", {5: "source_na", 6: "no_record"}, total=210.0))
    row = band(h4.resident_by_band(master, status), "A", "20G")
    assert (row["RESIDENT"], row["RESIDENT_LOW"], row["RESIDENT_HIGH"]) == (2.5, 1.0, 4.0)
    assert row["N_MASKED_CELLS"] == 1


def test_60gu_by_subtraction_with_reversed_bounds():
    # 0~59세 12칸 중 1칸 비공개, 나머지 10명씩 = 110 + (1~4)
    master, status = build(make_oa("A", {1: "source_na"}, total=300.0))
    row = band(h4.resident_by_band(master, status), "A", "60GU")
    assert row["RESIDENT"] == 300.0 - 112.5
    assert row["RESIDENT_LOW"] == 300.0 - 114.0  # 0~59세 상한을 뺀다
    assert row["RESIDENT_HIGH"] == 300.0 - 111.0
    assert not row["RESIDENT_CLIPPED"]


def test_negative_60gu_is_clipped_to_zero():
    master, status = build(make_oa("A", {}, total=100.0))  # 0~59세 합 120 > 총인구
    row = band(h4.resident_by_band(master, status), "A", "60GU")
    assert row["RESIDENT"] == 0.0
    assert row["RESIDENT_LOW"] == 0.0
    assert row["RESIDENT_CLIPPED"]


def test_no_resident_only_when_total_is_zero():
    all_missing = {i: "no_record" for i in range(1, 13)}
    master, status = build(
        make_oa("EMPTY", {i: "no_record" for i in AGE_CELLS}, total=0.0),
        make_oa("CARE", all_missing, total=90.0),  # 요양시설: 0~59세가 모두 비어도 거주 인구 있음
    )
    res = h4.resident_by_band(master, status)
    assert band(res, "EMPTY", "60GU")[["RESIDENT", "RESIDENT_LOW"]].isna().all()
    assert band(res, "CARE", "60GU")["RESIDENT"] == 90.0
    assert band(res, "CARE", "20G")["RESIDENT"] == 0.0


def test_flow_other_excludes_target_band():
    row = {"TOT_OA_CD": "A", "STD_YM": "202507"}
    for i, g in enumerate(h4.AGE_BANDS, start=1):
        row[f"MAN_FLOW_POP_CNT_{g}_sum"] = float(i)
        row[f"WMAN_FLOW_POP_CNT_{g}_sum"] = float(i)
    flow = h4.flow_by_band(pd.DataFrame([row])).set_index("AGE_BAND")
    assert flow.loc["60GU", "FLOW"] == 12.0
    assert flow.loc["60GU", "FLOW_OTHER"] == 2.0 * (1 + 2 + 3 + 4 + 5)


def test_hold_reasons_joined_and_judged():
    master, status = build(
        make_oa("OK", {}, total=500.0),
        make_oa("NOSK", {}, total=500.0, HAS_SK_POINTS=False, is_small_sample=False),
        make_oa("INST", {}, total=500.0, SGIS2024_to_ga_002=1.0),  # 가구원 100명 vs 인구 500
        make_oa("SMALL20", {5: 3.0, 6: 4.0}, total=500.0),
    )
    res = h4.hold_reasons(h4.resident_by_band(master, status), h4.oa_table(master))
    assert band(res, "OK", "20G")["JUDGEMENT_STATUS"] == "judged"
    assert pd.isna(band(res, "OK", "20G")["HOLD_REASON"])
    assert band(res, "NOSK", "40G")["HOLD_REASON"] == "no_sk"
    assert band(res, "INST", "40G")["HOLD_REASON"] == "institution"
    assert band(res, "SMALL20", "20G")["HOLD_REASON"] == "small_resident_band"
    assert band(res, "SMALL20", "40G")["JUDGEMENT_STATUS"] == "judged"


def test_multiple_reasons_keep_fixed_order():
    master, status = build(
        make_oa("A", {}, total=0.0, HAS_SK_POINTS=False, is_small_sample=True),
        make_oa("B", {}, total=500.0),
    )
    res = h4.hold_reasons(h4.resident_by_band(master, status), h4.oa_table(master))
    assert band(res, "A", "40G")["HOLD_REASON"] == "no_sk;no_resident;small_sample"


def test_work_area_threshold_is_wider_for_youth_and_within_region():
    # 강남 20개(종사자 비율 1~20), 춘천 20개(0.01~0.20): 지역별로 세면 춘천에서도 걸린다
    oas = []
    for i in range(1, 21):
        oas.append(make_oa(f"G{i:02d}", {}, total=500.0, SGIS2024_to_em_020=500.0 * i))
        oas.append(
            make_oa(f"C{i:02d}", {}, total=500.0, SGIS2024_to_em_020=5.0 * i, REGION="춘천시")
        )
    master, status = build(*oas)
    res = h4.hold_reasons(h4.resident_by_band(master, status), h4.oa_table(master))
    work = res[res["HOLD_REASON"].fillna("").str.contains("work_area")]
    assert set(work.loc[work["AGE_BAND"] == "60GU", "TOT_OA_CD"]) == {"G20", "C20"}
    assert set(work.loc[work["AGE_BAND"] == "20G", "TOT_OA_CD"]) == {"G19", "G20", "C19", "C20"}


@pytest.mark.requires_data
def test_real_data_panel_counts():
    from src.data import paths

    master = pd.read_csv(
        paths.PROCESSED_DIR / "master_analysis.csv",
        dtype={"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str},
    )
    status = pd.read_csv(paths.INTERIM_DIR / "1차 merge" / "sgis2024_value_status.csv", dtype=str)
    res = h4.hold_reasons(h4.resident_by_band(master, status), h4.oa_table(master))
    assert len(res) == 1698 * len(h4.AGE_BANDS)
    assert res["TOT_OA_CD"].str.len().eq(14).all()
    reasons = res["HOLD_REASON"].fillna("")
    oa_count = lambda r: res.loc[reasons.str.contains(r), "TOT_OA_CD"].nunique()  # noqa: E731
    assert oa_count("no_resident") == 30
    assert oa_count("institution") == 15
    assert oa_count("extreme_visitor") == 11
    assert band(res, "11230760040002", "60GU")["RESIDENT"] > 300  # 요양시설 집계구
    flow = h4.flow_by_band(master)
    assert len(flow) == len(master) * len(h4.AGE_BANDS)
    assert flow["FLOW"].isna().sum() == 108
