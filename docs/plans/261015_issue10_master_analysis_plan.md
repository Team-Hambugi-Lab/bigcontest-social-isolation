# 집계구 마스터 기반 분석용 피처 테이블(#10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 집계구 마스터(`master_sgis2024.csv`, 10,188행 × 491열)를 읽어 열을 정리하고 구성비 피처를 붙인 분석용 테이블 `data/processed/master_analysis.csv`와 열 정의서 `data/processed/master_analysis_dictionary.csv`를 코드 한 번 실행으로 재현 가능하게 만든다.

**Architecture:** 새 모듈 `src/features/master_analysis.py` 하나에 순수 함수로 나눠 담는다.
- 열 선택 → 사업체수 `no_record` 0 처리 → 구성비·플래그 추가 → 정의서 생성 순서로 진행한다.
- 입력 경로 탐색은 기존 `src/data/paths.py`에 `INTERIM_DIR`·`PROCESSED_DIR`와 `master_files()`를 추가해 해결한다. 한글 폴더(`1차 merge`)라 NFD 문제가 있어 glob을 쓴다.
- 마스터 원본은 읽기만 하고, 모든 변환은 새 DataFrame을 반환한다.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest(`requires_data` 마커), uv, ruff.

**Spec:** 별도 spec 문서는 없다. 아래를 spec으로 삼는다.
- GitHub 이슈 #10 본문: 작업 범위, 완료 조건, 산출물 파일명
- 이슈 #6 본문의 2026-10-08 방침: 모집단 1,698개 유지, `ga_sd_005` 결측을 0으로 덮지 않음
- 이슈 #7 공통 규칙: `TOT_OA_CD` 14자리 키, 격자 `NULL`을 임의로 0으로 바꾸지 않음
- 10/11 팀 회의 결정: SGIS 113열 제외

## 계획 작성 중 확인한 사실 (실데이터, 2026-10-15)

