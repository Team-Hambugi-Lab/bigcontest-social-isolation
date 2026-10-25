"""청년 고립 위험 특징의 근거 수치를 모아 risk_features_youth.csv로 저장한다.

- 보건복지부 실태조사(2023): 특징별 "해당" 비율을 은둔·고립 집단별로 집계한다(비교 집단 없음).
- 서울시 실태조사(2022): 집계표에서 고립·은둔과 전체 청년의 비율을 읽어 비교한다.
- 필요 지원·도움받지 않은 이유 분포(mohw_survey.build_support_tables)를 같은 파일에 합친다.
"해당" 기준은 외부 절단점이 없는 설계자 판단이다(PHQ-9 10점만 예외).
"""

import pandas as pd

from src.data.paths import INTERIM_DIR
from src.features import mohw_survey, seoul_survey

MOHW_SOURCE = "보건복지부 2023"
SEOUL_SOURCE = "서울시 2022"
SEOUL_GROUP, SEOUL_COMPARE = "고립은둔", "전체"
LOW_FREQ = [1, 2, 3]  # 한 달에 한 번 / 2-3주에 한 번 / 일주일에 한 번
OFTEN = [3, 4]  # 자주 그렇다 / 항상 그렇다
CIRCULAR_NOTE = "서울시 고립·은둔 판정 기준 문항이라 근거 아님"

# (특징 코드, 이름, 기준 설명, 결합 방식, {문항: 해당 보기})
# all: 모든 문항이 해당, any: 하나라도 해당. 분모는 all이면 모두 응답, any면 하나라도 응답.
MOHW_FEATURES = [
    ("REL_NO_CONFIDANT", "속마음 털어놓을 사람 없음", "가족·친구·그 외 모두 없다", "all",
     {"q153a1": [2], "q153a2": [2], "q153a3": [2]}),
    ("REL_NO_ADVICE", "조언 구할 사람 없음", "가족·친구·그 외 모두 없다", "all",
     {"q151a1": [2], "q151a2": [2], "q151a3": [2]}),
    ("REL_FAMILY_CONFLICT", "가족 관계 악화", "가족 관계 나쁨 이하 또는 은둔 갈등 심함", "any",
     {"q16a1": [4, 5], "q16a2": [4, 5], "q16a3": [4, 5], "q16a4": [4, 5], "q16a5": [4, 5],
      "q17": [4]}),
    ("REL_NO_FAMILY", "가족 없음", "가족이 없다", "any", {"q166": [1]}),
    ("REL_LONELY", "외로움", "지난 7일 외로움 자주 이상", "any", {"q131": OFTEN}),
    ("OUT_LONG_DURATION", "장기 은둔·고립", "은둔·고립 기간 1년 이상", "any", {"q4": [4, 5, 6, 7]}),
    ("OUT_NO_ACTIVITY", "무위 생활", "주 활동 1순위가 잠 또는 특별히 하는 것 없음", "any",
     {"q51": [7, 8]}),
    ("SOLO_LIVING", "1인 가구", "혼자 생활", "any", {"hq97": [7]}),
    ("SOLO_MEAL", "혼밥", "직접 차리거나 배달해 혼자 먹음", "any", {"q7": [1, 2]}),
    ("BODY_POOR_HEALTH", "신체 건강 나쁨·장애", "신체건강 안 좋음 이하 또는 장애 있음", "any",
     {"q11": [1, 2], "hq5": [2, 3, 4]}),
    ("BODY_HYGIENE", "위생 관리 어려움", "옷·목욕·세수 중 하나라도 일주일에 한 번 이하", "any",
     {"q81": LOW_FREQ, "q82": LOW_FREQ, "q83": LOW_FREQ}),
    ("BODY_HOME_CARE", "생활공간 관리 어려움", "방 정리 2-3주에 한 번 이하", "any",
     {"q84": [1, 2]}),
    ("BODY_SLEEP", "수면 문제", "밤낮 바뀜 그렇다 이상 또는 수면 4시간 미만·12시간 이상", "any",
     {"q91": [3, 4], "q10": [1, 4]}),
    ("MIND_POOR_MENTAL", "정신건강 나쁨", "정신건강 안 좋음 이하 또는 정신과 진단·투약", "any",
     {"q12": [1, 2], "hq6": [2, 3, 4]}),
    ("MIND_HOPELESS", "절망감", "희망 없음·절망 중 하나라도 자주 이상", "any",
     {"q135": OFTEN, "q136": OFTEN}),
    ("MIND_SOCIAL_ANXIETY", "대인 불안", "대인 두려움·불안·평가 걱정 중 하나라도 자주 이상", "any",
     {"q132": OFTEN, "q133": OFTEN, "q134": OFTEN}),
    ("MIND_SUICIDE_IDEA", "최근 자살·자해 생각", "죽고 싶다고 생각한 적 있음(평생)", "any", {"q14": [1]}),
    # q14a1은 q14=1에게만 물으므로 q14(해당 보기 없음)를 넣어 분모를 q14 응답자로 둔다.
    ("MIND_SUICIDE_ATTEMPT", "최근 자살 시도·자해 행동", "자살을 시도한 적 있음(평생)", "any",
     {"q14a1": [1], "q14": []}),
    ("ECON_NO_INCOME", "소득 활동 없음", "지난주 돈 버는 일 안 함", "any", {"hq10": [2]}),
    ("ECON_LOW_STATUS", "낮은 경제 수준", "가정 또는 본인 사회경제적 수준 하", "any",
     {"hq11": [3], "hq12": [3]}),
    ("HOUSE_UNSTABLE", "주거 불안정", "고시원 거주 또는 보증금 없는 월세", "any",
     {"hq7": [5], "hq8": [4]}),
]  # fmt: skip

