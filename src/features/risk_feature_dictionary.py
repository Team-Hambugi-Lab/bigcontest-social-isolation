"""청년(A-1)과 고령·중장년(A-2) 작업본을 합쳐 위험 특징 사전 risk_feature_dictionary.csv를 만든다.

- 행은 청년 사전의 21개 특징 코드다. 연령별 차이는 범주를 나누지 않고 AGE_PATTERN에 적는다.
- 코드·이름·정의·감지 데이터·위기 여부·필요 지원은 10/20에 확정한 청년 사전을 따른다.
  SUPPORT_NEED_PCT가 실태조사 "매우 필요함" 비율이라 고령 쪽(비율 없음)은 넣지 않는다.
- 근거 출처·수치·감지 방법은 연령대별로 이어 붙인다.
- INSTITUTION_TAGS는 #18에서 채운다(A-2 태그 후보는 feature_tag_mapping_a2_draft.csv).
- A-2 신규 코드 후보(proposed_senior_features.csv)는 팀 합의 전이라 넣지 않는다.
"""

import pandas as pd

from src.data.paths import INTERIM_DIR, PROCESSED_DIR
from src.features.risk_features_youth import DICTIONARY_COLUMNS, MOHW_SOURCE

YOUTH_LABEL, SENIOR_LABEL = "청년", "고령·중장년"
NO_SENIOR = "A-2 근거 없음"
CONCAT_COLUMNS = ["EVIDENCE_SOURCE", "EVIDENCE_VALUE", "DETECT_RULE"]
CRISIS_FLAG = {1: "Y", 0: "N"}  # A-2는 IS_CRISIS를 0/1로 적었다


def _labeled(youth: str, senior: str | None) -> str:
    """청년·고령 문장을 연령대 표시를 붙여 한 칸에 잇는다."""
    text = f"[{YOUTH_LABEL}] {youth}"
    return text if senior is None else f"{text} [{SENIOR_LABEL}] {senior}"


def youth_rates(evidence: pd.DataFrame) -> pd.Series:
    """청년 근거 표에서 특징별 보건복지부 해당 비율 문장을 만든다."""
    feats = evidence[(evidence["TABLE"] == "RISK_FEATURE") & (evidence["SOURCE"] == MOHW_SOURCE)]
    pct = feats.pivot(index="FEATURE_CODE", columns="GROUP", values="PCT")
    return (
        "고립·은둔 청년 중 은둔 "
        + pct["은둔"].map("{:.1f}%".format)
        + "·고립 "
        + pct["고립"].map("{:.1f}%".format)
        + " 해당(보건복지부 2023)"
    )


def merge_dictionary(
    youth: pd.DataFrame, senior: pd.DataFrame, rates: pd.Series
) -> tuple[pd.DataFrame, list[str]]:
    """청년 사전에 고령 행을 합치고, 두 작업본이 엇갈린 항목을 함께 반환한다."""
    unknown = sorted(set(senior["FEATURE_CODE"]) - set(youth["FEATURE_CODE"]))
    if unknown:
        raise KeyError(f"senior codes not in youth dictionary: {unknown}")
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
        row["INSTITUTION_TAGS"] = pd.NA
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=DICTIONARY_COLUMNS), conflicts


def main() -> None:
    """data/interim/의 두 작업본을 합쳐 data/processed/risk_feature_dictionary.csv로 저장한다."""
    youth = pd.read_csv(INTERIM_DIR / "risk_feature_dictionary_youth.csv")
    senior = pd.read_csv(INTERIM_DIR / "risk_features_senior.csv", encoding="utf-8-sig")
    evidence = pd.read_csv(INTERIM_DIR / "risk_features_youth.csv")
    merged, conflicts = merge_dictionary(youth, senior, youth_rates(evidence))
    out = PROCESSED_DIR / "risk_feature_dictionary.csv"
    merged.to_csv(out, index=False, encoding="utf-8")
    print(f"saved: {out} {merged.shape}")
    for c in conflicts:
        print(f"conflict: {c}")


if __name__ == "__main__":
    main()