| 항목 | 확인 결과 |
|------|------|
| 마스터 | 10,188행 × 491열, `(STD_YM, TOT_OA_CD)` 중복 없음, 1,698개 집계구 × 6개월 |
| SGIS 열 | 297개, 6개월 동안 집계구별로 값이 같다 (2024년 한 시점 값의 반복) |
| SGIS 결측 표현 | 마스터에서는 `no_record`와 `source_na`가 모두 `NaN`이다. 구분하려면 `sgis2024_value_status.csv`(1,698행 × 298열, 값은 `numeric`/`no_record`/`source_na`)가 필요하다 |
| 사업체수 `no_record` | `cp_bnu_*`, `cp2_bnu_*`를 `no_record = 0`으로 합하면 1,698개 집계구 **전부** `to_fa_010`(총사업체수)과 일치한다 |
| 1인가구 `ga_sd_005` | `numeric` 1,639, `no_record` 34, `source_na` 25 (결측 59개 = 이슈 #6의 59개) |
| `*_mean` | 43열. `mean = sum / n_valid`가 10,188행 전부 성립 |
| 변수별 품질 열 | `*_n_valid` 43열 + `*_missing_rate` 43열이 테이블별 대표 열(`{age,hour,weekday}_n_complete`, `*_incomplete_rate`)과 전부 같은 값. `*_n_partial` 3열은 전부 0 |
| SK 미매칭 | `HAS_SK_POINTS = False`인 집계구 3개 × 6개월 = 18행. SK `*_sum`은 `NaN` |
| 소표본 | SK 매칭 집계구 중 `N_GRID <= 2`가 150개(× 6개월 = 900행). 6개월 내내 같은 집계구 |
| 분모 0 | SK 매칭 행 중 시간대·요일·연령 합계가 0인 행은 없음 |

## Global Constraints

- 마스터 원본 CSV 파일과, 함수에 전달된 입력 DataFrame을 수정하지 않는다. 모든 변환 함수는 새 DataFrame을 반환한다.
- 출력 행 수는 10,188행(1,698개 × 6개월)으로 유지한다. SK 미매칭 3개 집계구도 행을 지우지 않는다(이슈 #6).
- 키 `STD_YM`, `TOT_OA_CD`는 문자열(dtype `str`)로 읽고, 출력의 맨 앞 두 열로 둔다.
- 유동인구 피처는 `*_sum`만 쓴다. 구성비는 같은 테이블 안에서만 계산한다(시간대끼리, 요일끼리, 연령끼리).
- 분모가 결측이거나 0이면 구성비는 `NaN`이다. 0이나 `inf`로 두지 않는다.
- `no_record → 0`은 **사업체수 열(`cp_bnu_*`, `cp2_bnu_*`)에만** 적용한다. 다른 SGIS 결측은 `NaN`으로 유지한다.
- SK 품질 열 89개 제외는 팀 확인 전이라 기본값을 끈다(`drop_sk_quality=False`). 켜는 옵션만 제공한다.
- 출력 경로: `data/processed/master_analysis.csv`, `data/processed/master_analysis_dictionary.csv`, UTF-8 CSV.
- 실데이터 의존 테스트는 `@pytest.mark.requires_data`를 붙인다. CI는 `-m "not requires_data"`로 돈다.
- 커밋 메시지는 Conventional Commits, 타입은 영어, 콜론 뒤 설명은 한국어로 쓰고, `Co-Authored-By`를 넣지 않는다(`AGENTS.md`).
- push·PR은 사용자가 요청할 때만 한다.

## Review Focus

- **`no_record → 0` 범위 누수:** 패턴을 넓게 잡으면 `ga_sd_005`(1인가구)나 `in_age_*`의 `no_record`까지 0이 된다. 이슈 #6 방침 위반이다. Task 3의 실데이터 테스트에서 `ga_sd_005` 결측이 59개 집계구 그대로인지 확인한다.
- **SK 미매칭 행의 구성비:** 분모가 `NaN`인 18행에서 `share_*`가 0이나 `inf`가 되면 군집에 잘못 들어간다. Task 4 단위 테스트와 Task 5 실데이터 테스트에서 `NaN`인지 확인한다.
- **입력 DataFrame 변형:** `df[cols] = ...`를 원본에 직접 쓰면 노트북에서 같은 마스터를 재사용할 때 값이 바뀐다. Task 3·5 테스트에서 호출 전후 입력이 같은지 확인한다.
- **키 dtype:** `TOT_OA_CD`를 숫자로 읽으면 14자리가 지수 표기나 float으로 깨지고, `value_status`와의 조인이 실패한다. Task 5 실데이터 테스트에서 길이 14 문자열인지 확인한다.
- **한글 폴더 경로:** `INTERIM_DIR / "1차 merge"`처럼 리터럴로 경로를 만들면 NFD 환경에서 `FileNotFoundError`가 난다. Task 1은 glob으로 찾고, 두 개 이상 매칭되면 오류를 낸다.

---

### Task 1: `paths.py`에 interim·processed 경로와 마스터 파일 탐색 추가

**Files:**
- Modify: `src/data/paths.py` (`CARD_DIR` 정의 아래, 함수 정의 끝)
- Test: `tests/test_paths.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: 기존 `PROJECT_ROOT`
- Produces:
  - `INTERIM_DIR: Path`, `PROCESSED_DIR: Path`
  - `MASTER_FILE_NAMES: dict[str, str]`
  - `master_files(interim_dir: Path = INTERIM_DIR) -> dict[str, Path]`. 키는 `"master"`, `"status"`, `"dictionary"`이다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_paths.py` 끝에 추가

```python
def test_master_files_finds_files_in_any_subfolder(tmp_path):
    sub = tmp_path / "1차 merge"
    sub.mkdir()
    for name in paths.MASTER_FILE_NAMES.values():
        (sub / name).write_text("x")

    found = paths.master_files(tmp_path)

    assert set(found) == {"master", "status", "dictionary"}
    assert found["master"].name == "master_sgis2024.csv"
    assert all(p.exists() for p in found.values())


def test_master_files_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="master_sgis2024.csv"):
        paths.master_files(tmp_path)


def test_master_files_rejects_ambiguous_copies(tmp_path):
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        for name in paths.MASTER_FILE_NAMES.values():
            (tmp_path / folder / name).write_text("x")

    with pytest.raises(FileNotFoundError, match="found 2"):
        paths.master_files(tmp_path)


@pytest.mark.requires_data
def test_master_files_exist_in_interim():
    found = paths.master_files()
    assert all(p.exists() for p in found.values())
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_paths.py -k master_files -v`
Expected: FAIL — `AttributeError: module 'src.data.paths' has no attribute 'MASTER_FILE_NAMES'`

- [ ] **Step 3: 구현** — `src/data/paths.py`

`CARD_DIR = RAW_DIR / "shinhan_card"` 바로 아래에 추가한다.

```python
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

MASTER_FILE_NAMES = {
    "master": "master_sgis2024.csv",
    "status": "sgis2024_value_status.csv",
    "dictionary": "sgis2024_variable_dictionary.csv",
}
```

파일 끝에 추가한다.

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_paths.py -k master_files -v`
Expected: 4 passed (실데이터가 있는 로컬 기준)

- [ ] **Step 5: 커밋**

```bash
git add src/data/paths.py tests/test_paths.py
git commit -m "feat: 집계구 마스터 파일 경로 탐색 함수 추가 (#10)"
```

---

### Task 2: 제외할 열 목록과 제외 사유

**Files:**
- Create: `src/features/master_analysis.py`
- Create: `tests/test_master_analysis.py`

**Interfaces:**
- Consumes: 없음
- Produces (`src/features/master_analysis.py`):
  - 상수: `KEY_COLS`, `SGIS_PREFIX = "SGIS2024_"`
  - `sgis_drop_columns(columns: Iterable[str]) -> list[str]`: SGIS 113열
  - `sk_mean_columns(columns: Iterable[str]) -> list[str]`: `*_mean` 43열
  - `sk_redundant_quality_columns(columns: Iterable[str]) -> list[str]`: 89열
  - `quality_family(column: str) -> str`: `"age"`, `"hour"`, `"weekday"` 중 하나
  - `drop_reasons(columns: Iterable[str], drop_sk_quality: bool = False) -> dict[str, str]`: 제외 열 → 사유

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_master_analysis.py` 새로 만들기

```python
"""집계구 마스터 → 분석용 피처 테이블(이슈 #10) 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import master_analysis as ma

SGIS_SAMPLE = [
    "SGIS2024_cp2_bem_01",  # 제외: 중분류 종사자수
    "SGIS2024_cp_bem_001",  # 제외: 대분류 종사자수
    "SGIS2024_ho_yr_005",  # 유지: 2010년 이전 건축연도 구간
    "SGIS2024_ho_yr_006",  # 제외
    "SGIS2024_ho_yr_020",  # 제외
    "SGIS2024_ga_sd_004",  # 제외: 전부 공백
    "SGIS2024_ga_sd_005",  # 유지: 1인가구
    "SGIS2024_cp2_bnu_35",  # 제외: 대분류와 중복
    "SGIS2024_cp2_bnu_47",  # 유지: 소매업
    "SGIS2024_to_em_020",  # 유지: 총종사자수
]


class TestDropColumns:
    def test_sgis_drop_columns_follows_meeting_decision(self):
        assert ma.sgis_drop_columns(SGIS_SAMPLE) == [
            "SGIS2024_cp2_bem_01",
            "SGIS2024_cp_bem_001",
            "SGIS2024_ho_yr_006",
            "SGIS2024_ho_yr_020",
            "SGIS2024_ga_sd_004",
            "SGIS2024_cp2_bnu_35",
        ]

    def test_sgis_drop_columns_ignores_non_sgis(self):
        assert ma.sgis_drop_columns(["TMST_00_sum", "cp2_bem_01"]) == []

    def test_sk_mean_columns(self):
        cols = ["TMST_00_sum", "TMST_00_mean", "MAN_FLOW_POP_CNT_10G_mean"]
        assert ma.sk_mean_columns(cols) == ["TMST_00_mean", "MAN_FLOW_POP_CNT_10G_mean"]

    def test_sk_redundant_quality_columns_keeps_representatives(self):
        cols = [
            "TMST_00_n_valid",
            "TMST_00_missing_rate",
            "age_n_partial",
            "hour_n_complete",
            "hour_incomplete_rate",
        ]
        assert ma.sk_redundant_quality_columns(cols) == [
            "TMST_00_n_valid",
            "TMST_00_missing_rate",
            "age_n_partial",
        ]

    @pytest.mark.parametrize(
        ("col", "family"),
        [
            ("MAN_FLOW_POP_CNT_60GU_n_valid", "age"),
            ("WMAN_FLOW_POP_CNT_10G_missing_rate", "age"),
            ("TMST_23_n_valid", "hour"),
            ("FLOW_POP_CNT_SUN_missing_rate", "weekday"),
        ],
    )
    def test_quality_family(self, col, family):
        assert ma.quality_family(col) == family

    def test_quality_family_rejects_unknown(self):
        with pytest.raises(ValueError, match="N_GRID"):
            ma.quality_family("N_GRID")

    def test_drop_reasons_excludes_quality_by_default(self):
        cols = ["SGIS2024_ga_sd_004", "TMST_00_mean", "TMST_00_n_valid"]
        assert set(ma.drop_reasons(cols)) == {"SGIS2024_ga_sd_004", "TMST_00_mean"}
        assert set(ma.drop_reasons(cols, drop_sk_quality=True)) == set(cols)
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_master_analysis.py -v`
Expected: FAIL — `ImportError: cannot import name 'master_analysis'`

- [ ] **Step 3: 구현** — `src/features/master_analysis.py` 새로 만들기

```python
"""집계구 마스터(SK 2025.07~12 + SGIS 2024)를 분석용 피처 테이블로 정리한다 (이슈 #10).

마스터 원본은 수정하지 않는다. 열 제외 기준은 10/11 팀 회의 결정(SGIS 113열)과
이슈 #10 본문(`*_mean` 43열, 팀 확인 전인 SK 품질 89열은 옵션)을 따른다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

KEY_COLS = ["STD_YM", "TOT_OA_CD"]
SGIS_PREFIX = "SGIS2024_"

# 10/11 회의 결정: 분석용 사본에서 제외할 SGIS 열(113열)
SGIS_DROP_PATTERNS = (r"cp2_bem_\d+", r"cp_bem_\d+")  # 업종별 종사자수 → to_em_020으로 대체
SGIS_DROP_CODES = frozenset(
    [f"ho_yr_{i:03d}" for i in range(6, 21)]  # 2010~2024 건축연도별 주택수
    + ["ga_sd_004", "in_age_050", "in_age_051", "in_age_081"]  # 전부 공백
    + ["cp2_bnu_35", "cp2_bnu_68", "cp2_bnu_84", "cp2_bnu_85"]  # 대분류 사업체수와 동일
)
SK_PARTIAL_COLS = ("age_n_partial", "hour_n_partial", "weekday_n_partial")


def sgis_drop_columns(columns: Iterable[str]) -> list[str]:
    """10/11 회의에서 분석용 사본에서 빼기로 한 SGIS 열을 입력 순서대로 반환한다."""
    drop = []
    for col in columns:
        if not col.startswith(SGIS_PREFIX):
            continue
        code = col.removeprefix(SGIS_PREFIX)
        if code in SGIS_DROP_CODES or any(re.fullmatch(p, code) for p in SGIS_DROP_PATTERNS):
            drop.append(col)
    return drop


def sk_mean_columns(columns: Iterable[str]) -> list[str]:
    """`sum ÷ n_valid`와 같은 값이라 중복인 SK 평균 열을 반환한다."""
    return [c for c in columns if c.endswith("_mean")]


def sk_redundant_quality_columns(columns: Iterable[str]) -> list[str]:
    """테이블별 대표 품질 열과 값이 같은 변수별 품질 열과, 항상 0인 `*_n_partial` 열.

    같은 SK 테이블 안에서는 격자가 통째로 있거나 없어서(all-or-nothing) 변수별
    `n_valid`·`missing_rate`가 `{age,hour,weekday}_n_complete`·`_incomplete_rate`와 같다.
    """
    return [
        c for c in columns if c.endswith(("_n_valid", "_missing_rate")) or c in SK_PARTIAL_COLS
    ]


def quality_family(column: str) -> str:
    """변수별 SK 열이 속한 원본 테이블(age·hour·weekday)을 반환한다."""
    if column.startswith(("MAN_", "WMAN_")):
        return "age"
    if column.startswith("TMST_"):
        return "hour"
    if column.startswith("FLOW_POP_CNT_"):
        return "weekday"
    raise ValueError(f"not a per-variable SK column: {column}")


def drop_reasons(columns: Iterable[str], drop_sk_quality: bool = False) -> dict[str, str]:
    """분석 테이블에서 뺄 열과 그 사유를 반환한다."""
    columns = list(columns)
    reasons = {c: "SGIS 제외(10/11 회의 결정)" for c in sgis_drop_columns(columns)}
    reasons |= {c: "sum과 중복(mean = sum / n_valid)" for c in sk_mean_columns(columns)}
    if drop_sk_quality:
        reasons |= {
            c: "대표 품질 열과 값이 같거나 항상 0"
            for c in sk_redundant_quality_columns(columns)
        }
    return reasons
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_master_analysis.py -v`
Expected: 10 passed (`test_quality_family`는 parametrize로 4건)

- [ ] **Step 5: 실데이터 검증 테스트 추가** — `tests/test_master_analysis.py` 끝에 추가

```python
@pytest.fixture(scope="module")
def master():
    from src.data import paths

    return pd.read_csv(paths.master_files()["master"], dtype=ma.READ_DTYPES)


@pytest.mark.requires_data
class TestDropColumnsOnMaster:
    def test_counts_match_issue(self, master):
        assert len(ma.sgis_drop_columns(master.columns)) == 113
        assert len(ma.sk_mean_columns(master.columns)) == 43
        assert len(ma.sk_redundant_quality_columns(master.columns)) == 89

    def test_mean_equals_sum_over_n_valid(self, master):
        for col in ma.sk_mean_columns(master.columns):
            base = col.removesuffix("_mean")
            expected = master[f"{base}_sum"] / master[f"{base}_n_valid"]
            assert np.allclose(master[col], expected, equal_nan=True), col

    def test_quality_columns_carry_no_extra_information(self, master):
        for col in ma.sk_redundant_quality_columns(master.columns):
            if col in ma.SK_PARTIAL_COLS:
                assert (master[col] == 0).all(), col
                continue
            family = ma.quality_family(col)
            rep = (
                f"{family}_n_complete"
                if col.endswith("_n_valid")
                else f"{family}_incomplete_rate"
            )
            assert master[col].equals(master[rep]) or np.allclose(
                master[col], master[rep], equal_nan=True
            ), col
```

`READ_DTYPES`는 Task 5에서 정의한다. 이 단계에서는 `src/features/master_analysis.py`의 `SK_PARTIAL_COLS` 아래에 미리 추가한다.

```python
READ_DTYPES = {"STD_YM": str, "TOT_OA_CD": str, "ADM_CD": str, "BASE_DATE": str}
```

- [ ] **Step 6: 실데이터 테스트 확인**

Run: `uv run pytest tests/test_master_analysis.py -v`
Expected: 13 passed

- [ ] **Step 7: 커밋**

```bash
git add src/features/master_analysis.py tests/test_master_analysis.py
git commit -m "feat: 분석용 사본의 제외 열 목록과 사유 정의 (#10)"
```

---

### Task 3: 사업체수 `no_record`를 0으로 처리

**Files:**
- Modify: `src/features/master_analysis.py`
- Test: `tests/test_master_analysis.py`

**Interfaces:**
- Consumes: `SGIS_PREFIX`, `master` fixture(Task 2)
- Produces:
  - `BUSINESS_COUNT_PATTERN = r"cp2?_bnu_\d+"`
  - `business_count_columns(columns: Iterable[str]) -> list[str]`
  - `fill_business_no_record(df: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame`. `status`는 `TOT_OA_CD`와 SGIS 열을 가진 `sgis2024_value_status.csv`다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_master_analysis.py`의 `master` fixture **위**에 추가

```python
def _status_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TOT_OA_CD": ["A", "B"],
            "SGIS2024_cp2_bnu_47": ["no_record", "numeric"],
            "SGIS2024_cp_bnu_001": ["numeric", "no_record"],
            "SGIS2024_ga_sd_005": ["no_record", "source_na"],
        }
    )


