"""고립 신호 후보 4축 지표와 합성 지수.

방향성 외부검증 전 단계이므로 순위를 고립 위험도로 확정 해석하지 않는다.
n=47에서 요인분석은 성립하지 않아 동등가중 합산 + 민감도 분석을 쓴다.
"""

import numpy as np
import pandas as pd

from src.features.sk_dong import AGE_COLS, NIGHT_COLS, SENIOR_COLS, TIME_COLS, WKDY_COLS

DISCLAIMER = (
    "본 지수는 방향성 외부검증 전 단계다. 동별·집단별 순위를 고립 위험도로 확정 해석하지 않는다."
)


def minmax(s: pd.Series, invert: bool = False) -> pd.Series:
    """min-max 정규화. invert=True면 작은 값이 1이 된다(위험 방향 정렬용)."""
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    out = (s - lo) / (hi - lo)
    return 1.0 - out if invert else out


def _entropy(row: np.ndarray) -> float:
    """비중 벡터의 섀넌 엔트로피. 합이 0이면 0을 반환한다."""
    total = row.sum()
    if total <= 0:
        return 0.0
    p = row / total
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def space_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """공간축 지표를 동 단위로 산출한다. 월별 값을 평균해 동당 1행으로 만든다."""
    df = panel.copy()
    unit = "dong_cd" if "dong_cd" in df.columns else "tong_cd"
    wkdy = df[WKDY_COLS]
    time = df[TIME_COLS]

    df["total"] = df[AGE_COLS].sum(axis=1)
    # 사회활동: 요일간 변동계수가 낮으면 생활 리듬 변화가 적다
    df["wkdy_cv"] = wkdy.std(axis=1, ddof=0) / wkdy.mean(axis=1)
    # 사회활동: 시간대 분포 엔트로피가 낮으면 활동 시간대가 한쪽에 쏠려 있다
    df["time_entropy"] = [_entropy(r) for r in time.to_numpy()]
    # 고립형 생활: 야간(22~05시) 유동 비중
    df["night_share"] = time[NIGHT_COLS].sum(axis=1) / time.sum(axis=1)
    # 고립형 생활: 주간 피크 대비 시간대 평균 비
    df["peak_ratio"] = time.mean(axis=1) / time.max(axis=1)
    df["senior_share"] = df[SENIOR_COLS].sum(axis=1) / df["total"]

    cols = ["wkdy_cv", "time_entropy", "night_share", "peak_ratio", "senior_share", "total"]
    return df.groupby(unit, observed=True)[cols].mean().reset_index()


def cohort_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """집단축 지표를 산출한다. 월별 값을 합산해 집단당 1행으로 만든다."""
    keys = ["MCT_SGG_CD", "SEX_CCD", "age_band"]
    g = panel.groupby(keys, observed=True).agg(
        amount_ex=("amount_ex", "sum"),
        count_ex=("count_ex", "sum"),
        social_amount=("social_amount", "sum"),
        n_ry=("n_ry", "max"),
    )
    out = g.reset_index()
    # 사회적 관계: 미분류·비소비 제외 금액 중 대면 관계 소비 비중
    out["social_share"] = out["social_amount"] / out["amount_ex"]
    # 경제적 불안정: 건당 결제액
    out["amount_per_use"] = out["amount_ex"] / out["count_ex"]
    # 경제적 불안정: 업종 다양성
    out["ry_diversity"] = out["n_ry"].astype(float)
    return out


def composite(
    frame: pd.DataFrame,
    cols: list[str],
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """정규화된 축들을 가중합한다. 입력은 0~1 범위여야 한다."""
    sub = frame[cols]
    if not ((sub >= -1e-9) & (sub <= 1 + 1e-9)).all().all():
        raise ValueError("composite 입력은 0~1 범위로 정규화되어 있어야 한다")
    w = np.array([1.0] * len(cols) if weights is None else [weights[c] for c in cols])
    w = w / w.sum()
    return pd.Series(sub.to_numpy() @ w, index=frame.index)


def sensitivity(
    frame: pd.DataFrame,
    cols: list[str],
    n_trials: int = 200,
    pct: float = 0.2,
    seed: int = 42,
) -> pd.DataFrame:
    """가중치를 +-pct 범위에서 흔들어 순위 안정성을 본다."""
    rng = np.random.default_rng(seed)
    base = np.ones(len(cols))
    ranks = np.empty((n_trials, len(frame)))
    values = frame[cols].to_numpy()
    for i in range(n_trials):
        w = base * rng.uniform(1 - pct, 1 + pct, size=len(cols))
        w = w / w.sum()
        score = values @ w
        ranks[i] = pd.Series(score).rank(ascending=False).to_numpy()
    return pd.DataFrame(
        {
            "rank_mean": ranks.mean(axis=0),
            "rank_std": ranks.std(axis=0),
            "rank_min": ranks.min(axis=0),
            "rank_max": ranks.max(axis=0),
        },
        index=frame.index,
    )
