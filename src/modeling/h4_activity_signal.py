"""연령대별 기대 유동 모델, 활동 저하 신호 판정, 행정동 집계, 민감도.

기대값 모델(연령대별 OLS):
    log(FLOW_a) ~ log(RESIDENT_a) + log1p(EMPLOYEES) + log(FLOW_OTHER_a) + C(STD_YM) + C(REGION)
보류가 아닌 행으로만 적합하고, 잔차는 log가 정의되는 모든 행에 계산한다.
설계 근거: docs/design/activity_signal_design.md 3~6절, 민감도 절.

실행: uv run python -m src.modeling.h4_activity_signal
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.data import paths
from src.features import card_cohort
from src.features import h4_age_panel as h4

RANDOM_STATE = 42
N_MONTHS = 6
DEFAULT_K = 4
# 잔차 크기 기준. RESID < -0.1 = 기대보다 약 10% 낮음. 0이면 판정 집계구의 절반이 신호가 된다
# (ICC 0.92~0.97로 잔차가 집계구마다 거의 고정). 근거: 보고서 2절, 계획 4절.
DEFAULT_TAU = 0.1
N_BOOTSTRAP = 200
N_RESIDENT_QUANTILES = 5
STATUS_PATH = paths.INTERIM_DIR / "1차 merge" / "sgis2024_value_status.csv"
MASTER_PATH = paths.PROCESSED_DIR / "master_analysis.csv"
OUTPUTS = {
    "signal_oa": paths.PROCESSED_DIR / "h4_signal_oa.csv",
    "residual": paths.INTERIM_DIR / "h4_residual_oa_month.csv",
    "signal_dong": paths.PROCESSED_DIR / "h4_signal_dong.csv",
    "sensitivity": paths.INTERIM_DIR / "h4_sensitivity.csv",
    "diagnostics": paths.INTERIM_DIR / "h4_model_diagnostics.csv",
    "coefficients": paths.INTERIM_DIR / "h4_model_coefficients.csv",
    "resident_quantile": paths.INTERIM_DIR / "h4_resident_quantile_check.csv",
    "card_context": paths.PROCESSED_DIR / "card_sgg_context.csv",
}
PRIORITY_BANDS = ("60GU", "20G", "30G")


@dataclass(frozen=True)
class Spec:
    """모델·판정 설정. 민감도 변형은 이 값만 바꾼다."""

    k: int = DEFAULT_K
    tau: float = DEFAULT_TAU
    fixed_effect: str = "REGION"  # M1: "ADM_CD"
    scale: str = "FLOW_OTHER"  # M2: "FLOW_TOTAL"
    resident_col: str = "RESIDENT"  # M4: "RESIDENT_LOW", "RESIDENT_HIGH"
    min_resident: float = h4.MIN_RESIDENT
    work_q: float = h4.WORK_Q
    work_q_youth: float = h4.WORK_Q_YOUTH
    work_by_region: bool = True


# ponytail: M3(성별로 나눈 연령대)과 M5(60대 이상 직접 합)는 아직 없다. M5는 데이터 점검에서
# 빼기 계산과 차이 중앙값이 0.5% 이내라 우선순위를 낮췄다(보고서 1.3절).
VARIANTS = {
    "K3": Spec(k=3),
    "K5": Spec(k=5),
    "K6": Spec(k=6),
    "tau0": Spec(tau=0.0),
    "tau0.2": Spec(tau=0.2),
    "tau0.3": Spec(tau=0.3),
    "M1_dong_fe": Spec(fixed_effect="ADM_CD"),
    "M2_total_flow": Spec(scale="FLOW_TOTAL"),
    "M4_resident_low": Spec(resident_col="RESIDENT_LOW"),
    "M4_resident_high": Spec(resident_col="RESIDENT_HIGH"),
    "work_q10": Spec(work_q=0.10, work_q_youth=0.20),
    "work_q20": Spec(work_q=0.20, work_q_youth=0.20),
    "work_pooled": Spec(work_by_region=False),
    "min_resident10": Spec(min_resident=10),
    "min_resident50": Spec(min_resident=50),
}


def build_panel(master: pd.DataFrame, status: pd.DataFrame, spec: Spec = Spec()) -> pd.DataFrame:
    """집계구 × 월 × 연령대 패널(유동, 거주 인구, 종사자, 보류 사유)을 만든다."""
    oa = h4.oa_table(master)
    resident = h4.hold_reasons(
        h4.resident_by_band(master, status),
        oa,
        min_resident=spec.min_resident,
        work_q=spec.work_q,
        work_q_youth=spec.work_q_youth,
        work_by_region=spec.work_by_region,
    )
    flow = h4.flow_by_band(master)
    flow["FLOW_TOTAL"] = flow["FLOW"] + flow["FLOW_OTHER"]
    panel = flow.merge(resident, on=["TOT_OA_CD", "AGE_BAND"], how="left", validate="m:1")
    panel["EMPLOYEES"] = panel["TOT_OA_CD"].map(oa["EMP"])
    return panel


def _design(panel: pd.DataFrame, spec: Spec) -> pd.DataFrame:
    """회귀 설계행렬. 월·지역(또는 행정동)은 첫 범주를 뺀 더미다."""
    with np.errstate(divide="ignore", invalid="ignore"):
        x = pd.DataFrame(
            {
                "log_resident": np.log(
                    panel[spec.resident_col].where(panel[spec.resident_col] > 0)
                ),
                "log1p_employees": np.log1p(panel["EMPLOYEES"]),
                "log_scale": np.log(panel[spec.scale].where(panel[spec.scale] > 0)),
            },
            index=panel.index,
        )
    dummies = pd.get_dummies(
        panel[["STD_YM", spec.fixed_effect]].astype(str), drop_first=True, dtype=float
    )
    return pd.concat([x, dummies], axis=1)


def fit_expected(panel: pd.DataFrame, band: str, spec: Spec = Spec()) -> dict:
    """한 연령대의 기대값 모델을 적합하고 계수, R², 행별 기대값·잔차를 반환한다."""
    rows = panel[panel["AGE_BAND"] == band]
    x = _design(rows, spec)
    with np.errstate(divide="ignore"):
        y = np.log(rows["FLOW"].where(rows["FLOW"] > 0))
    valid = x.notna().all(axis=1) & y.notna()
    train = valid & rows["JUDGEMENT_STATUS"].eq("judged")
    model = LinearRegression().fit(x[train], y[train])
    log_expected = pd.Series(np.nan, index=rows.index)
    log_expected[valid] = model.predict(x[valid])
    return {
        "coef": pd.Series(model.coef_, index=x.columns),
        "intercept": model.intercept_,
        "r2": model.score(x[train], y[train]),
        "n_train": int(train.sum()),
        "log_expected": log_expected,
        "resid": y - log_expected,
    }


def residual_panel(panel: pd.DataFrame, spec: Spec = Spec()) -> tuple[pd.DataFrame, dict]:
    """모든 연령대를 적합해 `EXPECTED`, `RESID`를 붙인 패널과 연령대별 적합 결과를 반환한다."""
    out = panel.copy()
    fits = {}
    for band in h4.AGE_BANDS:
        fit = fit_expected(panel, band, spec)
        out.loc[fit["resid"].index, "RESID"] = fit["resid"]
        out.loc[fit["log_expected"].index, "EXPECTED"] = np.exp(fit["log_expected"])
        fits[band] = fit
    return out, fits


def persistence(
    resid_panel: pd.DataFrame, k: int = DEFAULT_K, tau: float = DEFAULT_TAU
) -> pd.DataFrame:
    """집계구 × 연령대로 `N_LOW_MONTHS`, `MEAN_RESID`, `SIGNAL`을 낸다. 보류 행은 결측이다.

    `N_LOW_MONTHS`는 `RESID < -tau`인 달 수, 신호는 그 달이 k개 이상이고 평균도 `-tau` 미만이다.
    """
    keys = ["TOT_OA_CD", "AGE_BAND"]
    first = (
        resid_panel.drop_duplicates(keys)
        .set_index(keys)
        .drop(columns=["STD_YM", "FLOW", "FLOW_OTHER", "FLOW_TOTAL", "EXPECTED", "RESID"])
    )
    g = resid_panel.groupby(keys)["RESID"]
    out = first.assign(
        N_VALID_MONTHS=g.count(),
        N_LOW_MONTHS=resid_panel["RESID"].lt(-tau).groupby([resid_panel[c] for c in keys]).sum(),
        MEAN_RESID=g.mean(),
    )
    out["N_LOW_MONTHS"] = out["N_LOW_MONTHS"].astype("Int64")
    out["SIGNAL"] = (out["N_LOW_MONTHS"] >= k) & (out["MEAN_RESID"] < -tau)
    held = out["JUDGEMENT_STATUS"].eq("held")
    out["SIGNAL"] = out["SIGNAL"].astype("boolean").mask(held)
    out["N_LOW_MONTHS"] = out["N_LOW_MONTHS"].mask(held)
    return out.reset_index()


def aggregate_dong(signal_oa: pd.DataFrame, resid_panel: pd.DataFrame) -> pd.DataFrame:
    """행정동 × 연령대로 신호 비율과 동 단위 합산 잔차를 낸다."""
    judged = signal_oa["JUDGEMENT_STATUS"].eq("judged")
    g = signal_oa.assign(JUDGED=judged, SIG=signal_oa["SIGNAL"].fillna(False).astype(bool))
    out = g.groupby(["ADM_CD", "AGE_BAND"]).agg(
        REGION=("REGION", "first"),
        N_OA=("TOT_OA_CD", "size"),
        N_JUDGED=("JUDGED", "sum"),
        N_SIGNAL=("SIG", "sum"),
        RESIDENT=("RESIDENT", "sum"),
    )
    out["N_HELD"] = out["N_OA"] - out["N_JUDGED"]
    out["SIGNAL_RATE"] = out["N_SIGNAL"] / out["N_JUDGED"].where(out["N_JUDGED"] > 0)
    # 보류 집계구도 포함해 동 전체 실제/기대 유동 비를 본다(잔차를 계산할 수 없는 행 제외).
    # ponytail: exp(log 예측)은 평균이 아니라 중앙값 쪽 기대값이다. 동 간 비교용 참고값으로만 쓴다.
    ok = resid_panel[resid_panel["RESID"].notna()]
    monthly = ok.groupby(["ADM_CD", "AGE_BAND", "STD_YM"])[["FLOW", "EXPECTED"]].sum()
    pooled = np.log(monthly["FLOW"] / monthly["EXPECTED"]).groupby(["ADM_CD", "AGE_BAND"]).mean()
    out["DONG_POOLED_RESID"] = pooled
    cols = ["REGION", "N_OA", "N_JUDGED", "N_HELD", "N_SIGNAL", "SIGNAL_RATE", "RESIDENT"]
    return out[[*cols, "DONG_POOLED_RESID"]].reset_index()


def icc(resid_panel: pd.DataFrame, band: str) -> float:
    """판정 행 월별 잔차의 집계구 내 상관 ICC(1)."""
    r = resid_panel[
        (resid_panel["AGE_BAND"] == band) & resid_panel["JUDGEMENT_STATUS"].eq("judged")
    ].dropna(subset=["RESID"])
    groups = r.groupby("TOT_OA_CD")["RESID"]
    n = groups.size()
    k0 = (n.sum() - (n**2).sum() / n.sum()) / (len(n) - 1)
    grand = r["RESID"].mean()
    ms_between = (n * (groups.mean() - grand) ** 2).sum() / (len(n) - 1)
    ms_within = ((r["RESID"] - groups.transform("mean")) ** 2).sum() / (n.sum() - len(n))
    return float((ms_between - ms_within) / (ms_between + (k0 - 1) * ms_within))


def resident_quantile_check(signal_oa: pd.DataFrame) -> pd.DataFrame:
    """거주 인구 5분위별 신호율·평균 잔차. 신호가 작은 집계구로 몰리는지 본다."""
    judged = signal_oa[signal_oa["JUDGEMENT_STATUS"].eq("judged")].copy()
    judged["RESIDENT_Q"] = judged.groupby("AGE_BAND")["RESIDENT"].transform(
        lambda s: pd.qcut(s, N_RESIDENT_QUANTILES, labels=False, duplicates="drop") + 1
    )
    return (
        judged.groupby(["AGE_BAND", "RESIDENT_Q"])
        .agg(
            N=("TOT_OA_CD", "size"),
            RESIDENT_MEDIAN=("RESIDENT", "median"),
            SIGNAL_RATE=("SIGNAL", "mean"),
            MEAN_RESID=("MEAN_RESID", "mean"),
        )
        .reset_index()
    )


def bootstrap_coefs(panel: pd.DataFrame, band: str, spec: Spec = Spec()) -> pd.DataFrame:
    """집계구 단위로 다시 뽑아 연속 변수 계수의 95% 구간을 낸다."""
    rng = np.random.default_rng(RANDOM_STATE)
    rows = panel[panel["AGE_BAND"] == band]
    codes = rows["TOT_OA_CD"].unique()
    by_oa = {c: g for c, g in rows.groupby("TOT_OA_CD")}
    draws = []
    for _ in range(N_BOOTSTRAP):
        sample = pd.concat([by_oa[c] for c in rng.choice(codes, len(codes))], ignore_index=True)
        coef = fit_expected(sample, band, spec)["coef"]
        draws.append(coef[["log_resident", "log1p_employees", "log_scale"]])
    d = pd.DataFrame(draws)
    return pd.DataFrame({"CI_LOW": d.quantile(0.025), "CI_HIGH": d.quantile(0.975)})


def run(master: pd.DataFrame, status: pd.DataFrame, spec: Spec = Spec()) -> dict:
    """패널 → 잔차 → 신호 → 행정동 집계를 한 번에 실행한다."""
    panel = build_panel(master, status, spec)
    resid, fits = residual_panel(panel, spec)
    signal_oa = persistence(resid, spec.k, spec.tau)
    return {
        "panel": panel,
        "resid": resid,
        "fits": fits,
        "signal_oa": signal_oa,
        "signal_dong": aggregate_dong(signal_oa, resid),
    }


def sensitivity(
    master: pd.DataFrame, status: pd.DataFrame, base: dict, variants: dict[str, Spec] = VARIANTS
) -> pd.DataFrame:
    """기본 설정 대비 신호 집계구 겹침(Jaccard)과 `MEAN_RESID` 순위상관을 연령대별로 낸다."""
    keys = ["TOT_OA_CD", "AGE_BAND"]
    b = base["signal_oa"].set_index(keys)
    rows = []
    for name, spec in variants.items():
        v = run(master, status, spec)["signal_oa"].set_index(keys)
        for band in h4.AGE_BANDS:
            bb, vb = b.xs(band, level="AGE_BAND"), v.xs(band, level="AGE_BAND")
            s1 = set(bb.index[bb["SIGNAL"].fillna(False).astype(bool)])
            s2 = set(vb.index[vb["SIGNAL"].fillna(False).astype(bool)])
            both = bb[["MEAN_RESID"]].join(vb[["MEAN_RESID"]], rsuffix="_V").dropna()
            rows.append(
                {
                    "VARIANT": name,
                    "AGE_BAND": band,
                    "N_SIGNAL_BASE": len(s1),
                    "N_SIGNAL_VARIANT": len(s2),
                    "JACCARD": len(s1 & s2) / len(s1 | s2) if s1 | s2 else np.nan,
                    "SPEARMAN_MEAN_RESID": both["MEAN_RESID"].corr(
                        both["MEAN_RESID_V"], method="spearman"
                    ),
                }
            )
    return pd.DataFrame(rows)


def diagnostics(result: dict) -> pd.DataFrame:
    """연령대별 R², 학습 행 수, ICC, 신호 수, 지역별 평균 잔차."""
    resid, signal_oa = result["resid"], result["signal_oa"]
    rows = []
    for band, fit in result["fits"].items():
        r = resid[(resid["AGE_BAND"] == band) & resid["JUDGEMENT_STATUS"].eq("judged")]
        s = signal_oa[signal_oa["AGE_BAND"] == band]
        rows.append(
            {
                "AGE_BAND": band,
                "R2": fit["r2"],
                "N_TRAIN": fit["n_train"],
                "ICC": icc(resid, band),
                "N_JUDGED_OA": int(s["JUDGEMENT_STATUS"].eq("judged").sum()),
                "N_SIGNAL_OA": int(s["SIGNAL"].fillna(False).sum()),
                **{
                    f"MEAN_RESID_{reg}": m for reg, m in r.groupby("REGION")["RESID"].mean().items()
                },
            }
        )
    return pd.DataFrame(rows)


def coefficient_table(result: dict, bands=PRIORITY_BANDS) -> pd.DataFrame:
    """연속 변수 계수와 집계구 부트스트랩 95% 구간."""
    rows = []
    for band in bands:
        coef = result["fits"][band]["coef"][["log_resident", "log1p_employees", "log_scale"]]
        ci = bootstrap_coefs(result["panel"], band)
        rows.append(ci.assign(COEF=coef, AGE_BAND=band).rename_axis("TERM").reset_index())
    return pd.concat(rows, ignore_index=True)[["AGE_BAND", "TERM", "COEF", "CI_LOW", "CI_HIGH"]]


DICTIONARIES = {
    "card_context": [
        ("MCT_SGG_CD", "가맹점 시군구(서울 강남구·강원 춘천시)", "", ""),
        ("SEX_CCD", "성별", "", ""),
        ("age_band", "카드 연령대(10~90, 10세 단위)", "세", ""),
        ("AGE_BAND", "SK 연령대 대응(60 이상은 60GU)", "", ""),
        ("amount", "이용금액 합(2025-07~12)", "원", ""),
        ("amount_ex", "미분류·비소비 업종(ZZ_나머지, 세금공과금)을 뺀 이용금액 합", "원", ""),
        ("CLASSIFIED_SHARE", "amount_ex / amount", "비율", ""),
        ("SOCIAL_SHARE_AMOUNT", "대면 관계 소비 12종 금액 / amount_ex", "비율", ""),
        ("SOCIAL_SHARE_COUNT", "대면 관계 소비 12종 건수 / 미분류 제외 건수", "비율", ""),
        (
            "OUTSIDE_SHARE",
            "춘천 가맹점의 강원 밖 고객 건수 비중. 고객 거주지가 시도 단위라 강원 다른 시군 "
            "고객은 지역 고객으로 잡혀 과소 추정",
            "비율",
            "강남(서울 고객이 강남구민인지 알 수 없음)",
        ),
    ],
    "signal_oa": [
        ("TOT_OA_CD", "집계구 코드(14자리 문자열)", "", ""),
        ("AGE_BAND", "SK 연령대(10G~50G, 60GU=60대 이상)", "", ""),
        ("RESIDENT", "해당 연령대 거주 인구 점추정(SGIS 2024, 비공개 칸 2.5명)", "명", "총인구 0"),
        (
            "RESIDENT_LOW",
            "거주 인구 하한(비공개 칸 1명, 60대 이상은 0~59세 상한을 뺌)",
            "명",
            "총인구 0",
        ),
        (
            "RESIDENT_HIGH",
            "거주 인구 상한(비공개 칸 4명, 60대 이상은 0~59세 하한을 뺌)",
            "명",
            "총인구 0",
        ),
        ("N_MASKED_CELLS", "비공개 5세 칸 수(60대 이상은 0~59세 칸 기준)", "개", ""),
        ("RESIDENT_CLIPPED", "60대 이상 빼기 결과가 음수라 0으로 자름", "bool", ""),
        ("REGION", "지역(강남구·춘천시)", "", ""),
        ("ADM_CD", "행정동 코드(8자리 문자열)", "", ""),
        ("HOLD_REASON", "판단 보류 사유(;로 연결)", "", "보류 아님"),
        ("JUDGEMENT_STATUS", "judged 또는 held", "", ""),
        ("EMPLOYEES", "총종사자수(SGIS 2024)", "명", ""),
        ("N_VALID_MONTHS", "잔차를 계산한 달 수", "개월", ""),
        ("N_LOW_MONTHS", "잔차 < -0.1(기대보다 약 10% 낮음)인 달 수", "개월", "보류"),
        (
            "MEAN_RESID",
            "6개월 평균 잔차 log(실제/기대). 보류 행도 계산되면 참고값",
            "log 비",
            "잔차 계산 불가",
        ),
        ("SIGNAL", "N_LOW_MONTHS >= 4 이고 MEAN_RESID < -0.1", "bool", "보류"),
    ],
    "residual": [
        ("TOT_OA_CD", "집계구 코드", "", ""),
        ("STD_YM", "기준 연월", "", ""),
        ("AGE_BAND", "SK 연령대", "", ""),
        (
            "FLOW",
            "해당 연령대 SK 일평균 유동(남녀 합, 시간대 합 인·시간으로 보임)",
            "인·시간",
            "SK 미매칭",
        ),
        ("EXPECTED", "기대 유동 exp(log 예측)", "인·시간", "잔차 계산 불가"),
        ("RESID", "log(FLOW) − log(EXPECTED)", "log 비", "잔차 계산 불가"),
        ("JUDGEMENT_STATUS", "judged 또는 held", "", ""),
    ],
    "signal_dong": [
        ("ADM_CD", "행정동 코드(8자리 문자열)", "", ""),
        ("AGE_BAND", "SK 연령대", "", ""),
        ("REGION", "지역", "", ""),
        ("N_OA", "행정동의 집계구 수", "개", ""),
        ("N_JUDGED", "판정한 집계구 수", "개", ""),
        ("N_HELD", "보류 집계구 수", "개", ""),
        ("N_SIGNAL", "신호 집계구 수", "개", ""),
        ("SIGNAL_RATE", "N_SIGNAL / N_JUDGED", "비율", "판정 집계구 0개"),
        ("RESIDENT", "해당 연령대 거주 인구 합(보류 포함)", "명", ""),
        (
            "DONG_POOLED_RESID",
            "동 전체 log(Σ실제/Σ기대)의 6개월 평균(보류 포함)",
            "log 비",
            "잔차 행 없음",
        ),
    ],
}


def save(df: pd.DataFrame, key: str) -> None:
    """CSV와 열 정의서를 UTF-8로 저장한다."""
    path = OUTPUTS[key]
    df.to_csv(path, index=False, encoding="utf-8")
    if key in DICTIONARIES:
        pd.DataFrame(
            DICTIONARIES[key], columns=["COLUMN", "DESCRIPTION", "UNIT", "MISSING"]
        ).to_csv(path.with_name(f"{path.stem}_dictionary.csv"), index=False, encoding="utf-8")
    print(f"saved {path.relative_to(paths.PROJECT_ROOT)} {df.shape}")


def main() -> None:
    """기본 설정 결과, 진단, 민감도를 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-sensitivity", action="store_true")
    parser.add_argument("--skip-card", action="store_true", help="신한카드 맥락표를 만들지 않는다")
    args = parser.parse_args()

    master = pd.read_csv(MASTER_PATH, dtype={"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str})
    status = pd.read_csv(STATUS_PATH, dtype=str)
    result = run(master, status)

    oa_cols = [c for c, *_ in DICTIONARIES["signal_oa"]]
    save(result["signal_oa"][oa_cols], "signal_oa")
    save(result["resid"][[c for c, *_ in DICTIONARIES["residual"]]], "residual")
    save(result["signal_dong"][[c for c, *_ in DICTIONARIES["signal_dong"]]], "signal_dong")
    save(diagnostics(result), "diagnostics")
    save(resident_quantile_check(result["signal_oa"]), "resident_quantile")
    save(coefficient_table(result), "coefficients")
    if not args.skip_sensitivity:
        save(sensitivity(master, status, result), "sensitivity")
    if not args.skip_card:
        context = card_cohort.sgg_context(card_cohort.cohort_panel(card_cohort.prepare_card(2)))
        save(context[[c for c, *_ in DICTIONARIES["card_context"]]], "card_context")


if __name__ == "__main__":
    main()