class TestFillBusinessNoRecord:
    def _df(self) -> pd.DataFrame:
        # 같은 집계구가 두 달 반복되는 마스터 구조를 흉내 낸다
        return pd.DataFrame(
            {
                "STD_YM": ["202507", "202507", "202508"],
                "TOT_OA_CD": ["A", "B", "A"],
                "SGIS2024_cp2_bnu_47": [np.nan, 3.0, np.nan],
                "SGIS2024_cp_bnu_001": [5.0, np.nan, 5.0],
                "SGIS2024_ga_sd_005": [np.nan, np.nan, np.nan],
            }
        )

    def test_no_record_business_counts_become_zero(self):
        out = ma.fill_business_no_record(self._df(), _status_frame())
        assert out["SGIS2024_cp2_bnu_47"].tolist() == [0.0, 3.0, 0.0]
        assert out["SGIS2024_cp_bnu_001"].tolist() == [5.0, 0.0, 5.0]

    def test_non_business_columns_stay_missing(self):
        out = ma.fill_business_no_record(self._df(), _status_frame())
        assert out["SGIS2024_ga_sd_005"].isna().all()

    def test_input_is_not_modified(self):
        df = self._df()
        before = df.copy()
        ma.fill_business_no_record(df, _status_frame())
        pd.testing.assert_frame_equal(df, before)

    def test_business_count_columns(self):
        cols = ["SGIS2024_cp2_bnu_47", "SGIS2024_cp_bnu_001", "SGIS2024_cp2_bem_01"]
        assert ma.business_count_columns(cols) == cols[:2]
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_master_analysis.py -k FillBusiness -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'fill_business_no_record'`

- [ ] **Step 3: 구현** — `src/features/master_analysis.py`

import 블록을 아래처럼 바꾼다.

```python
import re
from collections.abc import Iterable

