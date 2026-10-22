"""#24 제공 v3.2. 저장소 루트에서 uv run python -m src.features.isolation_index_v3.

입출력은 src.data.paths의 공통 경로를 사용한다.
계산 가정과 남은 오류는 docs/isolation_index_v3.md 참조.
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

IMPUTE = 0
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


def write_dictionary(frame):
    """이번 출력의 36개 변수 정의와 값 요약을 함께 저장한다."""
    definitions = [
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
            "definition": "SGIS2024_to_ga_001. 행정동 집계 시 가중치",
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
            "definition": "업무지(work_ratio>5) / 집단가구(pop_per_hh>5) / 거주없음(인구·일반가구·총거처 중 하나라도 0 이하; 결측 0 대치 후 판정) / 빈값. 거주없음 중 인구 양수 5행이 있어 명칭 해석 주의",
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
            "definition": "(50~64세 구간합 + 65세+ 역산) / 총인구",
            "unit": "0~1",
        },
        {
            "column": "p_apt",
            "name_kr": "아파트 비율",
            "group": "기초 비율",
            "definition": "SGIS2024_ho_gb_003 / 총주택. 총주택 0이면 0으로 처리하는 모델 규약. 임대단지 추정 서명용",
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
            "definition": "노년부양비·노령화지수가 모두 양수이면 1/(1+100/노년부양비+100/노령화지수), 그 외 0. 노령화지수 0·고령 인구 양수 사례는 남은 오류(docs 참조)",
            "unit": "0~1",
        },
        {
            "column": "oldho",
            "name_kr": "노후 비아파트",
            "group": "테마 A 차원",
            "definition": "(1979년 이전 + 1980년대)/총주택 × (단독+다세대+연립)/총주택. 총주택 0이면 0으로 처리하는 모델 규약; 실제 교차 주택수 직접 관측 아님",
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
    values = frame.reset_index()
    rows = []
    for definition in definitions:
        name = definition["column"]
        series = values[name]
        row = dict(definition)
        row["dtype"] = str(series.dtype)
        row["n_missing"] = int(series.isna().sum())
        if name in {"TOT_OA_CD", "ADM_CD"}:
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
    ].to_csv(OUT_DICTIONARY, index=False, encoding="utf-8-sig")


def main() -> None:
    if not SRC.is_file():
        raise FileNotFoundError(f"입력 마스터를 {SRC.relative_to(ROOT)}에 배치한 뒤 실행하세요.")
    df = pd.read_csv(SRC, dtype={"TOT_OA_CD": str, "ADM_CD": str, "STD_YM": str}, low_memory=False)
    one = df[df.STD_YM == df.STD_YM.min()].set_index("TOT_OA_CD")
    sg = [c for c in one.columns if c.startswith(S)]
    print("집계구", len(one), "| SGIS 변수", len(sg))

    # ## 2. 차원·테마·등급 계산

    def build(impute=IMPUTE, strat=STRATIFY, clip=CLIP_Z, themes=THEMES):
        d = one.copy()
        d[sg] = d[sg].fillna(impute)
        pop, hh, ho = d[S + "to_in_001"], d[S + "to_ga_001"], d[S + "to_ho_001"]
        dwell_all = ho + d[S + "ho_gb_006"]  # 총거처 = 주택 + 주택이외 거처(오피스텔·고시원)
        d["resident"] = (
            (pop > 0) & (hh > 0) & (dwell_all > 0)
        )  # ※ 총주택>0 조건은 오피스텔·고시원 전용 집계구를 잘못 제외함
        excluded = d[~d.resident].copy()
        d = d[d.resident].copy()
        pop, hh, ho = pop[d.index], hh[d.index], ho[d.index]

        def age(ids):
            return d[[f"{S}in_age_{i:03d}" for i in ids]].sum(axis=1)

        odr, ai = d[S + "to_in_005"], d[S + "to_in_004"]
        p65 = pd.Series(
            np.where(
                (odr > 0) & (ai > 0),
                1 / (1 + 100 / odr.replace(0, np.nan) + 100 / ai.replace(0, np.nan)),
                0.0,
            ),
            index=d.index,
        )
        p50 = age([11, 12, 13]) / pop + p65
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

        # 유형 라벨
        topA = d["theme_A_pct"] >= TOP * 100 if "A" in themes else pd.Series(False, index=d.index)
        topB = d["theme_B_pct"] >= TOP * 100 if "B" in themes else pd.Series(False, index=d.index)
        d["rental_est"] = (
            (d.p_1in >= RENTAL_SIG["p_1in"])
            & (d.old >= RENTAL_SIG["old"])
            & (d.p_apt >= RENTAL_SIG["p_apt"])
        )  # 임대단지 추정 (서명 규칙, LH·SH 미확인)
        d["type_label"] = np.select(
            [d.hold, topA & topB, topA, topB],
            ["보류", "복합형", "고령 독거형", "중장년 독거형"],
            "일반",
        )
        d.loc[d.mixed & ~d.hold, "type_label"] += "(혼합지)"
        # 평가 조건 미충족 행도 유지. 기존 사유명 '거주없음'에는 인구 양수 행도 포함됨(docs 참조).
        excluded["hold"] = True
        excluded["hold_reason"] = "거주없음"
        excluded["mixed"] = False
        excluded["grade"] = 0
        excluded["type_label"] = "보류"
        excluded["rental_est"] = False
        d = pd.concat([d, excluded], axis=0).reindex(one.index)
        d["REGION"] = one["REGION"]
        d["ADM_CD"] = one["ADM_CD"]
        return d

    base = build()
    print(
        "집계구",
        len(base),
        "| 보류",
        int(base.hold.sum()),
        base.hold_reason[base.hold].value_counts().to_dict(),
        "| 혼합지",
        int(base.mixed.sum()),
    )

    # ## 3. 결과

    print("[지역 × 등급, 0 = 보류]")
    print(pd.crosstab(base.REGION, base.grade))
    print("[지역 × 유형]")
    print(pd.crosstab(base.REGION, base.type_label))
    print("[임대단지 추정 × 유형]")
    print(pd.crosstab(base.rental_est, base.type_label))
    print("[테마 상위 20% 겹침]")
    print(
        pd.crosstab(
            base.theme_A_pct >= 80, base.theme_B_pct >= 80, rownames=["A상위"], colnames=["B상위"]
        )
    )
    print(
        "테마 A·B 점수 Spearman:",
        round(
            base[~base.hold.astype(bool)].theme_A_score.corr(
                base[~base.hold.astype(bool)].theme_B_score, method="spearman"
            ),
            3,
        ),
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

    # ## 4. 차원 기여도·민감도

    ok = ~base.hold.astype(bool)
    g5 = base.grade == 5
    z = base.loc[ok, ["z_" + k for k in DIMS]].copy()
    z.columns = DIMS
    imp = pd.DataFrame(index=DIMS)
    imp["테마"] = ["A"] * 3 + ["B"] * 3
    imp["종합 상관"] = [spearmanr(z[k], base.loc[ok, "score"]).correlation for k in DIMS]
    imp["5등급 평균 z"] = z[g5[ok]].mean()
    print(imp.round(3))

    def agree(a, b):
        j = a[["score", "grade"]].join(b[["score", "grade"]], rsuffix="_b")
        j = j[(j.grade > 0) & (j.grade_b > 0)]
        return round(
            spearmanr(j.score, j.score_b).correlation, 3
        ), f"{((j.grade == 5) & (j.grade_b == 5)).sum() / (j.grade == 5).sum():.0%}"

    alts = {
        "결측 2 대치": build(impute=2),
        "전체 통합 백분위": build(strat=None),
        "테마 A만": build(themes={"A": THEMES["A"]}),
        "테마 B만": build(themes={"B": THEMES["B"]}),
    }
    print(
        pd.DataFrame(
            {k: agree(base, v) for k, v in alts.items()}, index=["Spearman", "5등급 일치"]
        ).T
    )

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
            "rental_est",
            "hold",
            "hold_reason",
            "mixed",
            "work_ratio",
            "pop_per_hh",
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
    strcols = {"REGION", "ADM_CD", "type_label", "rental_est", "hold", "hold_reason", "mixed"}
    types = ['"String"'] + [
        '"String"' if c in strcols else '"Integer"' if c == "grade" else '"Real"' for c in cols
    ]
    OUT_TYPES.write_text(",".join(types) + "\n", encoding="utf-8")
    write_dictionary(out[cols])
    print("saved:", OUT.relative_to(ROOT), "| rows/columns:", len(out), len(cols) + 1)
    print("dictionary:", OUT_DICTIONARY.relative_to(ROOT))


if __name__ == "__main__":
    main()
