# EDA 0~3단계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검증된 데이터 제약 위에서 SK 유동인구와 신한카드 결제를 이중 해상도로 분리 분석해, 행정동 47개의 공간 위험 프로파일과 지역×성×연령 36집단의 집단 위험 프로파일을 산출한다.

**Architecture:** 원본 로딩을 `src/data/loaders.py` 한 곳에 가둬 12월 중복·인코딩·NFD 경로를 일괄 처리한다. `src/features/`가 공간축(동×월)과 집단축(지역×성×연령×월) 두 패널을 따로 만들고, 노트북 4본은 그 함수를 호출만 한다. 두 축은 곱하거나 나누지 않고 시군구 수준에서 방향만 대조한다.

**Tech Stack:** Python 3.13.15, pandas 3.0.6, numpy 2.5.2, matplotlib 3.11.2, seaborn 0.13.2, pyproj 3.8.0, scikit-learn 1.9.1, nbformat 5.11.1 + nbclient 0.11.0 (노트북 생성·실행), pytest 9.1.1

**Spec:** `docs/plans/260920_EDA_design.md`

## Global Constraints

- **커밋 금지.** `AGENTS.md`는 사용자가 명시적으로 요청한 경우에만 커밋·푸시·PR을 허용한다. 모든 Task의 마지막 단계는 커밋이 아니라 테스트 통과 확인이다.
- **`uv` 미설치.** `AGENTS.md`의 `uv run` 워크플로를 쓸 수 없다. 모든 명령은 전역 Python으로 실행한다: `python -m pytest`, `python -m ruff`.
- 작업 디렉터리는 `C:\Users\kte04\orca\workspaces\bigcontest-social-isolation\dovekie` 고정.
- 원본 데이터 경로: `data/raw/sk_telecom/` (CSV 18), `data/raw/shinhan_card/` (CSV 2). 모두 UTF-8 BOM, 쉼표 구분.
- **한글 파일명은 NFD로 저장되어 있다.** 문자열 리터럴로 열면 `FileNotFoundError`. 반드시 `Path.glob()`으로 접근한다.
- SK 공통 PK: `["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]`
- 12월 `flow_time`·`flow_wkdy`는 전체 2배 복제 → `drop_duplicates(subset=PK)` 필수.
- 분석 단위는 `BLOCK_CD[:8]` (행정동). 대상 시군구는 `11230`(서울 강남구), `32010`(강원 춘천시) 2종만. 나머지 8종 337행은 경계 격자로 제외한다.
- 3테이블 결합 시 **공통 격자로 제한하지 않는다.** 각 테이블 전체 격자로 동 집계 후 동 키로 결합한다.
- WKDY 각 칸은 해당 요일의 **일평균**이다. 7로 나누지 않는다.
- SK 값의 0은 결측으로 바꾸지 않고 실제 0으로 집계한다.
- 금액 지표는 `ZZ_나머지`·`세금공과금` 제외 후 산출한다.
- 카드는 **데이터2 주력**. 데이터1과 합산 금지 (법인카드 포함 여부가 달라 모집단이 다름).
- 난수 시드 `random_state=42` 고정.
- ruff `line-length = 100`, `quote-style = "double"`.
- 로그·`print` 출력에 이모지 금지. 코드 주석은 한국어 허용.
- 노트북 파일명 `YYMMDD_유형_주제.ipynb`, 리포트 H1 `# [유형] 주제 — YYYY-MM-DD`.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `src/data/paths.py` | 경로 상수 및 NFD 안전 파일 탐색 |
| `src/data/loaders.py` | 원본 로딩 단일 관문 (인코딩·중복제거·타입변환) |
| `src/data/regions.py` | `BLOCK_CD` 파싱, 시군구·행정동 코드 부여, 좌표 변환 |
| `src/features/sk_dong.py` | SK → 동×월 패널 (공간축) |
| `src/features/card_cohort.py` | 카드 → 지역×성×연령×월 패널 (집단축) |
| `src/features/isolation.py` | 4축 지표 산출·정규화·합성 |
| `src/visualization/style.py` | 한글 폰트, colorblind 팔레트 |
| `tests/test_paths.py` ~ `tests/test_isolation.py` | 모듈별 단위 테스트 |
| `scripts/build_notebook.py` | nbformat으로 노트북 생성·실행하는 헬퍼 |
| `notebooks/260920_EDA_0{0..3}_*.ipynb` | 단계별 분석 |
| `reports/260920_*.md` | 단계별 요약 |

---

## Task 1: 경로 모듈과 NFD 안전 탐색

**Files:**
- Create: `src/data/__init__.py`
- Create: `src/data/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `PROJECT_ROOT: Path`, `RAW_DIR: Path`, `SK_DIR: Path`, `CARD_DIR: Path`
  - `SK_TABLES: tuple[str, ...] = ("age", "time", "wkdy")`
  - `MONTHS: tuple[str, ...] = ("202507", ..., "202512")`
  - `sk_file(table: str, ym: str) -> Path`
  - `card_file(dataset: int) -> Path`
  - `list_raw_files() -> pd.DataFrame` — 컬럼 `["group", "name", "size_mb"]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_paths.py`:

```python
"""경로 모듈 테스트 — NFD 한글 파일명 접근이 핵심."""

import pytest

from src.data import paths


def test_raw_dirs_exist():
    assert paths.SK_DIR.is_dir()
    assert paths.CARD_DIR.is_dir()


def test_sk_file_returns_existing_path():
    p = paths.sk_file("age", "202507")
    assert p.exists()
    assert p.name == "flow_age_pop_202507.csv"


def test_sk_file_rejects_unknown_table():
    with pytest.raises(ValueError, match="table"):
        paths.sk_file("bogus", "202507")


def test_card_file_finds_nfd_korean_name():
    # 한글 파일명이 NFD로 저장되어 있어 문자열 리터럴로는 열리지 않는다
    p2 = paths.card_file(2)
    assert p2.exists()
    assert p2.stat().st_size > 100_000_000

    p1 = paths.card_file(1)
    assert p1.exists()
    assert p1 != p2


def test_all_18_sk_files_present():
    found = [paths.sk_file(t, m) for t in paths.SK_TABLES for m in paths.MONTHS]
    assert len(found) == 18
    assert all(p.exists() for p in found)