PHQ9_CUTOFF = 10
PHQ9_ROWS = [f"{score}.00" for score in range(PHQ9_CUTOFF, 28)]
A7_HOME_ROWS = [
    "보통은 집에 있지만, 자신의 취미생활만을 위해 외출한다",
    "보통은 집에 있지만, 인근 편의점 등에 외출한다",
    "자기 방에서 나오지만, 집 밖으로는 나가지 않는다",
    "자기 방에서 거의 나오지 않는다",
]
LOW_FREQ_ROWS = ["한 달에한 번", "2~3주에한 번", "일주일에한 번"]

# (특징 코드, 서울시 표 코드, 해당 보기 행, 비고)
# REL_LOW_CONTACT는 고령·중장년 제안 코드라 청년 사전 행은 없고, 병합 사전(risk_feature_dictionary)이 쓴다.
SEOUL_EVIDENCE = [
    ("REL_NO_CONFIDANT", "A12_4_1 TO A12_4_4", ["없음"], CIRCULAR_NOTE),
    ("REL_LOW_CONTACT", "A11", ["0회"], "판정 기준 밖 문항(2주간 교류 0회), 문항 응답자 기준"),
    ("REL_NO_ADVICE", "A12_1_1 TO A12_1_4", ["없음"], CIRCULAR_NOTE),
    ("REL_FAMILY_CONFLICT", "B1_1", ["Bottom2(①+②)"], "가족 친밀도 문항(보건복지부 문항과 다름)"),
    ("OUT_LONG_DURATION", "A7", A7_HOME_ROWS, CIRCULAR_NOTE),
    ("OUT_NO_ACTIVITY", "B5_1", ["잠", "아무것도 하지 않는다"], ""),
    ("SOLO_LIVING", "SQ6_R", ["1명"], "서울연구원 로짓에서는 반대 방향(오즈비 0.625)"),
    ("SOLO_MEAL", "B8", ["혼자서 직접 차려 먹는다", "혼자서 배달시켜 먹는다",
                        "가족이 식탁에 차려 놓으면 혼자 먹는다",
                        "가족이 식사를 차려서 방 앞에 두거나 방에 넣어 준다"], ""),
    ("BODY_POOR_HEALTH", "B10", ["Bottom2(①+②)"], ""),
    ("BODY_HYGIENE", "B9_1", LOW_FREQ_ROWS, "문항별 비율(하나라도 해당 비율은 집계표로 계산 불가)"),
    ("BODY_HYGIENE", "B9_2", LOW_FREQ_ROWS, "문항별 비율"),
    ("BODY_HYGIENE", "B9_3", LOW_FREQ_ROWS, "문항별 비율, 전체 청년이 더 높음(반대 방향)"),
    ("BODY_HOME_CARE", "B9_4", LOW_FREQ_ROWS[:2], ""),
    ("BODY_SLEEP", "B1_3", ["Top2(④+⑤)"], ""),
    ("MIND_POOR_MENTAL", "B12_1 TO B12_9", PHQ9_ROWS, "PHQ-9 총점 10점 이상(외부 절단점)"),
    ("MIND_POOR_MENTAL", "B11", ["예"], "약물 복용"),
    ("MIND_SUICIDE_IDEA", "B12_9", ["2, 3일 이상", "7일 이상", "거의 매일"],
     "지난 2주 기준(보건복지부 q14는 평생)"),
    ("ECON_NO_INCOME", "A1", ["일을 하지 않았다."], ""),
    ("ECON_LOW_STATUS", "A5", ["하"], "가정의 주관적 수준"),
    ("HOUSE_UNSTABLE", "DQ5", ["준주거시설(고시원)"], ""),
    ("HOUSE_UNSTABLE", "DQ6", ["보증금 없는 월세"], ""),
]  # fmt: skip

