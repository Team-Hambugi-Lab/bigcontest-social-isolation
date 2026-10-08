# 진재언 위험지수 5변수 재현과 Cronbach's α 검증 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 진재언 님 보고서에 설명된 5개 위험지수 변수(평탄도·야간비중·주말비·고령비중·추세)를 SK 통합 파일로 독립 재현하고, 방향 정렬 후 Cronbach's α를 계산해 충돌 #2("지수 산출 방법론")를 데이터로 검증한다.

**Architecture:** 격자 단위 SK 통합 파일(`data/raw/sk_통신인구_*_통합.csv`, 이미 생성됨)을 집계구(BLOCK_CD 앞 13자리) × 월 패널로 합산하고, 그 패널에서 5개 변수를 계산해 집계구 단위로 축약한 뒤, 방향을 정렬해 상관행렬 기반 표준화 Cronbach's α를 구한다. 모든 계산 함수는 합성 데이터로만 단위 테스트하여 실데이터 없이도 CI에서 돈다(이번에 발견한 "CI엔 데이터 없음" 문제를 반복하지 않음). 실데이터 실행과 결과 보고는 노트북에서 한다.

**Tech Stack:** Python, pandas, numpy, pytest (기존 저장소 스택과 동일, 신규 의존성 없음)

**Spec:** 진재언 님 Notion 보고서 "사회적 고립 예방 AI 에이전트 — 데이터 탐색 및 분석 설계 보고서" 4장(집계 단위)·6장(신호 추출 설계)·8장(위험 지수 설계). 원 코드는 아직 공유되지 않아 보고서 서술만으로 재구성한다 — 각 함수 docstring에 가정을 명시한다.

## Global Constraints

- 랜덤성 없음 — 시드 불필요
- 숫자 출력은 소수점 3자리(통계), 퍼센트는 1자리로 표시 (프로젝트 `04_output_format` 규칙)
- 원본 데이터는 읽기 전용, 새 파일은 생성하지 않고 노트북 안에서만 계산
- Task 1~4의 모든 테스트는 합성 데이터만 사용한다 — `data/raw/` 실데이터에 의존하는 테스트는 추가하지 않는다 (CI에서 항상 돌아야 함)

## Review Focus

- 집계구 그룹 안의 모든 격자가 특정 테이블(예: 시간대)에서 전부 결측이면 합계가 0이 아니라 결측으로 남아야 한다 — Task 1에서 `min_count=1`로 처리하고 테스트로 고정
- 강남구(11230)·춘천시(32010) 외 시군구 격자가 섞여 있으면 집계구 값이 왜곡된다 — Task 1에서 필터링하고 테스트로 고정
- 집계구가 6개월 중 1개월만 관측되면 추세(회귀 기울기)를 계산할 수 없다 — Task 3에서 NaN을 명시적으로 반환
- 항목 척도가 서로 다르면(0~1 비율 vs 로그 회귀 기울기) 원값 그대로 Cronbach's α를 계산할 때 분산이 큰 항목이 지배한다 — Task 4에서 상관행렬 기반 표준화 공식 사용
- 평탄도·추세는 "낮을수록/감소할수록 위험"이라 부호를 뒤집지 않으면 방향이 거꾸로 해석된다 — Task 4의 `align_risk_direction`에서 처리하고 테스트로 고정

---

## Task 1: 격자 데이터를 집계구×월 패널로 집계

**Files:**
- Create: `src/features/block_panel.py`
- Test: `tests/test_block_panel.py`

**Interfaces:**
- Consumes: `data/raw/sk_통신인구_{월}_통합.csv` 와 동일한 스키마의 DataFrame (`STD_YM`, `BLOCK_CD`, `X_COORD`, `Y_COORD` + 43개 값 컬럼)
- Produces: `aggregate_to_block(df: pd.DataFrame) -> pd.DataFrame` — 컬럼 `["STD_YM", "집계구", *43개 값 컬럼]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""집계구 패널 집계 단위 테스트."""

import pandas as pd

from src.features.block_panel import aggregate_to_block


class TestAggregateToBlock:
    def test_sums_grids_sharing_block_prefix(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["1123051010102000001", "1123051010102000002"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [1.0, 2.0],
            }
        )

        result = aggregate_to_block(df)

        assert len(result) == 1
        assert result.loc[0, "집계구"] == "1123051010102"
        assert result.loc[0, "TMST_00"] == 3.0

    def test_excludes_non_target_sigungu(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507"],
                "BLOCK_CD": ["4111351010102000001"],
                "X_COORD": [1.0],
                "Y_COORD": [1.0],
                "TMST_00": [5.0],
            }
        )

        result = aggregate_to_block(df)

        assert len(result) == 0

    def test_all_missing_group_stays_nan_not_zero(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["1123051010102000001", "1123051010102000002"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [float("nan"), float("nan")],
            }
        )

        result = aggregate_to_block(df)

        assert pd.isna(result.loc[0, "TMST_00"])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_block_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.features.block_panel'`