import numpy as np
import pandas as pd
```

`SK_PARTIAL_COLS` 아래에 상수를 추가한다.

```python
BUSINESS_COUNT_PATTERN = r"cp2?_bnu_\d+"
```

`drop_reasons` 아래에 함수를 추가한다.

```python
def business_count_columns(columns: Iterable[str]) -> list[str]:
    """업종별 사업체수 SGIS 열(대분류 `cp_bnu_*`, 중분류 `cp2_bnu_*`)을 반환한다."""
    return [
        c
        for c in columns
        if c.startswith(SGIS_PREFIX)
        and re.fullmatch(BUSINESS_COUNT_PATTERN, c.removeprefix(SGIS_PREFIX))
    ]


def fill_business_no_record(df: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """사업체수 열에서 SGIS 원본에 기록이 없는(`no_record`) 값을 0으로 채운다.

    업종별 사업체수를 no_record=0으로 합하면 1,698개 집계구 전부 총사업체수(to_fa_010)와
    일치한다. 그래서 '기록 없음'을 '해당 업종 사업체 없음'으로 본다. 1인가구 등 다른 SGIS
    열의 no_record는 이런 근거가 없어 결측으로 둔다(이슈 #6: ga_sd_005를 0으로 덮지 않음).
    """
    out = df.copy()
    cols = business_count_columns(out.columns)
    no_record = (
        status.set_index("TOT_OA_CD")[cols].reindex(out["TOT_OA_CD"]).eq("no_record").to_numpy()
    )
    out[cols] = np.where(no_record, 0.0, out[cols].to_numpy(dtype=float))
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_master_analysis.py -k FillBusiness -v`
Expected: 4 passed

- [ ] **Step 5: 실데이터 검증 테스트 추가** — `tests/test_master_analysis.py` 끝에 추가

```python
@pytest.fixture(scope="module")
def status():
    from src.data import paths

    return pd.read_csv(paths.master_files()["status"], dtype={"TOT_OA_CD": str})


@pytest.mark.requires_data
class TestFillBusinessNoRecordOnMaster:
    def test_business_sums_match_total_after_fill(self, master, status):
        out = ma.fill_business_no_record(master, status)
        for pattern in (r"^SGIS2024_cp_bnu_\d+$", r"^SGIS2024_cp2_bnu_\d+$"):
            total = out.filter(regex=pattern).sum(axis=1)
            assert np.allclose(total, out["SGIS2024_to_fa_010"]), pattern

    def test_one_person_household_missing_is_kept(self, master, status):
        out = ma.fill_business_no_record(master, status)
        missing = out.loc[out["SGIS2024_ga_sd_005"].isna(), "TOT_OA_CD"].nunique()
        assert missing == 59
```

- [ ] **Step 6: 실데이터 테스트 확인**

Run: `uv run pytest tests/test_master_analysis.py -v`
Expected: 19 passed

- [ ] **Step 7: 커밋**

```bash
git add src/features/master_analysis.py tests/test_master_analysis.py
git commit -m "feat: 사업체수 no_record를 업종 없음(0)으로 처리 (#10)"
```

---

### Task 4: 구성비 피처와 소표본 플래그

**Files:**
- Modify: `src/features/master_analysis.py`
- Test: `tests/test_master_analysis.py`

**Interfaces:**
- Consumes: 마스터 열 `TMST_00_sum`~`TMST_23_sum`, `FLOW_POP_CNT_{MON,TUS,WED,THU,FRI,SAT,SUN}_sum`, `{MAN,WMAN}_FLOW_POP_CNT_{10G,20G,30G,40G,50G,60GU}_sum`, `N_GRID`, `HAS_SK_POINTS`
- Produces:
  - 상수: `HOURS`, `DAWN_HOURS`, `WEEKDAYS`, `WEEKEND`, `AGE_GROUPS`, `SMALL_SAMPLE_MAX_GRID = 2`
  - `add_share_features(df: pd.DataFrame) -> pd.DataFrame`. 아래 40열을 덧붙인 새 DataFrame을 반환한다.
    - `share_hour_00`~`share_hour_23` (24)
    - `share_wkdy_MON`~`share_wkdy_SUN` (7)
    - `share_age_10G`~`share_age_60GU` (6, 남녀 합산. `share_age_60GU`가 이슈의 "60대 이상 비중"이다)
    - `share_dawn`, `share_weekend`, `is_small_sample` (3)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_master_analysis.py`의 `master` fixture **위**에 추가

```python
def _sk_frame() -> pd.DataFrame:
    """SK 매칭 집계구 1행 + 미매칭 1행 + 소표본 1행."""
    rows = {"N_GRID": [10, 0, 2], "HAS_SK_POINTS": [True, False, True]}
    for h in ma.HOURS:
        rows[f"TMST_{h}_sum"] = [1.0, np.nan, 1.0]
    rows["TMST_00_sum"] = [25.0, np.nan, 1.0]  # 첫 행 합계 = 25 + 23 = 48
    for d in ma.WEEKDAYS:
        rows[f"FLOW_POP_CNT_{d}_sum"] = [10.0, np.nan, 1.0]  # 첫 행 합계 = 70
    for g in ma.AGE_GROUPS:
        rows[f"MAN_FLOW_POP_CNT_{g}_sum"] = [5.0, np.nan, 1.0]
        rows[f"WMAN_FLOW_POP_CNT_{g}_sum"] = [5.0, np.nan, 1.0]  # 첫 행 합계 = 60
    return pd.DataFrame(rows)


class TestAddShareFeatures:
    def test_adds_40_columns(self):
        out = ma.add_share_features(_sk_frame())
        assert out.shape[1] == _sk_frame().shape[1] + 40

    def test_shares_sum_to_one_per_table(self):
        out = ma.add_share_features(_sk_frame()).iloc[[0, 2]]
        for prefix in ("share_hour_", "share_wkdy_", "share_age_"):
            assert np.allclose(out.filter(like=prefix).sum(axis=1), 1.0), prefix

    def test_share_values(self):
        out = ma.add_share_features(_sk_frame()).iloc[0]
        assert out["share_hour_00"] == pytest.approx(25 / 48)
        assert out["share_dawn"] == pytest.approx((25 + 5) / 48)
        assert out["share_weekend"] == pytest.approx(2 / 7)
        assert out["share_age_60GU"] == pytest.approx(10 / 60)

    def test_unmatched_row_has_missing_shares_not_zero(self):
        out = ma.add_share_features(_sk_frame()).iloc[1]
        shares = out.filter(like="share_")
        assert shares.isna().all()

    def test_zero_total_gives_missing_share(self):
        df = _sk_frame().iloc[[0]].copy()
        df[[f"TMST_{h}_sum" for h in ma.HOURS]] = 0.0
        out = ma.add_share_features(df)
        assert out.filter(like="share_hour_").isna().all(axis=None)
        assert np.isnan(out["share_dawn"].iloc[0])

    def test_small_sample_flag_only_for_matched_blocks(self):
        out = ma.add_share_features(_sk_frame())
        assert out["is_small_sample"].tolist() == [False, False, True]
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_master_analysis.py -k AddShare -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'HOURS'`

- [ ] **Step 3: 구현** — `src/features/master_analysis.py`

`BUSINESS_COUNT_PATTERN` 아래에 상수를 추가한다.

```python
HOURS = [f"{h:02d}" for h in range(24)]
DAWN_HOURS = HOURS[:6]  # 00~05시
WEEKDAYS = ["MON", "TUS", "WED", "THU", "FRI", "SAT", "SUN"]  # 마스터 표기 그대로(TUS)
WEEKEND = ["SAT", "SUN"]
AGE_GROUPS = ["10G", "20G", "30G", "40G", "50G", "60GU"]
SMALL_SAMPLE_MAX_GRID = 2  # 격자 1~2개짜리 집계구는 비율이 쉽게 튄다
```

`fill_business_no_record` 아래에 함수를 추가한다.

```python
def _shares(values: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """행 합계로 나눈 구성비. 합계가 결측이거나 0이면 결측으로 둔다."""
    total = values.sum(axis=1, min_count=1)
    total = total.where(total > 0)
    return values.div(total, axis=0).set_axis(names, axis=1)


def add_share_features(df: pd.DataFrame) -> pd.DataFrame:
    """시간대·요일·연령 구성비, 새벽·주말 비중, 소표본 플래그를 덧붙인다.

    구성비는 같은 SK 테이블 안에서만 계산한다. 같은 테이블 안에서는 격자가 통째로
    빠지므로 분자와 분모가 같은 격자 집합에서 나온다. SK 미매칭 집계구는 분모가
    결측이라 구성비도 결측이다(0으로 채우지 않는다).
    """
    hour = _shares(
        df[[f"TMST_{h}_sum" for h in HOURS]], [f"share_hour_{h}" for h in HOURS]
    )
    wkdy = _shares(
        df[[f"FLOW_POP_CNT_{d}_sum" for d in WEEKDAYS]], [f"share_wkdy_{d}" for d in WEEKDAYS]
    )
    age_total = pd.DataFrame(
        {
            g: df[f"MAN_FLOW_POP_CNT_{g}_sum"] + df[f"WMAN_FLOW_POP_CNT_{g}_sum"]
            for g in AGE_GROUPS
        }
    )
    age = _shares(age_total, [f"share_age_{g}" for g in AGE_GROUPS])
    extra = pd.DataFrame(
        {
            "share_dawn": hour[[f"share_hour_{h}" for h in DAWN_HOURS]].sum(
                axis=1, min_count=1
            ),
            "share_weekend": wkdy[[f"share_wkdy_{d}" for d in WEEKEND]].sum(
                axis=1, min_count=1
            ),
            "is_small_sample": df["HAS_SK_POINTS"] & (df["N_GRID"] <= SMALL_SAMPLE_MAX_GRID),
        }
    )
    return pd.concat([df, hour, wkdy, age, extra], axis=1)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_master_analysis.py -k AddShare -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add src/features/master_analysis.py tests/test_master_analysis.py
git commit -m "feat: 시간대·요일·연령 구성비와 소표본 플래그 추가 (#10)"
```

---

### Task 5: 분석 테이블·열 정의서 생성과 실행 진입점

**Files:**
- Modify: `src/features/master_analysis.py`
- Test: `tests/test_master_analysis.py`

**Interfaces:**
- Consumes: Task 1 `paths.master_files`, `paths.PROCESSED_DIR` / Task 2 `drop_reasons`, `READ_DTYPES` / Task 3 `fill_business_no_record`, `business_count_columns` / Task 4 `add_share_features`, 상수들
- Produces:
  - `OUTPUT_NAME = "master_analysis.csv"`, `DICTIONARY_NAME = "master_analysis_dictionary.csv"`
  - `build_master_analysis(master: pd.DataFrame, status: pd.DataFrame, drop_sk_quality: bool = False) -> pd.DataFrame`
  - `derived_definition(column: str) -> tuple[str, str]`: (설명, 계산식)
  - `build_dictionary(master_columns: Iterable[str], analysis: pd.DataFrame, sgis_dictionary: pd.DataFrame, drop_sk_quality: bool = False) -> pd.DataFrame`. 열은 `COLUMN, STATUS, SOURCE, DESCRIPTION, FORMULA_OR_REASON`이다.
  - `main(argv: list[str] | None = None) -> None`. 실행은 `uv run python -m src.features.master_analysis [--drop-sk-quality]`로 한다.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_master_analysis.py`의 `master` fixture **위**에 추가

```python
def _mini_master() -> pd.DataFrame:
    sk = _sk_frame().iloc[[0, 1]].reset_index(drop=True)
    meta = pd.DataFrame(
        {
            "STD_YM": ["202507", "202507"],
            "TOT_OA_CD": ["B", "A"],  # 정렬 확인용으로 역순
            "TMST_00_mean": [1.0, np.nan],
            "TMST_00_n_valid": [3, 0],
            "SGIS2024_ga_sd_004": [np.nan, np.nan],
            "SGIS2024_cp2_bnu_47": [np.nan, 2.0],
            "SGIS2024_ga_sd_005": [7.0, np.nan],
        }
    )
    return pd.concat([meta, sk], axis=1)


def _mini_status() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TOT_OA_CD": ["A", "B"],
            "SGIS2024_cp2_bnu_47": ["numeric", "no_record"],
            "SGIS2024_ga_sd_005": ["no_record", "numeric"],
        }
    )


