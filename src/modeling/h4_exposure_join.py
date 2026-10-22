"""60대 이상 활동 저하 신호(#16)를 SGIS 노출 지수 v3.3(#24)와 집계구 단위로 결합한다.

H4 판정(JUDGEMENT_STATUS, HOLD_REASON, SIGNAL)은 바꾸지 않고 지수 쪽 상태를 따로 붙인다.
지수 점수가 없는 집계구는 빼지 않고 EXPOSURE_STATUS = held,
EXPOSURE_HOLD_REASON = no_exposure_score로 남긴다. #24 합의대로 지수 보류 집계구는
H4 신호로만 판단하므로 SIGNAL을 지우지 않는다.

관찰 후보(EXPOSURE_HIGH)는 지수의 watch 열을 그대로 쓴다:
보류 아님 AND (5등급 OR 테마 A ≥ 80 OR 테마 B ≥ 80) (#24 후속 3번).
20·30대 신호는 외부검증에서 반대 방향이라 결합하지 않는다(보고서 4절).
두 값을 곱하거나 더한 점수는 만들지 않는다. 노출(누가 사나)과 활동(얼마나 움직이나)은
지역마다 연관 방향이 달라(보고서 7절) 나란히 표시한다.

행정동 표는 H4 행정동 집계와 지수의 행정동 파일(<지수>_adm.csv)을 나란히 붙인다.
분모가 다르다: SIGNAL_RATE는 판정 집계구 수, 지수 *_w는 평가 가구 가중평균.

실행: uv run python -m src.modeling.h4_exposure_join [--index 경로]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from scipy import stats

from src.data import paths

BAND = "60GU"
INDEX_PATH = paths.INTERIM_DIR / "v3.3" / "isolation_index_v3.csv"
SIGNAL_OA_PATH = paths.PROCESSED_DIR / "h4_signal_oa.csv"
SIGNAL_DONG_PATH = paths.PROCESSED_DIR / "h4_signal_dong.csv"
OUTPUT_PATH = paths.PROCESSED_DIR / "h4_exposure_oa.csv"
DONG_OUTPUT_PATH = paths.PROCESSED_DIR / "h4_exposure_combined_dong.csv"
SUMMARY_PATH = paths.INTERIM_DIR / "h4_exposure_summary.csv"
ASSOCIATION_PATH = paths.INTERIM_DIR / "h4_exposure_association.csv"
INDEX_COLS = [
    "grade",
    "theme_A_pct",
    "theme_B_pct",
    "type_label",
    "rental_est",
    "hold_reason",
    "watch",
]

DICTIONARY = [
    ("TOT_OA_CD", "집계구 코드(14자리 문자열)", "", ""),
    ("REGION", "지역(강남구·춘천시)", "", ""),
    ("ADM_CD", "행정동 코드(8자리 문자열)", "", ""),
    ("AGE_BAND", "SK 연령대(60GU=60대 이상만)", "", ""),
    ("INDEX_VERSION", "결합에 쓴 지수 버전(지수 파일이 있는 폴더 이름)", "", ""),
    ("JUDGEMENT_STATUS", "H4 판정 상태 judged 또는 held(h4_signal_oa 그대로)", "", ""),
    ("HOLD_REASON", "H4 보류 사유(;로 연결)", "", "H4 보류 아님"),
    ("N_LOW_MONTHS", "잔차 < -0.1인 달 수", "개월", "H4 보류"),
    ("MEAN_RESID", "6개월 평균 잔차 log(실제/기대)", "log 비", "잔차 계산 불가"),
    ("SIGNAL", "N_LOW_MONTHS >= 4 이고 MEAN_RESID < -0.1", "bool", "H4 보류"),
    ("EXPOSURE_STATUS", "지수 상태 scored 또는 held", "", ""),
    ("EXPOSURE_HOLD_REASON", "지수 점수가 없으면 no_exposure_score", "", "지수 점수 있음"),
    (
        "INDEX_HOLD_REASON",
        "지수 v3.3 보류 사유(업무지·집단가구·인구없음·일반가구없음·거처자료없음), "
        "지수 파일에 없으면 not_in_index",
        "",
        "지수 보류 아님",
    ),
    (
        "grade",
        "지수 종합 등급 1~5. 0은 낮은 위험이 아니라 보류(등급 미부여)",
        "",
        "지수 파일에 없음",
    ),
    (
        "theme_A_pct",
        "테마 A(고령 독거) 지역 안 백분위. 고령은 65세 이상 기준(H4는 60세 이상)",
        "0~100",
        "지수 보류",
    ),
    ("theme_B_pct", "테마 B(중장년 독거·주거취약) 지역 안 백분위", "0~100", "지수 보류"),
    ("type_label", "지수 유형 라벨", "", "지수 파일에 없음"),
    ("rental_est", "고령 임대단지 추정(LH·SH 미확인)", "bool", "지수 파일에 없음"),
    ("EXPOSURE_HIGH", "지수 watch: 보류 아님 AND (5등급 OR A >= 80 OR B >= 80)", "bool", ""),
    (
        "COMBINED_STATUS",
        "judged_both / exposure_held(신호로만 판단) / signal_held(지수로만 판단) / double_held",
        "",
        "",
    ),
]


INDEX_ADM_COLS = [
    "n_oa_eval",
    "hh_total",
    "hh_eval",
    "share_hh_eval",
    "share_hh_hold",
    "score_w",
    "theme_A_pct_w",
    "theme_B_pct_w",
    "n_grade5",
    "n_watch",
    "hh_watch",
]
DONG_DICTIONARY = [
    ("ADM_CD", "행정동 코드(8자리 문자열)", "", ""),
    ("REGION", "지역", "", ""),
    ("AGE_BAND", "SK 연령대(60GU만)", "", ""),
    ("INDEX_VERSION", "결합에 쓴 지수 버전", "", ""),
    ("N_OA", "[H4] 행정동의 집계구 수", "개", ""),
    ("N_JUDGED", "[H4] 신호를 판정한 집계구 수 = SIGNAL_RATE 분모", "개", ""),
    ("N_HELD", "[H4] 보류 집계구 수", "개", ""),
    ("N_SIGNAL", "[H4] 신호 집계구 수", "개", ""),
    ("SIGNAL_RATE", "[H4] N_SIGNAL / N_JUDGED", "비율", "판정 집계구 0개"),
    ("DONG_POOLED_RESID", "[H4] 동 전체 log(Σ실제/Σ기대) 6개월 평균(보류 포함)", "log 비", ""),
    ("n_oa_eval", "[지수] 평가 집계구 수(보류 아님 & 점수 유효)", "개", ""),
    ("hh_total", "[지수] 총가구", "가구", ""),
    ("hh_eval", "[지수] 평가 집계구 총가구 = *_w 가중평균 분모", "가구", ""),
    ("share_hh_eval", "[지수] hh_eval / hh_total. 낮으면 지수 동 값 해석 주의", "0~1", ""),
    ("share_hh_hold", "[지수] 보류 집계구 가구 비중", "0~1", ""),
    ("score_w", "[지수] 종합 점수 가구 가중평균(평가 집계구만)", "0~100", ""),
    ("theme_A_pct_w", "[지수] 테마 A 백분위 가구 가중평균", "0~100", ""),
    ("theme_B_pct_w", "[지수] 테마 B 백분위 가구 가중평균", "0~100", ""),
    ("n_grade5", "[지수] 5등급 집계구 수", "개", ""),
    ("n_watch", "[지수] 관찰 후보(watch) 집계구 수", "개", ""),
    ("hh_watch", "[지수] 관찰 후보 집계구 일반가구 합", "가구", ""),
    ("N_WATCH_SIGNAL", "[결합] 관찰 후보이면서 H4 신호인 집계구 수", "개", ""),
    ("N_SIGNAL_EXPOSURE_HELD", "[결합] 지수 보류이고 H4 신호인 집계구 수(신호로만 판단)", "개", ""),
    ("N_DOUBLE_HELD", "[결합] 지수와 H4 모두 보류인 집계구 수", "개", ""),
]


def join(signal_oa: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """60GU 신호 행에 지수 열을 붙이고 결합 상태를 판정한다(H4 행 수 유지)."""
    sig = signal_oa[signal_oa["AGE_BAND"] == BAND]
    out = sig.merge(index[["TOT_OA_CD", "hold", *INDEX_COLS]], on="TOT_OA_CD", how="left")
    scored = out["hold"].eq(False)
    out["EXPOSURE_STATUS"] = scored.map({True: "scored", False: "held"})
    out["EXPOSURE_HOLD_REASON"] = scored.map({True: pd.NA, False: "no_exposure_score"})
    out["INDEX_HOLD_REASON"] = out["hold_reason"].where(out["hold"].notna(), "not_in_index")
    out["EXPOSURE_HIGH"] = scored & out["watch"].eq(True)
    h4_judged = out["JUDGEMENT_STATUS"].eq("judged")
    out["COMBINED_STATUS"] = "double_held"
    out.loc[h4_judged & scored, "COMBINED_STATUS"] = "judged_both"
    out.loc[h4_judged & ~scored, "COMBINED_STATUS"] = "exposure_held"
    out.loc[~h4_judged & scored, "COMBINED_STATUS"] = "signal_held"
    return out[[c for c, *_ in DICTIONARY if c != "INDEX_VERSION"]]


def combine_dong(
    joined: pd.DataFrame, signal_dong: pd.DataFrame, index_adm: pd.DataFrame
) -> pd.DataFrame:
    """60GU 행정동 신호 집계, 지수 행정동 값, 결합 상태 개수를 나란히 붙인다."""
    signal = joined["SIGNAL"].eq(True)
    counts = (
        joined.assign(
            N_WATCH_SIGNAL=joined["EXPOSURE_HIGH"] & signal,
            N_SIGNAL_EXPOSURE_HELD=joined["COMBINED_STATUS"].eq("exposure_held") & signal,
            N_DOUBLE_HELD=joined["COMBINED_STATUS"].eq("double_held"),
        )
        .groupby("ADM_CD")[["N_WATCH_SIGNAL", "N_SIGNAL_EXPOSURE_HELD", "N_DOUBLE_HELD"]]
        .sum()
        .reset_index()
    )
    dong = signal_dong[signal_dong["AGE_BAND"] == BAND]
    out = dong.merge(index_adm[["ADM_CD", *INDEX_ADM_COLS]], on="ADM_CD", how="left").merge(
        counts, on="ADM_CD", how="left"
    )
    return out[[c for c, *_ in DONG_DICTIONARY if c != "INDEX_VERSION"]]


def summarize(joined: pd.DataFrame) -> pd.DataFrame:
    """지역 × 결합 상태 × 관찰 후보 × 신호별 집계구 수를 낸다."""
    keys = ["REGION", "COMBINED_STATUS", "EXPOSURE_HIGH", "SIGNAL"]
    return (
        joined.assign(SIGNAL=joined["SIGNAL"].astype("string").fillna("held"))
        .groupby(keys, dropna=False)
        .size()
        .rename("N_OA")
        .reset_index()
    )


def association(joined: pd.DataFrame) -> pd.DataFrame:
    """지역마다 관찰 후보와 신호의 연관을 낸다: 전체 오즈비(Fisher)와 같은 동 안 비교(MH)."""
    rows = []
    both = joined[joined["COMBINED_STATUS"].eq("judged_both")]
    for region, d in both.groupby("REGION"):
        high, sig = d["EXPOSURE_HIGH"].astype(bool), d["SIGNAL"].eq(True)
        table = pd.crosstab(high, sig).reindex(index=[True, False], columns=[True, False])
        odds, p = stats.fisher_exact(table.fillna(0).to_numpy())
        # Mantel-Haenszel: 동마다 2×2 표를 만들어 합친다. 동 구성 차이를 걷어 낸다
        cells = (
            pd.DataFrame({"a": high & sig, "b": high & ~sig, "c": ~high & sig, "d": ~high & ~sig})
            .groupby(d["ADM_CD"])
            .sum()
        )
        n = cells.sum(axis=1)
        mh = (cells["a"] * cells["d"] / n).sum() / (cells["b"] * cells["c"] / n).sum()
        rows.append(
            {
                "REGION": region,
                "N_OA": len(d),
                "N_HIGH": int(high.sum()),
                "SIGNAL_RATE_HIGH": sig[high].mean(),
                "SIGNAL_RATE_OTHER": sig[~high].mean(),
                "ODDS_RATIO": odds,
                "P_VALUE": p,
                "MH_ODDS_RATIO_WITHIN_DONG": mh,
            }
        )
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, path: Path, dictionary: list | None = None) -> None:
    """CSV와 열 정의서를 UTF-8로 저장한다."""
    df.to_csv(path, index=False, encoding="utf-8")
    if dictionary:
        pd.DataFrame(dictionary, columns=["COLUMN", "DESCRIPTION", "UNIT", "MISSING"]).to_csv(
            path.with_name(f"{path.stem}_dictionary.csv"), index=False, encoding="utf-8"
        )
    print(f"saved {path.relative_to(paths.PROJECT_ROOT)} {df.shape}")


def main() -> None:
    """집계구 결합표, 행정동 결합표, 집계표를 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--index", type=Path, default=INDEX_PATH, help="지수 집계구 CSV")
    args = parser.parse_args()
    index_path = args.index
    version = index_path.parent.name  # 드라이브 폴더 이름(v3.3)을 버전으로 기록
    read = {"dtype": {"TOT_OA_CD": str, "ADM_CD": str}, "encoding": "utf-8-sig"}

    signal_oa = pd.read_csv(SIGNAL_OA_PATH, dtype={"TOT_OA_CD": str, "ADM_CD": str})
    index = pd.read_csv(index_path, **read)
    index_adm = pd.read_csv(index_path.with_name(f"{index_path.stem}_adm.csv"), **read)
    signal_dong = pd.read_csv(SIGNAL_DONG_PATH, dtype={"ADM_CD": str})

    joined = join(signal_oa, index)
    missing = set(index["TOT_OA_CD"]) - set(joined["TOT_OA_CD"])
    if missing:
        print(f"지수에만 있는 집계구 {len(missing)}개(결합표에 없음)")
    dong = combine_dong(joined, signal_dong, index_adm)
    summary = summarize(joined)
    assoc = association(joined)

    for df in (joined, dong, summary, assoc):
        df.insert(df.columns.get_loc("REGION") + 1, "INDEX_VERSION", version)
    oa_cols = [c for c, *_ in DICTIONARY]
    save(joined[oa_cols], OUTPUT_PATH, DICTIONARY)
    save(dong[[c for c, *_ in DONG_DICTIONARY]], DONG_OUTPUT_PATH, DONG_DICTIONARY)
    save(summary, SUMMARY_PATH)
    save(assoc, ASSOCIATION_PATH)
    print(summary.to_string(index=False))
    print(assoc.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
