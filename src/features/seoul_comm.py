"""강남 동별 1차 프로토타입 민감도와 서울 통신 보조 지표를 정리한다.

통신 관심집단 검증의 v3.3 주 대조 지표는 로컬 결과를 읽기만 한다. 원자료와 결과 CSV는 Git에 넣지 않는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.data import paths
from src.evaluation import telecom_validation as tv

MASTER = paths.PROCESSED_DIR / "master_sgis2024_selected_no_industry_counts.csv"
INTEREST_COLUMNS = {
    "외출-커뮤니케이션이 모두 적은 집단(전체)": "main_low",
    "외출이 매우 적은 집단(전체)": "low_out",
    "커뮤니케이션이 적은 집단": "low_comm",
}
TELECOM_COLUMNS = {
    "평균 통화대상자 수": ("contacts", None),
    "집 추정 위치 평일 총 체류시간": (
        "home_weekday",
        "집 추정 위치 평일 총 체류시간 미추정 인구수",
    ),
    "집 추정 위치 휴일 총 체류시간": (
        "home_holiday",
        "집 추정 위치 휴일 총 체류시간 미추정 인구수",
    ),
    "평일 총 이동 횟수": ("moves_weekday", "평일 총 이동 횟수 미추정 인구수"),
    "휴일 총 이동 횟수 평균": ("moves_holiday", "휴일 이동 미추정 인구수"),
}
TARGET_AGES = {"all": None, "old65": (65, 70, 75), "old60": (60, 65, 70, 75)}
MASTER_COLS = [
    "STD_YM",
    "TOT_OA_CD",
    "ADM_CD",
    "REGION",
    "SGIS2024_to_in_001",
    "SGIS2024_to_ga_001",
    "SGIS2024_to_ho_001",
    "HAS_SK_POINTS",
]
GANGNAM = "11230"
N_OA = 1698
N_MISSING = 49
N_DONG = 22
N_BOOT = 2000
SEED = 42


def prototype_files(interim_dir: Path = paths.INTERIM_DIR) -> tuple[Path, Path]:
    folders = [
        p
        for p in interim_dir.iterdir()
        if p.is_dir() and (p / "isolation_index_prototype.csv").is_file()
    ]
    if len(folders) != 1:
        raise FileNotFoundError(
            f"expected one prototype folder under {interim_dir}, found {len(folders)}"
        )
    return folders[0] / "isolation_index_prototype.csv", folders[0] / "isolation_index_no_oldho.csv"


def load_prototypes() -> tuple[pd.DataFrame, pd.DataFrame]:
    files = prototype_files()
    base, without = [pd.read_csv(p, dtype={"TOT_OA_CD": str, "ADM_CD": str}) for p in files]
    for data in (base, without):
        if data["TOT_OA_CD"].duplicated().any():
            raise ValueError("prototype has duplicate TOT_OA_CD")
    if set(base["TOT_OA_CD"]) != set(without["TOT_OA_CD"]):
        raise ValueError("prototype versions have different OA sets")
    if (
        not base.set_index("TOT_OA_CD")["ADM_CD"]
        .sort_index()
        .equals(without.set_index("TOT_OA_CD")["ADM_CD"].sort_index())
    ):
        raise ValueError("prototype versions disagree on ADM_CD")
    if (
        not base.set_index("TOT_OA_CD")["SGIS2024_to_ga_001"]
        .sort_index()
        .equals(without.set_index("TOT_OA_CD")["SGIS2024_to_ga_001"].sort_index())
    ):
        raise ValueError("prototype versions disagree on household weights")
    return base, without


def master_oa(master: pd.DataFrame) -> pd.DataFrame:
    """월 반복 마스터에서 7월의 집계구별 한 행을 선택하고 SGIS 값 불변을 검사한다."""
    cols = ["SGIS2024_to_in_001", "SGIS2024_to_ga_001", "SGIS2024_to_ho_001"]
    if master.duplicated(["STD_YM", "TOT_OA_CD"]).any():
        raise ValueError("master has duplicate month/OA keys")
    if master.groupby("TOT_OA_CD")[cols + ["ADM_CD"]].nunique(dropna=False).gt(1).any().any():
        raise ValueError("master SGIS values or ADM_CD vary by month")
    first = master.loc[master["STD_YM"] == "202507"].copy()
    if len(first) != N_OA or first["TOT_OA_CD"].nunique() != N_OA:
        raise ValueError(f"expected {N_OA} July OA rows, got {len(first)}")
    return first


def excluded_oa(master: pd.DataFrame, prototype: pd.DataFrame) -> pd.DataFrame:
    """빠진 코드를 모두 보존하고 실패 조건과 설명용 대표 사유를 붙인다."""
    missing = master.loc[~master["TOT_OA_CD"].isin(prototype["TOT_OA_CD"])].copy()
    if len(missing) != N_MISSING:
        raise ValueError(f"expected {N_MISSING} missing OA, got {len(missing)}")
    checks = {
        "no_population": missing["SGIS2024_to_in_001"].fillna(0).le(0),
        "no_households": missing["SGIS2024_to_ga_001"].fillna(0).le(0),
        "no_housing": missing["SGIS2024_to_ho_001"].fillna(0).le(0),
        "no_sk": ~missing["HAS_SK_POINTS"].astype(str).str.lower().eq("true"),
    }
    for name, failed in checks.items():
        missing[name] = failed
    missing["primary_reason"] = np.select(
        list(checks.values()), list(checks), default="unexplained"
    )
    if (missing["primary_reason"] == "unexplained").any():
        raise ValueError("missing OA without a documented exclusion condition")
    return missing.sort_values("TOT_OA_CD", ignore_index=True)


def prototype_dong(master: pd.DataFrame, base: pd.DataFrame, without: pd.DataFrame) -> pd.DataFrame:
    """같은 집계구·가구 가중치로 두 점수를 동에 올리고 평가 범위를 함께 붙인다."""
    merged = base[["TOT_OA_CD", "ADM_CD", "SGIS2024_to_ga_001", "score", "grade"]].merge(
        without[["TOT_OA_CD", "score", "grade"]],
        on="TOT_OA_CD",
        validate="one_to_one",
        suffixes=("_with_oldho", "_no_oldho"),
    )
    hh = merged["SGIS2024_to_ga_001"]
    if hh.isna().any() or hh.le(0).any():
        raise ValueError("evaluated OA has invalid household weight")
    if merged[["score_with_oldho", "score_no_oldho"]].isna().any().any():
        raise ValueError("evaluated OA has missing prototype score")
    for variant in ("with_oldho", "no_oldho"):
        merged[f"weighted_{variant}"] = merged[f"score_{variant}"] * hh
        merged[f"grade5_hh_{variant}"] = hh.where(merged[f"grade_{variant}"] == 5, 0)
        merged[f"grade5_oa_{variant}"] = merged[f"grade_{variant}"].eq(5)
    group = merged.groupby("ADM_CD").agg(
        n_oa_eval=("TOT_OA_CD", "size"),
        hh_eval=("SGIS2024_to_ga_001", "sum"),
        **{f"weighted_{v}": (f"weighted_{v}", "sum") for v in ("with_oldho", "no_oldho")},
        **{f"grade5_hh_{v}": (f"grade5_hh_{v}", "sum") for v in ("with_oldho", "no_oldho")},
        **{f"grade5_oa_{v}": (f"grade5_oa_{v}", "sum") for v in ("with_oldho", "no_oldho")},
    )
    for variant in ("with_oldho", "no_oldho"):
        group[f"score_{variant}"] = group.pop(f"weighted_{variant}") / group["hh_eval"]
        group[f"grade5_hh_share_{variant}"] = group[f"grade5_hh_{variant}"] / group["hh_eval"]
    all_dong = master.groupby("ADM_CD").agg(
        n_oa_total=("TOT_OA_CD", "size"),
        hh_total=("SGIS2024_to_ga_001", "sum"),
    )
    out = all_dong.join(group)
    out["n_oa_missing"] = out["n_oa_total"] - out["n_oa_eval"].fillna(0)
    out["share_hh_eval"] = out["hh_eval"] / out["hh_total"].replace(0, np.nan)
    return out.reset_index()


def monthly_ratio(df: pd.DataFrame, value: str, target: str) -> pd.Series:
    ages = TARGET_AGES[target]
    cells = df if ages is None else df[df["age"].isin(ages)]
    if cells[[value, "pop"]].isna().any().any() or cells["pop"].le(0).any():
        raise ValueError(f"invalid interest group numerator or denominator: {value}")
    monthly = cells.groupby(["ADM_CD", "ym"])[[value, "pop"]].sum(min_count=1)
    if monthly["pop"].le(0).any():
        raise ValueError("interest group denominator is zero")
    return (monthly[value] / monthly["pop"]).groupby("ADM_CD").mean()


def interest_supplement(files: list[Path] | None = None) -> pd.DataFrame:
    files = paths.interest_group_files() if files is None else files
    columns = ["자치구", "행정동코드", "성별", "연령대", "총인구", *INTEREST_COLUMNS]
    frames = []
    for file in files:
        raw = pd.read_excel(file, usecols=columns, dtype={"행정동코드": str})
        frames.append(raw.loc[raw["자치구"] == "강남구"].assign(ym=tv.ym_from_file(file)))
    df = pd.concat(frames, ignore_index=True).rename(
        columns={
            "행정동코드": "dong_cd",
            "성별": "sex",
            "연령대": "age",
            "총인구": "pop",
            **INTEREST_COLUMNS,
        }
    )
    if df.duplicated(["ym", "dong_cd", "sex", "age"]).any() or len(df) != 528 * 6:
        raise ValueError("interest group cells are missing or duplicated")
    df["ADM_CD"] = tv.to_sgis_code(df["dong_cd"])
    out = pd.DataFrame(index=sorted(df["ADM_CD"].unique()))
    for value in INTEREST_COLUMNS.values():
        for target in ("old60",) if value == "main_low" else TARGET_AGES:
            out[f"ratio_pop_{value}_{target}"] = monthly_ratio(df, value, target)
    return out.rename_axis("ADM_CD").reset_index()


def weighted_monthly(
    df: pd.DataFrame, value: str, missing: str | None, target: str
) -> pd.DataFrame:
    ages = TARGET_AGES[target]
    cells = (df if ages is None else df[df["age"].isin(ages)]).copy()
    cells["weight"] = cells["pop"] if missing is None else cells["pop"] - cells[missing]
    if cells["weight"].lt(0).any():
        raise ValueError(f"negative valid population for {value}")
    cells.loc[cells[value].isna(), "weight"] = 0
    cells["weighted"] = cells[value].fillna(0) * cells["weight"]
    monthly = cells.groupby(["ADM_CD", "ym"]).agg(
        weighted=("weighted", "sum"),
        valid_pop=("weight", "sum"),
        pop=("pop", "sum"),
    )
    monthly["value"] = monthly["weighted"] / monthly["valid_pop"].replace(0, np.nan)
    monthly["coverage"] = np.nan if missing is None else monthly["valid_pop"] / monthly["pop"]
    return monthly.groupby("ADM_CD")[["value", "coverage"]].mean()


def telecom_supplement(files: list[Path] | None = None) -> pd.DataFrame:
    files = (
        sorted((paths.REFERENCE_DIR / "서울_29개_통신정보").glob("*.xlsx"))
        if files is None
        else files
    )
    if len(files) != 6:
        raise FileNotFoundError(f"expected 6 telecom files, found {len(files)}")
    columns = ["행정동코드", "성별", "연령대", "총인구수", *TELECOM_COLUMNS]
    columns += [m for _, m in TELECOM_COLUMNS.values() if m is not None]
    frames = []
    for file in files:
        raw = pd.read_excel(file, usecols=columns, dtype={"행정동코드": str})
        frames.append(
            raw.loc[raw["행정동코드"].str.startswith(GANGNAM)].assign(ym=tv.ym_from_file(file))
        )
    df = pd.concat(frames, ignore_index=True).rename(
        columns={"행정동코드": "dong_cd", "성별": "sex", "연령대": "age", "총인구수": "pop"}
    )
    if df.duplicated(["ym", "dong_cd", "sex", "age"]).any() or len(df) != 528 * 6:
        raise ValueError("telecom cells are missing or duplicated")
    df["ADM_CD"] = tv.to_sgis_code(df["dong_cd"])
    out = pd.DataFrame(index=sorted(df["ADM_CD"].unique()))
    for source, (name, missing) in TELECOM_COLUMNS.items():
        for target in TARGET_AGES:
            mean = weighted_monthly(df, source, missing, target)
            out[f"{name}_{target}"] = mean["value"]
            out[f"coverage_{name}_{target}"] = mean["coverage"]
    return out.rename_axis("ADM_CD").reset_index()


def correlations(table: pd.DataFrame) -> pd.DataFrame:
    predictors = ("score_with_oldho", "score_no_oldho", "score_w")
    targets = [
        c for c in table if c.startswith("ratio_pop_") and not c.startswith("ratio_pop_oldho")
    ]
    targets += [
        f"{name}_{target}" for name, _ in TELECOM_COLUMNS.values() for target in TARGET_AGES
    ]
    rows = []
    for predictor in predictors:
        for target in targets:
            valid = table[[predictor, target]].dropna()
            rho, p = (
                stats.spearmanr(valid[predictor], valid[target])
                if len(valid) >= 3
                else (np.nan, np.nan)
            )
            rows.append(
                {
                    "predictor": predictor,
                    "target": target,
                    "n_dong": len(valid),
                    "rho": rho,
                    "p_value": p,
                }
            )
    return pd.DataFrame(rows)


def paired_sensitivity(table: pd.DataFrame, target: str, n_boot: int = N_BOOT) -> dict:
    cols = ["score_with_oldho", "score_no_oldho", target]
    valid = table[cols].dropna()
    if len(valid) != N_DONG:
        raise ValueError(f"expected {N_DONG} paired dong, got {len(valid)}")

    def delta(frame: pd.DataFrame) -> float:
        return (
            stats.spearmanr(frame[cols[0]], frame[target]).statistic
            - stats.spearmanr(frame[cols[1]], frame[target]).statistic
        )

    rng = np.random.default_rng(SEED)
    boots = [delta(valid.iloc[rng.integers(0, len(valid), len(valid))]) for _ in range(n_boot)]
    loo = [delta(valid.drop(valid.index[i])) for i in range(len(valid))]
    return {
        "target": target,
        "n_dong": len(valid),
        "rho_difference": delta(valid),
        "ci_low": np.nanpercentile(boots, 2.5),
        "ci_high": np.nanpercentile(boots, 97.5),
        "loo_min": min(loo),
        "loo_max": max(loo),
    }


def build_tables(
    master: pd.DataFrame,
    base: pd.DataFrame,
    without: pd.DataFrame,
    reference: pd.DataFrame,
    interest: pd.DataFrame,
    telecom: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exposure = prototype_dong(master, base, without)
    table = reference.merge(
        exposure, on="ADM_CD", validate="one_to_one", suffixes=("_v33", "_prototype")
    )
    table = table.merge(interest, on="ADM_CD", validate="one_to_one").merge(
        telecom, on="ADM_CD", validate="one_to_one"
    )
    if len(table) != N_DONG or table["ADM_CD"].duplicated().any():
        raise ValueError("expected 22 matched Gangnam dong")
    table["rank_with_oldho"] = table["score_with_oldho"].rank(ascending=False, method="min")
    table["rank_no_oldho"] = table["score_no_oldho"].rank(ascending=False, method="min")
    table["rank_change"] = table["rank_no_oldho"] - table["rank_with_oldho"]
    supp = table[
        ["ADM_CD", "ADM_NM", *interest.columns.drop("ADM_CD"), *telecom.columns.drop("ADM_CD")]
    ].copy()
    return table.sort_values("ADM_CD", ignore_index=True), supp.sort_values(
        "ADM_CD", ignore_index=True
    )


def write_dictionary(table: pd.DataFrame, path: Path) -> None:
    descriptions = {
        "ADM_CD": "SGIS 8자리 행정동 코드",
        "ADM_NM": "SGIS 행정동명",
        "dong_cd": "서울 통신자료 7자리 행정동 코드",
        "dong_nm": "서울 통신자료 행정동명",
        "TOT_OA_CD": "SGIS 집계구 코드",
        "primary_reason": "제외 조건 우선순위에 따른 대표 사유",
        "ratio_pop_all": "통신 검증 전체 관심집단 추정 인원 / 동일 통신자료 인구의 월별 비율 6개월 평균",
        "ratio_pop_old65": "통신 검증 65세 이상 관심집단 추정 비율",
        "score_with_oldho": "1차 프로토타입 노후주택 포함 집계구 점수의 일반가구 가중 동 평균",
        "score_no_oldho": "1차 프로토타입 노후주택 제외 집계구 점수의 일반가구 가중 동 평균",
        "score_w": "v3.3의 유효 일반가구 가중 동 점수; 1차 프로토타입 점수와 척도가 다름",
        "share_hh_eval": "전체 일반가구 중 1차 프로토타입 평가 집계구에 속한 가구 비중",
        "rank_change": "노후주택 제외 순위 - 포함 순위; 양수면 제외 후 순위 하락",
    }
    rows = []
    for col in table.columns:
        desc = descriptions.get(col)
        if desc is None:
            if col.startswith("ratio_pop_"):
                desc = "해당 관심집단 추정 인원 / 같은 동·성·연령·월 인구의 비율, 월별 산출 후 6개월 평균"
            elif col.startswith("coverage_"):
                desc = (
                    "통화대상자 수에는 미추정 인구수 열이 없어 확인 불가"
                    if col.startswith("coverage_contacts_")
                    else "해당 통신 지표의 유효 인구 / 대상 인구 비중, 월별 산출 후 6개월 평균"
                )
            elif col.startswith(("contacts_", "home_", "moves_")):
                desc = "29개 통신정보의 셀별 지표를 유효 인구로 가중한 월별 평균의 6개월 평균; 단위는 원자료 기준"
            elif col.startswith("no_"):
                desc = "프로토타입에서 제외된 집계구의 해당 포함 조건 실패 여부"
            elif col.startswith("n_oa_"):
                desc = "해당 행정동의 집계구 수; 전체·평가·제외를 구분"
            elif col.startswith("hh_"):
                desc = "해당 행정동의 일반가구 수; 전체·평가·보류를 구분"
            elif col.startswith("grade5_"):
                desc = "1차 프로토타입 5등급의 집계구·일반가구 수 또는 평가 가구 비중"
            else:
                desc = "통신 검증 결과 또는 1차 프로토타입의 원본 열; 해당 출처의 사전·보고서 참조"
        if col.startswith(("ratio_", "coverage_", "share_")) or "_share_" in col:
            unit = "비율(0~1)"
        elif col.startswith("n_oa_") or col.startswith("grade5_oa_"):
            unit = "집계구"
        elif col.startswith(("hh_", "grade5_hh_")):
            unit = "가구"
        elif col.startswith("contacts_"):
            unit = "명(원자료 평균)"
        elif col.startswith(("home_", "moves_")):
            unit = "원자료 단위"
        elif col.startswith(("score_", "theme_")):
            unit = "지수 점수(버전별 척도 상이)"
        elif col in ("rho", "rho_difference", "ci_low", "ci_high", "loo_min", "loo_max"):
            unit = "순위 상관계수"
        elif col == "p_value":
            unit = "확률(0~1)"
        else:
            unit = "코드·이름·사유 또는 원자료 단위"
        numeric = pd.to_numeric(table[col], errors="coerce")
        rows.append(
            {
                "column": col,
                "description": desc,
                "unit": unit,
                "observed_range": (
                    f"{numeric.min():.6g}~{numeric.max():.6g}"
                    if numeric.notna().any()
                    else "관측값 없음 또는 비수치"
                ),
                "dtype": str(table[col].dtype),
                "missing": (
                    "미추정 인구수 열 미제공"
                    if col.startswith("coverage_contacts_")
                    else "계산 불가·원자료 결측"
                    if table[col].isna().any()
                    else "없음"
                ),
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")


def save_scatter(table: pd.DataFrame) -> Path:
    """같은 22개 동의 두 프로토타입 점수와 통신 검증 주 대조 비율을 그린다."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True, sharey=True)
    for ax, (column, title) in zip(
        axes,
        (("score_with_oldho", "Old housing included"), ("score_no_oldho", "Old housing excluded")),
        strict=True,
    ):
        ax.scatter(table["ratio_pop_all"], table[column], color="#17608d", alpha=0.8)
        ax.set(title=title, xlabel="Low outing + communication (estimated share)")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Prototype dong score (household weighted)")
    fig.tight_layout()
    path = paths.PROJECT_ROOT / "reports/261023_gangnam_prototype_scatter.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=paths.PROCESSED_DIR)
    args = parser.parse_args(argv)
    base, without = load_prototypes()
    master = master_oa(
        pd.read_csv(
            MASTER, usecols=MASTER_COLS, dtype={"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str}
        )
    )
    excluded = excluded_oa(master, base)
    reference = pd.read_csv(
        paths.INTERIM_DIR / tv.VALIDATION_NAME, dtype={"dong_cd": str, "ADM_CD": str}
    )
    table, supplement = build_tables(
        master, base, without, reference, interest_supplement(), telecom_supplement()
    )
    correlation = correlations(table)
    sensitivity = pd.DataFrame(
        [paired_sensitivity(table, t) for t in ("ratio_pop_all", "ratio_pop_old65")]
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "validation_gangnam_dong.csv": table,
        "seoul_comm_gangnam_dong.csv": supplement,
        "validation_excluded_oa.csv": excluded,
        "validation_gangnam_correlations.csv": correlation,
        "validation_gangnam_sensitivity.csv": sensitivity,
    }
    for name, data in outputs.items():
        file = args.out_dir / name
        data.to_csv(file, index=False, encoding="utf-8")
        write_dictionary(data, file.with_name(file.stem + "_dictionary.csv"))
        print(f"saved {name}: {len(data)} rows x {len(data.columns)} cols")
    print(f"saved {save_scatter(table).relative_to(paths.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