class TestBuildMasterAnalysis:
    def test_drops_agreed_columns_and_keeps_quality_by_default(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status())
        assert "SGIS2024_ga_sd_004" not in out.columns
        assert "TMST_00_mean" not in out.columns
        assert "TMST_00_n_valid" in out.columns

    def test_drop_sk_quality_option(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status(), drop_sk_quality=True)
        assert "TMST_00_n_valid" not in out.columns

    def test_keys_first_and_sorted(self):
        out = ma.build_master_analysis(_mini_master(), _mini_status())
        assert out.columns[:2].tolist() == ma.KEY_COLS
        assert out["TOT_OA_CD"].tolist() == ["A", "B"]

    def test_input_is_not_modified(self):
        master = _mini_master()
        before = master.copy()
        ma.build_master_analysis(master, _mini_status())
        pd.testing.assert_frame_equal(master, before)


class TestBuildDictionary:
    def test_lists_kept_derived_and_dropped_columns(self):
        master = _mini_master()
        out = ma.build_master_analysis(master, _mini_status())
        sgis_dict = pd.DataFrame(
            {
                "OUTPUT_COLUMN": ["SGIS2024_ga_sd_005", "SGIS2024_cp2_bnu_47"],
                "VARIABLE_NAME": ["1인가구", "소매업"],
            }
        )

        d = ma.build_dictionary(master.columns, out, sgis_dict).set_index("COLUMN")

        assert d.columns.tolist() == ["STATUS", "SOURCE", "DESCRIPTION", "FORMULA_OR_REASON"]
        assert set(d.index) == set(out.columns) | {"SGIS2024_ga_sd_004", "TMST_00_mean"}
        assert d.loc["SGIS2024_ga_sd_005", "DESCRIPTION"] == "1인가구"
        assert d.loc["share_hour_00", "STATUS"] == "파생"
        assert d.loc["TMST_00_mean", "STATUS"] == "제외"
        assert "no_record" in d.loc["SGIS2024_cp2_bnu_47", "FORMULA_OR_REASON"]

    def test_derived_definition_rejects_unknown(self):
        with pytest.raises(KeyError):
            ma.derived_definition("TMST_00_sum")
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_master_analysis.py -k "BuildMaster or BuildDictionary" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'build_master_analysis'`

- [ ] **Step 3: 구현** — `src/features/master_analysis.py`

import 블록 맨 위(`import re` 위)에 `import argparse`를 추가하고, `import pandas as pd` 아래에 추가한다.

```python
from src.data import paths
```

`SMALL_SAMPLE_MAX_GRID` 아래에 상수를 추가한다.

```python
OUTPUT_NAME = "master_analysis.csv"
DICTIONARY_NAME = "master_analysis_dictionary.csv"
SK_SOURCE = "SK 유동인구 2025.07~12"
SGIS_SOURCE = "SGIS 집계구 통계 2024"
```

파일 끝에 추가한다.

```python
def build_master_analysis(
    master: pd.DataFrame, status: pd.DataFrame, drop_sk_quality: bool = False
) -> pd.DataFrame:
    """마스터를 분석용 피처 테이블로 정리한다. 입력 마스터는 수정하지 않는다."""
    out = master.drop(columns=list(drop_reasons(master.columns, drop_sk_quality)))
    out = fill_business_no_record(out, status)
    out = add_share_features(out)
    return out.sort_values(KEY_COLS, ignore_index=True)


