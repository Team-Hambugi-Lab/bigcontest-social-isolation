"""청년(A-1)과 고령·중장년(A-2) 작업본을 합쳐 위험 특징 사전 risk_feature_dictionary.csv를 만든다.

- 행은 청년 사전의 21개 특징 코드와 10/22에 채택한 A-2 제안 코드 3개다.
  연령별 차이는 범주를 나누지 않고 AGE_PATTERN에 적는다.
- 코드·이름·정의·감지 데이터·위기 여부·필요 지원은 10/20에 확정한 청년 사전을 따른다.
  SUPPORT_NEED_PCT가 실태조사 "매우 필요함" 비율이라 고령 쪽(비율 없음)은 넣지 않는다.
- 근거 출처·수치·감지 방법은 연령대별로 이어 붙인다.
- 제안 코드의 이름·정의는 A-2 값을 쓰고, 청년 근거는 서울시 집계표에 있는 것만 붙인다.
  보건복지부 문항이 없어 SUPPORT_TYPES·SUPPORT_NEED_PCT는 비운다.
- INSTITUTION_TAGS는 #18의 세부 특징 매핑에서 채운다.
"""

import argparse
import re
from pathlib import Path

import pandas as pd

from src.data.paths import INTERIM_DIR, PROCESSED_DIR
from src.features import risk_features_youth as rf
from src.features.institutions import TYPE_RULES

YOUTH_LABEL, SENIOR_LABEL = "청년", "고령·중장년"
NO_SENIOR = "A-2 근거 없음"
NO_YOUTH = "청년 실태조사 근거 없음"
PROPOSED_PATTERN = "A-2 제안 코드(10/22 채택), 고령 근거: {}"
CONCAT_COLUMNS = ["EVIDENCE_SOURCE", "EVIDENCE_VALUE", "DETECT_RULE"]
CRISIS_FLAG = {1: "Y", 0: "N"}  # A-2는 IS_CRISIS를 0/1로 적었다
SOURCE_REF = re.compile(r"S\d+ pp?\.\S+")  # A-2 근거 문장의 "S1 p.14(PDF18)" 같은 출처
# SGIS 지수 v3.2(#24)에서 이 특징에 쓰는 지표. 고령·중장년 감지 방법 끝에 붙인다.
INDEX_RULES = {
    "SOLO_LIVING": "지역 지수 v3.2(#24): 테마 A solo50(1인가구율×50세+ 비율), 테마 B male_solo"
    "(50-64세 남성 비율×1인가구율) 백분위가 높음",
    "HOUSE_UNSTABLE": "지역 지수 v3.2(#24): 테마 B housv(비주거용 건물 내 주택·20㎡ 이하 비율), "
    "other50(주택 이외 거처 비율×50세+ 비율, 고시원 대리) 백분위가 높음",
}


def _labeled(youth: str, senior: str | None) -> str:
    """청년·고령 문장을 연령대 표시를 붙여 한 칸에 잇는다."""
    text = f"[{YOUTH_LABEL}] {youth}"
    return text if senior is None else f"{text} [{SENIOR_LABEL}] {senior}"


def youth_rates(evidence: pd.DataFrame) -> pd.Series:
    """청년 근거 표에서 특징별 보건복지부 해당 비율 문장을 만든다."""
    feats = evidence[(evidence["TABLE"] == "RISK_FEATURE") & (evidence["SOURCE"] == rf.MOHW_SOURCE)]
    pct = feats.pivot(index="FEATURE_CODE", columns="GROUP", values="PCT")
    return (
        "고립·은둔 청년 중 은둔 "
        + pct["은둔"].map("{:.1f}%".format)
        + "·고립 "
        + pct["고립"].map("{:.1f}%".format)
        + " 해당(보건복지부 2023)"
    )