CRISIS_FEATURES = {"MIND_SUICIDE_IDEA", "MIND_SUICIDE_ATTEMPT"}
DEFINITIONS = {
    "REL_NO_CONFIDANT": "낙심하거나 우울할 때 속마음을 털어놓을 사람이 없다",
    "REL_NO_ADVICE": "중요하거나 어려운 일이 있을 때 조언을 구할 사람이 없다",
    "REL_FAMILY_CONFLICT": "가족과의 관계가 나쁘거나 가족과 갈등이 심하다",
    "REL_NO_FAMILY": "가족이 없다",
    "REL_LONELY": "외로움을 자주 느낀다",
    "OUT_LONG_DURATION": "집 안에 머무는 은둔·고립 생활이 1년 이상 이어졌다",
    "OUT_NO_ACTIVITY": "하루 대부분을 잠이나 특별한 활동 없이 보낸다",
    "SOLO_LIVING": "혼자 산다",
    "SOLO_MEAL": "주로 혼자 식사한다",
    "BODY_POOR_HEALTH": "신체 건강이 나쁘거나 장애가 있다",
    "BODY_HYGIENE": "옷 갈아입기, 목욕, 세수 같은 기본 위생 관리를 거의 하지 못한다",
    "BODY_HOME_CARE": "생활공간(방)을 거의 정리하지 못한다",
    "BODY_SLEEP": "밤낮이 바뀌었거나 수면 시간이 지나치게 짧거나 길다",
    "MIND_POOR_MENTAL": "정신건강이 나쁘거나 정신과 진단·투약 중이다",
    "MIND_HOPELESS": "미래에 대한 희망이 없거나 절망감을 자주 느낀다",
    "MIND_SOCIAL_ANXIETY": "사람을 만나는 것이 두렵거나 불안하다",
    "MIND_SUICIDE_IDEA": "지난 2주 안에 죽고 싶다는 생각이나 자해 생각을 했다",
    "MIND_SUICIDE_ATTEMPT": "지난 2주 안에 자살을 시도했거나 자해 행동을 했다",
    "ECON_NO_INCOME": "돈을 버는 일을 하지 않는다",
    "ECON_LOW_STATUS": "스스로 경제 수준을 낮게 본다",
    "HOUSE_UNSTABLE": "고시원이나 보증금 없는 월세처럼 주거가 불안정하다",
}
NO_DETECT = ("감지 불가", "지역 데이터로 감지할 수 없음, 대화(체크인)로 확인")
# 활동 신호 외부 검증에서 20·30대 활동 저하 신호는 반대 방향이라 고령층(60대 이상)에만 쓴다.
SK_YOUTH_RULE = (
    "활동 신호 외부 검증에서 20·30대 유동 신호는 반대 방향(신호가 많은 동일수록 더 많이 이동)이라 "
    "쓰지 않음, 대화(체크인)로 확인"
)
CARD_DETECT = ("신한카드", "거주지 20·30대 집단의 소비가 낮거나 줄어듦, 강남구·춘천만 해당")
# SGIS 지수 v3.2는 50세 이상 비율을 곱해 청년 오피스텔을 빼므로 청년에게는 지역 신호가 없다.
SGIS_YOUTH_RULE = (
    "v3.2 지수는 50세 이상 가중이라 청년은 지역 신호로 잡히지 않음, 대화(체크인)로 확인"
)
DETECT = {
    "SOLO_LIVING": ("SGIS", SGIS_YOUTH_RULE),
    "HOUSE_UNSTABLE": ("SGIS", SGIS_YOUTH_RULE),
    "OUT_LONG_DURATION": (NO_DETECT[0], SK_YOUTH_RULE),
    "OUT_NO_ACTIVITY": ("SK", SK_YOUTH_RULE),  # 고령 지역 신호로만 쓴다
    "ECON_NO_INCOME": CARD_DETECT,
    "ECON_LOW_STATUS": CARD_DETECT,
}  # fmt: skip
VERY_NEEDED = 4  # 필요 지원 4점 척도의 "매우 필요함"
TOP_SUPPORTS = 3
DICTIONARY_COLUMNS = [
    "FEATURE_CODE", "FEATURE_NAME", "DEFINITION", "AGE_PATTERN", "EVIDENCE_SOURCE",
    "EVIDENCE_VALUE", "DETECT_DATA", "DETECT_RULE", "IS_CRISIS", "INSTITUTION_TAGS",
    "SUPPORT_TYPES", "SUPPORT_NEED_PCT",
]  # fmt: skip