- [ ] **Step 3: 최소 구현 작성**

```python
"""SK 유동인구 격자 데이터를 집계구(BLOCK_CD 앞 13자리) 단위 월별 패널로 집계.

BLOCK_CD는 보고서(진재언, 2026-09-26)에 따르면 통계청 집계구 코드 체계를
따르며 앞 5자리=시군구, 앞 13자리=집계구다. 원 코드는 공유되지 않아 이
전제를 그대로 가져왔다 — 검증이 필요하면 재언 님 코드와 대조한다.
"""

import pandas as pd

TARGET_SGG_PREFIXES = ("11230", "32010")  # 서울 강남구, 강원 춘천시
BLOCK_LEVEL_DIGITS = 13
KEY_COLS = ["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]


def aggregate_to_block(df: pd.DataFrame) -> pd.DataFrame:
    """격자 단위 SK 통합 데이터를 (기준월, 집계구) 단위로 합산한다.

    강남구·춘천시 외 시군구 접두는 제외한다. 값 컬럼이 그룹 내에서 전부
    결측이면 0이 아니라 결측으로 남긴다(min_count=1).
    """
    is_target = df["BLOCK_CD"].str.startswith(TARGET_SGG_PREFIXES)
    filtered = df.loc[is_target].copy()
    filtered["집계구"] = filtered["BLOCK_CD"].str.slice(0, BLOCK_LEVEL_DIGITS)

    value_cols = [c for c in filtered.columns if c not in (*KEY_COLS, "집계구")]
    grouped = filtered.groupby(["STD_YM", "집계구"], as_index=False)[value_cols].sum(
        min_count=1
    )
    return grouped
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_block_panel.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/features/block_panel.py tests/test_block_panel.py
git commit -m "feat: SK 격자 데이터를 집계구 단위 패널로 집계하는 함수 추가"
```

---

## Task 2: 월별 패널에서 5개 변수 계산

**Files:**
- Create: `src/features/risk_axes_v1.py`
- Test: `tests/test_risk_axes_v1.py`