def proposed_rows(proposed: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    """채택한 A-2 제안 코드를 사전 행으로 만든다. 청년 근거는 근거 표에 있으면 붙인다."""
    feats = evidence[evidence["TABLE"] == "RISK_FEATURE"]
    rows = []
    for p in proposed.to_dict("records"):
        sub = feats[feats["FEATURE_CODE"] == p["FEATURE_CODE"]]
        youth_value = rf._evidence_text(sub) if not sub.empty else NO_YOUTH
        rows.append({
            "FEATURE_CODE": p["FEATURE_CODE"], "FEATURE_NAME": p["FEATURE_NAME"],
            "DEFINITION": p["DEFINITION"],
            "AGE_PATTERN": _labeled(youth_value, PROPOSED_PATTERN.format(p["EVIDENCE"])),
            "EVIDENCE_SOURCE": _labeled(
                rf._source_text(sub) if not sub.empty else NO_YOUTH,
                "; ".join(SOURCE_REF.findall(p["EVIDENCE"])),
            ),
            "EVIDENCE_VALUE": _labeled(youth_value, p["EVIDENCE"]),
            "DETECT_DATA": rf.NO_DETECT[0],
            "DETECT_RULE": _labeled(rf.NO_DETECT[1], p["DETECT_RULE"]),
            "IS_CRISIS": "N",
        })  # fmt: skip
    return pd.DataFrame(rows)


def _insert_by_category(base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """추가 행을 같은 범주(코드 앞부분)의 마지막 행 뒤에 넣는다."""
    category = base["FEATURE_CODE"].str.split("_").str[0]
    order = {c: i for i, c in enumerate(dict.fromkeys(category))}
    both = pd.concat([base, extra], ignore_index=True)
    key = both["FEATURE_CODE"].str.split("_").str[0].map(order)
    if key.isna().any():
        raise KeyError(f"unknown category: {both.loc[key.isna(), 'FEATURE_CODE'].tolist()}")
    return both.assign(_key=key).sort_values("_key", kind="stable").drop(columns="_key")


def merge_dictionary(
    youth: pd.DataFrame, senior: pd.DataFrame, rates: pd.Series, extra: pd.DataFrame
) -> tuple[pd.DataFrame, list[str]]:
    """청년 사전에 고령 행과 제안 코드 행을 합치고, 두 작업본이 엇갈린 항목을 함께 반환한다."""
    unknown = sorted(set(senior["FEATURE_CODE"]) - set(youth["FEATURE_CODE"]))
    if unknown:
        raise KeyError(f"senior codes not in youth dictionary: {unknown}")
    dup = sorted(set(extra["FEATURE_CODE"]) & set(youth["FEATURE_CODE"]))
    if dup:
        raise KeyError(f"proposed codes already in youth dictionary: {dup}")
    s = senior.set_index("FEATURE_CODE")
    crisis = s["IS_CRISIS"].map(CRISIS_FLAG)
    if crisis.isna().any():
        raise ValueError(f"unexpected IS_CRISIS values: {s['IS_CRISIS'].unique().tolist()}")

    conflicts = []
    rows = []
    for row in youth.to_dict("records"):
        code = row["FEATURE_CODE"]
        has_senior = code in s.index
        sr = s.loc[code] if has_senior else None
        if has_senior:
            if crisis[code] != row["IS_CRISIS"]:
                raise ValueError(
                    f"{code}: IS_CRISIS youth={row['IS_CRISIS']} senior={crisis[code]}"
                )
            for col in ("FEATURE_NAME", "DETECT_DATA"):
                if sr[col] != row[col]:
                    conflicts.append(
                        f"{code} {col}: 청년 '{row[col]}' / 고령 '{sr[col]}' -> 청년 값"
                    )
        row["AGE_PATTERN"] = _labeled(rates[code], sr["AGE_PATTERN"] if has_senior else NO_SENIOR)
        for col in CONCAT_COLUMNS:
            row[col] = _labeled(row[col], sr[col] if has_senior else None)
        if code in INDEX_RULES:
            senior_rule = f"{sr['DETECT_RULE']} " if has_senior else ""
            row["DETECT_RULE"] = _labeled(rf.DETECT[code][1], senior_rule + INDEX_RULES[code])
        row["INSTITUTION_TAGS"] = pd.NA
        rows.append(row)
    merged = _insert_by_category(pd.DataFrame(rows), extra)
    return merged.reindex(columns=rf.DICTIONARY_COLUMNS).reset_index(drop=True), conflicts


def apply_institution_tags(risk: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """검증된 긴 형태 매핑에서 특징별 후보 태그 요약을 채운다."""
    required = {"FEATURE_CODE", "TAG", "PRIORITY", "NOTE"}
    if not required <= set(mapping.columns):
        raise ValueError(f"매핑에 필요한 열 누락: {sorted(required - set(mapping.columns))}")
    if mapping[list(required)].isna().any().any() or not mapping["NOTE"].str.strip().all():
        raise ValueError("매핑에 빈 코드·태그·우선순위·근거가 있음")
    if mapping.duplicated(["FEATURE_CODE", "TAG"]).any():
        raise ValueError("특징·태그 중복 연결")
    codes = set(risk["FEATURE_CODE"])
    mapped = set(mapping["FEATURE_CODE"])
    if (
        codes != mapped
        or risk["FEATURE_CODE"].isna().any()
        or risk["FEATURE_CODE"].duplicated().any()
    ):
        raise ValueError(
            f"매핑 코드 불일치: 누락={sorted(codes - mapped)}, 미등록={sorted(mapped - codes)}"
        )
    tags = {tag for value, _ in TYPE_RULES.values() for tag in value.split(";")}
    if unknown := set(mapping["TAG"]) - tags:
        raise ValueError(f"미등록 서비스 태그: {sorted(unknown)}")
    for code, rows in mapping.groupby("FEATURE_CODE"):
        if sorted(rows["PRIORITY"].tolist()) != list(range(1, len(rows) + 1)):
            raise ValueError(f"{code}: 잘못된 우선순위")
    ordered = mapping.sort_values(["FEATURE_CODE", "PRIORITY"])
    for code in risk.loc[risk["IS_CRISIS"].eq("Y"), "FEATURE_CODE"]:
        if ordered.loc[ordered["FEATURE_CODE"].eq(code), "TAG"].iloc[0] != "CRISIS_LINE":
            raise ValueError(f"{code}: 위기 이관 태그가 1순위가 아님")
    summary = ordered.groupby("FEATURE_CODE", sort=False)["TAG"].agg(";".join)
    result = risk.copy()
    result["INSTITUTION_TAGS"] = result["FEATURE_CODE"].map(summary)
    return result


def main(argv: list[str] | None = None) -> None:
    """data/interim/의 두 작업본을 합쳐 data/processed/risk_feature_dictionary.csv로 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-path", default=str(PROCESSED_DIR / "feature_tag_mapping.csv"))
    parser.add_argument("--out-dir", default=str(PROCESSED_DIR))
    args = parser.parse_args(argv)
    youth = pd.read_csv(INTERIM_DIR / "risk_feature_dictionary_youth.csv")
    senior = pd.read_csv(INTERIM_DIR / "risk_features_senior.csv", encoding="utf-8-sig")
    proposed = pd.read_csv(INTERIM_DIR / "proposed_senior_features.csv", encoding="utf-8-sig")
    evidence = pd.read_csv(INTERIM_DIR / "risk_features_youth.csv")
    extra = proposed_rows(proposed, evidence)
    merged, conflicts = merge_dictionary(youth, senior, youth_rates(evidence), extra)
    merged = apply_institution_tags(merged, pd.read_csv(args.mapping_path))
    dictionary_path = PROCESSED_DIR / "risk_feature_dictionary_dictionary.csv"
    description = pd.read_csv(dictionary_path)
    tag_row = description["COLUMN"].eq("INSTITUTION_TAGS")
    if tag_row.sum() != 1:
        raise ValueError("위험 특징 열 정의서에 INSTITUTION_TAGS가 정확히 한 번 있어야 함")
    description.loc[tag_row, "DESCRIPTION"] = (
        "특징별 후보 서비스 태그(; 구분, PRIORITY 순). 추천 확정·이용 자격 아님"
    )
    description.loc[tag_row, "MISSING"] = "24개 특징 모두 연결. 결측이면 매핑 오류"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "risk_feature_dictionary.csv"
    merged.to_csv(out, index=False, encoding="utf-8")
    description.to_csv(out_dir / dictionary_path.name, index=False, encoding="utf-8")
    print(f"saved: {out} {merged.shape}")
    for c in conflicts:
        print(f"conflict: {c}")


if __name__ == "__main__":
    main()
