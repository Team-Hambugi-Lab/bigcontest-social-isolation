"""#24 v3 기준 코드. 저장소 루트에서 다음과 같이 실행한다.

uv run python -m src.features.isolation_index_v3

입력과 출력은 src.data.paths의 공통 경로를 사용한다.
원자료 재계산과 에이전트 입력 계약의 추가 작업은 docs/isolation_index_v3.md 참조.
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


# 제공 v3의 분석 파라미터
IMPUTE = 0
CLIP_Z = 3
STRATIFY = "REGION"
WORK_MIXED = 1.0
WORK_HOLD = 5.0
GROUP_HOLD = 5.0
TOP = 0.8
THEMES = {"A": ["solo50", "old", "oldho"], "B": ["male_solo", "housv", "other50"]}
RENTAL_SIG = dict(p_1in=0.55, old=0.40, p_apt=0.90)
S = "SGIS2024_"
DIMS = THEMES["A"] + THEMES["B"]


def main() -> None:
    if not SRC.is_file():
        raise FileNotFoundError(f"입력 마스터를 {SRC.relative_to(ROOT)}에 배치한 뒤 실행하세요.")
    df = pd.read_csv(SRC, dtype={"TOT_OA_CD": str, "ADM_CD": str, "STD_YM": str}, low_memory=False)
    one = df[df.STD_YM == df.STD_YM.min()].set_index("TOT_OA_CD")
    sg = [c for c in one.columns if c.startswith(S)]
    print("집계구", len(one), "| SGIS 변수", len(sg))

    def build(impute=IMPUTE, strat=STRATIFY, clip=CLIP_Z, themes=THEMES):
        d = one.copy()
        d[sg] = d[sg].fillna(impute)
        pop, hh, ho = d[S + "to_in_001"], d[S + "to_ga_001"], d[S + "to_ho_001"]
        valid = (pop > 0) & (hh > 0) & (ho > 0)
        d = d[valid].copy()
        pop, hh, ho = pop[valid], hh[valid], ho[valid]

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
        nonapt = (d[S + "ho_gb_001"] + d[S + "ho_gb_002"] + d[S + "ho_gb_004"]) / ho

        d["p_1in"] = d[S + "ga_sd_005"] / hh
        d["p_50"] = p50
        d["p_apt"] = d[S + "ho_gb_003"] / ho
        d["p_other"] = d[S + "ho_gb_006"] / dwell
        # 테마 A
        d["solo50"] = d.p_1in * p50
        d["old"] = p65
        d["oldho"] = (d[S + "ho_yr_001"] + d[S + "ho_yr_002"]) / ho * nonapt
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
        d["score"] = d[[f"theme_{t}_pct" for t in themes]].mean(axis=1)
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
        rental = (
            (d.p_1in >= RENTAL_SIG["p_1in"])
            & (d.old >= RENTAL_SIG["old"])
            & (d.p_apt >= RENTAL_SIG["p_apt"])
        )
        d["type_label"] = np.select(
            [d.hold, rental, topA & topB, topA, topB],
            ["보류", "고령 임대단지형", "복합형", "고령 독거형", "중장년 독거형"],
            "일반",
        )
        d.loc[d.mixed & ~d.hold, "type_label"] += "(혼합지)"
        return d

    base = build()
    print(
        "포함",
        len(base),
        "| 보류",
        base.hold.sum(),
        base.hold_reason[base.hold].value_counts().to_dict(),
        "| 혼합지",
        base.mixed.sum(),
    )

    print("[지역 × 등급, 0 = 보류]")
    print(pd.crosstab(base.REGION, base.grade))
    print("[지역 × 유형]")
    print(pd.crosstab(base.REGION, base.type_label))
    print("[테마 상위 20% 겹침]")
    print(
        pd.crosstab(
            base.theme_A_pct >= 80, base.theme_B_pct >= 80, rownames=["A상위"], colnames=["B상위"]
        )
    )
    print(
        "테마 A·B 점수 Spearman:",
        round(
            base[~base.hold].theme_A_score.corr(base[~base.hold].theme_B_score, method="spearman"),
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

    ok = ~base.hold
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
    strcols = {"REGION", "ADM_CD", "type_label", "hold", "hold_reason", "mixed"}
    types = ['"String"'] + [
        '"String"' if c in strcols else '"Integer"' if c == "grade" else '"Real"' for c in cols
    ]
    OUT_TYPES.write_text(",".join(types) + "\n", encoding="utf-8")
    print("saved:", OUT.relative_to(ROOT), "| rows/columns:", len(out), len(cols) + 1)

    # 원본 35개 열의 설명을 공통 공유 규칙에 맞춰 함께 저장한다.
    column_info = {
        "TOT_OA_CD": ("SGIS 집계구 코드", "string", "14자리 문자열"),
        "REGION": ("지역 이름; 현재 제공 결과는 강남구·춘천시", "string", "시군구 구분"),
        "ADM_CD": ("SGIS 행정동 코드; 행안부 코드와 구분", "string", "8자리 문자열"),
        "pop_total": ("총인구", "number", "명"),
        "hh_total": ("일반가구 수; 행정동 집계 가중치 후보", "number", "가구"),
        "hh_single": ("1인가구 수", "number", "가구"),
        "score": ("보류 제외 테마 백분위의 평균", "number", "0~100"),
        "pctile": ("종합 점수의 지역 내 백분위", "number", "0 초과 100 이하; 보류는 결측"),
        "grade": ("지역 내 상대 등급; 0은 보류", "integer", "0 또는 1~5"),
        "type_label": (
            "원본 v3의 복합 유형 라벨; 임대단지형은 확인 전 후보",
            "string",
            "보류/일반/고령 독거형/중장년 독거형/복합형/고령 임대단지형; 혼합지 접미 가능",
        ),
        "hold": ("종사자비 또는 인구/가구 비율 기준의 보류 여부", "boolean", "True/False"),
        "hold_reason": (
            "원본 v3 보류 사유; 두 조건 동시 충족 시 업무지 우선",
            "string",
            "업무지/집단가구; 비보류는 공란",
        ),
        "mixed": ("비보류 중 종사자/거주자 > WORK_MIXED", "boolean", "True/False"),
        "work_ratio": ("종사자 수 / 총인구", "number", "배"),
        "pop_per_hh": ("총인구 / 일반가구 수", "number", "명/가구"),
        "p_1in": ("1인가구 수 / 일반가구 수", "number", "비율"),
        "p_50": ("50~64세 비율과 역산 65세 이상 비율의 합", "number", "추정 비율"),
        "p_apt": ("아파트 수 / 총주택 수", "number", "비율"),
        "p_other": ("주택이외 거처 / 총거처", "number", "비율"),
        "solo50": (
            "1인가구율 × 50세 이상 비율; 교차 가구수 직접 관측 아님",
            "number",
            "지역 대리지표",
        ),
        "old": ("노년부양비·노령화지수로 역산한 65세 이상 비율", "number", "추정 비율"),
        "oldho": (
            "1989년 이전 주택 비율 × 비아파트 비율; 실제 교차 주택수 아님",
            "number",
            "지역 대리지표",
        ),
        "male_solo": (
            "50~64세 남성 비율 × 1인가구율; 실제 남성 독거 교차 인구 아님",
            "number",
            "지역 대리지표",
        ),
        "housv": (
            "비주거용 건물내 주택과 20m2 이하 주택 합 / 총거처",
            "number",
            "비율; 분자 중복 가능",
        ),
        "other50": (
            "주택이외 거처 비율 × 50세 이상 비율; 고시원 직접 관측 아님",
            "number",
            "지역 대리지표",
        ),
    }
    for theme in THEMES:
        column_info[f"theme_{theme}_score"] = (
            f"테마 {theme}의 차원별 z 평균",
            "number",
            "표준화 점수",
        )
        column_info[f"theme_{theme}_pct"] = (
            f"보류를 제외한 테마 {theme} 지역 내 백분위",
            "number",
            "0 초과 100 이하; 보류는 결측",
        )
    for dim in DIMS:
        column_info[f"z_{dim}"] = (
            f"{dim} 지역 내 표준화 후 절단; 표준화에는 보류 행도 포함",
            "number",
            f"-{CLIP_Z}~{CLIP_Z}",
        )
    dictionary_rows = []
    for name in ["TOT_OA_CD", *cols]:
        description, data_type, unit = column_info[name]
        missing = "원본 v3의 결측 대치·필터 이후 값; 계산 불가 결측을 위험 없음으로 해석하지 않음"
        if name in {"theme_A_pct", "theme_B_pct", "score", "pctile"}:
            missing = "보류 행 또는 계산 불가; 0점·안전과 구분"
        elif name == "hold_reason":
            missing = "비보류이면 공란; hold와 함께 읽음"
        dictionary_rows.append(
            {
                "COLUMN_NAME": name,
                "DESCRIPTION": description,
                "DATA_TYPE": data_type,
                "UNIT_OR_RANGE": unit,
                "MISSING_MEANING": missing,
            }
        )
    pd.DataFrame(dictionary_rows).to_csv(OUT_DICTIONARY, index=False, encoding="utf-8-sig")
    print("QGIS types:", OUT_TYPES.relative_to(ROOT))
    print("dictionary:", OUT_DICTIONARY.relative_to(ROOT))


if __name__ == "__main__":
    main()