def test_list_raw_files_counts_20():
    inv = paths.list_raw_files()
    assert len(inv) == 20
    assert set(inv["group"]) == {"sk", "card"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data'`

- [ ] **Step 3: 구현**

`src/data/__init__.py`: 빈 파일.

`src/data/paths.py`:

```python
"""원본 데이터 경로 상수와 NFD 안전 파일 탐색."""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SK_DIR = RAW_DIR / "sk_telecom"
CARD_DIR = RAW_DIR / "shinhan_card"

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

    OneDrive가 한글 파일명을 NFD로 저장하므로 문자열 리터럴 대신 glob으로 찾는다.
    """
    if dataset not in (1, 2):
        raise ValueError(f"dataset must be 1 or 2, got {dataset!r}")
    candidates = sorted(CARD_DIR.glob("*.csv"), key=lambda p: p.stat().st_size)
    if len(candidates) != 2:
        raise FileNotFoundError(f"expected 2 card CSVs in {CARD_DIR}, found {len(candidates)}")
    # 데이터1(약 73MB)이 데이터2(약 128MB)보다 작다
    return candidates[0] if dataset == 1 else candidates[1]


def list_raw_files() -> pd.DataFrame:
    """원본 파일 인벤토리를 반환한다."""
    rows = []
    for p in sorted(SK_DIR.glob("*.csv")):
        rows.append({"group": "sk", "name": p.name, "size_mb": p.stat().st_size / 1024 / 1024})
    for p in sorted(CARD_DIR.glob("*.csv")):
        rows.append({"group": "card", "name": p.name, "size_mb": p.stat().st_size / 1024 / 1024})
    return pd.DataFrame(rows).round({"size_mb": 2})
```

`card_file`이 크기로 데이터1/2를 구분하는 이유: NFD 파일명이라 이름 비교가 불안정하다. 크기 차이가 73MB 대 128MB로 커서 안전하다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_paths.py -v`
Expected: 6 passed

- [ ] **Step 5: 린트**

Run: `python -m ruff check src/data/paths.py tests/test_paths.py && python -m ruff format --check src/data/paths.py tests/test_paths.py`
Expected: 통과. 실패 시 `python -m ruff format` 적용 후 재확인.

---

## Task 2: SK·카드 로더

**Files:**
- Create: `src/data/loaders.py`
- Test: `tests/test_loaders.py`

**Interfaces:**
- Consumes: `src.data.paths`의 `sk_file`, `card_file`, `SK_TABLES`, `MONTHS`
- Produces:
  - `SK_PK: list[str] = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]`
  - `load_sk(table: str, ym: str | None = None, dedupe: bool = True) -> pd.DataFrame`
  - `sk_value_cols(df: pd.DataFrame) -> list[str]`
  - `load_card(dataset: int = 2) -> pd.DataFrame` — `TS_AT`·`USE_CNT`는 int64
  - `dedupe_report() -> pd.DataFrame` — 컬럼 `["table", "ym", "rows_raw", "rows_dedup", "dropped"]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_loaders.py`:

```python
"""로더 테스트 — 12월 중복 제거와 타입 변환이 핵심."""

import pandas as pd

from src.data import loaders


def test_load_sk_age_july_shape():
    df = loaders.load_sk("age", "202507")
    assert len(df) == 98_129
    assert df.shape[1] == 16
    assert df["STD_YM"].dtype == object
    assert df["BLOCK_CD"].dtype == object
    assert df["BLOCK_CD"].str.len().eq(20).all()


def test_december_time_duplicates_removed():
    raw = loaders.load_sk("time", "202512", dedupe=False)
    dedup = loaders.load_sk("time", "202512", dedupe=True)
    assert len(raw) == 185_090
    assert len(dedup) == 92_545
    assert len(raw) == 2 * len(dedup)


def test_december_wkdy_duplicates_removed():
    dedup = loaders.load_sk("wkdy", "202512")
    assert len(dedup) == 121_267


def test_non_december_files_have_no_duplicates():
    for ym in ("202507", "202510"):
        df = loaders.load_sk("time", ym, dedupe=False)
        assert df.duplicated(subset=loaders.SK_PK).sum() == 0


def test_load_sk_all_months_concatenates():
    df = loaders.load_sk("age")
    assert len(df) == 596_252  # 6개월 합계
    assert sorted(df["STD_YM"].unique()) == list(loaders.MONTHS)


def test_sk_value_cols_counts():
    assert len(loaders.sk_value_cols(loaders.load_sk("age", "202507"))) == 12
    assert len(loaders.sk_value_cols(loaders.load_sk("time", "202507"))) == 24
    assert len(loaders.sk_value_cols(loaders.load_sk("wkdy", "202507"))) == 7


def test_sk_values_have_no_nulls():
    df = loaders.load_sk("age", "202507")
    cols = loaders.sk_value_cols(df)
    assert df[cols].isnull().sum().sum() == 0


def test_load_card_dataset2():
    df = loaders.load_card(2)
    assert len(df) == 1_806_800
    assert list(df.columns) == [
        "TA_YMD", "MCT_SGG_CD", "MCT_RY_CD", "CLN_SGG_CD",
        "SEX_CCD", "AGE_CCD", "TS_AT", "USE_CNT",
    ]
    assert pd.api.types.is_integer_dtype(df["TS_AT"])
    assert pd.api.types.is_integer_dtype(df["USE_CNT"])
    assert df["USE_CNT"].min() == 5
    assert df["TS_AT"].min() == 6
    assert df["TA_YMD"].nunique() == 184
    assert df["SEX_CCD"].nunique() == 2
    assert df["MCT_RY_CD"].nunique() == 90


def test_load_card_dataset1_has_corporate():
    df = loaders.load_card(1)
    assert len(df) == 1_044_710
    assert "TIME_GB" in df.columns
    assert "법인" in set(df["SEX_CCD"])


def test_dedupe_report_flags_only_december():
    rep = loaders.dedupe_report()
    assert len(rep) == 18
    dropped = rep[rep["dropped"] > 0]
    assert set(dropped["ym"]) == {"202512"}
    assert set(dropped["table"]) == {"time", "wkdy"}
    assert rep["rows_raw"].sum() == 2_101_675
    assert rep["rows_dedup"].sum() == 1_887_863
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_loaders.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.loaders'`

- [ ] **Step 3: 구현**

`src/data/loaders.py`:

```python
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
    dedupe=True면 PK 중복을 제거한다(12월 time·wkdy 파일이 2배 복제 배포됨).
    """
    if table not in SK_TABLES:
        raise ValueError(f"table must be one of {SK_TABLES}, got {table!r}")

    months = MONTHS if ym is None else (ym,)
    frames = []
    for m in months:
        df = pd.read_csv(
            sk_file(table, m),
            encoding=ENCODING,
            dtype={"STD_YM": "string", "BLOCK_CD": "string"},
        )
        if dedupe:
            df = df.drop_duplicates(subset=SK_PK)
        frames.append(df)

    out = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    out = out.reset_index(drop=True)
    out["STD_YM"] = out["STD_YM"].astype(object)
    out["BLOCK_CD"] = out["BLOCK_CD"].astype(object)
    return out


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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_loaders.py -v`
Expected: 10 passed. `dedupe_report` 테스트는 18개 파일을 두 번 읽어 1~2분 걸린다.

- [ ] **Step 5: 린트**

Run: `python -m ruff check src/data/loaders.py tests/test_loaders.py`

---

## Task 3: 지역 코드 파싱과 좌표 변환

**Files:**
- Create: `src/data/regions.py`
- Test: `tests/test_regions.py`

**Interfaces:**
- Consumes: 없음 (DataFrame을 인자로 받음)
- Produces:
  - `SGG_NAMES: dict[str, str]` — `{"11230": "서울 강남구", "32010": "강원 춘천시"}`
  - `TARGET_SGG: tuple[str, str] = ("11230", "32010")`
  - `add_region_codes(df: pd.DataFrame) -> pd.DataFrame` — `sgg_cd`(5), `dong_cd`(8), `tong_cd`(10), `sgg_name` 추가
  - `filter_target_sgg(df: pd.DataFrame) -> pd.DataFrame`
  - `add_wgs84(df: pd.DataFrame) -> pd.DataFrame` — `lon`, `lat` 추가
  - `GRID_AREA_M2: int = 2500`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_regions.py`:

```python
"""BLOCK_CD 파싱과 좌표 변환 테스트."""

import pandas as pd

from src.data import loaders, regions


def test_add_region_codes_splits_correctly():
    df = pd.DataFrame({"BLOCK_CD": ["11230510101020000001"]})
    out = regions.add_region_codes(df)
    assert out.loc[0, "sgg_cd"] == "11230"
    assert out.loc[0, "dong_cd"] == "11230510"
    assert out.loc[0, "tong_cd"] == "1123051010"
    assert out.loc[0, "sgg_name"] == "서울 강남구"


def test_unknown_sgg_gets_none_name():
    df = pd.DataFrame({"BLOCK_CD": ["99999510101020000001"]})
    out = regions.add_region_codes(df)
    assert pd.isna(out.loc[0, "sgg_name"])