**Interfaces:**
- Consumes: Task 1의 `aggregate_to_block` 출력과 같은 스키마(집계구×월 패널)
- Produces: `total_flow`, `flatness_cv`, `night_share`, `weekend_ratio`, `elderly_share` — 전부 `(panel: pd.DataFrame) -> pd.Series`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""위험 신호 변수 계산 단위 테스트 (1부: 월별 변수)."""

import pytest
import pandas as pd

from src.features.risk_axes_v1 import (
    elderly_share,
    flatness_cv,
    night_share,
    total_flow,
    weekend_ratio,
)


def _panel_row(**overrides) -> dict:
    row = {f"TMST_{h:02d}": 1.0 for h in range(24)}
    row.update(
        {
            "MAN_FLOW_POP_CNT_10G": 1.0, "MAN_FLOW_POP_CNT_20G": 1.0,
            "MAN_FLOW_POP_CNT_30G": 1.0, "MAN_FLOW_POP_CNT_40G": 1.0,
            "MAN_FLOW_POP_CNT_50G": 1.0, "MAN_FLOW_POP_CNT_60GU": 1.0,
            "WMAN_FLOW_POP_CNT_10G": 1.0, "WMAN_FLOW_POP_CNT_20G": 1.0,
            "WMAN_FLOW_POP_CNT_30G": 1.0, "WMAN_FLOW_POP_CNT_40G": 1.0,
            "WMAN_FLOW_POP_CNT_50G": 1.0, "WMAN_FLOW_POP_CNT_60GU": 1.0,
            "FLOW_POP_CNT_MON": 1.0, "FLOW_POP_CNT_TUS": 1.0,
            "FLOW_POP_CNT_WED": 1.0, "FLOW_POP_CNT_THU": 1.0,
            "FLOW_POP_CNT_FRI": 1.0, "FLOW_POP_CNT_SAT": 1.0,
            "FLOW_POP_CNT_SUN": 1.0,
        }
    )
    row.update(overrides)
    return row


class TestTotalFlow:
    def test_sums_twelve_age_columns(self):
        panel = pd.DataFrame([_panel_row()])
        assert total_flow(panel).iloc[0] == 12.0


class TestFlatnessCv:
    def test_perfectly_flat_profile_is_zero(self):
        panel = pd.DataFrame([_panel_row()])
        assert flatness_cv(panel).iloc[0] == pytest.approx(0.0)

    def test_peaked_profile_has_positive_cv(self):
        row = _panel_row()
        row["TMST_09"] = 100.0
        panel = pd.DataFrame([row])
        assert flatness_cv(panel).iloc[0] > 0.0


class TestNightShare:
    def test_all_activity_at_night_gives_share_one(self):
        row = {f"TMST_{h:02d}": (1.0 if h < 6 else 0.0) for h in range(24)}
        panel = pd.DataFrame([row])
        assert night_share(panel).iloc[0] == pytest.approx(1.0)

    def test_no_night_activity_gives_share_zero(self):
        row = {f"TMST_{h:02d}": (0.0 if h < 6 else 1.0) for h in range(24)}
        panel = pd.DataFrame([row])
        assert night_share(panel).iloc[0] == pytest.approx(0.0)


class TestWeekendRatio:
    def test_equal_weekday_weekend_gives_one(self):
        panel = pd.DataFrame([_panel_row()])
        assert weekend_ratio(panel).iloc[0] == pytest.approx(1.0)

    def test_weekend_double_weekday_gives_two(self):
        row = _panel_row(FLOW_POP_CNT_SAT=2.0, FLOW_POP_CNT_SUN=2.0)
        panel = pd.DataFrame([row])
        assert weekend_ratio(panel).iloc[0] == pytest.approx(2.0)


class TestElderlyShare:
    def test_only_elderly_gives_share_one(self):
        zeroed = {
            c: 0.0
            for c in [
                "MAN_FLOW_POP_CNT_10G", "MAN_FLOW_POP_CNT_20G", "MAN_FLOW_POP_CNT_30G",
                "MAN_FLOW_POP_CNT_40G", "MAN_FLOW_POP_CNT_50G",
                "WMAN_FLOW_POP_CNT_10G", "WMAN_FLOW_POP_CNT_20G", "WMAN_FLOW_POP_CNT_30G",
                "WMAN_FLOW_POP_CNT_40G", "WMAN_FLOW_POP_CNT_50G",
            ]
        }
        panel = pd.DataFrame([_panel_row(**zeroed)])
        assert elderly_share(panel).iloc[0] == pytest.approx(1.0)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.features.risk_axes_v1'`

- [ ] **Step 3: 최소 구현 작성**

```python
"""재언 보고서 재현용 위험 신호 5개 변수 계산.

