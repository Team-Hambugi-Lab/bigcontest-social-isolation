"""서울 통신 관심집단으로 SGIS 지수 v3.3을 연관 검증한다 (이슈 #25).

관심집단 값은 통계모형으로 추정한 인원이고, 월별 값은 직전 3개월 평균이다.
그래서 6개월은 평균 1회로 쓰고 월별 결과는 참고로만 둔다(#24 후속 7번 합의).

분자 '외출-커뮤니케이션이 모두 적은 집단(전체)'은 1인가구의 부분집합이 아니다.
강남 3,168셀 중 84셀에서 1인가구수보다 크다. 그래서 두 지표를 함께 낸다.
  ratio_1in = 분자 / 1인가구수  (이슈 정의, 강도 지표라 1을 넘을 수 있다)
  ratio_pop = 분자 / 총인구     (0~1 비율)

설계: docs/plans/261022_issue25_telecom_validation_design.md
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import pandas as pd

from src.data import paths

GANGNAM = "강남구"
GANGNAM_SGG = "11230"
N_DONGS = 22

# 서울시 7자리 행정동 코드 → SGIS 8자리. 기본은 끝에 0을 붙인다(h4_external_validation과 같은 방식).
# 일원2동(1123074)은 SGIS 2025 경계에 없고 같은 자리에 개포3동(11230511)이 있다.
# 일원2동이 개포3동으로 이름만 바뀐 것이다. 강남구청이 행정동 명칭만 바꾸고 법정동은
# 유지한다고 안내했고, 통신 20세 이상 인구 / SGIS 총인구가 0.857로 다른 21개 동 범위
# (0.73~1.34) 안에 있다. 서울시 자료는 개칭 전 코드를 계속 쓴다.
# TODO: #16 머지 후 h4_external_validation.CODE_EXCEPTIONS와 하나로 합친다.
CODE_EXCEPTIONS = {"1123074": "11230511"}
N_SEX = 2
N_AGE_GROUPS = 12
MALE = 1

# 원본 열 이름 -> 분석용 이름
COLUMN_MAP = {
    "행정동코드": "dong_cd",
    "행정동명": "dong_nm",
    "성별": "sex",
    "연령대": "age",
    "총인구": "pop",
    "1인가구수": "hh_single",
    "외출-커뮤니케이션이 모두 적은 집단(전체)": "n_isolated",
}
CELL_KEYS = ["dong_cd", "sex", "age"]
VALUE_COLS = ["pop", "hh_single", "n_isolated"]

# 대상 집단: (성별, 연령대 구간 시작값). None은 전체
TARGET_GROUPS: dict[str, tuple[int | None, tuple[int, ...] | None]] = {
    "old65": (None, (65, 70, 75)),
    "male5064": (MALE, (50, 55, 60)),
    "all": (None, None),
}
DENOMINATORS = {"ratio_1in": "hh_single", "ratio_pop": "pop"}

LONG_NAME = "gangnam22_telecom_ratio_long.csv"
DONG_NAME = "gangnam22_telecom_ratio_dong.csv"
CODE_MAP_NAME = "gangnam22_dong_code_map.csv"

DBF_HEADER_SIZE = 32
DBF_FIELD_SIZE = 32
DBF_FIELD_END = 0x0D
DBF_DELETED = b"*"


def ym_from_file(path: Path) -> str:
    """파일명 앞 `2025.07`을 `202507`로 바꾼다."""
    return path.name[:7].replace(".", "")


def validate_gangnam(df: pd.DataFrame) -> None:
    """강남 관심집단 long 테이블의 행 수·키·결측·음수를 확인한다."""
    n_months = df["ym"].nunique()
    expected = N_DONGS * N_SEX * N_AGE_GROUPS * n_months
    if df["dong_cd"].nunique() != N_DONGS:
        raise ValueError(f"강남 행정동 {N_DONGS}개가 아니다: {df['dong_cd'].nunique()}개")
    if len(df) != expected:
        raise ValueError(f"행 수 {len(df)} != 기대 {expected}")
    n_dup = int(df.duplicated(["ym", *CELL_KEYS]).sum())
    if n_dup:
        raise ValueError(f"(ym, 동, 성별, 연령대) 중복 {n_dup}건")
    n_null = int(df[VALUE_COLS].isna().sum().sum())
    if n_null:
        raise ValueError(f"값 결측 {n_null}건")
    if (df[VALUE_COLS] < 0).any().any():
        raise ValueError("음수 인원이 있다")
    if (df[["pop", "hh_single"]] == 0).any().any():
        raise ValueError("분모(총인구 또는 1인가구수)가 0인 셀이 있다")


def load_interest_groups(files: list[Path] | None = None) -> pd.DataFrame:
    """관심집단 월별 xlsx를 읽어 강남 22개 동 long 테이블로 합친다."""
    files = paths.interest_group_files() if files is None else files
    parts = []
    for f in files:
        raw = pd.read_excel(f, dtype={"행정동코드": str})
        part = raw.loc[raw["자치구"] == GANGNAM, list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
        parts.append(part.assign(ym=ym_from_file(f)))
    df = pd.concat(parts, ignore_index=True)
    validate_gangnam(df)
    return df


def _add_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """분자와 분모 합에서 두 지표를 계산해 붙인다."""
    out = df.copy()
    for name, denom in DENOMINATORS.items():
        out[name] = out["n_isolated"] / out[denom]
    return out


def cell_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """동 × 성별 × 연령대 셀마다 월별 비율을 구한 뒤 6개월 평균을 낸다."""
    monthly = _add_ratios(df)
    return (
        monthly.groupby(["dong_cd", "dong_nm", "sex", "age"], as_index=False)
        .agg(
            n_months=("ym", "nunique"),
            **{c: (c, "mean") for c in [*VALUE_COLS, *DENOMINATORS]},
        )
        .sort_values(CELL_KEYS, ignore_index=True)
    )


def select_target(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """대상 집단 정의(TARGET_GROUPS)에 맞는 셀만 남긴다."""
    sex, ages = TARGET_GROUPS[target]
    mask = pd.Series(True, index=df.index)
    if sex is not None:
        mask &= df["sex"] == sex
    if ages is not None:
        mask &= df["age"].isin(ages)
    return df[mask]


def target_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """동 × 대상 집단마다 월별로 분자 합 / 분모 합을 구하고 6개월 평균한다.

    셀 비율을 평균하지 않는다. 1인가구가 적은 셀의 비율이 크게 흔들리기 때문이다.
    결과는 동 22행 wide 테이블이고, 열 이름은 `{지표}_{대상}`이다.
    """
    names = df[["dong_cd", "dong_nm"]].drop_duplicates().set_index("dong_cd")
    cols = []
    for target in TARGET_GROUPS:
        monthly = (
            select_target(df, target).groupby(["dong_cd", "ym"])[VALUE_COLS].sum().pipe(_add_ratios)
        )
        mean = monthly.groupby("dong_cd")[list(DENOMINATORS)].mean()
        cols.append(mean.add_suffix(f"_{target}"))
    return names.join(cols).reset_index().sort_values("dong_cd", ignore_index=True)


def to_sgis_code(code7: pd.Series) -> pd.Series:
    """서울시 7자리 행정동 코드를 SGIS 8자리로 바꾼다."""
    code7 = code7.astype(str)
    return code7.map(CODE_EXCEPTIONS).fillna(code7 + "0")


def read_dbf(path: Path, encoding: str = "utf-8") -> pd.DataFrame:
    """dBASE III 파일의 문자 필드를 읽는다. 경계 속성(코드·이름)만 필요해 형상은 읽지 않는다."""
    data = path.read_bytes()
    n_records, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    pos = DBF_HEADER_SIZE
    while data[pos] != DBF_FIELD_END:
        name = data[pos : pos + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += DBF_FIELD_SIZE
    rows = []
    for i in range(n_records):
        rec = data[header_len + i * record_len : header_len + (i + 1) * record_len]
        if rec[:1] == DBF_DELETED:
            continue
        offset, row = 1, {}
        for name, length in fields:
            row[name] = rec[offset : offset + length].decode(encoding).strip()
            offset += length
        rows.append(row)
    return pd.DataFrame(rows, columns=[name for name, _ in fields])


def dong_code_table(telecom: pd.DataFrame, sgis: pd.DataFrame) -> pd.DataFrame:
    """통신 동과 SGIS 강남 동의 대응표를 만들고 22개 일대일 매칭을 확인한다.

    통신 쪽이나 SGIS 쪽에만 있는 동, 예외가 아닌데 이름이 다른 동이 있으면 멈춘다.
    """
    left = telecom[["dong_cd", "dong_nm"]].drop_duplicates()
    left = left.assign(ADM_CD=to_sgis_code(left["dong_cd"]))
    right = sgis.loc[sgis["ADM_CD"].str.startswith(GANGNAM_SGG), ["ADM_CD", "ADM_NM"]]
    table = left.merge(right, on="ADM_CD", how="outer", indicator=True, validate="one_to_one")
    unmatched = table[table["_merge"] != "both"]
    if len(unmatched):
        raise ValueError(f"미매칭 {len(unmatched)}건: {unmatched[['dong_cd', 'ADM_CD']].values}")
    table = table.drop(columns="_merge").assign(
        code_exception=lambda t: t["dong_cd"].isin(CODE_EXCEPTIONS),
        name_match=lambda t: t["dong_nm"] == t["ADM_NM"],
    )
    bad = table[~table["name_match"] & ~table["code_exception"]]
    if len(bad):
        raise ValueError(f"예외가 아닌데 동 이름이 다르다: {bad[['dong_nm', 'ADM_NM']].values}")
    if len(table) != N_DONGS:
        raise ValueError(f"대응표 {len(table)}행 != {N_DONGS}")
    return table.sort_values("dong_cd", ignore_index=True)


def main(argv: list[str] | None = None) -> None:
    """1단계: 강남 22개 동 관심집단 비율표와 동 코드 대응표를 data/interim/에 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=paths.INTERIM_DIR)
    args = parser.parse_args(argv)

    df = load_interest_groups()
    outputs = {
        LONG_NAME: cell_ratios(df),
        DONG_NAME: target_ratios(df),
        CODE_MAP_NAME: dong_code_table(df, read_dbf(paths.sgis_dong_dbf())),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, out in outputs.items():
        out.to_csv(args.out_dir / name, index=False, encoding="utf-8")
        print(f"saved {name}: {out.shape[0]:,} rows x {out.shape[1]} cols")


if __name__ == "__main__":
    main()