def test_target_dong_counts_match_admin_divisions():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    gangnam = df[df["sgg_cd"] == "11230"]
    chuncheon = df[df["sgg_cd"] == "32010"]
    assert gangnam["dong_cd"].nunique() == 22  # 강남구 행정동 22개
    assert chuncheon["dong_cd"].nunique() == 25  # 춘천시 1읍 9면 15동


def test_filter_target_sgg_drops_border_grids():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    kept = regions.filter_target_sgg(df)
    assert set(kept["sgg_cd"]) == set(regions.TARGET_SGG)
    assert len(df) - len(kept) == 60  # 경계 격자 60행


def test_add_wgs84_places_gangnam_and_chuncheon():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    df = regions.add_wgs84(regions.filter_target_sgg(df))
    gn = df[df["sgg_cd"] == "11230"]
    cc = df[df["sgg_cd"] == "32010"]
    # 강남구 중심 근방
    assert 37.45 < gn["lat"].mean() < 37.55
    assert 127.0 < gn["lon"].mean() < 127.12
    # 춘천시 중심 근방
    assert 37.7 < cc["lat"].mean() < 38.05
    assert 127.5 < cc["lon"].mean() < 127.95


def test_gangnam_observed_area_near_actual():
    df = regions.add_region_codes(loaders.load_sk("age", "202507"))
    gn = df[df["sgg_cd"] == "11230"]
    area_km2 = len(gn) * regions.GRID_AREA_M2 / 1e6
    assert 35 < area_km2 < 42  # 실제 강남구 39.5 km2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_regions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.regions'`

- [ ] **Step 3: 구현**

`src/data/regions.py`:

```python
"""BLOCK_CD 파싱과 좌표계 변환.

BLOCK_CD 20자리는 구(舊) 행정구역코드 체계다.
  11230  510  10  1020000001
  시군구  행정동 통  일련번호
앞 5자리는 좌표 역추적으로 시군구임을 확인했고,
6~8자리 개수가 강남구 행정동 22개·춘천시 읍면동 25개와 정확히 일치한다.
"""

import pandas as pd
from pyproj import Transformer

SGG_NAMES = {"11230": "서울 강남구", "32010": "강원 춘천시"}
TARGET_SGG = ("11230", "32010")
GRID_AREA_M2 = 2500  # 50m x 50m

_TRANSFORMER = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def add_region_codes(df: pd.DataFrame) -> pd.DataFrame:
    """BLOCK_CD에서 시군구·행정동·통 코드를 뽑아 컬럼으로 붙인다."""
    out = df.copy()
    code = out["BLOCK_CD"].astype(str)
    out["sgg_cd"] = code.str[:5]
    out["dong_cd"] = code.str[:8]
    out["tong_cd"] = code.str[:10]
    out["sgg_name"] = out["sgg_cd"].map(SGG_NAMES)
    return out


def filter_target_sgg(df: pd.DataFrame) -> pd.DataFrame:
    """대상 시군구(강남구·춘천시) 격자만 남긴다. 경계 격자는 제외된다."""
    if "sgg_cd" not in df.columns:
        df = add_region_codes(df)
    return df[df["sgg_cd"].isin(TARGET_SGG)].copy()


def add_wgs84(df: pd.DataFrame) -> pd.DataFrame:
    """UTM-K(EPSG:5179) 좌표를 WGS84 경위도로 변환해 붙인다."""
    out = df.copy()
    lon, lat = _TRANSFORMER.transform(out["X_COORD"].to_numpy(), out["Y_COORD"].to_numpy())
    out["lon"] = lon
    out["lat"] = lat
    return out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_regions.py -v`
Expected: 6 passed

- [ ] **Step 5: 린트**

Run: `python -m ruff check src/data/regions.py tests/test_regions.py`

---

## Task 4: 시각화 공통 스타일

**Files:**
- Create: `src/visualization/style.py`
- Test: `tests/test_style.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `setup_style() -> str` — 적용된 한글 폰트명 반환
  - `PALETTE: list[str]` — colorblind-safe 8색
  - `SGG_COLORS: dict[str, str]` — `{"서울 강남구": ..., "강원 춘천시": ...}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_style.py`:

```python
"""시각화 공통 스타일 테스트."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from src.visualization import style  # noqa: E402


def test_setup_style_sets_korean_font():
    font = style.setup_style()
    assert font in plt.rcParams["font.family"] or font == plt.rcParams["font.family"][0]
    assert plt.rcParams["axes.unicode_minus"] is False


def test_palette_is_colorblind_safe_length():
    assert len(style.PALETTE) == 8
    assert all(c.startswith("#") and len(c) == 7 for c in style.PALETTE)


def test_sgg_colors_cover_both_regions():
    assert set(style.SGG_COLORS) == {"서울 강남구", "강원 춘천시"}


def test_korean_label_renders_without_error(tmp_path):
    style.setup_style()
    fig, ax = plt.subplots()
    ax.set_title("행정동별 유동인구")
    ax.set_xlabel("연령대")
    out = tmp_path / "t.png"
    fig.savefig(out)
    plt.close(fig)
    assert out.stat().st_size > 1000
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_style.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/visualization/style.py`:

```python
"""matplotlib 공통 스타일 — 한글 폰트와 색약 친화 팔레트."""

import matplotlib
import matplotlib.pyplot as plt

# Okabe-Ito 색약 친화 팔레트
PALETTE = [
    "#0072B2",  # 파랑
    "#E69F00",  # 주황
    "#009E73",  # 청록
    "#CC79A7",  # 분홍
    "#56B4E9",  # 하늘
    "#D55E00",  # 주홍
    "#F0E442",  # 노랑
    "#666666",  # 회색
]

SGG_COLORS = {"서울 강남구": PALETTE[0], "강원 춘천시": PALETTE[1]}

_FONT_CANDIDATES = ("Malgun Gothic", "NanumGothic", "Pretendard", "AppleGothic")


def setup_style() -> str:
    """한글 폰트와 기본 rcParams를 적용하고 선택된 폰트명을 반환한다."""
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    font = next((f for f in _FONT_CANDIDATES if f in available), "DejaVu Sans")

    plt.rcParams["font.family"] = font
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 110
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["figure.figsize"] = (10, 6)
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["axes.prop_cycle"] = plt.cycler(color=PALETTE)
    return font
```

`src/visualization/__init__.py`가 없으면 빈 파일로 만든다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_style.py -v`
Expected: 4 passed

---

## Task 5: SK 공간축 패널 (동×월)

**Files:**
- Create: `src/features/sk_dong.py`
- Test: `tests/test_sk_dong.py`

**Interfaces:**
- Consumes: `loaders.load_sk`, `loaders.sk_value_cols`, `regions.add_region_codes`, `regions.filter_target_sgg`
- Produces:
  - `AGE_COLS: list[str]` (12), `TIME_COLS: list[str]` (24), `WKDY_COLS: list[str]` (7)
  - `SENIOR_COLS: list[str]` — `["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]`
  - `NIGHT_COLS: list[str]` — `TMST_22, 23, 00..05` (8개)
  - `aggregate_dong(table: str, unit: str = "dong_cd") -> pd.DataFrame` — index `[unit, "STD_YM"]`, 수치 컬럼 합계
  - `build_space_panel(unit: str = "dong_cd") -> pd.DataFrame` — 3테이블을 동×월로 결합한 wide 패널

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_sk_dong.py`:

```python
"""SK 공간축 패널 테스트."""

from src.features import sk_dong


def test_column_group_sizes():
    assert len(sk_dong.AGE_COLS) == 12
    assert len(sk_dong.TIME_COLS) == 24
    assert len(sk_dong.WKDY_COLS) == 7
    assert len(sk_dong.SENIOR_COLS) == 2
    assert len(sk_dong.NIGHT_COLS) == 8


def test_aggregate_dong_shape():
    agg = sk_dong.aggregate_dong("age")
    assert agg.index.names == ["dong_cd", "STD_YM"]
    assert agg.index.get_level_values("dong_cd").nunique() == 47
    assert len(agg) == 47 * 6
    assert list(agg.columns) == sk_dong.AGE_COLS


def test_all_three_tables_produce_same_47_dongs():
    dongs = {t: set(sk_dong.aggregate_dong(t).index.get_level_values("dong_cd")) for t in
             ("age", "time", "wkdy")}
    assert dongs["age"] == dongs["time"] == dongs["wkdy"]
    assert len(dongs["age"]) == 47


def test_space_panel_merges_without_loss():
    panel = sk_dong.build_space_panel()
    assert len(panel) == 47 * 6
    assert panel.isnull().sum().sum() == 0
    for c in sk_dong.AGE_COLS + sk_dong.TIME_COLS + sk_dong.WKDY_COLS:
        assert c in panel.columns


def test_age_total_matches_time_total_within_rounding():
    panel = sk_dong.build_space_panel()
    age_sum = panel[sk_dong.AGE_COLS].sum(axis=1)
    time_sum = panel[sk_dong.TIME_COLS].sum(axis=1)
    # 동 단위 집계 후에도 두 총량은 반올림 오차 범위에서 일치해야 한다
    rel_diff = ((age_sum - time_sum).abs() / age_sum).max()
    assert rel_diff < 0.01


def test_wkdy_sum_is_about_seven_times_daily_average():
    panel = sk_dong.build_space_panel()
    ratio = panel[sk_dong.WKDY_COLS].sum(axis=1).sum() / panel[sk_dong.AGE_COLS].sum(axis=1).sum()
    # WKDY 각 칸은 해당 요일의 일평균이므로 7칸 합은 일평균의 약 7배
    assert 6.5 < ratio < 7.5


def test_unit_tong_gives_more_units():
    agg = sk_dong.aggregate_dong("age", unit="tong_cd")
    assert agg.index.get_level_values("tong_cd").nunique() == 148
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_sk_dong.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.features.sk_dong'`

- [ ] **Step 3: 구현**

`src/features/sk_dong.py`:

```python
"""SK 유동인구를 공간축 패널(행정동 x 월)로 집계한다.

