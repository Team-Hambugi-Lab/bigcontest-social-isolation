"""서울 통신 관심집단으로 SGIS 지수 v3.3을 연관 검증한다.

관심집단 값은 통계모형으로 추정한 인원이고, 월별 값은 직전 3개월 평균이다.
그래서 6개월은 평균 1회로 쓰고 월별 결과는 참고로만 둔다.

분자 '외출-커뮤니케이션이 모두 적은 집단(전체)'은 1인가구의 부분집합이 아니다.
강남 3,168셀 중 84셀에서 1인가구수보다 크다. 그래서 두 지표를 함께 낸다.
  ratio_pop = 분자 / 같은 칸 인구 (주 지표, 0~1. 외출·커뮤니케이션이 모두 적은 집단의 추정 비율)
  ratio_1in = 분자 / 1인가구수   (참고. 1인가구 비중과 ρ = −0.91이라 판정에 쓰지 않는다)

설계: docs/design/telecom_validation_design.md
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.data import paths

# 서울시 7자리 → SGIS 8자리 코드 변환은 활동 신호 외부검증과 같은 규칙을 쓴다(근거: external.DONG_CODE_FIX)
from src.evaluation.h4_external_validation import CODE_EXCEPTIONS, to_sgis_code

GANGNAM = "강남구"
GANGNAM_SGG = "11230"
N_DONGS = 22

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

VALIDATION_NAME = "gangnam22_v3_validation.csv"
SPEARMAN_NAME = "gangnam22_v3_spearman.csv"
THEME_DIFF_NAME = "gangnam22_v3_theme_diff.csv"

V33_DIR = paths.INTERIM_DIR / "v3.3"
V33_OA_NAME = "isolation_index_v3.csv"
V33_ADM_NAME = "isolation_index_v3_adm.csv"

# SGIS 쪽 지표. 주 분석은 v3.3 행정동 집계본(보류 제외, hh_eval 가중)을 그대로 쓴다
PREDICTORS = {
    "theme_A": "theme_A_pct_w",
    "theme_B": "theme_B_pct_w",
    "composite": "score_w",
    "single_share": "single_share",  # 기준선: 1인가구 비중
    "watch_share": "watch_share",  # 보조: 관찰 후보 가구 비중
}
# 민감도: 테마 z 점수를 hh_total로 가중평균. 척도(z)를 고정하고 보류 제외(_eval)와 포함(_all)만 바꾼다
Z_SCORES = {"theme_A": "theme_A_score", "theme_B": "theme_B_score"}
Z_VARIANTS = ("eval", "all")
TARGET_PREFIXES = ("ratio_pop", "ratio_1in")
# 테마 가중 판정에 쓰는 비교: 테마 A·B의 대조 지표별 ρ 차이
THEMES = ("theme_A", "theme_B")

N_BOOT = 2000
RANDOM_STATE = 42
CI = (2.5, 97.5)
# SGIS 지수 v3 한계로 짚은 고령 임대단지 후보 (일원1동, 수서동)
RENTAL_CANDIDATES = ("11230730", "11230750")

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


def sgis_dong_scores(adm: pd.DataFrame, oa: pd.DataFrame) -> pd.DataFrame:
    """v3.3 행정동 집계본에 기준선·보조 지표와 z 점수 민감도 점수를 붙인다(강남만).

    z 점수는 보류 제외(행정동 집계본과 같은 '보류 아님 & 점수 유효' 행)와 보류 포함 두 가지로
    가중평균한다. 척도를 고정해야 보류 포함의 효과만 따로 볼 수 있다.
    """
    out = adm.loc[adm["ADM_CD"].str.startswith(GANGNAM_SGG)].copy()
    out["single_share"] = out["hh_single_eval"] / out["hh_eval"]
    out["watch_share"] = out["hh_watch"] / out["hh_eval"]

    gangnam = oa.loc[oa["ADM_CD"].str.startswith(GANGNAM_SGG)]
    rows = {"eval": gangnam[~gangnam["hold"] & gangnam["score"].notna()], "all": gangnam}
    z_scores = {}
    for theme, col in Z_SCORES.items():
        for variant in Z_VARIANTS:
            ok = rows[variant].dropna(subset=[col, "hh_total"])
            weighted = (ok[col] * ok["hh_total"]).groupby(ok["ADM_CD"]).sum()
            z_scores[f"{theme}_z_{variant}"] = weighted / ok.groupby("ADM_CD")["hh_total"].sum()
    return out.merge(pd.DataFrame(z_scores), left_on="ADM_CD", right_index=True)


def validation_table(
    dong_ratios: pd.DataFrame, code_map: pd.DataFrame, sgis: pd.DataFrame
) -> pd.DataFrame:
    """통신 대조 지표와 SGIS 동 점수를 동 코드 대응표로 붙인다. 22행이 아니면 멈춘다."""
    keys = code_map[["dong_cd", "ADM_CD", "ADM_NM"]]
    table = dong_ratios.merge(keys, on="dong_cd", validate="one_to_one").merge(
        sgis, on="ADM_CD", validate="one_to_one"
    )
    if len(table) != N_DONGS:
        raise ValueError(f"검증 표 {len(table)}행 != {N_DONGS}")
    return table.sort_values("dong_cd", ignore_index=True)


def predictor_columns(include_hold: bool = True) -> dict[str, str]:
    """SGIS 쪽 지표 이름 → 검증 표 열 이름."""
    cols = dict(PREDICTORS)
    if include_hold:
        cols.update({f"{t}_z_{v}": f"{t}_z_{v}" for t in Z_SCORES for v in Z_VARIANTS})
    return cols


def target_columns(table: pd.DataFrame) -> list[str]:
    """검증 표에서 대조 지표 열을 고른다(ratio_pop 먼저)."""
    return [c for p in TARGET_PREFIXES for c in table.columns if c.startswith(f"{p}_")]


def _rho_matrix(
    table: pd.DataFrame, predictors: dict[str, str], targets: list[str]
) -> pd.DataFrame:
    """SGIS 지표 × 대조 지표 Spearman ρ 행렬."""
    data = table[list(predictors.values()) + targets].rename(
        columns={v: k for k, v in predictors.items()}
    )
    return data.corr(method="spearman").loc[list(predictors), targets]


def spearman_table(table: pd.DataFrame) -> pd.DataFrame:
    """SGIS 지표 × 대조 지표마다 ρ·p, 부트스트랩 구간, leave-one-out 범위를 낸다."""
    predictors = predictor_columns()
    targets = target_columns(table)
    rows = []
    for name, col in predictors.items():
        for target in targets:
            rho, p = stats.spearmanr(table[col], table[target])
            rows.append({"predictor": name, "target": target, "rho": rho, "p_value": p})
    out = pd.DataFrame(rows)

    boot = bootstrap_rho(table, predictors, targets)
    ci = boot.quantile([CI[0] / 100, CI[1] / 100]).T
    ci.columns = ["ci_low", "ci_high"]
    loo = leave_one_out_rho(table, predictors, targets)
    no_rental = _rho_matrix(
        table[~table["ADM_CD"].isin(RENTAL_CANDIDATES)], predictors, targets
    ).stack()
    extra = ci.join(loo).join(no_rental.rename("rho_no_rental"))
    return out.join(extra, on=["predictor", "target"])


def bootstrap_rho(
    table: pd.DataFrame,
    predictors: dict[str, str],
    targets: list[str],
    n_boot: int = N_BOOT,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """동을 복원추출해 ρ를 다시 구한다. 열은 (지표, 대조 지표), 행은 반복이다."""
    rng = np.random.default_rng(random_state)
    samples = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(table), len(table))
        samples.append(_rho_matrix(table.iloc[idx], predictors, targets).stack())
    return pd.DataFrame(samples).reset_index(drop=True)


def leave_one_out_rho(
    table: pd.DataFrame, predictors: dict[str, str], targets: list[str]
) -> pd.DataFrame:
    """동을 하나씩 빼고 ρ를 다시 구해 최솟값·최댓값과 그때 뺀 동을 낸다."""
    runs = {
        code: _rho_matrix(table[table["ADM_CD"] != code], predictors, targets).stack()
        for code in table["ADM_CD"]
    }
    runs = pd.DataFrame(runs)
    return pd.DataFrame(
        {
            "loo_min": runs.min(axis=1),
            "loo_max": runs.max(axis=1),
            "loo_min_drop": runs.idxmin(axis=1),
            "loo_max_drop": runs.idxmax(axis=1),
        }
    )


def theme_diff(table: pd.DataFrame) -> pd.DataFrame:
    """대조 지표마다 ρ(테마 A) − ρ(테마 B)와 부트스트랩 구간을 낸다(§4.5 판정용)."""
    predictors = {k: PREDICTORS[k] for k in THEMES}
    targets = target_columns(table)
    point = _rho_matrix(table, predictors, targets)
    boot = bootstrap_rho(table, predictors, targets)
    rows = []
    for target in targets:
        diff = boot[("theme_A", target)] - boot[("theme_B", target)]
        rows.append(
            {
                "target": target,
                "diff_A_minus_B": point.loc["theme_A", target] - point.loc["theme_B", target],
                "ci_low": np.percentile(diff, CI[0]),
                "ci_high": np.percentile(diff, CI[1]),
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    """강남 22개 동 대조 지표(1단계)와 v3.3 연관 검증(2단계) 결과를 data/interim/에 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=paths.INTERIM_DIR)
    args = parser.parse_args(argv)

    df = load_interest_groups()
    dong = target_ratios(df)
    code_map = dong_code_table(df, read_dbf(paths.sgis_dong_dbf()))
    adm = pd.read_csv(V33_DIR / V33_ADM_NAME, dtype={"ADM_CD": str})
    oa = pd.read_csv(V33_DIR / V33_OA_NAME, dtype={"ADM_CD": str, "TOT_OA_CD": str})
    table = validation_table(dong, code_map, sgis_dong_scores(adm, oa))
    outputs = {
        LONG_NAME: cell_ratios(df),
        DONG_NAME: dong,
        CODE_MAP_NAME: code_map,
        VALIDATION_NAME: table,
        SPEARMAN_NAME: spearman_table(table),
        THEME_DIFF_NAME: theme_diff(table),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, out in outputs.items():
        out.to_csv(args.out_dir / name, index=False, encoding="utf-8")
        print(f"saved {name}: {out.shape[0]:,} rows x {out.shape[1]} cols")


if __name__ == "__main__":
    main()