def derived_definition(column: str) -> tuple[str, str]:
    """파생 열의 (설명, 계산식)을 반환한다."""
    if column.startswith("share_hour_"):
        h = column.removeprefix("share_hour_")
        return f"{h}시 유동인구 구성비", f"TMST_{h}_sum / sum(TMST_00~23_sum)"
    if column.startswith("share_wkdy_"):
        d = column.removeprefix("share_wkdy_")
        return f"{d} 유동인구 구성비", f"FLOW_POP_CNT_{d}_sum / sum(FLOW_POP_CNT_MON~SUN_sum)"
    if column.startswith("share_age_"):
        g = column.removeprefix("share_age_")
        return (
            f"{g} 유동인구 구성비(남녀 합산)",
            f"(MAN+WMAN)_FLOW_POP_CNT_{g}_sum / 남녀 6개 연령대 합계",
        )
    if column == "share_dawn":
        return "새벽(00~05시) 유동인구 비중", "sum(share_hour_00~05)"
    if column == "share_weekend":
        return "주말(토·일) 유동인구 비중", "share_wkdy_SAT + share_wkdy_SUN"
    if column == "is_small_sample":
        return (
            "소표본 집계구(격자 1~2개)",
            f"HAS_SK_POINTS & N_GRID <= {SMALL_SAMPLE_MAX_GRID}",
        )
    raise KeyError(column)


