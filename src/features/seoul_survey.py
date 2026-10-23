"""서울시 고립·은둔 청년 실태조사(2022) 집계표(TABLE_ 파일) 읽기.

집계표는 문항마다 `【코드】 문항명` 제목 행, `BASE` 행, `▣ 사례수 ▣` 행, 보기 행(전체 열
비율)이 이어지고 빈 행으로 끝난다. 개인 응답(DATA_ 파일)은 읽지 않는다.
"""

from pathlib import Path
import re
import unicodedata

import openpyxl
import pandas as pd

from src.data.paths import RAW_DIR

SURVEY_DIR = RAW_DIR / "reference_data" / "서울시_고립은둔청년_실태조사"
TABLE_SHEET = "테이블"
TABLE_FILES = {"전체": "TABLE_청년조사_전체", "고립은둔": "TABLE_청년조사_고립은둔"}
TOTAL_HEADER = "▣ 전  체 ▣"
N_ROW_LABEL = "▣ 사례수 ▣"
SUMMARY_PREFIXES = ("▣ 평", "Top2", "Bottom2")  # 합계 행은 버리고 요약 통계 행은 남긴다
OUTPUT_COLUMNS = ["GROUP", "TABLE_CODE", "TABLE_LABEL", "BASE", "N_BASE", "ROW_LABEL", "VALUE"]


def table_file(group: str, survey_dir: Path = SURVEY_DIR) -> Path:
    """집계표 xlsx 경로를 반환한다(NFD 한글 파일명 대응)."""
    prefix = TABLE_FILES[group]
    found = [
        p
        for p in survey_dir.glob("*.xlsx")
        if unicodedata.normalize("NFC", p.name).startswith(prefix + "_v")
    ]
    if len(found) != 1:
        raise FileNotFoundError(f"expected 1 {prefix} xlsx in {survey_dir}, found {len(found)}")
    return found[0]


def _is_blank(row: list) -> bool:
    """행의 모든 칸이 비어 있는지 확인한다."""
    return all(c is None or str(c).strip() == "" for c in row)


def parse_table_rows(rows: list[list], group: str) -> pd.DataFrame:
    """집계표 행 목록을 블록별로 읽어 전체 열 값을 긴 형태로 만든다."""
    out = []
    for i, row in enumerate(rows):
        title = str(row[0]) if row and row[0] is not None else ""
        if not title.startswith("【") or i + 1 >= len(rows):
            continue
        head = rows[i + 1]
        if len(head) < 2 or str(head[1]).strip() != TOTAL_HEADER:
            continue  # 응답자 프로필처럼 열 배치가 다른 블록은 제외한다
        code, label = title[1:].split("】", 1)
        base = str(head[0]).replace("BASE :", "").strip()
        j = i + 2
        while j < len(rows) and str(rows[j][0]).strip() != N_ROW_LABEL:
            j += 1
        n_base = int(re.search(r"\d+", str(rows[j][1])).group())
        k = j + 1
        while k < len(rows) and not _is_blank(rows[k]):
            row_label = str(rows[k][0]).strip()
            if not row_label.startswith("▣ 합"):
                out.append(
                    (group, code.strip(), label.strip(), base, n_base, row_label, rows[k][1])
                )
            k += 1
    df = pd.DataFrame(out, columns=OUTPUT_COLUMNS)
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    return df


def read_table_rows(path: Path) -> list[list]:
    """집계표 xlsx의 테이블 시트를 행 목록으로 읽는다."""
    wb = openpyxl.load_workbook(path, read_only=True)
    return [list(r) for r in wb[TABLE_SHEET].iter_rows(values_only=True)]


def build_seoul_tables() -> pd.DataFrame:
    """전체 청년과 고립·은둔 청년 집계표의 전체 열을 한 표로 합친다."""
    parts = [parse_table_rows(read_table_rows(table_file(g)), g) for g in TABLE_FILES]
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    """seoul_survey_tables.csv를 data/interim/에 저장한다."""
    from src.data.paths import INTERIM_DIR

    out = INTERIM_DIR / "seoul_survey_tables.csv"
    build_seoul_tables().to_csv(out, index=False, encoding="utf-8")
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
