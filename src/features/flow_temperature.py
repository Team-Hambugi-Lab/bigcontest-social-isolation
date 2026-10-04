"""집계구 월별 유동인구와 지역 월평균기온의 관계를 검정.

12월 유동인구 감소가 기온(한파) 때문인지, 기온과 무관하게 지속되는
악화인지 구분하는 1차 진단이다. 집계구 자신의 6개월 평균 대비 편차와
지역 기온의 6개월 평균 대비 편차를 비교한다 — 집계구마다 규모가 달라도
"그 집계구 기준으로 평소보다 늘었는지 줄었는지"만 보게 된다.

한계: 이 상관은 "기온 효과"와 "월 자체의 추세(trend)"를 완전히 분리하지
못한다. 기온도 7월에서 12월로 갈수록 단조롭게 떨어지므로, 유동인구가
단조 감소 추세라면 기온과도 높은 상관이 나올 수 있다 — 상관계수 하나로
"이건 순수 계절효과다/아니다"를 확정하지 않는다. 또한 같은 집계구의
6개 관측치는 서로 독립이 아니어서(반복측정), 전체를 풀링한 p-value는
과장돼 보일 수 있다.
"""

import numpy as np
import pandas as pd
from scipy import stats

from src.features.risk_axes_v1 import total_flow

REGION_BY_PREFIX = {"11230": "서울", "32010": "춘천"}


def monthly_log_flow(panel: pd.DataFrame) -> pd.DataFrame:
    """집계구×월 패널에서 ln(총유동인구)와 지역을 뽑는다.

    반환 컬럼: 집계구, STD_YM, ln유동인구, 지역.
    """
    out = panel[["집계구", "STD_YM"]].copy()
    out["ln유동인구"] = np.log(total_flow(panel))
    out["지역"] = panel["집계구"].str[:5].map(REGION_BY_PREFIX)
    return out


def flow_deviation(monthly_flow: pd.DataFrame) -> pd.DataFrame:
    """집계구마다 자신의 평균 대비 ln유동인구 편차를 구한다."""
    out = monthly_flow.copy()
    out["ln유동인구_편차"] = out.groupby("집계구")["ln유동인구"].transform(lambda s: s - s.mean())
    return out


def temperature_deviation(monthly_temp: pd.DataFrame) -> pd.DataFrame:
    """지역마다 자신의 평균 대비 기온 편차를 구한다."""
    out = monthly_temp.copy()
    out["평균기온_편차"] = out.groupby("지역")["평균기온"].transform(lambda s: s - s.mean())
    return out


def correlate_flow_with_temperature(flow_dev: pd.DataFrame, temp_dev: pd.DataFrame) -> pd.DataFrame:
    """지역별로 ln유동인구 편차와 기온 편차의 Spearman 상관을 검정한다.

    반환: 지역을 인덱스로, correlation·p_value·n 컬럼을 가진 DataFrame.
    """
    merged = flow_dev.merge(temp_dev[["지역", "STD_YM", "평균기온_편차"]], on=["지역", "STD_YM"])
    rows = []
    for region, g in merged.groupby("지역"):
        r, p = stats.spearmanr(g["ln유동인구_편차"], g["평균기온_편차"])
        rows.append({"지역": region, "correlation": r, "p_value": p, "n": len(g)})
    return pd.DataFrame(rows).set_index("지역")
