"""대면 접촉 기회 지표.

조작적 정의
    고립 = 타인과 대면 접촉할 기회가 구조적으로 적은 상태

이 정의에서 도출한 예측만 지표로 삼는다. 정의에서 나오지 않는 변수는 넣지 않는다.
지표를 합치기 전에 반드시 내적 일관성을 검정한다(`coherence`).

업종 분류 근거
    제공 데이터는 전부 오프라인 결제라 '대면 여부'만으로는 변별력이 없다.
    정의의 '접촉할 기회'에 맞춰 **체류하며 타인과 같은 공간에 있는 소비**를 A군으로 좁혔다.
    분류는 판단이므로 민감도 분석으로 영향을 확인한다.
"""

import numpy as np
import pandas as pd

# A군 — 체류형 대면. 머무르며 타인과 같은 공간에 있게 되는 소비
CONTACT_STAY = (
    # 식음료 체류
    "한식",
    "중식",
    "일식",
    "양식",
    "기타요식",
    "커피전문점",
    "제과점",
    "패스트푸드",
    # 여가·문화
    "노래방",
    "영화/공연",
    "게임방/오락실",
    "종합레저타운/놀이동산",
    "실내/실외골프장",
    "스포츠시설",
    "헬스장",
    # 몸돌봄 서비스 (타인이 직접 응대)
    "미용실",
    "미용서비스",
    "싸우나/목욕탕",
    "안마/마사지",
    # 학습 공간
    "독서실",
    "학원/학습지",
    # 의례
    "예식장/결혼서비스",
    "장례식장/묘지/장의사",
    # 유흥
    "유흥업소",
)

# B군 — 거래형 짧은 대면. 점원과 마주치나 체류하지 않음
CONTACT_BRIEF = (
    "편의점",
    "할인점/슈퍼마켓/양판점",
    "약국",
    "정육점",
    "농수산물",
    "기타식품",
    "화원",
    "세탁소",
    "주유소",
    "백화점",
    "의복/의류",
    "화장품",
    "패션잡화",
    "서점",
    "생활잡화/수입상품점",
    "문화용품",
    "스포츠/레저용품",
    "완구/아동용자전거",
    "애완동물",
    "악기/음반",
    "사무기기/문구용품",
    "주류판매",
    "전용매장",
    "시계/귀금속",
    "면세점",
    "가구",
    "가전",
    "인테리어/건축자재/주방기구",
    "수제용품점",
    "중고품판매점",
    "기타유통",
    "모텔,여관,기타숙박",
    "호텔/콘도",
    # 체인점: 업종명이 모호하다. 건당 9,651원, 저녁 비중 32.9%로 편의점(6,338원/31.0%)과
    # 유사한 소매 성격이라 B군에 넣었다. 건수 비중 0.0076%로 결과 영향은 미미하다
    "체인점",
)

# C군 — 의료. 대면이지만 필요에 의한 것이라 '기회'의 성격이 다르다. 민감도에서 따로 본다
CONTACT_CARE = (
    "일반병원",
    "종합병원",
    "치과병원",
    "한의원",
    "보건소",
    "기타의료",
    "동물병원",
)

# D군 — 비대면 가능하거나 대면 접촉과 무관
NON_CONTACT = (
    "쇼핑몰",
    "컴퓨터/소프트웨어",
    "통신요금(이동,시내전화)",
    "통신요금(PC통신,무선호출)",
    "보험",
    "결제대행(PG)",
    "세금공과금",
    "학교등록금",
    "상품권/복권",
    "법률/사무서비스",
    "회계/변리서비스",
    "연구/번역서비스",
    "부동산중개",
    "방문판매/다단계판매",
    "여행사/항공사",
    "유치원",
    "ZZ_나머지",
)

# E군 — 이동·차량
MOBILITY = (
    "택시",
    "고속버스/철도/여객선",
    "주차장",
    "자동차서비스",
    "자동차용품",
    "수입자동차",
    "중고차판매",
    "오토바이",
    "LPG가스",
)

TIERS = {
    "A_체류대면": CONTACT_STAY,
    "B_거래대면": CONTACT_BRIEF,
    "C_의료": CONTACT_CARE,
    "D_비대면": NON_CONTACT,
    "E_이동": MOBILITY,
}

