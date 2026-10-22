"""활동 저하 신호의 방향 가정을 서울 1인가구 통신정보로 대조한다 (이슈 #16 Task 5).

가정: 기대보다 유동이 낮은 동(SIGNAL_RATE 높음, DONG_POOLED_RESID 낮음)은 1인가구가
집에 오래 머물고 덜 이동한다. 강남 22개 동만 대조할 수 있다(춘천 자료 없음).

실행: uv run python -m src.evaluation.h4_external_validation
"""

from __future__ import annotations

import pandas as pd
from scipy import stats

from src.data import paths

TELECOM_DIR = paths.RAW_DIR / "reference_data" / "서울_29개_통신정보"
SIGNAL_DONG_PATH = paths.PROCESSED_DIR / "h4_signal_dong.csv"
OUTPUT_PATH = paths.INTERIM_DIR / "h4_external_validation.csv"
GANGNAM_PREFIX = "11230"

# 서울시 7자리 행정동 코드 → SGIS 8자리. 기본은 끝에 0을 붙인다.
# 일원2동(1123074)이 개포3동(11230511)으로 이름만 바뀐 것이다. 강남구청이 행정동 명칭만
# 바꾸고 법정동은 유지한다고 안내했고, 통신 20세 이상 인구 / SGIS 총인구가 0.857로 다른
# 21개 동 범위(0.73~1.34) 안에 있다(#25). 서울시 자료는 개칭 전 코드를 계속 쓴다.
CODE_EXCEPTIONS = {"1123074": "11230511"}

# 서울 자료는 5세 연령대(20~75). SK 연령대에 맞춘다.
AGE_MAP = {
    "20G": ("20", "25"),
    "30G": ("30", "35"),
    "40G": ("40", "45"),
    "50G": ("50", "55"),
    "60GU": ("60", "65", "70", "75"),
}
METRICS = {
    "집 추정 위치 평일 총 체류시간": "HOME_STAY_WEEKDAY",
    "집 추정 위치 휴일 총 체류시간": "HOME_STAY_HOLIDAY",
    "평일 총 이동 횟수": "MOVES_WEEKDAY",
    "휴일 총 이동 횟수 평균": "MOVES_HOLIDAY",
}
# 활동 저하 가정이 맞을 때 기대하는 상관 부호: (SIGNAL_RATE, DONG_POOLED_RESID)
EXPECTED_SIGN = {
    "HOME_STAY_WEEKDAY": (1, -1),
    "HOME_STAY_HOLIDAY": (1, -1),
    "MOVES_WEEKDAY": (-1, 1),
    "MOVES_HOLIDAY": (-1, 1),
}


def to_sgis_code(code7: pd.Series) -> pd.Series:
    """서울시 7자리 행정동 코드를 SGIS 8자리로 바꾼다."""
    code7 = code7.astype(str)
    return code7.map(CODE_EXCEPTIONS).fillna(code7 + "0")


def load_telecom(files=None) -> pd.DataFrame:
    """강남 행만 읽어 월 × 동 × 성 × 5세 연령대 표로 합친다."""
    files = files or sorted(TELECOM_DIR.glob("*.xlsx"))
    cols = ["행정동코드", "성별", "연령대", "총인구수", *METRICS]
    frames = []
    for f in files:
        df = pd.read_excel(f, usecols=cols, dtype={"행정동코드": str, "연령대": str})
        frames.append(df[df["행정동코드"].str.startswith(GANGNAM_PREFIX)].assign(FILE=f.name))
    out = pd.concat(frames, ignore_index=True).rename(columns=METRICS)
    out["ADM_CD"] = to_sgis_code(out["행정동코드"])
    return out


def dong_metrics(telecom: pd.DataFrame) -> pd.DataFrame:
    """동 × SK 연령대로 총인구수 가중 평균 지표를 낸다(성·5세 연령·월 합침)."""
    age_to_band = {age: band for band, ages in AGE_MAP.items() for age in ages}
    t = telecom.assign(AGE_BAND=telecom["연령대"].map(age_to_band)).dropna(subset=["AGE_BAND"])
    metric_cols = list(METRICS.values())
    weighted = (
        t[metric_cols]
        .mul(t["총인구수"], axis=0)
        .assign(W=t["총인구수"], ADM_CD=t["ADM_CD"], AGE_BAND=t["AGE_BAND"])
    )
    g = weighted.groupby(["ADM_CD", "AGE_BAND"]).sum()
    return g[metric_cols].div(g["W"], axis=0).reset_index()


def correlate(signal_dong: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    """연령대 × 지표마다 Spearman 상관과 기대 부호 일치 여부를 낸다."""
    joined = signal_dong.merge(metrics, on=["ADM_CD", "AGE_BAND"], how="inner")
    rows = []
    for band, d in joined.groupby("AGE_BAND"):
        for metric, (sign_rate, sign_pooled) in EXPECTED_SIGN.items():
            for target, sign in (
                ("SIGNAL_RATE", sign_rate),
                ("DONG_POOLED_RESID", sign_pooled),
            ):
                ok = d[[target, metric]].dropna()
                rho, p = stats.spearmanr(ok[target], ok[metric])
                rows.append(
                    {
                        "AGE_BAND": band,
                        "TARGET": target,
                        "METRIC": metric,
                        "N_DONG": len(ok),
                        "SPEARMAN": rho,
                        "P_VALUE": p,
                        "EXPECTED_SIGN": sign,
                        "SIGN_MATCH": bool(rho * sign > 0),
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    """강남 동 단위 대조표를 저장한다."""
    signal = pd.read_csv(SIGNAL_DONG_PATH, dtype={"ADM_CD": str})
    signal = signal[signal["ADM_CD"].str.startswith(GANGNAM_PREFIX)]
    metrics = dong_metrics(load_telecom())
    missing = set(signal["ADM_CD"]) - set(metrics["ADM_CD"])
    if missing:
        print("통신정보와 대응되지 않는 동:", sorted(missing))
    out = correlate(signal, metrics)
    out.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"saved {OUTPUT_PATH.relative_to(paths.PROJECT_ROOT)} {out.shape}")


if __name__ == "__main__":
    main()