def build_dictionary(
    master_columns: Iterable[str],
    analysis: pd.DataFrame,
    sgis_dictionary: pd.DataFrame,
    drop_sk_quality: bool = False,
) -> pd.DataFrame:
    """분석 테이블의 열 정의서(유지·파생 열 + 제외 열과 사유)를 만든다."""
    names = sgis_dictionary.set_index("OUTPUT_COLUMN")["VARIABLE_NAME"]
    business = set(business_count_columns(analysis.columns))
    rows = []
    for col in analysis.columns:
        if col.startswith(("share_", "is_small_sample")):
            desc, formula = derived_definition(col)
            rows.append((col, "파생", SK_SOURCE, desc, formula))
        elif col.startswith(SGIS_PREFIX):
            rule = "원값, no_record는 0(업종 없음)" if col in business else "원값, 결측 유지"
            rows.append((col, "유지", SGIS_SOURCE, names.get(col, ""), rule))
        elif col.endswith("_sum"):
            rows.append((col, "유지", SK_SOURCE, "집계구 내 격자 유동인구 합계", "원값"))
        else:
            rows.append((col, "유지", "마스터 메타·품질", "", "원값"))
    for col, reason in drop_reasons(master_columns, drop_sk_quality).items():
        source = SGIS_SOURCE if col.startswith(SGIS_PREFIX) else SK_SOURCE
        rows.append((col, "제외", source, names.get(col, ""), reason))
    return pd.DataFrame(
        rows, columns=["COLUMN", "STATUS", "SOURCE", "DESCRIPTION", "FORMULA_OR_REASON"]
    )


