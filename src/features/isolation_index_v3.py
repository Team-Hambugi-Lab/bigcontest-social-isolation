"""#24 제공 v3.3. uv run python -m src.features.isolation_index_v3.

입출력은 src.data.paths 공통 경로를 사용한다. 계산 가정은 docs/isolation_index_v3.md 참조.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

pd.set_option("display.width", 180)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.paths import INTERIM_DIR, PROCESSED_DIR  # noqa: E402

SRC = PROCESSED_DIR / "master_sgis2024_selected_no_industry_counts.csv"
OUT = INTERIM_DIR / "isolation_index_v3.csv"
OUT_TYPES = OUT.with_suffix(".csvt")
OUT_DICTIONARY = OUT.with_name(f"{OUT.stem}_dictionary.csv")
OUT_ADM = INTERIM_DIR / "isolation_index_v3_adm.csv"
OUT_ADM_TYPES = OUT_ADM.with_suffix(".csvt")
OUT_ADM_DICTIONARY = OUT_ADM.with_name(f"{OUT_ADM.stem}_dictionary.csv")

IMPUTE = 0
IMPUTE_ALT = 2
CLIP_Z = 3
STRATIFY = "REGION"
WORK_MIXED = 1.0
WORK_HOLD = 5.0
GROUP_HOLD = 5.0
TOP = 0.8
AGG = "mean"
THEMES = {"A": ["solo50", "old", "oldho"], "B": ["male_solo", "housv", "other50"]}
RENTAL_SIG = dict(p_1in=0.55, old=0.40, p_apt=0.90)
S = "SGIS2024_"
DIMS = THEMES["A"] + THEMES["B"]
AGE65 = list(range(14, 22))


def write_dictionary(frame, definitions, destination):
    """현재 출력의 열 정의·결측 수·값 요약을 저장한다."""
    values = frame.reset_index()
    rows = []
    for definition in definitions:
        series = values[definition["column"]]
        row = dict(definition)
        row["dtype"] = str(series.dtype)
        row["n_missing"] = int(series.isna().sum())
        if definition["column"] in {"TOT_OA_CD", "ADM_CD"}:
            row["summary"] = f"고유값 {series.nunique()}"
        elif pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            observed = series.dropna()
            row["summary"] = (
                f"평균 {observed.mean():.3f} / 중앙 {observed.median():.3f} / "
                f"최소 {observed.min():.3f} / 최대 {observed.max():.3f}"
                if len(observed)
                else "모두 결측"
            )
        else:
            row["summary"] = ", ".join(
                f"{key}:{count}"
                for key, count in series.fillna("")
                .astype(str)
                .replace("", "(빈값)")
                .value_counts()
                .items()
            )
        rows.append(row)
    pd.DataFrame(rows)[
        ["column", "name_kr", "group", "definition", "unit", "dtype", "n_missing", "summary"]
    ].to_csv(destination, index=False, encoding="utf-8-sig")


def write_output_dictionaries(oa, adm):
    oa_definitions = [
        {
            "column": "TOT_OA_CD",
            "name_kr": "집계구 코드",
            "group": "키",
            "definition": "문자열 14자리. SGIS 집계구 경계와 조인 키",
            "unit": "—",
        },
        {
            "column": "REGION",
            "name_kr": "지역",
            "group": "키",
            "definition": "강남구 / 춘천시. 백분위·등급은 이 안에서 계산",
            "unit": "—",
        },
        {
            "column": "ADM_CD",
            "name_kr": "행정동 코드",
            "group": "키",
            "definition": "문자열 8자리. SGIS 경계 bnd_dong_00_2025_2Q.dbf 로 이름 조인 (행안부 코드표와 체계 다름)",
            "unit": "—",
        },
        {
            "column": "pop_total",
            "name_kr": "총인구",
            "group": "가중치",
            "definition": "SGIS2024_to_in_001",
            "unit": "명",
        },
        {
            "column": "hh_total",
            "name_kr": "총가구",
            "group": "가중치",
            "definition": "SGIS2024_to_ga_001. 행정동 집계 시 가중치 (분모 = 보류 아님 & 점수 유효 행)",
            "unit": "가구",
        },
        {
            "column": "hh_single",
            "name_kr": "1인가구 수",
            "group": "가중치",
            "definition": "SGIS2024_ga_sd_005 (결측=5 미만 비공개 → 0)",
            "unit": "가구",
        },
        {
            "column": "theme_A_score",
            "name_kr": "테마 A 점수",
            "group": "테마",
            "definition": "solo50·old·oldho z-score 평균",
            "unit": "z",
        },
        {
            "column": "theme_A_pct",
            "name_kr": "테마 A 백분위",
            "group": "테마",
            "definition": "지역 내 백분위, 보류 제외. 높을수록 고령 독거 위험",
            "unit": "0~100",
        },
        {
            "column": "theme_B_score",
            "name_kr": "테마 B 점수",
            "group": "테마",
            "definition": "male_solo·housv·other50 z-score 평균",
            "unit": "z",
        },
        {
            "column": "theme_B_pct",
            "name_kr": "테마 B 백분위",
            "group": "테마",
            "definition": "지역 내 백분위, 보류 제외. 높을수록 중장년 독거·주거취약 위험",
            "unit": "0~100",
        },
        {
            "column": "score",
            "name_kr": "종합 점수",
            "group": "종합",
            "definition": "(theme_A_pct + theme_B_pct)/2. 평균 유지로 합의(이슈 #24)",
            "unit": "0~100",
        },
        {
            "column": "pctile",
            "name_kr": "종합 백분위",
            "group": "종합",
            "definition": "score 의 지역 내 백분위",
            "unit": "0~100",
        },
        {
            "column": "grade",
            "name_kr": "최종 등급",
            "group": "종합",
            "definition": "pctile 5분위. 5 = 상위 20%. **0 = 보류(등급 미부여)** — 가장 안전한 등급이 아님",
            "unit": "0~5",
        },
        {
            "column": "type_label",
            "name_kr": "유형 라벨",
            "group": "유형",
            "definition": '고령 독거형 / 중장년 독거형 / 복합형 / 일반 / 보류. "(혼합지)" 접미 = work_ratio 1~5. 임대단지는 rental_est 열로 분리(v3.2)',
            "unit": "범주",
        },
        {
            "column": "watch",
            "name_kr": "관찰 후보",
            "group": "유형",
            "definition": "보류 아님 AND (grade=5 OR theme_A_pct≥80 OR theme_B_pct≥80). 종합 3~4등급이어도 한 테마가 상위면 포함 (이슈 #24 후속 3번, v3.3). 지역 우선 후보 조건으로 C 작업과 공유",
            "unit": "T/F",
        },
        {
            "column": "rental_est",
            "name_kr": "고령 임대단지 추정",
            "group": "유형",
            "definition": '서명 규칙 p_1in≥0.55 & old≥0.40 & p_apt≥0.90. LH·SH 단지 자료로 확인한 것이 아닌 추정값 → 에이전트 설명에 "임대단지 추정"으로 표기',
            "unit": "T/F",
        },
        {
            "column": "hold",
            "name_kr": "보류 여부",
            "group": "플래그",
            "definition": "True면 등급 미부여 (grade=0)",
            "unit": "T/F",
        },
        {
            "column": "hold_reason",
            "name_kr": "보류 사유",
            "group": "플래그",
            "definition": '업무지(work_ratio>5) / 집단가구(pop_per_hh>5) / 인구없음(총인구 0) / 일반가구없음(인구는 있으나 일반가구 0; 특정 시설 확인 아님) / 거처자료없음(주택+주택이외거처 0) / 빈값(등급 부여). v3.3에서 "거주없음"을 세 사유로 분리',
            "unit": "범주",
        },
        {
            "column": "mixed",
            "name_kr": "혼합지 여부",
            "group": "플래그",
            "definition": "1 < work_ratio ≤ 5. 등급은 유지",
            "unit": "T/F",
        },
        {
            "column": "work_ratio",
            "name_kr": "종사자/거주자",
            "group": "플래그 입력",
            "definition": "SGIS2024_to_em_020 / 총인구",
            "unit": "배",
        },
        {
            "column": "pop_per_hh",
            "name_kr": "가구당 인구",
            "group": "플래그 입력",
            "definition": "총인구 / 총가구",
            "unit": "명",
        },
        {
            "column": "grade_imp2",
            "name_kr": "등급(결측 2 대치)",
            "group": "민감도",
            "definition": "결측을 0 대신 2로 대치했을 때의 grade. 참고용",
            "unit": "0~5",
        },
        {
            "column": "unstable_imp2",
            "name_kr": "결측 민감",
            "group": "민감도",
            "definition": "기본과 2 대치 양쪽에 등급이 있는 집계구 중 grade 또는 type_label이 바뀌는지. False에는 비교 대상 아님도 포함하므로 hold·grade와 함께 읽음. 대치 가정 민감성이며 실제 오차 확률이 아님",
            "unit": "T/F",
        },
        {
            "column": "p65_method",
            "name_kr": "65세+ 산출 방법",
            "group": "민감도",
            "definition": "기본 산출 분기: 역산(odr>0, ai>0) / 부양비만(odr>0, ai<=0: 유년 비중 0 근사) / 구간합(odr<=0). 기본 0 대치에서 공개 65세+ 구간 합/총인구를 하한으로 적용. ai=0이 유년 인구 0의 직접 확인은 아님",
            "unit": "범주",
        },
        {
            "column": "p_1in",
            "name_kr": "1인가구율",
            "group": "기초 비율",
            "definition": "1인가구 / 총가구",
            "unit": "0~1",
        },
        {
            "column": "p_50",
            "name_kr": "50세+ 비율",
            "group": "기초 비율",
            "definition": "50~64세 인구 / 총인구 + 추정한 65세+ 비율(old)",
            "unit": "0~1",
        },
        {
            "column": "p_apt",
            "name_kr": "아파트 비율",
            "group": "기초 비율",
            "definition": "SGIS2024_ho_gb_003 / 총주택. 임대단지 서명용",
            "unit": "0~1",
        },
        {
            "column": "p_other",
            "name_kr": "주택이외 거처 비율",
            "group": "기초 비율",
            "definition": "SGIS2024_ho_gb_006 / (총주택 + 주택이외 거처). 고시원·오피스텔 포함",
            "unit": "0~1",
        },
        {
            "column": "solo50",
            "name_kr": "중장년·고령 독거 추정",
            "group": "테마 A 차원",
            "definition": "p_1in × p_50 (1인가구×연령 교차표 대용)",
            "unit": "0~1",
        },
        {
            "column": "old",
            "name_kr": "65세+ 비율",
            "group": "테마 A 차원",
            "definition": "odr>0, ai>0: 1/(1+100/odr+100/ai); odr>0, ai<=0: odr/(100+odr) 근사; odr<=0: 연령 구간 합/총인구. 기본 0 대치에서 공개 구간 합 비율을 하한으로 적용. p65_method에 기본 산출 분기 기록",
            "unit": "0~1",
        },
        {
            "column": "oldho",
            "name_kr": "노후 비아파트",
            "group": "테마 A 차원",
            "definition": "(1979년 이전 + 1980년대)/총주택 × (단독+다세대+연립)/총주택",
            "unit": "0~1",
        },
        {
            "column": "male_solo",
            "name_kr": "중장년 남성 독거 추정",
            "group": "테마 B 차원",
            "definition": "50~64세 남성/총인구 × p_1in",
            "unit": "0~1",
        },
        {
            "column": "housv",
            "name_kr": "주거취약",
            "group": "테마 B 차원",
            "definition": "(비주거용 건물내 주택 + 20㎡ 이하)/(총주택 + 주택이외 거처)",
            "unit": "0~1",
        },
        {
            "column": "other50",
            "name_kr": "고시원 대리",
            "group": "테마 B 차원",
            "definition": "p_other × p_50. 오피스텔=청년, 고시원=중장년 가정. 고시원 현황 확보 시 교체",
            "unit": "0~1",
        },
        {
            "column": "z_solo50",
            "name_kr": "중장년·고령 독거 추정 z",
            "group": "z-score",
            "definition": "solo50 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
        {
            "column": "z_old",
            "name_kr": "65세+ 비율 z",
            "group": "z-score",
            "definition": "old 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
        {
            "column": "z_oldho",
            "name_kr": "노후 비아파트 z",
            "group": "z-score",
            "definition": "oldho 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
        {
            "column": "z_male_solo",
            "name_kr": "중장년 남성 독거 추정 z",
            "group": "z-score",
            "definition": "male_solo 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
        {
            "column": "z_housv",
            "name_kr": "주거취약 z",
            "group": "z-score",
            "definition": "housv 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
        {
            "column": "z_other50",
            "name_kr": "고시원 대리 z",
            "group": "z-score",
            "definition": "other50 의 지역 내 표준화, ±3 절단",
            "unit": "z",
        },
    ]
    adm_definitions = [
        {
            "column": "ADM_CD",
            "name_kr": "행정동 코드",
            "group": "행정동 집계",
            "definition": "문자열 8자리",
            "unit": "문자열 8자리",
        },
        {
            "column": "REGION",
            "name_kr": "지역",
            "group": "행정동 집계",
            "definition": "강남구 / 춘천시",
            "unit": "지역명",
        },
        {
            "column": "n_oa",
            "name_kr": "집계구 수",
            "group": "행정동 집계",
            "definition": "행정동 내 전체 집계구",
            "unit": "집계구",
        },
        {
            "column": "n_oa_eval",
            "name_kr": "평가 집계구 수",
            "group": "행정동 집계",
            "definition": "보류 아님 & 점수 유효",
            "unit": "집계구",
        },
        {
            "column": "hh_total",
            "name_kr": "총가구",
            "group": "행정동 집계",
            "definition": "전체 집계구 합",
            "unit": "가구",
        },
        {
            "column": "hh_eval",
            "name_kr": "평가 가구",
            "group": "행정동 집계",
            "definition": "평가 집계구의 총가구 합 = 가중평균 분모",
            "unit": "가구",
        },
        {
            "column": "hh_hold",
            "name_kr": "보류 가구",
            "group": "행정동 집계",
            "definition": "보류 집계구(업무지·집단가구·인구없음 등)의 총가구 합",
            "unit": "가구",
        },
        {
            "column": "hh_single_eval",
            "name_kr": "평가 1인가구",
            "group": "행정동 집계",
            "definition": "평가 집계구의 1인가구 합",
            "unit": "가구",
        },
        {
            "column": "score_w",
            "name_kr": "종합 점수 가중평균",
            "group": "행정동 집계",
            "definition": "score 를 hh_total 로 가중, 평가 집계구만",
            "unit": "0~100",
        },
        {
            "column": "theme_A_pct_w",
            "name_kr": "테마 A 가중평균",
            "group": "행정동 집계",
            "definition": "동일",
            "unit": "0~100",
        },
        {
            "column": "theme_B_pct_w",
            "name_kr": "테마 B 가중평균",
            "group": "행정동 집계",
            "definition": "동일",
            "unit": "0~100",
        },
        {
            "column": "n_grade5",
            "name_kr": "5등급 집계구 수",
            "group": "행정동 집계",
            "definition": "등급 5인 집계구 수",
            "unit": "집계구",
        },
        {
            "column": "hh_grade5",
            "name_kr": "5등급 가구",
            "group": "행정동 집계",
            "definition": "5등급 집계구의 총가구 합",
            "unit": "가구",
        },
        {
            "column": "n_watch",
            "name_kr": "관찰 후보 집계구 수",
            "group": "행정동 집계",
            "definition": "watch=True",
            "unit": "집계구",
        },
        {
            "column": "hh_watch",
            "name_kr": "관찰 후보 가구",
            "group": "행정동 집계",
            "definition": "watch=True인 집계구의 일반가구 합",
            "unit": "가구",
        },
        {
            "column": "share_hh_eval",
            "name_kr": "평가 가능 가구 비중",
            "group": "행정동 집계",
            "definition": "hh_eval / hh_total. 낮으면 동 집계값 해석 주의",
            "unit": "0~1",
        },
        {
            "column": "share_hh_hold",
            "name_kr": "보류 가구 비중",
            "group": "행정동 집계",
            "definition": "hh_hold / hh_total",
            "unit": "0~1",
        },
    ]
    write_dictionary(oa, oa_definitions, OUT_DICTIONARY)
    write_dictionary(adm, adm_definitions, OUT_ADM_DICTIONARY)


def main() -> None:
    if not SRC.is_file():
        raise FileNotFoundError(f"입력 마스터를 {SRC.relative_to(ROOT)}에 배치한 뒤 실행하세요.")
    df = pd.read_csv(SRC, dtype={"TOT_OA_CD": str, "ADM_CD": str, "STD_YM": str}, low_memory=False)
    one = df[df.STD_YM == df.STD_YM.min()].set_index("TOT_OA_CD")
    sg = [c for c in one.columns if c.startswith(S)]
    print("집계구", len(one), "| SGIS 변수", len(sg))

    # ## 2. 차원·테마·등급 계산
    #
    # 65세+ 비율: 노년부양비(odr = 65+/15~64)와 노령화지수(ai = 65+/0~14)가 모두 공개되면 `1/(1+100/odr+100/ai)`.
    # ai가 0이면 유년 비중 0 근사로 odr/(100+odr)를 사용한다. 유년 인구 0의 직접 확인은 아니다.
    # 기본 0 대치에서 공개 65세+ 구간 합/총인구를 하한으로 적용한다. 2 대치 실험의 구간 합에는 대치값이 포함된다.

    def build(impute=IMPUTE, strat=STRATIFY, clip=CLIP_Z, themes=THEMES, verbose=False):
        d = one.copy()
        d[sg] = d[sg].fillna(impute)
        pop, hh, ho = d[S + "to_in_001"], d[S + "to_ga_001"], d[S + "to_ho_001"]
        dwell_all = ho + d[S + "ho_gb_006"]  # 총거처 = 주택 + 주택이외 거처(오피스텔·고시원)
        d["resident"] = (pop > 0) & (hh > 0) & (dwell_all > 0)
        d["excl_reason"] = np.select(
            [pop <= 0, hh <= 0, dwell_all <= 0], ["인구없음", "일반가구없음", "거처자료없음"], ""
        )
        excluded = d[~d.resident].copy()
        d = d[d.resident].copy()
        pop, hh, ho = pop[d.index], hh[d.index], ho[d.index]

        def age(ids):
            return d[[f"{S}in_age_{i:03d}" for i in ids]].sum(axis=1)

        # 65세+ 비율 (v3.3 예외 처리)
        odr, ai = d[S + "to_in_005"], d[S + "to_in_004"]
        p65_direct = age(AGE65) / pop  # 기본 0 대치에서는 공개 구간 합 하한
        p65_inv = 1 / (1 + 100 / odr.replace(0, np.nan) + 100 / ai.replace(0, np.nan))
        p65_fb = odr / (100 + odr)  # ai=0: 0~14세 ≈ 0
        p65 = pd.Series(
            np.select([(odr > 0) & (ai > 0), odr > 0], [p65_inv, p65_fb], p65_direct), index=d.index
        )
        p65 = np.maximum(p65, p65_direct)
        d["p65_method"] = np.select([(odr > 0) & (ai > 0), odr > 0], ["역산", "부양비만"], "구간합")
        if verbose:
            print("65세+ 산출 방법:", d.p65_method.value_counts().to_dict())
        p50 = age([11, 12, 13]) / pop + p65  # 50~64세/총인구 + 65세+ 비율
        dwell = ho + d[S + "ho_gb_006"]
        ho_safe = ho.replace(0, np.nan)  # 주택 0인 집계구: 주택 기반 비율은 0
        nonapt = ((d[S + "ho_gb_001"] + d[S + "ho_gb_002"] + d[S + "ho_gb_004"]) / ho_safe).fillna(
            0
        )

        d["p_1in"] = d[S + "ga_sd_005"] / hh
        d["p_50"] = p50
        d["p_apt"] = (d[S + "ho_gb_003"] / ho_safe).fillna(0)
        d["p_other"] = d[S + "ho_gb_006"] / dwell
        # 테마 A
        d["solo50"] = d.p_1in * p50
        d["old"] = p65
        d["oldho"] = ((d[S + "ho_yr_001"] + d[S + "ho_yr_002"]) / ho_safe).fillna(0) * nonapt
        # 테마 B
        d["male_solo"] = age([41, 42, 43]) / pop * d.p_1in
        d["housv"] = (d[S + "ho_gb_005"] + d[S + "ho_ar_001"]) / dwell
        d["other50"] = d.p_other * p50
        # 보류·혼합 플래그
        d["work_ratio"] = d[S + "to_em_020"] / pop
        d["pop_per_hh"] = pop / hh
        d["hold"] = (d.work_ratio > WORK_HOLD) | (d.pop_per_hh > GROUP_HOLD)
        d["hold_reason"] = np.select(
            [d.work_ratio > WORK_HOLD, d.pop_per_hh > GROUP_HOLD], ["업무지", "집단가구"], ""
        )
        d["mixed"] = (d.work_ratio > WORK_MIXED) & ~d.hold

        # z → 테마 점수 → 테마 백분위 (지역 내, 보류 제외) → 종합
        grp = d.groupby(strat) if strat else None
        for k in DIMS:
            d["z_" + k] = (
                grp[k].transform(lambda s: (s - s.mean()) / s.std())
                if strat
                else (d[k] - d[k].mean()) / d[k].std()
            ).clip(-clip, clip)
        ok = ~d.hold
        for t, cols in themes.items():
            d[f"theme_{t}_score"] = d[["z_" + k for k in cols]].mean(axis=1)
            s = d.loc[ok, f"theme_{t}_score"]
            d[f"theme_{t}_pct"] = (
                s.groupby(d.loc[ok, strat]).rank(pct=True) if strat else s.rank(pct=True)
            ) * 100
        tp = d[[f"theme_{t}_pct" for t in themes]]
        d["score"] = tp.max(axis=1) if AGG == "max" else tp.mean(axis=1)
        s = d.loc[ok, "score"]
        d["pctile"] = (
            s.groupby(d.loc[ok, strat]).rank(pct=True) if strat else s.rank(pct=True)
        ) * 100
        d["grade"] = (
            pd.cut(d["pctile"], [0, 20, 40, 60, 80, 100], labels=[1, 2, 3, 4, 5])
            .astype("Int64")
            .fillna(0)
            .astype(int)
        )

        # 유형 라벨 · 관찰 후보
        topA = d["theme_A_pct"] >= TOP * 100 if "A" in themes else pd.Series(False, index=d.index)
        topB = d["theme_B_pct"] >= TOP * 100 if "B" in themes else pd.Series(False, index=d.index)
        d["rental_est"] = (
            (d.p_1in >= RENTAL_SIG["p_1in"])
            & (d.old >= RENTAL_SIG["old"])
            & (d.p_apt >= RENTAL_SIG["p_apt"])
        )  # 임대단지 추정 (LH·SH 미확인)
        d["type_label"] = np.select(
            [d.hold, topA & topB, topA, topB],
            ["보류", "복합형", "고령 독거형", "중장년 독거형"],
            "일반",
        )
        d.loc[d.mixed & ~d.hold, "type_label"] += "(혼합지)"
        d["watch"] = ok & ((d.grade == 5) | topA | topB)  # 지역 우선 후보 조건 (이슈 #24 3번)

        # 차원 계산에서 제외된 집계구도 행으로 유지 → grade 0, 보류 사유 세분화 (v3.3)
        excluded["hold"] = True
        excluded["hold_reason"] = excluded["excl_reason"]
        excluded["mixed"] = False
        excluded["grade"] = 0
        excluded["type_label"] = "보류"
        excluded["rental_est"] = False
        excluded["watch"] = False
        d = pd.concat([d, excluded], axis=0).reindex(one.index)
        d["REGION"] = one["REGION"]
        d["ADM_CD"] = one["ADM_CD"]
        return d

    base = build(verbose=True)
    print(
        "집계구",
        len(base),
        "| 보류",
        int(base.hold.sum()),
        base.hold_reason[base.hold].value_counts().to_dict(),
        "| 혼합지",
        int(base.mixed.sum()),
        "| 관찰 후보",
        int(base.watch.sum()),
    )

    # ## 3. 결과

    print("[지역 × 등급, 0 = 보류]")
    print(pd.crosstab(base.REGION, base.grade))
    print("[지역 × 유형]")
    print(pd.crosstab(base.REGION, base.type_label))
    print("[관찰 후보 × 종합 등급] — 5등급이 아닌데 후보인 곳 = 한 테마만 상위")
    print(pd.crosstab(base.watch, base.grade, rownames=["watch"], colnames=["grade"]))
    print("[임대단지 추정 × 유형]")
    print(pd.crosstab(base.rental_est, base.type_label))
    print("[테마 상위 20% 겹침]")
    print(
        pd.crosstab(
            base.theme_A_pct >= 80, base.theme_B_pct >= 80, rownames=["A상위"], colnames=["B상위"]
        )
    )
    nh = ~base.hold.astype(bool)
    print(
        "테마 A·B 점수 Spearman:",
        round(base[nh].theme_A_score.corr(base[nh].theme_B_score, method="spearman"), 3),
    )
    print("[유형별 프로파일 평균]")
    print(
        base.groupby("type_label")[
            ["p_1in", "p_50", "old", "male_solo", "housv", "other50", "oldho", "work_ratio"]
        ]
        .mean()
        .round(3)
    )

    print("[지역별 5등급 상위 10]")
    for reg, sub in base[base.grade == 5].groupby("REGION"):
        print(
            sub.sort_values("score", ascending=False)
            .head(10)[
                ["ADM_CD", "type_label", S + "to_in_001", S + "ga_sd_005", "p_1in", "old"]
                + DIMS
                + ["theme_A_pct", "theme_B_pct", "score"]
            ]
            .round(2)
        )

    # ## 4. 차원 기여도

    ok = ~base.hold.astype(bool)
    g5 = base.grade == 5
    z = base.loc[ok, ["z_" + k for k in DIMS]].copy()
    z.columns = DIMS
    imp = pd.DataFrame(index=DIMS)
    imp["테마"] = ["A"] * 3 + ["B"] * 3
    imp["종합 상관"] = [spearmanr(z[k], base.loc[ok, "score"]).correlation for k in DIMS]
    imp["5등급 평균 z"] = z[g5[ok]].mean()
    print(imp.round(3))

    # ## 5. 민감도 — 공통 평가 대상 비교
    #
    # v3.2까지는 두 결과를 그냥 합쳐 비교해 대치값에 따라 계산 대상 자체가 바뀌는 효과(1,663→1,665)와 순위 변화가 섞였다.
    # 양쪽 모두 등급이 있는 교집합에서 비교한다. 각 대치 조건의 표준화 기준 모집단은 고정하지 않는다.
    # 결측 2 대치에서 등급 또는 유형이 바뀌는 집계구는 `unstable_imp2` 열로 CSV에 기록한다.

    def compare(a, b, label):
        both = (a.grade > 0) & (b.grade > 0)
        j = a[both]
        k = b[both]
        set_change = int(((a.grade > 0) != (b.grade > 0)).sum())
        r = {
            "공통 평가 대상": int(both.sum()),
            "대상 집합 변동": set_change,
            "Spearman(score)": round(spearmanr(j.score, k.score).correlation, 4),
            "등급 변경": int((j.grade != k.grade).sum()),
            "5등급 교체": int(((j.grade == 5) & (k.grade != 5)).sum()),
            "5등급 진입": int(
                ((j.grade != 5) & (k.grade == 5)).sum()
            ),  # 동점 경계 때문에 이탈 수와 진입 수는 다를 수 있음
            "유형 변경": int((j.type_label != k.type_label).sum()),
            "A 상위 교체": int(((j.theme_A_pct >= 80) & ~(k.theme_A_pct >= 80)).sum()),
            "B 상위 교체": int(((j.theme_B_pct >= 80) & ~(k.theme_B_pct >= 80)).sum()),
            "관찰 후보 변경": int((j.watch != k.watch).sum()),
        }
        return pd.Series(r, name=label)

    alt_imp = build(impute=IMPUTE_ALT)
    sens = pd.DataFrame(
        [
            compare(base, alt_imp, f"결측 {IMPUTE_ALT} 대치"),
            compare(base, build(strat=None), "전체 통합 백분위"),
        ]
    )
    print(sens)

    both = (base.grade > 0) & (alt_imp.grade > 0)
    base["grade_imp2"] = alt_imp.grade
    base["unstable_imp2"] = both & (
        (base.grade != alt_imp.grade) | (base.type_label != alt_imp.type_label)
    )
    print(
        "unstable_imp2:",
        int(base.unstable_imp2.sum()),
        "| 그중 5등급:",
        int((base.unstable_imp2 & (base.grade == 5)).sum()),
        "| 관찰 후보:",
        int((base.unstable_imp2 & base.watch).sum()),
    )

    # ## 6. 행정동 집계 (기준 구현)
    #
    # - 가중평균(score·테마 백분위)의 분모 = **보류 아님 & 점수 유효** 행의 `hh_total`
    # - 전체 가구 대비 `share_hh_eval`(평가 가능), `share_hh_hold`(보류) 비중을 함께 남긴다 → 평가 비중이 낮은 동은 해석에 주의
    # - 5등급·관찰 후보 집계구 수와 그 가구 수도 함께

    ev = (~base.hold.astype(bool)) & base.score.notna()
    hh = base[S + "to_ga_001"].fillna(0)

    def wavg(col):
        return lambda g: (
            np.average(g[col], weights=hh[g.index]) if hh[g.index].sum() > 0 else np.nan
        )

    grpa = base.groupby("ADM_CD")
    adm = pd.DataFrame(
        {
            "REGION": grpa["REGION"].first(),
            "n_oa": grpa.size(),
            "n_oa_eval": base[ev].groupby("ADM_CD").size(),
            "hh_total": grpa[S + "to_ga_001"].sum(),
            "hh_eval": base[ev].groupby("ADM_CD")[S + "to_ga_001"].sum(),
            "hh_hold": base[~ev].groupby("ADM_CD")[S + "to_ga_001"].sum(),
            "hh_single_eval": base[ev].groupby("ADM_CD")[S + "ga_sd_005"].sum(),
            "score_w": base[ev].groupby("ADM_CD").apply(wavg("score")),
            "theme_A_pct_w": base[ev].groupby("ADM_CD").apply(wavg("theme_A_pct")),
            "theme_B_pct_w": base[ev].groupby("ADM_CD").apply(wavg("theme_B_pct")),
            "n_grade5": base[base.grade == 5].groupby("ADM_CD").size(),
            "hh_grade5": base[base.grade == 5].groupby("ADM_CD")[S + "to_ga_001"].sum(),
            "n_watch": base[base.watch.astype(bool)].groupby("ADM_CD").size(),
            "hh_watch": base[base.watch.astype(bool)].groupby("ADM_CD")[S + "to_ga_001"].sum(),
        }
    ).fillna(
        {
            "n_oa_eval": 0,
            "hh_eval": 0,
            "hh_hold": 0,
            "hh_single_eval": 0,
            "n_grade5": 0,
            "hh_grade5": 0,
            "n_watch": 0,
            "hh_watch": 0,
        }
    )
    adm["share_hh_eval"] = adm.hh_eval / adm.hh_total.replace(0, np.nan)
    adm["share_hh_hold"] = adm.hh_hold / adm.hh_total.replace(0, np.nan)
    for c in ["n_oa_eval", "n_grade5", "n_watch"]:
        adm[c] = adm[c].astype(int)
    OUT_ADM.parent.mkdir(parents=True, exist_ok=True)
    adm.to_csv(OUT_ADM, encoding="utf-8-sig", index_label="ADM_CD")
    adm_strcols = {"REGION"}
    adm_intcols = {"n_oa", "n_oa_eval", "n_grade5", "n_watch"}
    adm_types = ['"String"'] + [
        '"String"' if c in adm_strcols else '"Integer"' if c in adm_intcols else '"Real"'
        for c in adm.columns
    ]
    OUT_ADM_TYPES.write_text(",".join(adm_types) + "\n", encoding="utf-8")

    print("saved:", OUT_ADM.relative_to(ROOT), "| rows/columns:", len(adm), len(adm.columns) + 1)
    print(adm.sort_values("share_hh_eval").head(8).round(3))

    # ## 7. 저장 (C 작업용 컬럼: 집계구·행정동 코드, 테마 백분위, 종합 등급, 유형, 관찰 후보, 보류 사유, 결측 민감도, 가구 수)

    out = base.rename(
        columns={
            S + "to_ga_001": "hh_total",
            S + "ga_sd_005": "hh_single",
            S + "to_in_001": "pop_total",
        }
    )
    cols = (
        [
            "REGION",
            "ADM_CD",
            "pop_total",
            "hh_total",
            "hh_single",
            "theme_A_score",
            "theme_A_pct",
            "theme_B_score",
            "theme_B_pct",
            "score",
            "pctile",
            "grade",
            "type_label",
            "watch",
            "rental_est",
            "hold",
            "hold_reason",
            "mixed",
            "work_ratio",
            "pop_per_hh",
            "grade_imp2",
            "unstable_imp2",
            "p65_method",
            "p_1in",
            "p_50",
            "p_apt",
            "p_other",
        ]
        + DIMS
        + ["z_" + k for k in DIMS]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out[cols].to_csv(OUT, encoding="utf-8-sig", index_label="TOT_OA_CD")
    strcols = {
        "REGION",
        "ADM_CD",
        "type_label",
        "watch",
        "rental_est",
        "hold",
        "hold_reason",
        "mixed",
        "unstable_imp2",
        "p65_method",
    }
    types = ['"String"'] + [
        '"String"' if c in strcols else '"Integer"' if c in ("grade", "grade_imp2") else '"Real"'
        for c in cols
    ]
    OUT_TYPES.write_text(",".join(types) + "\n", encoding="utf-8")
    write_output_dictionaries(out[cols], adm)
    print("saved:", OUT.relative_to(ROOT), "| rows/columns:", len(out), len(cols) + 1)


if __name__ == "__main__":
    main()