OUTPUT_COLUMNS = [
    "TABLE", "SOURCE", "FEATURE_CODE", "GROUP", "ITEM_CODE", "ITEM_LABEL", "OPTION_CODE",
    "OPTION_LABEL", "RULE", "N", "N_VALID", "PCT", "COMPARE_PCT", "NOTE",
]  # fmt: skip


def feature_hits(df: pd.DataFrame, how: str, rule: dict[str, list]) -> tuple[pd.Series, pd.Series]:
    """특징 해당 여부와 분모(유효 응답) 여부를 행마다 반환한다."""
    cols = list(rule)
    matched = pd.concat({c: df[c].isin(v) for c, v in rule.items()}, axis=1)
    answered = df[cols].notna()
    if how == "all":
        return matched.all(axis=1), answered.all(axis=1)
    return matched.any(axis=1), answered.any(axis=1)


def mohw_feature_table(df: pd.DataFrame, group: str) -> pd.DataFrame:
    """보건복지부 응답에서 특징별 해당 수와 비율을 집계한다."""
    rows = []
    for code, name, rule_text, how, rule in MOHW_FEATURES:
        hit, valid = feature_hits(df, how, rule)
        n, n_valid = int((hit & valid).sum()), int(valid.sum())
        pct = round(n / n_valid * 100, mohw_survey.PCT_DECIMALS) if n_valid else float("nan")
        items = ", ".join(c for c, v in rule.items() if v)
        rows.append(("RISK_FEATURE", MOHW_SOURCE, code, group, items, name, rule_text,
                     n, n_valid, pct))  # fmt: skip
    cols = ["TABLE", "SOURCE", "FEATURE_CODE", "GROUP", "ITEM_CODE", "ITEM_LABEL", "RULE",
            "N", "N_VALID", "PCT"]  # fmt: skip
    return pd.DataFrame(rows, columns=cols)


def seoul_evidence_table(tables: pd.DataFrame) -> pd.DataFrame:
    """서울시 집계표에서 특징별 고립·은둔과 전체 청년의 해당 비율을 읽는다."""
    rows = []
    for code, table_code, labels, note in SEOUL_EVIDENCE:
        block = tables[tables["TABLE_CODE"] == table_code]
        pct = {}
        for group in (SEOUL_GROUP, SEOUL_COMPARE):
            part = block[block["GROUP"] == group]
            missing = set(labels) - set(part["ROW_LABEL"])
            if missing:
                raise KeyError(f"{table_code} {group}: rows not found {sorted(missing)}")
            pct[group] = part.loc[part["ROW_LABEL"].isin(labels), "VALUE"].sum()
        target = block[block["GROUP"] == SEOUL_GROUP].iloc[0]
        rows.append(("RISK_FEATURE", SEOUL_SOURCE, code, SEOUL_GROUP, table_code,
                     target["TABLE_LABEL"], " / ".join(labels), int(target["N_BASE"]),
                     round(pct[SEOUL_GROUP], 1), round(pct[SEOUL_COMPARE], 1), note))  # fmt: skip
    cols = ["TABLE", "SOURCE", "FEATURE_CODE", "GROUP", "ITEM_CODE", "ITEM_LABEL", "RULE",
            "N_VALID", "PCT", "COMPARE_PCT", "NOTE"]  # fmt: skip
    return pd.DataFrame(rows, columns=cols)


def build_risk_features_youth() -> pd.DataFrame:
    """보건복지부 특징 비율, 서울시 비교, 필요 지원 분포를 한 표로 합친다."""
    parts = []
    for group, (data_sheet, _) in mohw_survey.GROUP_SHEETS.items():
        parts.append(mohw_feature_table(mohw_survey.load_survey(data_sheet), group))
    parts.append(seoul_evidence_table(seoul_survey.build_seoul_tables()))
    parts.append(mohw_survey.build_support_tables().assign(SOURCE=MOHW_SOURCE))
    out = pd.concat(parts, ignore_index=True).reindex(columns=OUTPUT_COLUMNS)
    return out.astype({"N": "Int64", "OPTION_CODE": "Int64"})  # 결측이 섞여도 정수로 저장