3테이블의 격자 커버리지가 다르지만 동 단위로 올리면 47개 동이 동일하게 나오고
총량 차이도 중앙값 0.000%라, 공통 격자로 제한하지 않고 각 테이블 전체를 쓴다.
"""

import pandas as pd

from src.data import loaders, regions

AGE_COLS = [
    f"{sex}_FLOW_POP_CNT_{grp}"
    for sex in ("MAN", "WMAN")
    for grp in ("10G", "20G", "30G", "40G", "50G", "60GU")
]
TIME_COLS = [f"TMST_{h:02d}" for h in range(24)]
WKDY_COLS = [f"FLOW_POP_CNT_{d}" for d in ("MON", "TUS", "WED", "THU", "FRI", "SAT", "SUN")]

SENIOR_COLS = ["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]
# 야간은 22시~익일 05시로 정의한다
NIGHT_COLS = [f"TMST_{h:02d}" for h in (22, 23, 0, 1, 2, 3, 4, 5)]

_TABLE_COLS = {"age": AGE_COLS, "time": TIME_COLS, "wkdy": WKDY_COLS}


def aggregate_dong(table: str, unit: str = "dong_cd") -> pd.DataFrame:
    """SK 테이블 한 종을 지정 공간 단위 x 월로 합산한다."""
    df = loaders.load_sk(table)
    df = regions.filter_target_sgg(regions.add_region_codes(df))
    cols = _TABLE_COLS[table]
    return df.groupby([unit, "STD_YM"], observed=True)[cols].sum().sort_index()


def build_space_panel(unit: str = "dong_cd") -> pd.DataFrame:
    """3테이블을 지정 공간 단위 x 월로 결합한 wide 패널을 만든다."""
    parts = [aggregate_dong(t, unit=unit) for t in ("age", "time", "wkdy")]
    panel = pd.concat(parts, axis=1)
    if panel.isnull().any().any():
        n = int(panel.isnull().sum().sum())
        raise ValueError(f"패널 결합 후 결측 {n}건 발생 — 단위별 커버리지를 확인할 것")
    return panel.reset_index()
```

`src/features/__init__.py`가 없으면 빈 파일로 만든다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_sk_dong.py -v`
Expected: 7 passed. 18개 파일을 여러 번 읽으므로 3~5분 걸린다.

- [ ] **Step 5: 린트**

Run: `python -m ruff check src/features/sk_dong.py tests/test_sk_dong.py`

---

## Task 6: 카드 집단축 패널 (지역×성×연령×월)

**Files:**
- Create: `src/features/card_cohort.py`
- Test: `tests/test_card_cohort.py`

**Interfaces:**
- Consumes: `loaders.load_card`
- Produces:
  - `EXCLUDED_RY: tuple[str, str] = ("ZZ_나머지", "세금공과금")`
  - `SOCIAL_RY: tuple[str, ...]` — 대면 관계 소비 12종
  - `prepare_card(dataset: int = 2) -> pd.DataFrame` — `ym`, `age_band`(int), `is_social`, `is_excluded` 추가
  - `cohort_panel(df: pd.DataFrame) -> pd.DataFrame` — 컬럼 `["MCT_SGG_CD","SEX_CCD","age_band","ym","amount","count","amount_ex","count_ex","social_amount","social_count","n_ry","local_count"]`
  - `truncation_stats(df: pd.DataFrame, by: list[str]) -> pd.DataFrame` — 비식별 컷 편향 추정용

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_card_cohort.py`:

```python
"""카드 집단축 패널 테스트."""

import pandas as pd

from src.features import card_cohort


def test_social_categories_all_exist_in_data():
    df = card_cohort.prepare_card(2)
    present = set(df["MCT_RY_CD"])
    assert set(card_cohort.SOCIAL_RY) <= present
    assert len(card_cohort.SOCIAL_RY) == 12


def test_excluded_categories_are_half_the_amount():
    df = card_cohort.prepare_card(2)
    share = df.loc[df["is_excluded"], "TS_AT"].sum() / df["TS_AT"].sum()
    assert 0.48 < share < 0.51  # 실측 49.58%


def test_age_band_parses_space_format():
    df = card_cohort.prepare_card(2)
    assert df["age_band"].between(10, 90).all()
    assert sorted(df["age_band"].unique()) == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_ym_derived_from_ta_ymd():
    df = card_cohort.prepare_card(2)
    assert sorted(df["ym"].unique()) == [
        "202507", "202508", "202509", "202510", "202511", "202512",
    ]


def test_cohort_panel_shape():
    panel = card_cohort.cohort_panel(card_cohort.prepare_card(2))
    # 2지역 x 2성별 x 9연령 x 6개월 = 216, 빈 조합이 있을 수 있어 이하
    assert len(panel) <= 216
    assert panel["MCT_SGG_CD"].nunique() == 2
    assert panel["SEX_CCD"].nunique() == 2
    assert panel["age_band"].nunique() == 9
    for c in ("amount", "count", "amount_ex", "social_amount", "n_ry", "local_count"):
        assert c in panel.columns


def test_amount_ex_is_smaller_than_amount():
    panel = card_cohort.cohort_panel(card_cohort.prepare_card(2))
    assert (panel["amount_ex"] <= panel["amount"]).all()
    assert panel["amount_ex"].sum() < panel["amount"].sum()


def test_panel_total_matches_raw_total():
    df = card_cohort.prepare_card(2)
    panel = card_cohort.cohort_panel(df)
    assert panel["amount"].sum() == df["TS_AT"].sum()
    assert panel["count"].sum() == df["USE_CNT"].sum()


def test_truncation_stats_reports_near_cut_share():
    df = card_cohort.prepare_card(2)
    stats = card_cohort.truncation_stats(df, by=["age_band"])
    assert len(stats) == 9
    assert stats["near_cut_share"].between(0, 1).all()
    assert (stats["n_cells"] > 0).all()
    # 90대가 10대보다 절단 근접도가 높을 것으로 예상되나 단정하지 않는다
    assert "observed_combos" in stats.columns


def test_local_count_only_meaningful_for_chuncheon():
    # 강남은 CLN_SGG_CD가 시도 단위라 강남구민을 식별할 수 없다
    assert card_cohort.LOCAL_SIDO == {"강원 춘천시": "강원"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_card_cohort.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/features/card_cohort.py`:

```python
"""신한카드 데이터2를 집단축 패널(지역 x 성 x 연령 x 월)로 집계한다.

