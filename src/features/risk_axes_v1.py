"""재언 보고서 재현용 위험 신호 5개 변수 계산.

원 코드가 공유되지 않아 보고서 서술(4·6·8장)만으로 재구성했다. 각 함수의
정의는 docstring에 그대로 남긴다 — 원 코드 확인 전까지는 가정이다.
"""

import numpy as np
import pandas as pd

AGE_COLS = [
    "MAN_FLOW_POP_CNT_10G",
    "MAN_FLOW_POP_CNT_20G",
    "MAN_FLOW_POP_CNT_30G",
    "MAN_FLOW_POP_CNT_40G",
    "MAN_FLOW_POP_CNT_50G",
    "MAN_FLOW_POP_CNT_60GU",
    "WMAN_FLOW_POP_CNT_10G",
    "WMAN_FLOW_POP_CNT_20G",
    "WMAN_FLOW_POP_CNT_30G",
    "WMAN_FLOW_POP_CNT_40G",
    "WMAN_FLOW_POP_CNT_50G",
    "WMAN_FLOW_POP_CNT_60GU",
]
ELDERLY_COLS = ["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]
TIME_COLS = [f"TMST_{h:02d}" for h in range(24)]
NIGHT_COLS = [f"TMST_{h:02d}" for h in range(0, 6)]
WEEKDAY_COLS = [
    "FLOW_POP_CNT_MON",
    "FLOW_POP_CNT_TUS",
    "FLOW_POP_CNT_WED",
    "FLOW_POP_CNT_THU",
    "FLOW_POP_CNT_FRI",
]
WEEKEND_COLS = ["FLOW_POP_CNT_SAT", "FLOW_POP_CNT_SUN"]


def total_flow(panel: pd.DataFrame) -> pd.Series:
    """성·연령 12칸 합(=해당 행의 월간 총 유동인구).

    12칸이 전부 결측이면 0이 아니라 결측으로 남긴다(min_count=1) — 0으로
    새면 이후 ln(0)=-inf가 되어 해당 집계구의 추세 전체가 깨진다.
    """
    return panel[AGE_COLS].sum(axis=1, min_count=1)


def flatness_cv(panel: pd.DataFrame) -> pd.Series:
    """시간대 비중(TMST를 그 행의 시간대 합으로 나눈 값)의 변동계수.

    값이 작을수록 평탄(오르내림 없음)하다 — "낮을수록 위험" 방향이다.
    """
    time_total = panel[TIME_COLS].sum(axis=1)
    share = panel[TIME_COLS].div(time_total, axis=0)
    return share.std(axis=1) / share.mean(axis=1)


def night_share(panel: pd.DataFrame) -> pd.Series:
    """야간(00~05시) 유동인구가 하루 시간대 합에서 차지하는 비중."""
    time_total = panel[TIME_COLS].sum(axis=1)
    return panel[NIGHT_COLS].sum(axis=1) / time_total


def weekend_ratio(panel: pd.DataFrame) -> pd.Series:
    """주말(토·일) 평균 ÷ 평일(월~금) 평균."""
    weekday_mean = panel[WEEKDAY_COLS].mean(axis=1)
    weekend_mean = panel[WEEKEND_COLS].mean(axis=1)
    return weekend_mean / weekday_mean


def elderly_share(panel: pd.DataFrame) -> pd.Series:
    """60대 이상(남+여) 유동인구가 성·연령 12칸 합에서 차지하는 비중."""
    return panel[ELDERLY_COLS].sum(axis=1) / total_flow(panel)


def trend_slope(monthly_log_flow: pd.Series) -> float:
    """월 순서 대비 ln(총유동인구) 회귀 기울기.

    x값은 `monthly_log_flow`의 인덱스를 그대로 쓴다 — 호출자가 실제 월
    순서(예: months_order 기준 0,1,2…)를 인덱스에 담아 넘겨야 한다.
    dropna 이후 번호를 1,2,3…으로 새로 매기면 관측되지 않은 달이 있을 때
    (예: 0,1,5월만 관측) 기울기가 실제보다 몇 배 과장된다.
    관측치가 2개 미만이면 추세를 추정할 수 없어 NaN을 반환한다.
    """
    valid = monthly_log_flow.dropna()
    if len(valid) < 2:
        return float("nan")
    x = valid.index.to_numpy(dtype=float)
    slope, _ = np.polyfit(x, valid.to_numpy(), deg=1)
    return float(slope)


def reduce_to_block_level(panel: pd.DataFrame, months_order: list[str]) -> pd.DataFrame:
    """(기준월, 집계구) 패널에 변수를 계산하고 집계구 단위로 축약한다.

    평탄도·야간비중·주말비·고령비중은 6개월 평균, 추세는 월별
    ln(총유동인구)의 회귀 기울기로 계산한다.
    """
    work = panel.copy()
    work["평탄도"] = flatness_cv(work)
    work["야간비중"] = night_share(work)
    work["주말비"] = weekend_ratio(work)
    work["고령비중"] = elderly_share(work)
    work["ln총유동인구"] = np.log(total_flow(work))

    month_rank = {m: i for i, m in enumerate(months_order)}
    work["_순서"] = work["STD_YM"].map(month_rank)
    work = work.sort_values(["집계구", "_순서"])

    means = work.groupby("집계구")[["평탄도", "야간비중", "주말비", "고령비중"]].mean()
    # trend_slope는 Series의 인덱스를 x값(월 순서)으로 쓰므로, dropna 이후
    # 재번호가 매겨지지 않도록 "_순서"를 인덱스로 옮긴 뒤 groupby.apply한다.
    trends = work.set_index("_순서").groupby("집계구")["ln총유동인구"].apply(trend_slope)
    trends.name = "추세"

    return means.join(trends)


def align_risk_direction(block_level: pd.DataFrame) -> pd.DataFrame:
    """5개 변수를 모두 '높을수록 위험' 방향으로 정렬한다.

    평탄도는 낮을수록 위험(평탄함)이므로 부호를 뒤집는다. 추세는 더 많이
    감소할수록(기울기가 더 음수일수록) 위험이므로 부호를 뒤집는다. 야간비중·
    고령비중은 원값 그대로가 이미 '높을수록 위험'이다. 주말비는 원 보고서에
    구체적 변환식이 없어 원값을 그대로 쓴다 — 이 방향이 맞는지는 충돌 #3과
    직결된 열린 질문이며, 재언 님 코드가 공유되면 반드시 대조해야 한다.
    """
    return pd.DataFrame(
        {
            "평탄도_위험": -block_level["평탄도"],
            "야간비중_위험": block_level["야간비중"],
            "주말비_위험": block_level["주말비"],
            "고령비중_위험": block_level["고령비중"],
            "추세_위험": -block_level["추세"],
        }
    )


def cronbach_alpha_standardized(items: pd.DataFrame, method: str = "pearson") -> float:
    """상관행렬 기반 표준화 Cronbach's α.

    항목 척도가 서로 다르면(0~1 비율 vs 로그 회귀 기울기) 원값을 그대로
    더해 분산을 비교하는 raw-score 공식은 분산이 큰 항목이 지배한다. 평균
    쌍별 상관계수 기반 공식은 척도에 영향받지 않는다.
    alpha = k * mean_r / (1 + (k - 1) * mean_r)

    method: "pearson"(기본) 또는 "spearman". 주말비처럼 분포가 심하게
    치우친 항목이 섞여 있으면 이상치에 덜 민감한 spearman도 같이 보는 게
    좋다 — 이 데이터에서는 두 방식의 결론(0.7 미달)이 갈리지 않았지만,
    항목 하나를 빼는 식의 재계산에서는 갈릴 수 있다.
    """
    valid = items.dropna()
    if valid.shape[1] < 2:
        raise ValueError("항목이 2개 미만이면 α를 계산할 수 없습니다.")

    corr = valid.corr(method=method)
    k = corr.shape[0]
    off_diagonal = corr.to_numpy()[~np.eye(k, dtype=bool)]
    if np.isnan(off_diagonal).any():
        raise ValueError("상관계수에 결측이 있습니다 — 분산이 0인 항목을 확인하세요.")

    mean_r = off_diagonal.mean()
    return float(k * mean_r / (1 + (k - 1) * mean_r))