def feature_supports(df: pd.DataFrame, support_labels: dict[str, str]) -> pd.DataFrame:
    """특징 해당자가 전체 응답자보다 "매우 필요함"을 더 많이 고른 지원 상위 3개를 고른다.

    비율 자체로 고르면 모든 특징에서 경제적 지원이 1위라 특징 간 구별이 없어서, 전체 대비
    차이(%p)로 순위를 매기고 SUPPORT_NEED_PCT에는 해당자의 실제 비율을 적는다.
    """

    def very_needed_pct(part: pd.DataFrame) -> pd.Series:
        """지원 문항별 "매우 필요함" 비율(%)을 구한다."""
        return part.eq(VERY_NEEDED).sum() / part.notna().sum() * 100

    items = list(support_labels)
    base = very_needed_pct(df[items])
    rows = []
    for code, _, _, how, rule in MOHW_FEATURES:
        hit, valid = feature_hits(df, how, rule)
        pct = very_needed_pct(df.loc[hit & valid, items])
        top = pct[(pct - base).sort_values(ascending=False).index[:TOP_SUPPORTS]].round(1)
        rows.append((code, "; ".join(support_labels[i] for i in top.index),
                     "; ".join(f"{v:.1f}" for v in top)))  # fmt: skip
    return pd.DataFrame(rows, columns=["FEATURE_CODE", "SUPPORT_TYPES", "SUPPORT_NEED_PCT"])


def _evidence_text(rows: pd.DataFrame) -> str:
    """특징 하나의 근거 행들을 사람이 읽는 한 문단으로 만든다."""
    parts = []
    mohw = rows[rows["SOURCE"] == MOHW_SOURCE].set_index("GROUP")
    if not mohw.empty:
        parts.append(
            f"{MOHW_SOURCE}: 은둔 {mohw.loc['은둔', 'PCT']:.1f}%, 고립 {mohw.loc['고립', 'PCT']:.1f}% "
            f"해당({mohw['RULE'].iloc[0]}, 설계자 판단 기준)"
        )
    for r in rows[rows["SOURCE"] == SEOUL_SOURCE].itertuples():
        note = f", {r.NOTE}" if isinstance(r.NOTE, str) and r.NOTE else ""
        parts.append(
            f"{SEOUL_SOURCE} {r.ITEM_CODE}: 고립·은둔 {r.PCT:.1f}% 대 전체 청년 "
            f"{r.COMPARE_PCT:.1f}%{note}"
        )
    return " / ".join(parts)


def _source_text(rows: pd.DataFrame) -> str:
    """특징 하나의 근거 출처와 문항을 한 줄로 만든다."""
    return "; ".join(
        f"{source} ({', '.join(dict.fromkeys(g['ITEM_CODE']))})"
        for source, g in rows.groupby("SOURCE", sort=False)
    )


def build_dictionary_youth(evidence: pd.DataFrame, supports: pd.DataFrame) -> pd.DataFrame:
    """근거 표와 특징별 필요 지원으로 위험 특징 사전의 청년 행을 만든다."""
    feats = evidence[evidence["TABLE"] == "RISK_FEATURE"]
    rows = []
    for code, name, _, _, _ in MOHW_FEATURES:
        sub = feats[feats["FEATURE_CODE"] == code]
        detect_data, detect_rule = DETECT.get(code, NO_DETECT)
        rows.append({
            "FEATURE_CODE": code, "FEATURE_NAME": name, "DEFINITION": DEFINITIONS[code],
            "EVIDENCE_SOURCE": _source_text(sub), "EVIDENCE_VALUE": _evidence_text(sub),
            "DETECT_DATA": detect_data, "DETECT_RULE": detect_rule,
            "IS_CRISIS": "Y" if code in CRISIS_FEATURES else "N",
        })  # fmt: skip
    out = pd.DataFrame(rows).merge(supports, on="FEATURE_CODE", how="left")
    return out.reindex(columns=DICTIONARY_COLUMNS)


def main() -> None:
    """risk_features_youth.csv와 risk_feature_dictionary_youth.csv를 data/interim/에 저장한다."""
    evidence = build_risk_features_youth()
    support_labels = (
        evidence[evidence["TABLE"] == "SUPPORT_NEED"]
        .drop_duplicates("ITEM_CODE")
        .set_index("ITEM_CODE")["ITEM_LABEL"]
        .to_dict()
    )
    pooled = pd.concat(
        [mohw_survey.load_survey(s) for s, _ in mohw_survey.GROUP_SHEETS.values()],
        ignore_index=True,
    )
    dictionary = build_dictionary_youth(evidence, feature_supports(pooled, support_labels))
    for name, df in [("risk_features_youth", evidence),
                     ("risk_feature_dictionary_youth", dictionary)]:  # fmt: skip
        out = INTERIM_DIR / f"{name}.csv"
        df.to_csv(out, index=False, encoding="utf-8")
        print(f"saved: {out} {df.shape}")


if __name__ == "__main__":
    main()
