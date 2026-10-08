"""원본 데이터 로딩 단일 관문.

모든 로딩은 이 모듈을 거친다. 인코딩(UTF-8 BOM), 구분자(쉼표),
12월 중복 제거, 숫자형 변환을 한 곳에서 처리해 팀원 간 수치 불일치를 막는다.
"""

import pandas as pd

from src.data.paths import MONTHS, SK_TABLES, card_file, sk_file

SK_PK = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]
ENCODING = "utf-8-sig"
CARD_NUMERIC = ["TS_AT", "USE_CNT"]


def load_sk(table: str, ym: str | None = None, dedupe: bool = True) -> pd.DataFrame:
    """SK 유동인구 테이블을 읽는다.

    ym이 None이면 6개월 전체를 이어 붙인다.
    dedupe=True면 PK 중복을 제거한다. 12월 time·wkdy 파일이 전체 2배 복제 배포됐다.
    """
    if table not in SK_TABLES:
        raise ValueError(f"table must be one of {SK_TABLES}, got {table!r}")

    months = MONTHS if ym is None else (ym,)
    frames = []
    for m in months:
        df = pd.read_csv(
            sk_file(table, m),
            encoding=ENCODING,
            dtype={"STD_YM": str, "BLOCK_CD": str},
        )
        if dedupe:
            df = df.drop_duplicates(subset=SK_PK)
        frames.append(df)

    out = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    return out.reset_index(drop=True)


def sk_value_cols(df: pd.DataFrame) -> list[str]:
    """PK를 제외한 수치 컬럼 목록을 반환한다."""
    return [c for c in df.columns if c not in SK_PK]


def load_card(dataset: int = 2) -> pd.DataFrame:
    """신한카드 집계 데이터를 읽는다.

    TS_AT·USE_CNT를 정수형으로 변환하고 변환 실패가 있으면 예외를 던진다.
    """
    df = pd.read_csv(card_file(dataset), encoding=ENCODING, dtype=str)
    for col in CARD_NUMERIC:
        num = pd.to_numeric(df[col], errors="coerce")
        n_bad = int(num.isnull().sum())
        if n_bad:
            raise ValueError(f"{col} 숫자 변환 실패 {n_bad}건 (dataset={dataset})")
        df[col] = num.astype("int64")
    return df


def dedupe_report() -> pd.DataFrame:
    """18개 SK 파일의 중복 제거 전후 행 수를 표로 반환한다."""
    rows = []
    for table in SK_TABLES:
        for ym in MONTHS:
            raw = load_sk(table, ym, dedupe=False)
            n_raw = len(raw)
            n_dedup = len(raw.drop_duplicates(subset=SK_PK))
            rows.append(
                {
                    "table": table,
                    "ym": ym,
                    "rows_raw": n_raw,
                    "rows_dedup": n_dedup,
                    "dropped": n_raw - n_dedup,
                }
            )
    return pd.DataFrame(rows)