카드에는 시군구 2종밖에 없어 SK의 동 단위와 결합할 수 없다.
따라서 공간축과 분리해 집단축 지표만 만든다.
"""

import numpy as np
import pandas as pd

from src.data import loaders

# 금액의 49.6%를 차지하는 미분류·비소비 업종. 금액 지표에서 제외한다.
EXCLUDED_RY = ("ZZ_나머지", "세금공과금")

# 대면 관계 소비 12종. 혼자서도 이용하는 편의·의료 업종은 제외했다.
SOCIAL_RY = (
    "한식",
    "기타요식",
    "커피전문점",
    "제과점",
    "미용실",
    "헬스장",
    "노래방",
    "영화/공연",
    "싸우나/목욕탕",
    "스포츠시설",
    "게임방/오락실",
    "독서실",
)

# CLN_SGG_CD는 시도 단위다. 강남구 가맹점의 '서울' 고객은 강남구민인지 알 수 없으므로
# 지역민 비중은 춘천에 대해서만 근사치로 쓴다.
LOCAL_SIDO = {"강원 춘천시": "강원"}

COHORT_KEYS = ["MCT_SGG_CD", "SEX_CCD", "age_band", "ym"]


def prepare_card(dataset: int = 2) -> pd.DataFrame:
    """카드 원본에 파생 컬럼을 붙인다."""
    df = loaders.load_card(dataset)
    df["ym"] = df["TA_YMD"].str[:6]
    # AGE_CCD는 "10 대" 형태로 숫자와 '대' 사이에 공백이 있다
    df["age_band"] = df["AGE_CCD"].str.extract(r"(\d+)", expand=False).astype("int64")
    df["is_social"] = df["MCT_RY_CD"].isin(SOCIAL_RY)
    df["is_excluded"] = df["MCT_RY_CD"].isin(EXCLUDED_RY)
    df["is_local"] = [
        LOCAL_SIDO.get(sgg) == cln
        for sgg, cln in zip(df["MCT_SGG_CD"], df["CLN_SGG_CD"], strict=True)
    ]
    return df


def cohort_panel(df: pd.DataFrame) -> pd.DataFrame:
    """집단축 패널을 만든다. amount_ex는 미분류·비소비 업종을 뺀 금액이다."""
    keep = ~df["is_excluded"]
    out = (
        df.groupby(COHORT_KEYS, observed=True)
        .agg(
            amount=("TS_AT", "sum"),
            count=("USE_CNT", "sum"),
            n_ry=("MCT_RY_CD", "nunique"),
        )
        .join(
            df[keep]
            .groupby(COHORT_KEYS, observed=True)
            .agg(amount_ex=("TS_AT", "sum"), count_ex=("USE_CNT", "sum"))
        )
        .join(
            df[df["is_social"]]
            .groupby(COHORT_KEYS, observed=True)
            .agg(social_amount=("TS_AT", "sum"), social_count=("USE_CNT", "sum"))
        )
        .join(
            df[df["is_local"]]
            .groupby(COHORT_KEYS, observed=True)
            .agg(local_count=("USE_CNT", "sum"))
        )
        .fillna(0)
        .reset_index()
    )
    for c in ("amount_ex", "count_ex", "social_amount", "social_count", "local_count"):
        out[c] = out[c].astype("int64")
    return out


def truncation_stats(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """비식별 컷(USE_CNT >= 5) 편향을 간접 추정한다.

    near_cut_share  등장한 셀 중 USE_CNT가 5~9에 몰린 비율. 높을수록 절단에 가깝다.
    observed_combos 실제 등장한 (업종 x 거주지) 조합 수
    combo_coverage  가능한 조합 수 대비 등장 비율. 낮을수록 많이 지워졌다.
    """
    n_ry = df["MCT_RY_CD"].nunique()
    n_cln = df["CLN_SGG_CD"].nunique()
    possible = n_ry * n_cln

    g = df.groupby(by, observed=True)
    stats = pd.DataFrame(
        {
            "n_cells": g.size(),
            "near_cut_share": g["USE_CNT"].apply(lambda s: float((s <= 9).mean())),
            "median_use_cnt": g["USE_CNT"].median(),
            "observed_combos": g.apply(
                lambda d: d.groupby(["MCT_RY_CD", "CLN_SGG_CD"], observed=True).ngroups,
                include_groups=False,
            ),
        }
    )
    stats["combo_coverage"] = stats["observed_combos"] / possible
    return stats.reset_index()
```

`np`를 쓰지 않으면 import를 지운다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_card_cohort.py -v`
Expected: 9 passed

- [ ] **Step 5: 린트**

Run: `python -m ruff check src/features/card_cohort.py tests/test_card_cohort.py`

---

## Task 7: 4축 지표와 합성 지수

**Files:**
- Create: `src/features/isolation.py`
- Test: `tests/test_isolation.py`

**Interfaces:**
- Consumes: `sk_dong.AGE_COLS/TIME_COLS/WKDY_COLS/NIGHT_COLS/SENIOR_COLS`
- Produces:
  - `space_indicators(panel: pd.DataFrame) -> pd.DataFrame` — 컬럼 `["dong_cd","wkdy_cv","time_entropy","night_share","peak_ratio","senior_share","total"]`
  - `cohort_indicators(panel: pd.DataFrame) -> pd.DataFrame` — 컬럼 `[...keys, "social_share","amount_per_use","ry_diversity"]`
  - `minmax(s: pd.Series, invert: bool = False) -> pd.Series`
  - `composite(frame: pd.DataFrame, cols: list[str], weights: dict[str, float] | None = None) -> pd.Series`
  - `sensitivity(frame, cols, n_trials=200, pct=0.2, seed=42) -> pd.DataFrame` — 컬럼 `["rank_mean","rank_std","rank_min","rank_max"]`
  - `DISCLAIMER: str`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_isolation.py`:

```python
"""4축 지표와 합성 지수 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import isolation


def test_minmax_basic_range():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = isolation.minmax(s)
    assert out.min() == 0.0
    assert out.max() == 1.0
    assert out.iloc[1] == pytest.approx(1 / 3)


def test_minmax_invert_flips_direction():
    s = pd.Series([1.0, 2.0, 3.0])
    out = isolation.minmax(s, invert=True)
    assert out.iloc[0] == 1.0
    assert out.iloc[-1] == 0.0


def test_minmax_constant_series_returns_zeros():
    s = pd.Series([5.0, 5.0, 5.0])
    out = isolation.minmax(s)
    assert (out == 0.0).all()


def test_composite_equal_weights_is_mean():
    df = pd.DataFrame({"a": [0.0, 1.0], "b": [1.0, 0.0]})
    out = isolation.composite(df, ["a", "b"])
    assert out.tolist() == [0.5, 0.5]