def main(argv: list[str] | None = None) -> None:
    """마스터를 읽어 분석 테이블과 열 정의서를 data/processed/에 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--drop-sk-quality",
        action="store_true",
        help="대표 품질 열과 값이 같은 SK 품질 열 89개를 뺀다(팀 확인 후 사용)",
    )
    args = parser.parse_args(argv)

    files = paths.master_files()
    master = pd.read_csv(files["master"], dtype=READ_DTYPES)
    status = pd.read_csv(files["status"], dtype={"TOT_OA_CD": str})
    sgis_dictionary = pd.read_csv(files["dictionary"])

    analysis = build_master_analysis(master, status, args.drop_sk_quality)
    dictionary = build_dictionary(master.columns, analysis, sgis_dictionary, args.drop_sk_quality)

    paths.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(paths.PROCESSED_DIR / OUTPUT_NAME, index=False, encoding="utf-8")
    dictionary.to_csv(paths.PROCESSED_DIR / DICTIONARY_NAME, index=False, encoding="utf-8")
    print(f"saved {OUTPUT_NAME}: {analysis.shape[0]:,} rows x {analysis.shape[1]} cols")
    print(f"saved {DICTIONARY_NAME}: {len(dictionary)} rows")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_master_analysis.py -k "BuildMaster or BuildDictionary" -v`
Expected: 6 passed

- [ ] **Step 5: 실데이터 통합 테스트 추가** — `tests/test_master_analysis.py` 끝에 추가

```python
@pytest.fixture(scope="module")
def analysis(master, status):
    return ma.build_master_analysis(master, status)


@pytest.mark.requires_data
class TestMasterAnalysisOnMaster:
    def test_shape_and_keys(self, analysis):
        assert analysis.shape == (10_188, 375)  # 491 - 113 - 43 + 40
        assert not analysis.duplicated(ma.KEY_COLS).any()
        assert analysis["TOT_OA_CD"].str.len().eq(14).all()
        assert analysis["TOT_OA_CD"].nunique() == 1_698

    def test_drop_sk_quality_shape(self, master, status):
        out = ma.build_master_analysis(master, status, drop_sk_quality=True)
        assert out.shape == (10_188, 286)

    def test_shares_sum_to_one_for_matched_blocks(self, analysis):
        matched = analysis[analysis["HAS_SK_POINTS"]]
        for prefix in ("share_hour_", "share_wkdy_", "share_age_"):
            assert np.allclose(matched.filter(like=prefix).sum(axis=1), 1.0), prefix

    def test_unmatched_blocks_kept_with_missing_shares(self, analysis):
        unmatched = analysis[~analysis["HAS_SK_POINTS"]]
        assert unmatched["TOT_OA_CD"].nunique() == 3
        assert unmatched.filter(like="share_").isna().all(axis=None)

    def test_small_sample_blocks(self, analysis):
        assert analysis.loc[analysis["is_small_sample"], "TOT_OA_CD"].nunique() == 150

    def test_master_not_modified(self, master, status):
        before = master.copy()
        ma.build_master_analysis(master, status)
        pd.testing.assert_frame_equal(master, before)
```

- [ ] **Step 6: 전체 테스트 확인**

Run: `uv run pytest tests/test_master_analysis.py -v`
Expected: 37 passed

- [ ] **Step 7: 커밋**

```bash
git add src/features/master_analysis.py tests/test_master_analysis.py
git commit -m "feat: 집계구 분석 테이블과 열 정의서 생성 진입점 추가 (#10)"
```

---

### Task 6: 산출물 생성, 데이터 카탈로그 갱신, 최종 검증

**Files:**
- Modify: `data/raw/README.md` (`## 생성된 데이터 (data/processed/)` 표에 행 추가)
- Output (git 미추적): `data/processed/master_analysis.csv`, `data/processed/master_analysis_dictionary.csv`

**Interfaces:**
- Consumes: Task 5 `main`
- Produces: 팀이 쓸 분석 테이블 파일 2개

- [ ] **Step 1: 산출물 생성**

Run: `uv run python -m src.features.master_analysis`
Expected:
```
saved master_analysis.csv: 10,188 rows x 375 cols
saved master_analysis_dictionary.csv: 531 rows
```
(정의서 531행 = 유지·파생 375열 + 제외 156열(113 + 43))

- [ ] **Step 2: 저장 파일 재검증** — 다시 읽어 키 dtype과 행 수 확인

Run:
```bash
uv run python -c "import pandas as pd; df = pd.read_csv('data/processed/master_analysis.csv', dtype={'STD_YM': str, 'TOT_OA_CD': str}); print(df.shape, df.columns[:2].tolist(), df['TOT_OA_CD'].str.len().unique())"
```
Expected: `(10188, 375) ['STD_YM', 'TOT_OA_CD'] [14]`

- [ ] **Step 3: 데이터 카탈로그에 행 추가** — `data/raw/README.md`의 `## 생성된 데이터` 표, `sk_통합_집계구/` 행 아래

```markdown
| `master_analysis.csv`, `master_analysis_dictionary.csv`(2026-10-15 생성) | `uv run python -m src.features.master_analysis` (팀 확인 후 SK 품질 89열을 빼려면 `--drop-sk-quality`) | 집계구 × 월 10,188행 × 375열. `data/interim/1차 merge/master_sgis2024.csv`에서 SGIS 113열·`*_mean` 43열을 빼고 시간대·요일·연령 구성비 37열, 새벽·주말 비중, 소표본 플래그를 추가. 정의서에 유지·파생·제외 열과 계산식·사유 기록 | 군집화·회귀·이상치 탐지의 공통 입력(이슈 #10). 마스터 원본은 수정하지 않음 |
```

- [ ] **Step 4: 린트·포맷·전체 테스트**

포맷 검사가 실패하면 먼저 `uv run ruff format src/ tests/`로 고친 뒤 다시 검사한다.

Run:
```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/ -m "not requires_data" -v
uv run pytest tests/ -v
```
Expected: ruff 오류 0건. CI 선택식(`not requires_data`)에서 실데이터 테스트는 deselect되고 나머지는 통과. 전체 테스트 통과(실데이터 로컬 기준). 실패하면 출력 그대로 보고한다.

- [ ] **Step 5: 커밋**

```bash
git add data/raw/README.md
git commit -m "docs: 데이터 카탈로그에 집계구 분석 테이블 산출물 추가 (#10)"
```

- [ ] **Step 6: 사용자에게 보고하고 후속 확인 요청** (자동으로 하지 않는다)
  - 이슈 #10 본문의 "`no_record`는 0"은 **사업체수 열에만** 적용했다. 근거는 총사업체수 일치다. 1인가구 등은 결측 유지. 본문 수정 여부를 확인받는다.
  - SK 품질 89열 제외의 팀 확인 여부 → 확정되면 `--drop-sk-quality`로 다시 생성한다.
  - 팀 Google Drive 업로드와 push·PR 생성은 사용자 요청 시 진행한다.
