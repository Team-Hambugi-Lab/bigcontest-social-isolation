"""연령대별 거주 인구·유동 패널과 판단 보류 사유를 만든다 (이슈 #16, 가설 H4 확장).

SK 10세 구간 하나에 SGIS 5세 구간 두 칸을 맞춘다. 60대 이상은 비공개 칸이 많아
「총인구 − 0~59세」로 구한다. 규칙의 근거는 docs/plans/261017_issue16_h4_activity_signal_plan.md
1·2·5절과 reports/261017_REG_h4_activity_signal.md 1절이다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SGIS = "SGIS2024_"
AGE_BANDS = ("10G", "20G", "30G", "40G", "50G", "60GU")
BAND_CELLS = {"10G": (3, 4), "20G": (5, 6), "30G": (7, 8), "40G": (9, 10), "50G": (11, 12)}
UNDER60 = range(1, 13)  # in_age_001~012 = 0~59세

# SGIS 비공개 칸(source_na)은 1~4명이다
MASKED_POINT, MASKED_LOW, MASKED_HIGH = 2.5, 1.0, 4.0

MIN_RESIDENT = 20
WORK_Q = 0.05
WORK_Q_YOUTH = 0.10  # 20~30대는 출퇴근 영향이 커서 넓게 잡는다(가설 H1)
YOUTH_BANDS = ("20G", "30G")
INSTITUTION_RATIO = 1.5  # 총인구 / 가구원 수 합. 넘으면 주민의 1/3 이상이 집단시설 인구

# #12 코멘트(2026-10-15) "전체 기준 후보 11개 (춘천)": 유동 패턴이 4개월 이상 극단적인 집계구
EXTREME_VISITOR = frozenset(
    [
        "32010320030001", "32010350010001", "32010360010005", "32010360020001",
        "32010570060001", "32010370010005", "32010390010002", "32010600010020",
        "32010310040003", "32010360010004", "32010370010007",
    ]
)  # fmt: skip

# HOLD_REASON에 이어 붙이는 순서
HOLD_ORDER = (
    "no_sk",
    "no_resident",
    "small_sample",
    "extreme_visitor",
    "institution",
    "zero_resident_band",
    "small_resident_band",
    "work_area",
)


def age_col(i: int) -> str:
    """5세 단위 남녀 합계 연령 열 이름(`in_age_001` = 0~4세)."""
    return f"{SGIS}in_age_{i:03d}"


def _cell_values(master: pd.DataFrame, status: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """0~59세 칸마다 점추정·하한·상한·비공개 여부를 집계구 순서로 만든다."""
    st = status.set_index("TOT_OA_CD").reindex(master["TOT_OA_CD"])
    cells = {}
    for i in UNDER60:
        col = age_col(i)
        value = master[col].to_numpy(dtype=float)
        masked = st[col].eq("source_na").to_numpy()
        # no_record는 0명이다. 거주 인구가 없는 집계구는 총인구로 따로 판정한다.
        no_record = st[col].eq("no_record").to_numpy()
        base = np.where(no_record, 0.0, value)
        cells[i] = pd.DataFrame(
            {
                "point": np.where(masked, MASKED_POINT, base),
                "low": np.where(masked, MASKED_LOW, base),
                "high": np.where(masked, MASKED_HIGH, base),
                "masked": masked.astype(int),
            }
        )
    return cells


def resident_by_band(master: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """집계구 × 연령대 거주 인구(점추정·하한·상한, 비공개 칸 수)를 만든다.

    `master`는 집계구가 여러 달 반복되어도 된다. 첫 행만 쓴다.
    총인구가 0이면 거주 인구는 결측이다. 60대 이상 빼기 결과가 음수면 0으로 자른다.
    """
    oa = master.drop_duplicates("TOT_OA_CD").reset_index(drop=True)
    cells = _cell_values(oa, status)
    total = oa[f"{SGIS}to_in_001"].to_numpy(dtype=float)
    no_resident = ~(np.nan_to_num(total) > 0)

    frames = []
    for band, (a, b) in BAND_CELLS.items():
        frames.append(
            pd.DataFrame(
                {
                    "AGE_BAND": band,
                    "RESIDENT": cells[a]["point"] + cells[b]["point"],
                    "RESIDENT_LOW": cells[a]["low"] + cells[b]["low"],
                    "RESIDENT_HIGH": cells[a]["high"] + cells[b]["high"],
                    "N_MASKED_CELLS": cells[a]["masked"] + cells[b]["masked"],
                    "RESIDENT_CLIPPED": False,
                }
            )
        )
    under = {k: sum(cells[i][k] for i in UNDER60) for k in ("point", "low", "high", "masked")}
    point = total - under["point"]
    frames.append(
        pd.DataFrame(
            {
                "AGE_BAND": "60GU",
                "RESIDENT": point.clip(lower=0),
                "RESIDENT_LOW": (total - under["high"]).clip(lower=0),  # 0~59세 상한을 뺀다
                "RESIDENT_HIGH": (total - under["low"]).clip(lower=0),
                "N_MASKED_CELLS": under["masked"],
                "RESIDENT_CLIPPED": (total - under["high"]) < 0,
            }
        )
    )
    out = pd.concat(
        [f.assign(TOT_OA_CD=oa["TOT_OA_CD"].to_numpy()) for f in frames], ignore_index=True
    )
    resident_cols = ["RESIDENT", "RESIDENT_LOW", "RESIDENT_HIGH"]
    out.loc[np.tile(no_resident, len(AGE_BANDS)), resident_cols] = np.nan
    return out[["TOT_OA_CD", "AGE_BAND", *resident_cols, "N_MASKED_CELLS", "RESIDENT_CLIPPED"]]


def flow_by_band(master: pd.DataFrame) -> pd.DataFrame:
    """집계구 × 월 × 연령대 유동(남녀 합)과 그 연령대를 뺀 나머지 유동 합을 만든다."""
    flow = pd.DataFrame(
        {
            g: master[f"MAN_FLOW_POP_CNT_{g}_sum"] + master[f"WMAN_FLOW_POP_CNT_{g}_sum"]
            for g in AGE_BANDS
        }
    )
    total = flow.sum(axis=1, min_count=len(AGE_BANDS))
    out = flow.assign(TOT_OA_CD=master["TOT_OA_CD"], STD_YM=master["STD_YM"]).melt(
        ["TOT_OA_CD", "STD_YM"], var_name="AGE_BAND", value_name="FLOW"
    )
    out["FLOW_OTHER"] = np.tile(total.to_numpy(), len(AGE_BANDS)) - out["FLOW"]
    return out


def oa_table(master: pd.DataFrame) -> pd.DataFrame:
    """판단 보류에 쓰는 집계구 단위 속성표를 만든다."""
    return master.groupby("TOT_OA_CD", sort=False).agg(
        REGION=("REGION", "first"),
        ADM_CD=("ADM_CD", "first"),
        HAS_SK=("HAS_SK_POINTS", lambda s: s.astype(bool).all()),
        SMALL_SAMPLE=("is_small_sample", lambda s: s.astype(bool).any()),
        POP=(f"{SGIS}to_in_001", "first"),
        EMP=(f"{SGIS}to_em_020", "first"),
        HOUSEHOLDS=(f"{SGIS}to_ga_001", "first"),
        HOUSEHOLD_SIZE=(f"{SGIS}to_ga_002", "first"),
    )


def hold_reasons(
    resident: pd.DataFrame,
    oa: pd.DataFrame,
    min_resident: float = MIN_RESIDENT,
    work_q: float = WORK_Q,
    work_q_youth: float = WORK_Q_YOUTH,
) -> pd.DataFrame:
    """집계구 × 연령대에 `HOLD_REASON`(`;` 연결)과 `JUDGEMENT_STATUS`를 붙인다."""
    out = resident.join(oa[["REGION", "ADM_CD"]], on="TOT_OA_CD")
    attr = oa.reindex(out["TOT_OA_CD"]).reset_index(drop=True)
    pop = attr["POP"].where(attr["POP"] > 0)
    household_pop = attr["HOUSEHOLDS"] * attr["HOUSEHOLD_SIZE"]
    # 업무지 분위는 지역 안에서 센다. 합쳐서 세면 춘천 업무지가 거의 걸리지 않는다.
    work_ratio = (oa["EMP"] / oa["POP"].where(oa["POP"] > 0)).groupby(oa["REGION"])
    work_pct = work_ratio.rank(pct=True).reindex(out["TOT_OA_CD"]).to_numpy()
    work_cut = np.where(out["AGE_BAND"].isin(YOUTH_BANDS), 1 - work_q_youth, 1 - work_q)

    resident_value = out["RESIDENT"].to_numpy()
    flags = {
        "no_sk": ~attr["HAS_SK"].to_numpy(dtype=bool),
        "no_resident": pop.isna().to_numpy(),
        "small_sample": attr["SMALL_SAMPLE"].to_numpy(dtype=bool),
        "extreme_visitor": out["TOT_OA_CD"].isin(EXTREME_VISITOR).to_numpy(),
        "institution": (
            pop.notna()
            & (household_pop.fillna(0).le(0) | (pop / household_pop).gt(INSTITUTION_RATIO))
        ).to_numpy(),
        "zero_resident_band": resident_value <= 0,
        "small_resident_band": (resident_value > 0) & (resident_value < min_resident),
        "work_area": work_pct > work_cut,
    }
    reason = pd.Series("", index=out.index)
    for name in HOLD_ORDER:
        reason = reason.where(~flags[name], reason + ";" + name)
    reason = reason.str.lstrip(";")
    out["HOLD_REASON"] = reason.replace("", np.nan)
    out["JUDGEMENT_STATUS"] = np.where(reason.eq(""), "judged", "held")
    return out