원 코드가 공유되지 않아 보고서 서술(4·6·8장)만으로 재구성했다. 각 함수의
정의는 docstring에 그대로 남긴다 — 원 코드 확인 전까지는 가정이다.
"""

import numpy as np
import pandas as pd

AGE_COLS = [
    "MAN_FLOW_POP_CNT_10G", "MAN_FLOW_POP_CNT_20G", "MAN_FLOW_POP_CNT_30G",
    "MAN_FLOW_POP_CNT_40G", "MAN_FLOW_POP_CNT_50G", "MAN_FLOW_POP_CNT_60GU",
    "WMAN_FLOW_POP_CNT_10G", "WMAN_FLOW_POP_CNT_20G", "WMAN_FLOW_POP_CNT_30G",
    "WMAN_FLOW_POP_CNT_40G", "WMAN_FLOW_POP_CNT_50G", "WMAN_FLOW_POP_CNT_60GU",
]
ELDERLY_COLS = ["MAN_FLOW_POP_CNT_60GU", "WMAN_FLOW_POP_CNT_60GU"]
TIME_COLS = [f"TMST_{h:02d}" for h in range(24)]
NIGHT_COLS = [f"TMST_{h:02d}" for h in range(0, 6)]
WEEKDAY_COLS = [
    "FLOW_POP_CNT_MON", "FLOW_POP_CNT_TUS", "FLOW_POP_CNT_WED",
    "FLOW_POP_CNT_THU", "FLOW_POP_CNT_FRI",
]
WEEKEND_COLS = ["FLOW_POP_CNT_SAT", "FLOW_POP_CNT_SUN"]


def total_flow(panel: pd.DataFrame) -> pd.Series:
    """성·연령 12칸 합(=해당 행의 월간 총 유동인구)."""
    return panel[AGE_COLS].sum(axis=1)


def flatness_cv(panel: pd.DataFrame) -> pd.Series:
    """시간대 비중(TMST를 그 행의 시간대 합으로 나눈 값)의 변동계수.

    값이 작을수록 평탄(오르내림 없음)하다 — "낮을수록 위험" 방향이다.
    """
    time_total = panel[TIME_COLS].sum(axis=1)
    share = panel[TIME_COLS].div(time_total, axis=0)
    return share.std(axis=1) / share.mean(axis=1)


def night_share(panel: pd.DataFrame) -> pd.Series:
    """야간(00~05시) 유동인구가 하루 시간대 합에서 차지하는 비중."""
    time_total = panel[TIME_COLS].sum(axis=1)
    return panel[NIGHT_COLS].sum(axis=1) / time_total


def weekend_ratio(panel: pd.DataFrame) -> pd.Series:
    """주말(토·일) 평균 ÷ 평일(월~금) 평균."""
    weekday_mean = panel[WEEKDAY_COLS].mean(axis=1)
    weekend_mean = panel[WEEKEND_COLS].mean(axis=1)
    return weekend_mean / weekday_mean


def elderly_share(panel: pd.DataFrame) -> pd.Series:
    """60대 이상(남+여) 유동인구가 성·연령 12칸 합에서 차지하는 비중."""
    return panel[ELDERLY_COLS].sum(axis=1) / total_flow(panel)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/features/risk_axes_v1.py tests/test_risk_axes_v1.py
git commit -m "feat: 재언 보고서의 월별 위험 신호 변수 4종 재현"
```

---

## Task 3: 집계구 단위로 축약 + 추세(로그 회귀 기울기)

**Files:**
- Modify: `src/features/risk_axes_v1.py`
- Modify: `tests/test_risk_axes_v1.py`

**Interfaces:**
- Consumes: Task 2의 4개 변수 함수, Task 1의 `aggregate_to_block` 출력(컬럼 `집계구` 포함)
- Produces: `trend_slope(monthly_log_flow: pd.Series) -> float`, `reduce_to_block_level(panel: pd.DataFrame, months_order: list[str]) -> pd.DataFrame` — 인덱스가 `집계구`이고 컬럼이 `["평탄도", "야간비중", "주말비", "고령비중", "추세"]`인 DataFrame

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_risk_axes_v1.py`에 추가:

```python
from src.features.risk_axes_v1 import reduce_to_block_level, trend_slope


class TestTrendSlope:
    def test_declining_series_has_negative_slope(self):
        series = pd.Series([np.log(100.0), np.log(50.0), np.log(25.0)])
        assert trend_slope(series) < 0

    def test_single_observation_is_nan(self):
        series = pd.Series([np.log(100.0)])
        assert pd.isna(trend_slope(series))


class TestReduceToBlockLevel:
    def test_trend_is_negative_for_declining_flow(self):
        rows = []
        for i, month in enumerate(["202507", "202508", "202509"]):
            scale = 120.0 / (i + 1)
            row = _panel_row(
                **{c: scale / 12 for c in AGE_COLS}
            )
            row["STD_YM"] = month
            row["집계구"] = "B1"
            rows.append(row)
        panel = pd.DataFrame(rows)

        result = reduce_to_block_level(panel, months_order=["202507", "202508", "202509"])

        assert result.loc["B1", "추세"] < 0

    def test_single_month_trend_is_nan(self):
        row = _panel_row()
        row["STD_YM"] = "202507"
        row["집계구"] = "B1"
        panel = pd.DataFrame([row])

        result = reduce_to_block_level(panel, months_order=["202507"])

        assert pd.isna(result.loc["B1", "추세"])
```

파일 상단 import에 `AGE_COLS`도 추가: `from src.features.risk_axes_v1 import (..., AGE_COLS)`.

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: FAIL with `ImportError: cannot import name 'reduce_to_block_level'`

- [ ] **Step 3: 최소 구현 작성**

`src/features/risk_axes_v1.py` 끝에 추가:

```python
def trend_slope(monthly_log_flow: pd.Series) -> float:
    """월 순서(1, 2, 3…) 대비 ln(총유동인구) 회귀 기울기.

    관측치가 2개 미만이면 추세를 추정할 수 없어 NaN을 반환한다.
    """
    valid = monthly_log_flow.dropna()
    if len(valid) < 2:
        return float("nan")
    x = np.arange(1, len(valid) + 1, dtype=float)
    slope, _ = np.polyfit(x, valid.to_numpy(), deg=1)
    return float(slope)


def reduce_to_block_level(panel: pd.DataFrame, months_order: list[str]) -> pd.DataFrame:
    """(기준월, 집계구) 패널에 변수를 계산하고 집계구 단위로 축약한다.

    평탄도·야간비중·주말비·고령비중은 6개월 평균, 추세는 월별
    ln(총유동인구)의 회귀 기울기로 계산한다.
    """
    work = panel.copy()
    work["평탄도"] = flatness_cv(work)
    work["야간비중"] = night_share(work)
    work["주말비"] = weekend_ratio(work)
    work["고령비중"] = elderly_share(work)
    work["ln총유동인구"] = np.log(total_flow(work))

    month_rank = {m: i for i, m in enumerate(months_order)}
    work["_순서"] = work["STD_YM"].map(month_rank)
    work = work.sort_values(["집계구", "_순서"])

    means = work.groupby("집계구")[["평탄도", "야간비중", "주말비", "고령비중"]].mean()
    trends = work.groupby("집계구")["ln총유동인구"].apply(trend_slope)
    trends.name = "추세"

    return means.join(trends)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/features/risk_axes_v1.py tests/test_risk_axes_v1.py
git commit -m "feat: 집계구 단위 변수 축약과 추세(로그 회귀 기울기) 추가"
```

---

## Task 4: 방향 정렬 + 상관행렬 기반 표준화 Cronbach's α

**Files:**
- Modify: `src/features/risk_axes_v1.py`
- Modify: `tests/test_risk_axes_v1.py`

**Interfaces:**
- Consumes: Task 3의 `reduce_to_block_level` 출력(집계구 인덱스, 5개 원값 컬럼)
- Produces: `align_risk_direction(block_level: pd.DataFrame) -> pd.DataFrame`(컬럼 `["평탄도_위험","야간비중_위험","주말비_위험","고령비중_위험","추세_위험"]`), `cronbach_alpha_standardized(items: pd.DataFrame) -> float`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_risk_axes_v1.py`에 추가:

```python
from src.features.risk_axes_v1 import align_risk_direction, cronbach_alpha_standardized


class TestAlignRiskDirection:
    def test_flatness_and_trend_are_negated(self):
        block_level = pd.DataFrame(
            {
                "평탄도": [0.5], "야간비중": [0.3], "주말비": [1.2],
                "고령비중": [0.4], "추세": [-0.1],
            },
            index=pd.Index(["B1"], name="집계구"),
        )

        aligned = align_risk_direction(block_level)

        assert aligned.loc["B1", "평탄도_위험"] == -0.5
        assert aligned.loc["B1", "추세_위험"] == pytest.approx(0.1)
        assert aligned.loc["B1", "야간비중_위험"] == 0.3
        assert aligned.loc["B1", "고령비중_위험"] == 0.4
        assert aligned.loc["B1", "주말비_위험"] == 1.2


class TestCronbachAlphaStandardized:
    def test_perfectly_correlated_items_give_alpha_near_one(self):
        base = np.arange(100, dtype=float)
        items = pd.DataFrame({"a": base, "b": base * 2, "c": base + 5})

        alpha = cronbach_alpha_standardized(items)

        assert alpha == pytest.approx(1.0, abs=1e-6)

    def test_independent_items_give_low_alpha(self):
        rng = np.random.default_rng(42)
        items = pd.DataFrame(
            {
                "a": rng.normal(size=500),
                "b": rng.normal(size=500),
                "c": rng.normal(size=500),
            }
        )

        alpha = cronbach_alpha_standardized(items)

        assert alpha < 0.3

    def test_raises_on_constant_column(self):
        items = pd.DataFrame({"a": [1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0]})

        with pytest.raises(ValueError, match="결측"):
            cronbach_alpha_standardized(items)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: FAIL with `ImportError: cannot import name 'align_risk_direction'`

- [ ] **Step 3: 최소 구현 작성**

`src/features/risk_axes_v1.py` 끝에 추가:

```python
def align_risk_direction(block_level: pd.DataFrame) -> pd.DataFrame:
    """5개 변수를 모두 '높을수록 위험' 방향으로 정렬한다.

    평탄도는 낮을수록 위험(평탄함)이므로 부호를 뒤집는다. 추세는 더 많이
    감소할수록(기울기가 더 음수일수록) 위험이므로 부호를 뒤집는다. 야간비중·
    고령비중은 원값 그대로가 이미 '높을수록 위험'이다. 주말비는 원 보고서에
    구체적 변환식이 없어 원값을 그대로 쓴다 — 이 방향이 맞는지는 충돌 #3과
    직결된 열린 질문이며, 재언 님 코드가 공유되면 반드시 대조해야 한다.
    """
    return pd.DataFrame(
        {
            "평탄도_위험": -block_level["평탄도"],
            "야간비중_위험": block_level["야간비중"],
            "주말비_위험": block_level["주말비"],
            "고령비중_위험": block_level["고령비중"],
            "추세_위험": -block_level["추세"],
        }
    )


def cronbach_alpha_standardized(items: pd.DataFrame) -> float:
    """상관행렬 기반 표준화 Cronbach's α.

    항목 척도가 서로 다르면(0~1 비율 vs 로그 회귀 기울기) 원값을 그대로
    더해 분산을 비교하는 raw-score 공식은 분산이 큰 항목이 지배한다. 평균
    쌍별 상관계수 기반 공식은 척도에 영향받지 않는다.
    alpha = k * mean_r / (1 + (k - 1) * mean_r)
    """
    valid = items.dropna()
    if valid.shape[1] < 2:
        raise ValueError("항목이 2개 미만이면 α를 계산할 수 없습니다.")

    corr = valid.corr()
    k = corr.shape[0]
    off_diagonal = corr.to_numpy()[~np.eye(k, dtype=bool)]
    if np.isnan(off_diagonal).any():
        raise ValueError("상관계수에 결측이 있습니다 — 분산이 0인 항목을 확인하세요.")

    mean_r = off_diagonal.mean()
    return float(k * mean_r / (1 + (k - 1) * mean_r))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: PASS (17 passed)

- [ ] **Step 5: 전체 린트·테스트 확인**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/test_block_panel.py tests/test_risk_axes_v1.py -v
```

Expected: 전부 통과, 포맷 통과

- [ ] **Step 6: 커밋**

```bash
git add src/features/risk_axes_v1.py tests/test_risk_axes_v1.py
git commit -m "feat: 위험 방향 정렬과 표준화 Cronbach's α 계산 추가"
```

---

## Task 5: 실데이터로 실행해 α 결과 보고

**Files:**
- Create: `notebooks/261001_VERIFY_jaejaeon_risk_index_alpha.ipynb`

**Interfaces:**
- Consumes: `data/raw/sk_통신인구_{월}_통합.csv` 6개(Task 1~4의 함수), `src.features.block_panel.aggregate_to_block`, `src.features.risk_axes_v1.*`
- Produces: 노트북 실행 결과(인쇄된 α 값과 상관행렬) — 팀 공유용 산출물, 코드 산출물 없음

- [ ] **Step 1: 노트북 헤더 셀(마크다운) 작성**

```markdown
# [검증] 진재언 위험지수 5변수 재현과 Cronbach's α — 2026-10-01

- 작성자: 이정연 (`ljy`)
- 목적: 충돌 #2(지수 산출 방법론) 검증 — 보고서 서술만으로 5변수를 재현해 Cronbach's α를 독립 계산
- 입력: `data/raw/sk_통신인구_202507~202512_통합.csv` (6개월, outer join 생성본)
- 전제: 집계구=BLOCK_CD 앞 13자리, 대상 시군구=강남구(11230)·춘천시(32010)
- **원 코드 미확인 — 각 변수 정의는 `src/features/risk_axes_v1.py` docstring의 가정을 따름**
- 다루지 않는 범위: 최종 위험지수 가중합, 지역 내부 백분위 정규화, 5분위 구간화
```

- [ ] **Step 2: 데이터 로드·패널 구성 셀**

```python
from pathlib import Path

import pandas as pd

from src.features.block_panel import aggregate_to_block
from src.features.risk_axes_v1 import (
    align_risk_direction,
    cronbach_alpha_standardized,
    reduce_to_block_level,
)

MONTHS = ["202507", "202508", "202509", "202510", "202511", "202512"]

repo_root = Path.cwd()
if not (repo_root / "data" / "raw").exists():
    repo_root = repo_root.parent
raw_dir = repo_root / "data" / "raw"

frames = [
    pd.read_csv(
        raw_dir / f"sk_통신인구_{month}_통합.csv",
        dtype={"STD_YM": "string", "BLOCK_CD": "string"},
    )
    for month in MONTHS
]
combined = pd.concat(frames, ignore_index=True)
print(f"격자×월 전체 행: {len(combined):,}")

panel = aggregate_to_block(combined)
print(f"집계구×월 패널 행: {len(panel):,}, 고유 집계구 수: {panel['집계구'].nunique():,}")
```

- [ ] **Step 3: 변수 계산·방향 정렬·α 계산 셀**

```python
block_level = reduce_to_block_level(panel, months_order=MONTHS)
aligned = align_risk_direction(block_level)

print("집계구 단위 변수 요약:")
print(block_level.describe().round(3))

print("\n방향 정렬 후 상관행렬:")
print(aligned.corr().round(3))

alpha = cronbach_alpha_standardized(aligned)
print(f"\nCronbach's α (표준화, 상관행렬 기반): {alpha:.3f}")
print(f"항목 수: {aligned.shape[1]}, 유효 집계구 수: {aligned.dropna().shape[0]:,}")
```

- [ ] **Step 4: 결론 셀(마크다운) — 실행 후 실제 숫자로 채워 작성**

```markdown
## 결론

- Cronbach's α = <실행 결과 값>
- 0.7 이상이면: 5개 변수가 하나의 개념(고립 위험)을 일관되게 재는 것으로 판단 — 충돌 #2 해소, 진재언 님 지수 설계를 그대로 신뢰 가능
- 0.7 미만이면: 1차 설계(김태은)와 유사한 문제가 있을 가능성 — 어느 변수 쌍이 상관을 깎아먹는지 상관행렬에서 확인 후 재언 님과 공유
- **다음 확인 필요**: 주말비 방향(충돌 #3), 집계구 정의(BLOCK_CD 앞 13자리)를 재언 님 실제 코드와 대조
```

- [ ] **Step 5: 노트북 실행**

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/261001_VERIFY_jaejaeon_risk_index_alpha.ipynb
```

Expected: 에러 없이 완료, 출력 셀에 α 값과 상관행렬이 찍혀 있음

- [ ] **Step 6: 결론 셀을 실제 출력값으로 수정 후 커밋**

```bash
git add notebooks/261001_VERIFY_jaejaeon_risk_index_alpha.ipynb
git commit -m "feat: 재언 위험지수 5변수 재현 및 Cronbach's α 검증 노트북 추가"
```

---

## Self-Review

**Spec coverage:** 4장(집계구=BLOCK_CD 앞 13자리, 격자→집계구 합산) → Task 1. 6장(평탄도=CV, 야간비중, 주말비, 추세=로그회귀기울기) → Task 2·3. 3.2장(고령비중=성연령 합으로 나눔) → Task 2. 8장(방향 정렬, Cronbach's α) → Task 4. 실데이터 검증·보고 → Task 5. 누락 없음.

**Placeholder scan:** 모든 Step에 실제 코드·커맨드 포함. "TBD"·"적절히 처리" 류 없음. Task 5 Step 4만 "실행 결과로 채워 작성"이라 적었는데, 이는 실행 전엔 알 수 없는 숫자이기 때문이며 자리만 비워둔 게 아니라 작성 지침(0.7 기준 분기)을 구체적으로 줬다.

**Type consistency:** `aggregate_to_block`(Task 1) → `reduce_to_block_level`(Task 3)이 기대하는 컬럼(`STD_YM`, `집계구`, 변수 계산에 쓰이는 원본 컬럼들)이 일치. `align_risk_direction`(Task 4)이 기대하는 컬럼명(`평탄도`,`야간비중`,`주말비`,`고령비중`,`추세`)이 `reduce_to_block_level`의 출력 컬럼명과 정확히 일치.

**Review Focus:** 5개 항목 모두 담당 Task에서 테스트로 고정됨(위 Review Focus 절 참고).