COHORT_KEYS = ["MCT_SGG_CD", "SEX_CCD", "age_band"]
# 36셀에서는 contact_breadth가 포화된다(27.8%가 24종 전부 사용, 연령 내 폭 0.042).
# 월을 넣어 216셀로 올리면 표준편차가 0.082 -> 0.154로 늘어 변별력이 생긴다.
PANEL_KEYS = ["MCT_SGG_CD", "SEX_CCD", "age_band", "ym"]

# 분모 후보. 일상소비(A+B)는 의료·이동을 빼 구매력 오염이 덜하다
# (건당액 상관 -0.703 -> -0.581). 비대면(D)은 어느 경우에도 제외한다.
DENOM_DAILY = ("A_체류대면", "B_거래대면")
DENOM_OFFLINE = ("A_체류대면", "B_거래대면", "C_의료", "E_이동")


def tag_tier(df: pd.DataFrame) -> pd.DataFrame:
    """업종을 5개 군으로 태깅한다. 미분류가 있으면 예외를 던진다."""
    out = df.copy()
    mapping = {ry: tier for tier, rys in TIERS.items() for ry in rys}
    out["tier"] = out["MCT_RY_CD"].map(mapping)
    missing = sorted(set(out.loc[out["tier"].isna(), "MCT_RY_CD"]))
    if missing:
        raise ValueError(f"미분류 업종 {len(missing)}종: {missing}")
    out["is_stay"] = out["tier"] == "A_체류대면"
    return out


def _entropy(counts: np.ndarray) -> float:
    total = counts.sum()
    if total <= 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log(p)).sum())


def contact_indicators(
    df: pd.DataFrame,
    keys: list[str] | None = None,
    denom: tuple[str, ...] = DENOM_DAILY,
    min_cnt: int = 0,
) -> pd.DataFrame:
    """정의에서 도출한 예측 3개를 집단 단위로 산출한다.

    P1 contact_share   체류형 대면 소비의 **건수** 비중. 접촉 기회의 양.
                       금액이 아니라 건수를 쓰는 이유는 금액이 구매력에 오염되기 때문이다.
    P2 contact_entropy 체류형 대면 **안에서의** 업종 엔트로피. 접촉 종류의 다양성.
                       전체 업종 다양성이 아니라 A군 내부만 본다.
    P3 contact_breadth 이용한 체류형 대면 업종 수 / A군 전체 수. 접촉 장소의 폭.

    통제용으로 total_cnt(총 건수)와 amount_per_use(건당 결제액)를 함께 반환한다.
    min_cnt 미만 셀은 지표가 불안정해 제외한다.
    """
    keys = list(keys or PANEL_KEYS)
    d = tag_tier(df)
    d = d[d["tier"].isin(denom)]

    tot = d.groupby(keys, observed=True).agg(
        total_cnt=("USE_CNT", "sum"), total_amt=("TS_AT", "sum")
    )
    stay = d[d["is_stay"]]
    stay_cnt = stay.groupby(keys, observed=True)["USE_CNT"].sum().rename("stay_cnt")

    by_ry = stay.groupby(keys + ["MCT_RY_CD"], observed=True)["USE_CNT"].sum()
    ent = (
        by_ry.groupby(keys, observed=True)
        .apply(lambda s: _entropy(s.to_numpy()))
        .rename("contact_entropy")
    )
    brd = by_ry.groupby(keys, observed=True).size().rename("n_stay_ry")

    out = tot.join(stay_cnt).join(ent).join(brd).fillna(0)
    out["contact_share"] = out.stay_cnt / out.total_cnt
    out["contact_breadth"] = out.n_stay_ry / len(CONTACT_STAY)
    out["amount_per_use"] = out.total_amt / out.total_cnt
    return out[out.total_cnt >= min_cnt].reset_index()


PREDICTIONS = ["contact_share", "contact_entropy", "contact_breadth"]


def coherence(frame: pd.DataFrame, cols: list[str]) -> dict:
    """항목들이 하나의 개념을 재는지 본다.

    같은 상태의 다른 발현이라면 서로 양의 상관이어야 한다.
    Cronbach's alpha 0.7 미만이면 합산하지 않는다.
    """
    sub = frame[cols].astype(float)
    z = (sub - sub.mean()) / sub.std(ddof=1)
    k = len(cols)
    alpha = (k / (k - 1)) * (1 - z.var(ddof=1).sum() / z.sum(axis=1).var(ddof=1))
    c = sub.corr(method="spearman")
    off = c.to_numpy()[np.triu_indices(k, 1)]
    return {
        "alpha": float(alpha),
        "mean_inter_item": float(off.mean()),
        "min_inter_item": float(off.min()),
        "corr": c,
    }