def test_composite_custom_weights_normalized():
    df = pd.DataFrame({"a": [0.0, 1.0], "b": [1.0, 0.0]})
    out = isolation.composite(df, ["a", "b"], weights={"a": 3.0, "b": 1.0})
    assert out.iloc[0] == pytest.approx(0.25)
    assert out.iloc[1] == pytest.approx(0.75)


def test_composite_rejects_out_of_range_input():
    df = pd.DataFrame({"a": [0.0, 2.0], "b": [1.0, 0.0]})
    with pytest.raises(ValueError, match="0~1"):
        isolation.composite(df, ["a", "b"])


def test_sensitivity_is_reproducible():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.random((20, 3)), columns=["a", "b", "c"])
    r1 = isolation.sensitivity(df, ["a", "b", "c"], n_trials=50, seed=42)
    r2 = isolation.sensitivity(df, ["a", "b", "c"], n_trials=50, seed=42)
    pd.testing.assert_frame_equal(r1, r2)
    assert set(r1.columns) == {"rank_mean", "rank_std", "rank_min", "rank_max"}
    assert len(r1) == 20


def test_space_indicators_columns_and_range():
    from src.features import sk_dong

    panel = sk_dong.build_space_panel()
    ind = isolation.space_indicators(panel)
    assert ind["dong_cd"].nunique() == 47
    for c in ("wkdy_cv", "time_entropy", "night_share", "peak_ratio", "senior_share"):
        assert c in ind.columns
        assert ind[c].notna().all()
    assert ind["night_share"].between(0, 1).all()
    assert ind["senior_share"].between(0, 1).all()
    # 24개 구간 균등분포의 엔트로피 상한은 log(24)
    assert (ind["time_entropy"] <= np.log(24) + 1e-9).all()


def test_cohort_indicators_columns():
    from src.features import card_cohort

    panel = card_cohort.cohort_panel(card_cohort.prepare_card(2))
    ind = isolation.cohort_indicators(panel)
    for c in ("social_share", "amount_per_use", "ry_diversity"):
        assert c in ind.columns
    assert ind["social_share"].between(0, 1).all()
    assert (ind["amount_per_use"] > 0).all()


def test_disclaimer_mentions_unvalidated():
    assert "외부검증" in isolation.DISCLAIMER
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_isolation.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/features/isolation.py`:

```python
"""고립 신호 후보 4축 지표와 합성 지수.

방향성 외부검증 전 단계이므로 순위를 고립 위험도로 확정 해석하지 않는다.
n=47에서 요인분석은 성립하지 않아 동등가중 합산 + 민감도 분석을 쓴다.
"""

import numpy as np
import pandas as pd

from src.features.sk_dong import AGE_COLS, NIGHT_COLS, SENIOR_COLS, TIME_COLS, WKDY_COLS

DISCLAIMER = (
    "본 지수는 방향성 외부검증 전 단계다. "
    "동별·집단별 순위를 고립 위험도로 확정 해석하지 않는다."
)


def minmax(s: pd.Series, invert: bool = False) -> pd.Series:
    """min-max 정규화. invert=True면 작은 값이 1이 된다(위험 방향 정렬용)."""
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    out = (s - lo) / (hi - lo)
    return 1.0 - out if invert else out


def _entropy(row: np.ndarray) -> float:
    """비중 벡터의 섀넌 엔트로피. 합이 0이면 0을 반환한다."""
    total = row.sum()
    if total <= 0:
        return 0.0
    p = row / total
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def space_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """공간축 지표를 동 단위로 산출한다. 월별 값을 평균해 동당 1행으로 만든다."""
    df = panel.copy()
    wkdy = df[WKDY_COLS]
    time = df[TIME_COLS]

    df["total"] = df[AGE_COLS].sum(axis=1)
    # 사회활동: 요일간 변동계수가 낮으면 생활 리듬 변화가 적다
    df["wkdy_cv"] = wkdy.std(axis=1, ddof=0) / wkdy.mean(axis=1)
    # 사회활동: 시간대 분포 엔트로피가 낮으면 활동 시간대가 한쪽에 쏠려 있다
    df["time_entropy"] = [_entropy(r) for r in time.to_numpy()]
    # 고립형 생활: 야간 유동 비중
    df["night_share"] = time[NIGHT_COLS].sum(axis=1) / time.sum(axis=1)
    # 고립형 생활: 주간 피크 대비 일평균 비
    df["peak_ratio"] = time.mean(axis=1) / time.max(axis=1)
    df["senior_share"] = df[SENIOR_COLS].sum(axis=1) / df["total"]

    cols = ["wkdy_cv", "time_entropy", "night_share", "peak_ratio", "senior_share", "total"]
    return df.groupby("dong_cd", observed=True)[cols].mean().reset_index()


def cohort_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """집단축 지표를 산출한다. 월별 값을 합산해 집단당 1행으로 만든다."""
    keys = ["MCT_SGG_CD", "SEX_CCD", "age_band"]
    g = panel.groupby(keys, observed=True).agg(
        amount_ex=("amount_ex", "sum"),
        count_ex=("count_ex", "sum"),
        social_amount=("social_amount", "sum"),
        n_ry=("n_ry", "max"),
    )
    out = g.reset_index()
    # 사회적 관계: 미분류·비소비 제외 금액 중 대면 관계 소비 비중
    out["social_share"] = out["social_amount"] / out["amount_ex"]
    # 경제적 불안정: 건당 결제액
    out["amount_per_use"] = out["amount_ex"] / out["count_ex"]
    # 경제적 불안정: 업종 다양성
    out["ry_diversity"] = out["n_ry"]
    return out


def composite(
    frame: pd.DataFrame,
    cols: list[str],
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """정규화된 축들을 가중합한다. 입력은 0~1 범위여야 한다."""
    sub = frame[cols]
    if not ((sub >= -1e-9) & (sub <= 1 + 1e-9)).all().all():
        raise ValueError("composite 입력은 0~1 범위로 정규화되어 있어야 한다")
    w = np.array([1.0] * len(cols) if weights is None else [weights[c] for c in cols])
    w = w / w.sum()
    return pd.Series(sub.to_numpy() @ w, index=frame.index)


def sensitivity(
    frame: pd.DataFrame,
    cols: list[str],
    n_trials: int = 200,
    pct: float = 0.2,
    seed: int = 42,
) -> pd.DataFrame:
    """가중치를 +-pct 범위에서 흔들어 순위 안정성을 본다."""
    rng = np.random.default_rng(seed)
    base = np.ones(len(cols))
    ranks = np.empty((n_trials, len(frame)))
    values = frame[cols].to_numpy()
    for i in range(n_trials):
        w = base * rng.uniform(1 - pct, 1 + pct, size=len(cols))
        w = w / w.sum()
        score = values @ w
        ranks[i] = pd.Series(score).rank(ascending=False).to_numpy()
    return pd.DataFrame(
        {
            "rank_mean": ranks.mean(axis=0),
            "rank_std": ranks.std(axis=0),
            "rank_min": ranks.min(axis=0),
            "rank_max": ranks.max(axis=0),
        },
        index=frame.index,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_isolation.py -v`
Expected: 11 passed

- [ ] **Step 5: 전체 테스트 회귀 확인**

Run: `python -m pytest tests/ -v`
Expected: 모든 테스트 통과. 기존 `tests/test_features.py`가 템플릿 더미라면 그대로 통과해야 한다.

---

## Task 8: 노트북 빌드 헬퍼

**Files:**
- Create: `scripts/build_notebook.py`
- Test: 수동 검증 (Task 9에서 실사용으로 확인)

**Interfaces:**
- Consumes: 없음
- Produces:
  - `md(text: str) -> nbformat.NotebookNode`
  - `code(src: str) -> nbformat.NotebookNode`
  - `build(cells: list, out_path: Path, timeout: int = 1800) -> Path` — 노트북을 만들고 실행해 출력까지 저장

- [ ] **Step 1: 구현**

`scripts/build_notebook.py`:

```python
"""노트북을 코드로 생성하고 실행해 출력까지 저장하는 헬퍼.

Jupyter UI 없이 nbformat + nbclient로 처리한다.
"""

from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def md(text: str) -> nbformat.NotebookNode:
    """마크다운 셀을 만든다."""
    return nbformat.v4.new_markdown_cell(text.strip())


def code(src: str) -> nbformat.NotebookNode:
    """코드 셀을 만든다."""
    return nbformat.v4.new_code_cell(src.strip())


def build(cells: list, out_path: Path, timeout: int = 1800) -> Path:
    """셀 목록으로 노트북을 만들고 실행한 뒤 저장한다."""
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python (bigcontest)",
        "language": "python",
        "name": "bigcontest",
    }
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="bigcontest",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
    )
    client.execute()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, out_path)
    return out_path
