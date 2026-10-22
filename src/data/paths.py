"""원본 데이터 경로 상수와 NFD 안전 파일 탐색.

OneDrive가 한글 폴더·파일명을 NFD(자모 분리)로 저장하므로 문자열 리터럴로
경로를 만들면 FileNotFoundError가 난다. 한글이 섞인 경로는 glob으로만 찾는다.
"""

import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SK_DIR = RAW_DIR / "sk_telecom"
CARD_DIR = RAW_DIR / "shinhan_card"
REFERENCE_DIR = RAW_DIR / "reference_data"
INTEREST_GROUP_SUFFIX = "10개_관심집단수.xlsx"
SGIS_DONG_DBF_NAME = "bnd_dong_00_2025_2Q.dbf"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

MASTER_FILE_NAMES = {
    "master": "master_sgis2024.csv",
    "status": "sgis2024_value_status.csv",
    "dictionary": "sgis2024_variable_dictionary.csv",
}

SK_TABLES = ("age", "time", "wkdy")
MONTHS = ("202507", "202508", "202509", "202510", "202511", "202512")


def sk_file(table: str, ym: str) -> Path:
    """SK 유동인구 CSV 경로를 반환한다."""
    if table not in SK_TABLES:
        raise ValueError(f"table must be one of {SK_TABLES}, got {table!r}")
    if ym not in MONTHS:
        raise ValueError(f"ym must be one of {MONTHS}, got {ym!r}")
    return SK_DIR / f"flow_{table}_pop_{ym}.csv"


def card_file(dataset: int) -> Path:
    """신한카드 CSV 경로를 반환한다.

    파일명이 NFD 한글이라 이름 비교가 불안정하다. 크기로 구분한다.
    데이터1은 약 73MB, 데이터2는 약 128MB로 차이가 크다.
    """
    if dataset not in (1, 2):
        raise ValueError(f"dataset must be 1 or 2, got {dataset!r}")
    candidates = sorted(CARD_DIR.glob("*.csv"), key=lambda p: p.stat().st_size)
    if len(candidates) != 2:
        raise FileNotFoundError(f"expected 2 card CSVs in {CARD_DIR}, found {len(candidates)}")
    return candidates[0] if dataset == 1 else candidates[1]


def interest_group_files(reference_dir: Path = REFERENCE_DIR) -> list[Path]:
    """서울 10개 관심집단수 월별 xlsx 6개를 기준월 순으로 반환한다.

    폴더·파일명이 한글이라 NFD일 수 있어 NFC로 정규화한 이름으로 고른다.
    파일명 앞 7자(`2025.07`)가 ASCII라 이름순 정렬이 곧 기준월 순이다.
    """
    hits = sorted(
        p
        for p in reference_dir.glob("*/*.xlsx")
        if unicodedata.normalize("NFC", p.name).endswith(INTEREST_GROUP_SUFFIX)
    )
    if len(hits) != len(MONTHS):
        raise FileNotFoundError(
            f"expected {len(MONTHS)} interest group files under {reference_dir}, found {len(hits)}"
        )
    return hits


def sgis_dong_dbf(raw_dir: Path = RAW_DIR) -> Path:
    """SGIS 2025년 2분기 행정동 경계 dbf 경로를 반환한다.

    상위 폴더 3단이 한글이라 파일명(ASCII)으로만 찾는다.
    """
    hits = sorted(raw_dir.glob(f"*/*/*/{SGIS_DONG_DBF_NAME}"))
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected 1 {SGIS_DONG_DBF_NAME} under {raw_dir}, found {len(hits)}"
        )
    return hits[0]


def list_raw_files() -> pd.DataFrame:
    """원본 파일 인벤토리를 반환한다."""
    rows = []
    for p in sorted(SK_DIR.glob("*.csv")):
        rows.append({"group": "sk", "name": p.name, "size_mb": p.stat().st_size / 1024 / 1024})
    for p in sorted(CARD_DIR.glob("*.csv")):
        rows.append({"group": "card", "name": p.name, "size_mb": p.stat().st_size / 1024 / 1024})
    return pd.DataFrame(rows).round({"size_mb": 2})


def master_files(interim_dir: Path = INTERIM_DIR) -> dict[str, Path]:
    """집계구 마스터·SGIS 값 상태·변수사전 경로를 반환한다.

    팀 드라이브에서 받은 폴더명(`1차 merge`)이 한글이라 NFD로 저장될 수 있어
    폴더명을 리터럴로 쓰지 않고 하위 폴더 전체에서 파일명으로 찾는다.
    """
    found = {}
    for key, name in MASTER_FILE_NAMES.items():
        hits = sorted(interim_dir.glob(f"*/{name}"))
        if len(hits) != 1:
            raise FileNotFoundError(f"expected 1 {name} under {interim_dir}, found {len(hits)}")
        found[key] = hits[0]
    return found
