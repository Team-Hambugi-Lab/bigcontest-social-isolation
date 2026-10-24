"""보건복지부 고립·은둔 청년 실태조사(2023) 코드북 읽기와 응답 정리.

원본 xlsx는 읽기만 한다. 결측은 빈 칸이 아니라 문자열 "."로 들어 있다.
"""

from pathlib import Path
import unicodedata

import numpy as np
import pandas as pd

from src.data.paths import RAW_DIR

SURVEY_DIR = RAW_DIR / "reference_data"
SURVEY_KEYWORD = "보건복지부_고립_은둔_청년_실태조사"
CODEBOOK_COLUMNS = ["var", "qno", "value", "label", "question"]
MISSING_TOKEN = "."


def survey_file(survey_dir: Path = SURVEY_DIR) -> Path:
    """보건복지부 실태조사 xlsx 경로를 반환한다(NFD 한글 파일명 대응)."""
    found = [
        p
        for p in survey_dir.glob("*/*.xlsx")
        if SURVEY_KEYWORD in unicodedata.normalize("NFC", p.name) and not p.name.startswith("~$")
    ]
    if len(found) != 1:
        raise FileNotFoundError(f"expected 1 survey xlsx in {survey_dir}, found {len(found)}")
    return found[0]


def tidy_codebook(raw: pd.DataFrame) -> pd.DataFrame:
    """코드북 시트를 var, qno, value, label, question 긴 형태로 정리한다."""
    df = raw.iloc[:, :5].copy()
    df.columns = CODEBOOK_COLUMNS
    df = df.dropna(how="all")
    df[["var", "qno", "question"]] = df[["var", "qno", "question"]].ffill()
    return df.reset_index(drop=True)


def clean_survey(raw: pd.DataFrame) -> pd.DataFrame:
    """결측 토큰 "."를 NaN으로 바꾸고, 숫자로만 이뤄진 열은 숫자형으로 변환한다."""
    df = raw.replace(MISSING_TOKEN, np.nan)
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() == df[col].notna().sum():
            df[col] = converted
    return df


def read_codebook(sheet: str, path: Path | None = None) -> pd.DataFrame:
    """코드북 시트를 읽어 정리한 표를 반환한다."""
    return tidy_codebook(pd.read_excel(path or survey_file(), sheet_name=sheet))


def load_survey(sheet: str, path: Path | None = None) -> pd.DataFrame:
    """데이터 시트를 읽어 결측과 타입을 정리한 응답 표를 반환한다."""
    return clean_survey(pd.read_excel(path or survey_file(), sheet_name=sheet))


def _value_text(value: object) -> str:
    """보기 값을 문자열로 바꾼다(결측은 빈 문자열, 정수형 실수는 정수로)."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def variable_table(codebook: pd.DataFrame) -> pd.DataFrame:
    """코드북을 변수당 한 행(문항 문구, 보기 개수, 보기 목록)으로 요약한다."""
    return (
        codebook.assign(option=lambda d: d["value"].map(_value_text) + "=" + d["label"].fillna(""))
        .groupby("var", sort=False)
        .agg(
            qno=("qno", "first"),
            question=("question", "first"),
            n_options=("value", "size"),
            options=("option", " / ".join),
        )
        .reset_index()
    )


SUPPORT_ITEMS = [f"q21{i}" for i in range(1, 10)] + ["q2110"]
HELP_BARRIER_ITEM = "q20a1"
GROUP_SHEETS = {"은둔": ("(데이터)은둔", "(코드북)은둔"), "고립": ("(데이터)고립", "(코드북)고립")}
OUTPUT_COLUMNS = [
    "TABLE", "GROUP", "ITEM_CODE", "ITEM_LABEL", "OPTION_CODE", "OPTION_LABEL", "N", "N_VALID", "PCT",
]  # fmt: skip
PCT_DECIMALS = 1


def distribution_table(
    df: pd.DataFrame, group: str, items: list[str], codebook: pd.DataFrame, table: str
) -> pd.DataFrame:
    """문항별 보기 분포(N, 유효 응답 N, 비율)를 문항×보기 긴 형태로 만든다."""
    rows = []
    for item in items:
        options = codebook[codebook["var"] == item]
        item_label = options["question"].iloc[0].split("_", 1)[-1].strip()
        counts = df[item].value_counts()
        n_valid = int(df[item].notna().sum())
        for opt in options.itertuples():
            n = int(counts.get(float(opt.value), 0))
            pct = round(n / n_valid * 100, PCT_DECIMALS) if n_valid else np.nan
            rows.append(
                (table, group, item, item_label, int(opt.value), opt.label, n, n_valid, pct)
            )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def build_support_tables(path: Path | None = None) -> pd.DataFrame:
    """은둔·고립별 필요 지원과 도움받지 않은 이유의 분포를 한 표로 만든다."""
    parts = []
    for group, (data_sheet, codebook_sheet) in GROUP_SHEETS.items():
        df = load_survey(data_sheet, path)
        codebook = read_codebook(codebook_sheet, path)
        parts.append(distribution_table(df, group, SUPPORT_ITEMS, codebook, "SUPPORT_NEED"))
        parts.append(distribution_table(df, group, [HELP_BARRIER_ITEM], codebook, "HELP_BARRIER"))
    return pd.concat(parts, ignore_index=True)
