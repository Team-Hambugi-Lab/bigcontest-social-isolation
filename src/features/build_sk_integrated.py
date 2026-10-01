"""SK 유동인구 3개 테이블(성연령·시간대·요일)을 월별 통합 파일로 병합.

세 테이블은 같은 월 총량을 세 가지 방식으로 쪼갠 서로 다른 주변분포라 행 집합이
일치하지 않는다(격자마다 활성 테이블이 다름). 따라서 outer join으로 전체 격자를
보존하고, 특정 테이블에 없는 값은 0으로 채우지 않고 결측으로 남긴다.
2025년 12월 시간대·요일 원본은 완전 중복 행이 있어 병합 전 제거한다.
"""

from pathlib import Path

import pandas as pd

KEYS = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]
MONTHS = ["202507", "202508", "202509", "202510", "202511", "202512"]


def load_table(raw_dir: Path, table: str, month: str) -> pd.DataFrame:
    """SK 유동인구 원본 테이블 하나를 읽고 완전 중복 행을 제거한다."""
    path = raw_dir / f"flow_{table}_pop_{month}.csv"
    dtype = {"STD_YM": "string", "BLOCK_CD": "string"}
    return pd.read_csv(path, encoding="utf-8-sig", dtype=dtype).drop_duplicates()


def merge_month(raw_dir: Path, month: str) -> pd.DataFrame:
    """한 달치 성연령·시간대·요일 테이블을 격자 키 기준으로 outer join한다."""
    age = load_table(raw_dir, "age", month)
    time = load_table(raw_dir, "time", month)
    wkdy = load_table(raw_dir, "wkdy", month)

    merged = age.merge(time, on=KEYS, how="outer").merge(wkdy, on=KEYS, how="outer")
    assert not merged.duplicated(KEYS).any(), f"{month}: 병합 키 중복 발생"
    return merged


def build_all(raw_dir: Path, out_dir: Path) -> dict[str, int]:
    """6개월치 통합 파일을 생성해 저장하고 월별 행 수를 반환한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    for month in MONTHS:
        merged = merge_month(raw_dir, month)
        assert merged.shape[1] == 47, f"{month}: 47컬럼 기대, 실제 {merged.shape[1]}"
        out_path = out_dir / f"sk_통신인구_{month}_통합.csv"
        merged.to_csv(out_path, index=False, encoding="utf-8-sig")
        row_counts[month] = len(merged)
    return row_counts


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "data" / "raw" / "csv_변환" / "2026빅콘테스트_sk통신인구_데이터_레이아웃"
    out_dir = repo_root / "data" / "raw"

    counts = build_all(raw_dir, out_dir)
    total = sum(counts.values())
    for month, n in counts.items():
        print(f"{month}: {n:,}행")
    print(f"합계: {total:,}행 (47컬럼)")