```

- [ ] **Step 2: 스모크 테스트**

Run:

```bash
python -c "
from pathlib import Path
import sys; sys.path.insert(0, '.')
from scripts.build_notebook import md, code, build
p = build([md('# smoke'), code('print(1+1)')], Path('notebooks/_smoke.ipynb'))
import nbformat
nb = nbformat.read(p, as_version=4)
print('outputs:', nb.cells[1]['outputs'][0]['text'].strip())
"
```

Expected: `outputs: 2`

- [ ] **Step 3: 스모크 파일 삭제**

Run: `python -c "from pathlib import Path; Path('notebooks/_smoke.ipynb').unlink()"`

---

## Task 9: 0단계 노트북 — 데이터 신뢰성

**Files:**
- Create: `scripts/nb_00_integrity.py` (노트북 생성 스크립트)
- Create: `notebooks/260920_EDA_00_data_integrity_taeeunni.ipynb` (생성 결과)
- Create: `reports/260920_data_quality.md`

**Interfaces:**
- Consumes: `src.data.paths`, `src.data.loaders`, `src.data.regions`, `scripts.build_notebook`
- Produces: 실행된 노트북과 품질 리포트

- [ ] **Step 1: 노트북 생성 스크립트 작성**

`scripts/nb_00_integrity.py`는 아래 셀 구성으로 `build()`를 호출한다.

| 셀 | 종류 | 내용 |
|---|---|---|
| 1 | md | `# [EDA] 데이터 신뢰성 점검 — 2026-09-20` + 목적, 선행 문서 링크 |
| 2 | code | `sys.path` 설정, import, `setup_style()` |
| 3 | md | `## 1. 파일 인벤토리` |
| 4 | code | `paths.list_raw_files()` 출력, 총 용량 |
| 5 | code | 20개 파일 BOM·디코딩·구분자 판별 루프 출력 |
| 6 | md | `## 2. 12월 중복 배포` |
| 7 | code | `loaders.dedupe_report()` 출력, `dropped>0` 필터, 합계 2,101,675 → 1,887,863 |
| 8 | code | 12월 `time`의 PK별 등장 횟수 분포로 "정확히 2회" 입증 |
| 9 | md | `## 3. 스키마 검증` |
| 10 | code | 3테이블 컬럼·dtype·null, 카드 2종 컬럼·null·숫자변환 |
| 11 | md | `## 4. BLOCK_CD 해독` |
| 12 | code | `add_region_codes` 후 시군구별 격자수·중심 위경도·면적 |
| 13 | code | 강남·춘천 행정동 수 22·25 확인, 경계 격자 60행 제외 |
| 14 | md | `## 5. 값의 구조` |
| 15 | code | 0.0254 양자 전수 검정 (|k·q−v| ≤ 0.005), 최소 양수 0.03 |
| 16 | md | `## 6. 확정된 처리 규칙` + 3.3절 표 |
| 17 | md | `## 핵심 발견` 3줄 요약 |

각 code 셀은 `print()`와 `display()`로 결과를 남긴다. 이모지를 쓰지 않는다.

- [ ] **Step 2: 노트북 생성·실행**

Run: `python scripts/nb_00_integrity.py`
Expected: `notebooks/260920_EDA_00_data_integrity_taeeunni.ipynb` 생성, 예외 없음

- [ ] **Step 3: 출력 검증**

Run:

```bash
python -c "
import nbformat
nb = nbformat.read('notebooks/260920_EDA_00_data_integrity_taeeunni.ipynb', as_version=4)
err = [c for c in nb.cells if any(o.get('output_type')=='error' for o in c.get('outputs',[]))]
print('cells:', len(nb.cells), 'errors:', len(err))
assert not err
"
```

Expected: `errors: 0`

- [ ] **Step 4: 품질 리포트 작성**

`reports/260920_data_quality.md`를 `.claude/rules/04_output_format.md` 형식으로 쓴다.
H1은 `# [EDA] 데이터 품질 리포트 — 2026-09-20`. 다음 내용을 포함한다.

- 12월 중복 배포: 행수 표, 처리 방법, 대회 문의 필요성
- 비식별 컷 `USE_CNT >= 5`: 영향 방향 (고립 위험군이 사라지는 방향)
- `ZZ_나머지` + `세금공과금` 49.58%: 금액 지표 설계 시 제외
- 격자 커버리지 불일치: 행 21.2% vs 정보량 0.021%, 동 집계 시 소멸
- 0의 정체: 0.0254 양자, 마스킹 아닐 가능성
- 문서 정정 8건 표

---

## Task 10: 1단계 노트북 — 구조·품질 EDA

**Files:**
- Create: `scripts/nb_01_quality.py`
- Create: `notebooks/260920_EDA_01_quality_taeeunni.ipynb`
- Create: `reports/260920_eda_01_quality.md`

**Interfaces:**
- Consumes: Task 1~8의 모든 모듈
- Produces: 비식별 컷 편향 정량화 결과

- [ ] **Step 1: 노트북 생성 스크립트 작성**

| 셀 | 내용 |
|---|---|
| md | `# [EDA] 구조·품질 분석 — 2026-09-20` |
| code | import, 패널 로드 |
| md | `## 1. 0값의 정체` |
| code | 0.0254 양자 증거 3종: 전수 잔차 검정, TIME 전칸0 격자 0행, AGE0∧WKDY>0 0행 |
| code | 0칸 개수별 `age_sum − time_sum` 격차 표 + 반올림 오차 한계선 비교 |
| md | `## 2. 격자 소실 편향` |
| code | 테이블별 소실 격자수·비율·유동량 비중 표 |
| code | 소실 vs 유지 격자 유동인구 분포 비교 (로그 스케일 히스토그램) |
| code | 행정동별 소실률 상위 10 + 동 단위 집계 시 차이 0 입증 |
| md | `## 3. 비식별 컷 편향 정량화` |
| code | `truncation_stats(df, by=["age_band"])` — 연령별 절단 근접도·조합 커버리지 |
| code | `truncation_stats(df, by=["MCT_SGG_CD"])`, `by=["MCT_RY_CD"]` 상위/하위 |
| code | 연령 x 지역 히트맵 (`near_cut_share`) |
| md | `## 4. 시계열 무결성` |
| code | SK 월별 격자수 추이 그래프 |
| code | 카드 일별 행수·금액·건수 시계열 + 요일 효과 박스플롯 |
| code | 공휴일 후보 탐지 (행수 하위 10일) |
| md | `## 5. 분포 구조` |
| code | 동별 총유동 로그 분포, 상위 1% 격자 점유율, 강남 집중도 |
| md | `## 핵심 발견` 3줄 |

