"""#16 Task 1 데이터 점검: 연령대별 거주 인구·유동, 보류 사유 미리 보기, SK 유동 정의 간접 확인.

분석일: 2026-10-17. 결과는 reports/261017_REG_h4_activity_signal.md "데이터 점검" 절에 옮긴다.
실행: uv run python scripts/h4_data_check.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import paths

MASTER_PATH = paths.PROCESSED_DIR / "master_analysis.csv"
STATUS_PATH = paths.INTERIM_DIR / "1차 merge" / "sgis2024_value_status.csv"
SGIS = "SGIS2024_"
BANDS = {"10G": (3, 4), "20G": (5, 6), "30G": (7, 8), "40G": (9, 10), "50G": (11, 12)}
UNDER60 = range(1, 13)  # in_age_001~012 = 0~59세
OVER60 = range(13, 22)  # in_age_013~021 = 60~100세 이상
MASKED_POINT, MASKED_LOW, MASKED_HIGH = 2.5, 1.0, 4.0
MIN_RESIDENT_GRID = (10, 20, 50)
INSTITUTION_RATIO = 1.5  # 총인구 / 가구원 수 합. 넘으면 집단시설 인구가 1/3 이상 섞인 집계구
WORK_Q_GRID = (0.05, 0.10, 0.20)
GRID_AREA_M2 = 2_500  # SK 50m 격자
# #12 코멘트(2026-10-15) "전체 기준 후보 11개 (춘천)"
EXTREME_VISITOR = (
    "32010320030001", "32010350010001", "32010360010005", "32010360020001",
    "32010570060001", "32010370010005", "32010390010002", "32010600010020",
    "32010310040003", "32010360010004", "32010370010007",
)  # fmt: skip


def age_col(i: int) -> str:
    """5세 단위 남녀 합계 연령 열 이름."""
    return f"{SGIS}in_age_{i:03d}"


def resident_by_band(oa: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """집계구 × 연령대 거주 인구(점추정·하한·상한)를 계산한다."""
    st = status.set_index("TOT_OA_CD").reindex(oa.index)
    cells = {}
    for i in list(UNDER60) + list(OVER60):
        c = age_col(i)
        v = oa[c].astype(float)
        masked = st[c].eq("source_na")
        no_rec = st[c].eq("no_record")
        cells[i] = {
            "point": v.mask(masked, MASKED_POINT).mask(no_rec, 0.0),
            "low": v.mask(masked, MASKED_LOW).mask(no_rec, 0.0),
            "high": v.mask(masked, MASKED_HIGH).mask(no_rec, 0.0),
            "masked": masked,
        }
    # 0~59세 칸이 모두 비어도 총인구가 있으면 거주 인구가 있다(요양시설: 11230760040002)
    no_resident = oa[f"{SGIS}to_in_001"].fillna(0).le(0)
    total = oa[f"{SGIS}to_in_001"].astype(float)
    rows = []
    for band, (a, b) in BANDS.items():
        rows.append(
            pd.DataFrame(
                {
                    "AGE_BAND": band,
                    "RESIDENT": cells[a]["point"] + cells[b]["point"],
                    "RESIDENT_LOW": cells[a]["low"] + cells[b]["low"],
                    "RESIDENT_HIGH": cells[a]["high"] + cells[b]["high"],
                    "N_MASKED_CELLS": cells[a]["masked"].astype(int) + cells[b]["masked"],
                }
            )
        )
    under = {k: sum(cells[i][k] for i in UNDER60) for k in ("point", "low", "high")}
    rows.append(
        pd.DataFrame(
            {
                "AGE_BAND": "60GU",
                "RESIDENT": total - under["point"],
                "RESIDENT_LOW": total - under["high"],
                "RESIDENT_HIGH": total - under["low"],
                "N_MASKED_CELLS": sum(cells[i]["masked"].astype(int) for i in UNDER60),
                "RESIDENT_DIRECT": sum(cells[i]["point"] for i in OVER60),
            }
        )
    )
    out = pd.concat(rows).rename_axis("TOT_OA_CD").reset_index()
    out["NO_RESIDENT"] = out["TOT_OA_CD"].map(no_resident)
    out.loc[out["NO_RESIDENT"], ["RESIDENT", "RESIDENT_LOW", "RESIDENT_HIGH"]] = np.nan
    return out


def flow_by_band(master: pd.DataFrame) -> pd.DataFrame:
    """집계구 × 월 × 연령대 유동(남녀 합)과 나머지 연령대 유동 합을 만든다."""
    bands = list(BANDS) + ["60GU"]
    flow = pd.DataFrame(
        {
            g: master[f"MAN_FLOW_POP_CNT_{g}_sum"] + master[f"WMAN_FLOW_POP_CNT_{g}_sum"]
            for g in bands
        }
    )
    total = flow.sum(axis=1, min_count=len(bands))
    long = flow.assign(TOT_OA_CD=master["TOT_OA_CD"], STD_YM=master["STD_YM"]).melt(
        ["TOT_OA_CD", "STD_YM"], var_name="AGE_BAND", value_name="FLOW"
    )
    long["FLOW_OTHER"] = np.tile(total.to_numpy(), len(bands)) - long["FLOW"]
    return long


def section(title: str) -> None:
    """출력 구분선."""
    print(f"\n## {title}")


def main() -> None:
    """점검 결과를 표로 출력한다."""
    master = pd.read_csv(MASTER_PATH, dtype={"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str})
    status = pd.read_csv(STATUS_PATH, dtype=str)
    print("master", master.shape, "status", status.shape)

    oa = master.drop_duplicates("TOT_OA_CD").set_index("TOT_OA_CD")
    res = resident_by_band(oa, status).merge(
        oa[["REGION", "ADM_CD", f"{SGIS}to_em_020", f"{SGIS}to_in_001"]],
        left_on="TOT_OA_CD",
        right_index=True,
    )
    flow = flow_by_band(master)

    section("1. 연령대별 거주 인구 분포 (점추정, 거주 인구 없는 집계구 제외)")
    q = [0.05, 0.25, 0.5, 0.75, 0.95]
    print(res.groupby("AGE_BAND")["RESIDENT"].quantile(q).unstack().round(1))
    zero = res[~res["NO_RESIDENT"]].assign(Z=lambda d: d["RESIDENT"].le(0))
    print("거주 인구 <= 0 집계구 수:", zero.groupby("AGE_BAND")["Z"].sum().to_dict())
    print("비공개 칸 1개 이상 비율:")
    print(res.groupby("AGE_BAND")["N_MASKED_CELLS"].apply(lambda s: s.gt(0).mean()).round(3))

    section("2. 연령대별 유동 분포 (집계구-월)")
    print(flow.groupby("AGE_BAND")["FLOW"].quantile(q).unstack().round(1))
    print("FLOW 결측:", flow["FLOW"].isna().sum(), "FLOW<=0:", flow["FLOW"].le(0).sum())
    print("FLOW_OTHER<=0:", flow["FLOW_OTHER"].le(0).sum())

    section("3. 유동/거주 비율 (6개월 평균 유동 / 거주 인구), 지역별 중앙값")
    mean_flow = flow.groupby(["TOT_OA_CD", "AGE_BAND"])["FLOW"].mean().rename("FLOW_MEAN")
    ratio = res.join(mean_flow, on=["TOT_OA_CD", "AGE_BAND"])
    ratio = ratio[ratio["RESIDENT"].gt(0)]
    ratio["RATIO"] = ratio["FLOW_MEAN"] / ratio["RESIDENT"]
    print(ratio.groupby(["REGION", "AGE_BAND"])["RATIO"].median().unstack().round(2))

    section("4. 60대 이상: 빼기 vs 직접 합, 음수")
    r60 = res[(res["AGE_BAND"] == "60GU") & ~res["NO_RESIDENT"]].copy()
    r60["DIFF_RATE"] = (r60["RESIDENT"] - r60["RESIDENT_DIRECT"]) / r60["RESIDENT"]
    print(r60.groupby("REGION")["DIFF_RATE"].describe().round(3))
    print("점추정 < 0:", r60.groupby("REGION")["RESIDENT"].apply(lambda s: s.lt(0).sum()).to_dict())
    print(
        "하한 < 0:", r60.groupby("REGION")["RESIDENT_LOW"].apply(lambda s: s.lt(0).sum()).to_dict()
    )

    section("5. 보류 사유 미리 보기 (집계구 수, 사유는 겹칠 수 있음)")
    sk = master.groupby("TOT_OA_CD").agg(
        NO_SK=("HAS_SK_POINTS", lambda s: ~s.astype(bool).all()),
        SMALL=("is_small_sample", lambda s: s.astype(bool).any()),
        SMALL_VARIES=("is_small_sample", "nunique"),
    )
    print("is_small_sample이 월마다 바뀌는 집계구:", int(sk["SMALL_VARIES"].gt(1).sum()))
    res = res.join(sk, on="TOT_OA_CD")
    res["EXTREME"] = res["TOT_OA_CD"].isin(EXTREME_VISITOR)
    household_pop = oa[f"{SGIS}to_ga_001"] * oa[f"{SGIS}to_ga_002"]
    inst_ratio = oa[f"{SGIS}to_in_001"] / household_pop.where(lambda s: s > 0)
    institution = oa[f"{SGIS}to_in_001"].gt(0) & (
        household_pop.fillna(0).le(0) | inst_ratio.gt(INSTITUTION_RATIO)
    )
    res["INSTITUTION"] = res["TOT_OA_CD"].map(institution)
    print(
        "집단시설 인구가 섞인 집계구:",
        int(institution.sum()),
        oa.loc[institution, "REGION"].value_counts().to_dict(),
    )
    work_ratio = oa[f"{SGIS}to_em_020"] / oa[f"{SGIS}to_in_001"].where(lambda s: s > 0)
    res["WORK_RATIO"] = res["TOT_OA_CD"].map(work_ratio)
    res["WORK_PCT_REGION"] = res.groupby(["REGION", "AGE_BAND"])["WORK_RATIO"].rank(pct=True)
    res["WORK_PCT_ALL"] = res.groupby("AGE_BAND")["WORK_RATIO"].rank(pct=True)

    base = {
        "no_sk": res["NO_SK"],
        "no_resident": res["NO_RESIDENT"],
        "small_sample": res["SMALL"],
        "extreme_visitor": res["EXTREME"],
        "institution": res["INSTITUTION"],
        "zero_resident_band": ~res["NO_RESIDENT"] & res["RESIDENT"].le(0),
    }
    for m in MIN_RESIDENT_GRID:
        base[f"small_resident_band<{m}"] = ~res["NO_RESIDENT"] & res["RESIDENT"].between(
            0, m, inclusive="neither"
        )
    for wq in WORK_Q_GRID:
        base[f"work_area_region_top{int(wq * 100)}"] = res["WORK_PCT_REGION"].gt(1 - wq)
        base[f"work_area_all_top{int(wq * 100)}"] = res["WORK_PCT_ALL"].gt(1 - wq)
    hold = pd.DataFrame(base).assign(AGE_BAND=res["AGE_BAND"], REGION=res["REGION"])
    print(hold.groupby("AGE_BAND").sum(numeric_only=True).T)
    print("\n강남/춘천 분리 (work_area, 60GU):")
    print(
        hold[hold["AGE_BAND"] == "60GU"]
        .groupby("REGION")[[c for c in hold if c.startswith("work_area")]]
        .sum()
        .T
    )

    default_work = np.where(
        res["AGE_BAND"].isin(["20G", "30G"]),
        res["WORK_PCT_REGION"].gt(0.90),
        res["WORK_PCT_REGION"].gt(0.95),
    )
    held_any = (
        base["no_sk"] | base["no_resident"] | base["small_sample"] | base["extreme_visitor"]
        | base["institution"] | base["zero_resident_band"] | base["small_resident_band<20"] | default_work
    )  # fmt: skip
    summary = res.assign(HELD=held_any).groupby(["AGE_BAND", "REGION"])["HELD"].agg(["sum", "mean"])
    print("\n기본 설정(MIN_RESIDENT=20, work 5%/20~30대 10%, 지역별)으로 보류되는 집계구:")
    print(summary.round(3))
    dong = res.assign(HELD=held_any).groupby(["AGE_BAND", "ADM_CD"])["HELD"].agg(["size", "sum"])
    dong["N_JUDGED"] = dong["size"] - dong["sum"]
    print(
        "판정 집계구 0개인 동:", dong[dong["N_JUDGED"].eq(0)].groupby("AGE_BAND").size().to_dict()
    )
    print(
        "판정 집계구 5개 미만인 동:",
        dong[dong["N_JUDGED"].lt(5)].groupby("AGE_BAND").size().to_dict(),
    )

    section("6. SK 유동에 거주자 포함 여부 (간접 확인, 6개월 평균)")
    hours = master.groupby("TOT_OA_CD")[[f"TMST_{h:02d}_sum" for h in range(24)]].mean()
    age_total = flow.groupby(["TOT_OA_CD", "STD_YM"])["FLOW"].sum().groupby("TOT_OA_CD").mean()
    chk = pd.DataFrame(
        {
            "NIGHT": hours["TMST_03_sum"],
            "DAY": hours["TMST_14_sum"],
            "HOUR_SUM": hours.sum(axis=1),
            "AGE_TOTAL": age_total,
            "POP": oa[f"{SGIS}to_in_001"],
            "EMP": oa[f"{SGIS}to_em_020"],
            "REGION": oa["REGION"],
        }
    ).dropna()
    chk = chk[chk["POP"].gt(0)]
    cover = (master.groupby("TOT_OA_CD")["N_GRID"].mean() * GRID_AREA_M2 / oa["AREA_M2"]).clip(
        upper=1
    )
    print(
        "격자 커버리지(격자 수 x 2,500m2 / 면적) 분위:",
        cover.quantile([0.1, 0.5, 0.9]).round(3).to_dict(),
    )
    chk["WORK_Q"] = pd.qcut(
        chk["EMP"] / chk["POP"], 5, labels=["Q1 주거", "Q2", "Q3", "Q4", "Q5 업무"]
    )
    print("종사자/거주 5분위별 03시 유동 / 거주 인구 중앙값:")
    print(
        chk.assign(R=chk["NIGHT"] / chk["POP"])
        .groupby("WORK_Q", observed=True)["R"]
        .median()
        .round(3)
    )
    print(
        "log 거주 인구 표준편차:",
        round(np.log(chk["POP"]).std(), 3),
        "log1p 종사자 표준편차:",
        round(np.log1p(chk["EMP"]).std(), 3),
    )
    print("AGE_TOTAL / HOUR_SUM 중앙값:", round((chk["AGE_TOTAL"] / chk["HOUR_SUM"]).median(), 3))
    print("AGE_TOTAL / NIGHT 중앙값:", round((chk["AGE_TOTAL"] / chk["NIGHT"]).median(), 3))
    for reg, g in chk.groupby("REGION"):
        lg = np.log1p(g[["NIGHT", "DAY", "POP", "EMP"]])
        print(
            reg,
            "n=",
            len(g),
            "| corr(log 03시, log 거주)=",
            round(lg["NIGHT"].corr(lg["POP"]), 3),
            "corr(log 03시, log 종사자)=",
            round(lg["NIGHT"].corr(lg["EMP"]), 3),
            "| corr(log 14시, log 거주)=",
            round(lg["DAY"].corr(lg["POP"]), 3),
            "corr(log 14시, log 종사자)=",
            round(lg["DAY"].corr(lg["EMP"]), 3),
            "| 03시/거주 중앙값=",
            round((g["NIGHT"] / g["POP"]).median(), 3),
        )


if __name__ == "__main__":
    main()
