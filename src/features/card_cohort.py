"""신한카드 데이터2를 집단축 패널(지역 x 성 x 연령 x 월)로 집계한다.

카드에는 시군구 2종밖에 없어 SK의 동 단위(47개)와 결합할 수 없다.
따라서 공간축과 분리해 집단축 지표만 만든다.
"""

import pandas as pd

from src.data import loaders

# 금액의 49.6%를 차지하는 미분류·비소비 업종. 금액 지표에서 제외한다.
EXCLUDED_RY = ("ZZ_나머지", "세금공과금")

# 대면 관계 소비 12종. 혼자서도 이용하는 편의·의료 업종은 제외했다.
SOCIAL_RY = (
    "한식",
    "기타요식",
    "커피전문점",
    "제과점",
    "미용실",
    "헬스장",
    "노래방",
    "영화/공연",
    "싸우나/목욕탕",
    "스포츠시설",
    "게임방/오락실",
    "독서실",
)

# CLN_SGG_CD는 시도 단위다. 강남구 가맹점의 '서울' 고객이 강남구민인지 알 수 없으므로
# 지역민 비중은 춘천에 대해서만 근사치로 쓴다.
LOCAL_SIDO = {"강원 춘천시": "강원"}

COHORT_KEYS = ["MCT_SGG_CD", "SEX_CCD", "age_band", "ym"]

# USE_CNT 최솟값은 5다(5건 미만 집계셀 삭제). 데이터2는 여기에 더해 추가 비식별 처리를
# 받아 7~10, 14~15, 20~21이 아예 등장하지 않는다. 등장 구간은 [5,6] [11,13] [16,19] [22~]다.
# 따라서 '절단선에 붙은 셀'은 최하단 밴드인 USE_CNT <= 6으로 정의한다.
NEAR_CUT_MAX = 6
# 데이터2에서 관측되지 않는 USE_CNT 값 (60 이하)
MISSING_USE_CNT = (1, 2, 3, 4, 7, 8, 9, 10, 14, 15, 20, 21)


def prepare_card(dataset: int = 2) -> pd.DataFrame:
    """카드 원본에 파생 컬럼을 붙인다.

    데이터1에는 법인카드 행이 있어 AGE_CCD가 "법인"이다. 숫자로 바꿀 수 없으므로
    age_band는 nullable 정수형으로 두고 해당 행은 <NA>가 된다.
    """
    df = loaders.load_card(dataset)
    df["ym"] = df["TA_YMD"].str[:6]
    # AGE_CCD는 "10 대" 형태로 숫자와 '대' 사이에 공백이 있다
    df["age_band"] = pd.to_numeric(
        df["AGE_CCD"].str.extract(r"(\d+)", expand=False), errors="coerce"
    ).astype("Int64")
    df["is_corporate"] = df["SEX_CCD"].eq("법인")
    df["is_social"] = df["MCT_RY_CD"].isin(SOCIAL_RY)
    df["is_excluded"] = df["MCT_RY_CD"].isin(EXCLUDED_RY)
    if "CLN_SGG_CD" in df.columns:
        expected_sido = df["MCT_SGG_CD"].map(LOCAL_SIDO)
        df["is_local"] = expected_sido.notna() & (expected_sido == df["CLN_SGG_CD"])
    else:
        # 데이터1에는 고객 거주지 컬럼이 없다
        df["is_local"] = False
    return df


def cohort_panel(df: pd.DataFrame) -> pd.DataFrame:
    """집단축 패널을 만든다. amount_ex는 미분류·비소비 업종을 뺀 금액이다."""
    keep = ~df["is_excluded"]
    out = (
        df.groupby(COHORT_KEYS, observed=True)
        .agg(
            amount=("TS_AT", "sum"),
            count=("USE_CNT", "sum"),
            n_ry=("MCT_RY_CD", "nunique"),
        )
        .join(
            df[keep]
            .groupby(COHORT_KEYS, observed=True)
            .agg(amount_ex=("TS_AT", "sum"), count_ex=("USE_CNT", "sum"))
        )
        .join(
            df[df["is_social"]]
            .groupby(COHORT_KEYS, observed=True)
            .agg(social_amount=("TS_AT", "sum"), social_count=("USE_CNT", "sum"))
        )
        .join(
            df[df["is_local"]]
            .groupby(COHORT_KEYS, observed=True)
            .agg(local_count=("USE_CNT", "sum"))
        )
        .fillna(0)
        .reset_index()
    )
    for c in ("amount_ex", "count_ex", "social_amount", "social_count", "local_count"):
        out[c] = out[c].astype("int64")
    return out


def truncation_stats(
    df: pd.DataFrame,
    by: list[str],
    near_cut_max: int = NEAR_CUT_MAX,
) -> pd.DataFrame:
    """비식별 컷(USE_CNT >= 5) 편향을 간접 추정한다.

    정답을 볼 수 없으므로 살아남은 셀의 모양으로 역추정한다.

    near_cut_share  등장한 셀 중 USE_CNT가 최하단 밴드(<= near_cut_max)인 비율.
                    높을수록 절단선에 붙어 있어 조금만 더 희소했으면 지워졌을 집단이다.
    observed_combos 실제 등장한 (업종 x 거주지) 조합 수
    combo_coverage  가능한 조합 수 대비 등장 비율. 낮을수록 많이 지워졌다.
    """
    combo_cols = [c for c in ("MCT_RY_CD", "CLN_SGG_CD") if c in df.columns]
    possible = 1
    for c in combo_cols:
        possible *= df[c].nunique()

    g = df.groupby(by, observed=True)
    combos = g[combo_cols].apply(lambda d: d.drop_duplicates().shape[0])
    stats = pd.DataFrame(
        {
            "n_cells": g.size(),
            "near_cut_share": g["USE_CNT"].apply(lambda s: float((s <= near_cut_max).mean())),
            "median_use_cnt": g["USE_CNT"].median(),
            "observed_combos": combos,
        }
    )
    stats["combo_coverage"] = stats["observed_combos"] / possible
    return stats.reset_index()