모든 그래프에 제목·축 레이블·범례를 넣고 `PALETTE`를 쓴다.

- [ ] **Step 2: 노트북 생성·실행**

Run: `python scripts/nb_01_quality.py`
Expected: 예외 없음

- [ ] **Step 3: 출력 검증**

Run: Task 9 Step 3과 동일한 검증 스크립트를 `260920_EDA_01_quality_taeeunni.ipynb`에 적용
Expected: `errors: 0`

- [ ] **Step 4: 리포트 작성**

`reports/260920_eda_01_quality.md` — H1 `# [EDA] 구조·품질 분석 — 2026-09-20`.
핵심 발견 3가지 이내, 수치 요약 표, 해석 2~3문장, 권장 다음 단계.

---

## Task 11: 2단계 노트북 — 지역·인구 프로파일링

**Files:**
- Create: `scripts/nb_02_profiling.py`
- Create: `notebooks/260920_EDA_02_profiling_taeeunni.ipynb`
- Create: `reports/260920_eda_02_profiling.md`

**Interfaces:**
- Consumes: `sk_dong.build_space_panel`, `card_cohort.cohort_panel`, `isolation.space_indicators`
- Produces: 동별 프로파일과 시간대 군집 라벨

- [ ] **Step 1: 노트북 생성 스크립트 작성**

| 셀 | 내용 |
|---|---|
| md | `# [EDA] 지역·인구 프로파일링 — 2026-09-20` |
| code | import, 공간축·집단축 패널 로드 |
| md | `## 1. 강남 vs 춘천 대조` |
| code | 시군구별 연령 구성 비중 막대 (남녀 12구간) |
| code | 시군구별 24시간 프로파일 선그래프 (총량 정규화) |
| code | 시군구별 요일 프로파일 |
| md | `## 2. 고령층 비중` |
| code | 동별 `senior_share` 상위 15 표 + 막대 |
| code | 좌표 산점도 — 색상 `senior_share`, 강남·춘천 별도 패널 |
| md | `## 3. 시간대 패턴 군집` |
| code | 동 47개 × 24시간 비중 행렬 표준화 → `KMeans(random_state=42)` k=2..6 실루엣 |
| code | 선택된 k로 군집, 군집별 평균 프로파일 그래프, 군집별 동 목록 |
| md | `## 4. 카드 집단 프로파일` |
| code | 지역×성×연령별 `social_share`, `amount_per_use`, `ry_diversity` 히트맵 |
| code | 연령별 업종 구성 상위 10 (미분류·비소비 제외) |
| md | `## 5. 외지인 비중` |
| code | 춘천 `강원` 거주 비중 — 연령·성별. 강남은 산출 불가 사유 명시 |
| md | `## 핵심 발견` 3줄 |

- [ ] **Step 2: 노트북 생성·실행**

Run: `python scripts/nb_02_profiling.py`

- [ ] **Step 3: 출력 검증**

Run: Task 9 Step 3과 동일한 검증
Expected: `errors: 0`

- [ ] **Step 4: 리포트 작성**

`reports/260920_eda_02_profiling.md`

---

## Task 12: 3단계 노트북 — 고립 신호 후보

**Files:**
- Create: `scripts/nb_03_isolation.py`
- Create: `notebooks/260920_EDA_03_isolation_signals_taeeunni.ipynb`
- Create: `reports/260920_eda_03_isolation_signals.md`

**Interfaces:**
- Consumes: `isolation` 전체
- Produces: 동별 공간 위험 순위, 집단별 위험 순위, 민감도·강건성 결과

- [ ] **Step 1: 노트북 생성 스크립트 작성**

| 셀 | 내용 |
|---|---|
| md | `# [EDA] 고립 신호 후보 도출 — 2026-09-20` + `DISCLAIMER` 배너 |
| code | import, 지표 산출 |
| md | `## 1. 축 정의와 방향 가정` + 4축 표 |
| md | `## 2. 공간축 지표` |
| code | `space_indicators` 결과 기술통계 |
| code | 축 간 상관행렬 히트맵 + 0.9 초과 쌍 경고 출력 |
| code | min-max 정규화 후 `composite` → 동별 순위 상위 15 |
| md | `## 3. 민감도 분석` |
| code | `sensitivity(n_trials=200, pct=0.2, seed=42)` → 순위 변동폭 그래프 |
| md | `## 4. 강건성 — 통(10자리) 단위 재현` |
| code | `build_space_panel(unit="tong_cd")` → 동일 절차 → 통 점수를 동으로 평균 → Spearman 순위상관 |
| md | `## 5. 집단축 지표` |
| code | `cohort_indicators` 결과, 정규화, 합성, 집단별 순위 |
| code | 지역×성×연령 히트맵 |
| md | `## 6. 시군구 수준 교차 대조` |
| code | 공간축 평균 점수와 집단축 평균 점수를 시군구 2개에서 나란히 표로 (검정 아님을 명시) |
| md | `## 한계` — 방향성 미검증, n=47, 카드 시도 단위, 0의 의미 |
| md | `## 핵심 발견` 3줄 |

Spearman은 `pandas`의 `Series.corr(other, method="spearman")`으로 계산한다. scipy가 없어도 된다.

- [ ] **Step 2: 노트북 생성·실행**

Run: `python scripts/nb_03_isolation.py`

- [ ] **Step 3: 출력 검증**

Run: Task 9 Step 3과 동일한 검증
Expected: `errors: 0`

- [ ] **Step 4: 리포트 작성**

`reports/260920_eda_03_isolation_signals.md` — 상단에 `DISCLAIMER` 고정.

- [ ] **Step 5: 최종 회귀 확인**

Run: `python -m pytest tests/ -v && python -m ruff check src/ tests/ scripts/ && python -m ruff format --check src/ tests/ scripts/`
Expected: 전부 통과

---

## Self-Review 결과

**스펙 커버리지**

| 스펙 절 | 담당 Task |
|---|---|
| 1.1~1.3 파일·중복 | Task 1, 2, 9 |
| 1.4 BLOCK_CD | Task 3, 9 |
| 1.5~1.6 정합성·커버리지 | Task 5, 10 |
| 1.7 값 구조·0의 정체 | Task 10 |
| 1.8 카드 실측 | Task 2, 6, 9 |
| 2.1 이중 해상도 | Task 5, 6 (분리 구현), Task 12 (시군구 대조) |
| 2.2 `CLN_SGG_CD` 한계 | Task 6 `LOCAL_SIDO`, Task 11 |
| 2.3 라벨 부재 | Task 7 `DISCLAIMER`, Task 12 |
| 2.4 n=47 검정력 | Task 7 `composite`·`sensitivity` |
| 3.2 모듈 구성 | Task 1~7 |
| 3.3 처리 규칙 | Global Constraints + 각 Task |
| 4.1~4.4 단계별 산출 | Task 9~12 |
| 5 산출물 | Task 9~12 |

누락 없음.

**플레이스홀더 스캔**: 없음. 모든 코드 셀에 실제 구현이 들어 있다.
노트북 셀은 표 형식으로 명세했으나 각 행이 구체적 산출물을 지정한다.

**타입 일관성 확인**
- `SK_PK`는 `loaders`에만 정의하고 다른 모듈은 import해 쓴다
- `dong_cd`/`tong_cd`/`sgg_cd` 명칭을 `regions` → `sk_dong` → `isolation` 전체에서 통일
- `AGE_COLS`/`TIME_COLS`/`WKDY_COLS`/`NIGHT_COLS`/`SENIOR_COLS`는 `sk_dong`에 단일 정의, `isolation`이 import
- `amount_ex`/`count_ex`/`social_amount`는 `card_cohort.cohort_panel`이 만들고 `isolation.cohort_indicators`가 소비 — 이름 일치 확인
