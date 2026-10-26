"""대회 제공 원본을 src/data/가 읽는 쉼표 구분 CSV로 변환한다.

SK 유동인구 원본은 파이프(`|`) 구분 UTF-8(BOM), 신한카드 원본은 탭 구분 CP949라
`paths.SK_DIR`, `paths.CARD_DIR`에 쉼표 구분 UTF-8(BOM) 사본을 만든다.
값과 줄바꿈(CRLF)은 바꾸지 않고 구분자와 인코딩만 바꾼다.
"""

import csv
import unicodedata
from pathlib import Path

from src.data.paths import CARD_DIR, RAW_DIR, SK_DIR

SK_SRC_PREFIX = "2026빅콘테스트_sk통신인구_데이터_레이아웃"
CARD_SRC_PREFIX = "2026빅콘테스트_신한카드_데이터_레이아웃"
OUT_ENCODING = "utf-8-sig"


def find_dir(name: str, raw_dir: Path = RAW_DIR) -> Path:
    """NFD 한글 폴더명도 찾도록 NFC로 비교해 원본 폴더를 반환한다."""
    for p in raw_dir.iterdir():
        if p.is_dir() and unicodedata.normalize("NFC", p.name) == name:
            return p
    raise FileNotFoundError(f"{raw_dir}/{name} 폴더가 없음")


def convert(src: Path, dst: Path, delimiter: str, encoding: str) -> int:
    """구분자·인코딩만 바꿔 쉼표 CSV로 저장하고 행 수(헤더 제외)를 반환한다."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = -1
    with (
        src.open(encoding=encoding, newline="") as fin,
        dst.open("w", encoding=OUT_ENCODING, newline="") as fout,
    ):
        writer = csv.writer(fout, lineterminator="\r\n")
        for n, row in enumerate(csv.reader(fin, delimiter=delimiter)):
            writer.writerow(row)
    return n


def main() -> None:
    """SK 18개 파일과 신한카드 2개 파일을 변환한다."""
    sk_src = find_dir(SK_SRC_PREFIX)
    for src in sorted(sk_src.glob("flow_*_pop_*.csv")):
        n = convert(src, SK_DIR / src.name, "|", "utf-8-sig")
        print(f"{src.name}: {n:,}행")
    card_src = find_dir(CARD_SRC_PREFIX)
    for src in sorted(card_src.glob("*.txt")):
        name = unicodedata.normalize("NFC", src.stem) + ".csv"
        n = convert(src, CARD_DIR / name, "\t", "cp949")
        print(f"{name}: {n:,}행")


if __name__ == "__main__":
    main()
