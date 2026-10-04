# 집계구 유동인구-기온 계절성 검증 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 집계구별 월별 SK 유동인구(ln 총유동인구)의 변화가 기온(Open-Meteo ERA5 월평균기온)과 상관있는지 검정해, 12월 유동인구 감소가 계절성(한파) 때문인지 기온과 무관하게 지속되는 악화인지 구분할 1차 근거를 만든다.

**Architecture:** 기존 `block_panel.py`(집계구 공간조인)와 `risk_axes_v1.total_flow`로 집계구×월 ln(유동인구) 패널을 만들고, `기상/` 폴더의 Open-Meteo ERA5 일별 기온을 월평균으로 집계한다. 각 집계구 자신의 6개월 평균 대비 ln유동인구 편차와, 각 지역(서울/춘천) 자신의 6개월 평균 대비 기온 편차를 구해, 지역별로 Spearman 상관을 검정한다. 규모가 다른 집계구를 섞어도 "그 집계구 평소 대비 늘었는지 줄었는지"만 비교하게 되므로 편차로 본다.

**Tech Stack:** Python 3.11, pandas, scipy.stats, pytest. 신규 의존성 없음(scipy는 이미 기본 의존성).

**Spec:** 이 저장소에는 별도 spec 문서가 없다. 아래를 spec으로 삼는다:
- `data/raw/reference_data/기상/2025_기상_자료_수집정보.md` — 기온 데이터의 출처·한계(ERA5는 재분석 격자 추정치, 서울/춘천 지점은 도시권 대리변수)와 "SK 유동인구·카드 소비 감소가 기상 영향으로 설명되는지 검증"이라는 수집 목적
- `notebooks/260923_EDA_external_factors.ipynb` — 선행 분석. 카드·기상·전철을 **지역 단위**(강남 전체 vs 춘천 전체)로 결합했고, "6개월 자료만으로 계절성이나 인과효과를 확정하지 않는다"는 원칙과 "외부 요인 반영 전후의 월별 잔여 소비를 비교한다"는 다음 단계를 남겨뒀다. 이 플랜은 그 다음 단계를 **SK 유동인구 + 집계구 단위**로 수행한다 — 카드 데이터나 지역 전체 지수는 다시 다루지 않는다.
- `src/features/risk_axes_v1.py`의 `trend_slope`/`reduce_to_block_level` — "12월 스냅샷이냐 6개월 평균이냐"는 최근 논의에서, 12월 감소가 한파 때문인지 확인하는 게 이 검증의 직접적인 동기다.

## Global Constraints

- 지역은 서울(강남구 집계구, `TOT_OA_CD` 앞 5자리 `11230`)과 춘천(춘천시 집계구, 앞 5자리 `32010`) 둘로만 나눈다 — `src/data/regions.py`의 `SGG_NAMES` 접두어와 동일한 기준.
- 기상 CSV는 `pd.read_csv(path, skiprows=3)`로 읽는다(앞 2행 격자 메타데이터 + 3번째 행 공백) — `2025_기상_자료_수집정보.md`에 명시된 그대로.
- 기온 컬럼은 `temperature_2m_mean (°C)`를 쓴다(일 평균기온). 강수·적설은 이 플랜에서 다루지 않는다.
- 이 상관검정은 **진단용**이다. 상관계수 하나로 "이건 순수 계절효과다/아니다"를 확정하지 않는다 — 기온도 7월에서 12월로 단조 감소하므로, 유동인구가 기온과 무관한 다른 이유로 단조 감소해도 비슷한 상관이 나올 수 있다. 결론 셀에 이 한계를 반드시 명시한다.
- 커밋 메시지는 Conventional Commits, 설명은 한국어, `Co-Authored-By` 트레일러는 추가하지 않는다(`AGENTS.md`).

## Review Focus

- **집계구가 6개월 중 일부만 데이터가 있을 때**: `flow_deviation`이 그 집계구의 평균을 관측된 달만으로 계산하는지, 그리고 편차 계산 자체가 결측을 전파하지 않는지 — 이번 집계구 패널은 `aggregate_to_block`이 `min_count=1`로 만들어서 부분 결측이 있을 수 있다.
- **지역 매핑 실패(알 수 없는 접두어)**: `TOT_OA_CD`가 `11230`/`32010`이 아닌 경우(있을 수 없지만) `지역`이 `NaN`이 되고, 이후 merge에서 조용히 빠지는지 확인한다.
- **반복측정 pseudo-replication**: 같은 집계구의 6개 관측치는 서로 독립이 아니다. 전체를 하나로 풀링해 p-value를 낸 Spearman 검정은 유의성이 과장될 수 있다 — 결론에서 "n이 크다고 통계적으로 강한 증거는 아니다"라고 명시한다.
- **기온-월 공선성**: 기온 자체가 월(계절) 순서의 대리변수라, 상관이 높게 나와도 그게 "기온의 인과적 영향"인지 "둘 다 그냥 12월을 향해 단조 변화하는 두 시계열"인지 이 분석만으로는 구분 못 한다. 결론에 명시.
- **기상 파일이 지역 전체 대리변수**: ERA5 서울 지점은 강남구 내부 관측이 아니라 도시권 전체 추정치다(선행 노트북이 이미 지적). 모든 강남 집계구에 동일한 서울 지점 기온을 적용하는 전제를 결론에 다시 적어둔다.

---

### Task 1: 기상 데이터 월별 집계

**Files:**
- Create: `src/data/weather.py`
- Test: `tests/test_weather.py`

**Interfaces:**
- Produces: `load_monthly_temperature(weather_dir: Path) -> pd.DataFrame`, 컬럼 `["지역", "STD_YM", "평균기온"]`. `지역`은 `"서울"` 또는 `"춘천"`, `STD_YM`은 `"202507"` 같은 6자리 문자열.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_weather.py`를 새로 만든다:

```python
"""기상 월별 집계 테스트."""

import pandas as pd

from src.data.weather import load_monthly_temperature

SEOUL_CSV = """latitude,longitude,elevation,utc_offset_seconds,timezone,timezone_abbreviation
37.5,127.0,70.0,32400,Asia/Seoul,GMT+9

time,temperature_2m_mean (°C),temperature_2m_min (°C),temperature_2m_max (°C),precipitation_sum (mm),snowfall_sum (cm)
2025-07-01,25.0,20.0,30.0,0.0,0.0
2025-07-02,27.0,22.0,32.0,0.0,0.0
2025-12-01,-2.0,-5.0,1.0,0.0,0.0
2025-12-02,-4.0,-7.0,-1.0,0.0,0.0
"""

CHUNCHEON_CSV = """latitude,longitude,elevation,utc_offset_seconds,timezone,timezone_abbreviation
38.0,127.75,76.0,32400,Asia/Seoul,GMT+9

time,temperature_2m_mean (°C),temperature_2m_min (°C),temperature_2m_max (°C),precipitation_sum (mm),snowfall_sum (cm)
2025-07-01,20.0,15.0,25.0,0.0,0.0
2025-07-02,22.0,17.0,27.0,0.0,0.0
2025-12-01,-6.0,-9.0,-3.0,0.0,0.0
2025-12-02,-8.0,-11.0,-5.0,0.0,0.0
"""


def test_monthly_mean_by_region(tmp_path):
    (tmp_path / "OpenMeteo_ERA5_20250701_20251231_서울_ASOS108좌표.csv").write_text(
        SEOUL_CSV, encoding="utf-8"
    )
    (tmp_path / "OpenMeteo_ERA5_20250701_20251231_춘천_ASOS101좌표.csv").write_text(
        CHUNCHEON_CSV, encoding="utf-8"
    )

    result = load_monthly_temperature(tmp_path)

    assert set(result.columns) == {"지역", "STD_YM", "평균기온"}
    assert len(result) == 4  # 2개 지역 x 2개월

    seoul = result[result.지역 == "서울"].set_index("STD_YM")["평균기온"]
    assert seoul["202507"] == 26.0  # (25.0 + 27.0) / 2
    assert seoul["202512"] == -3.0  # (-2.0 + -4.0) / 2

    chuncheon = result[result.지역 == "춘천"].set_index("STD_YM")["평균기온"]
    assert chuncheon["202507"] == 21.0
    assert chuncheon["202512"] == -7.0
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `uv run pytest tests/test_weather.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.weather'`

- [ ] **Step 3: 최소 구현**

`src/data/weather.py`를 새로 만든다:

```python
"""Open-Meteo ERA5 일별 기상 자료를 월평균으로 집계.

data/raw/reference_data/기상/2025_기상_자료_수집정보.md 참고: 파일 앞 2행은
격자 메타데이터, 3번째 행은 빈 행이라 skiprows=3으로 읽는다. 서울·춘천 지점은
구·시 내부 관측이 아니라 도시권 전체의 대리변수다.
"""

from pathlib import Path

import pandas as pd

WEATHER_FILES = {
    "서울": "OpenMeteo_ERA5_20250701_20251231_서울_ASOS108좌표.csv",
    "춘천": "OpenMeteo_ERA5_20250701_20251231_춘천_ASOS101좌표.csv",
}


def load_monthly_temperature(weather_dir: Path) -> pd.DataFrame:
    """지역별 일평균기온을 월평균으로 집계해 반환한다.

    반환 컬럼: 지역("서울"/"춘천"), STD_YM(YYYYMM 문자열), 평균기온(섭씨).
    """
    parts = []
    for region, filename in WEATHER_FILES.items():
        df = pd.read_csv(weather_dir / filename, skiprows=3)
        df["STD_YM"] = pd.to_datetime(df["time"]).dt.strftime("%Y%m")
        monthly = df.groupby("STD_YM", as_index=False)["temperature_2m_mean (°C)"].mean()
        monthly = monthly.rename(columns={"temperature_2m_mean (°C)": "평균기온"})
        monthly["지역"] = region
        parts.append(monthly)
    return pd.concat(parts, ignore_index=True)[["지역", "STD_YM", "평균기온"]]
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `uv run pytest tests/test_weather.py -v`
Expected: PASS — 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/data/weather.py tests/test_weather.py
git commit -m "feat: Open-Meteo 기온 데이터를 지역·월별로 집계하는 로더 추가"
```

---

### Task 2: 집계구 유동인구-기온 편차 상관 검정

**Files:**
- Create: `src/features/flow_temperature.py`
- Test: `tests/test_flow_temperature.py`

**Interfaces:**
- Consumes: `src.features.risk_axes_v1.total_flow(panel) -> pd.Series`(기존), `load_monthly_temperature`의 출력 컬럼(`지역`, `STD_YM`, `평균기온`)
- Produces:
  - `monthly_log_flow(panel: pd.DataFrame) -> pd.DataFrame`, 컬럼 `["집계구", "STD_YM", "ln유동인구", "지역"]`
  - `flow_deviation(monthly_flow: pd.DataFrame) -> pd.DataFrame`, 위 컬럼 + `"ln유동인구_편차"`
  - `temperature_deviation(monthly_temp: pd.DataFrame) -> pd.DataFrame`, 입력 컬럼 + `"평균기온_편차"`
  - `correlate_flow_with_temperature(flow_dev: pd.DataFrame, temp_dev: pd.DataFrame) -> pd.DataFrame`, `지역`을 인덱스로 하고 `correlation`, `p_value`, `n` 컬럼을 가진 DataFrame

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_flow_temperature.py`를 새로 만든다:

```python
"""집계구 유동인구-기온 상관 검정 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features.flow_temperature import (
    flow_deviation,
    monthly_log_flow,
    temperature_deviation,
    correlate_flow_with_temperature,
)
from src.features.risk_axes_v1 import AGE_COLS


def _panel_row(집계구: str, STD_YM: str, total: float) -> dict:
    row = {c: total / len(AGE_COLS) for c in AGE_COLS}
    row["집계구"] = 집계구
    row["STD_YM"] = STD_YM
    return row


class TestMonthlyLogFlow:
    def test_computes_ln_flow_and_region(self):
        panel = pd.DataFrame(
            [
                _panel_row("1123051001", "202507", 100.0),
                _panel_row("3201051001", "202507", 50.0),
            ]
        )

        result = monthly_log_flow(panel)

        assert result.loc[result.집계구 == "1123051001", "ln유동인구"].iloc[0] == pytest.approx(
            np.log(100.0)
        )
        assert result.loc[result.집계구 == "1123051001", "지역"].iloc[0] == "서울"
        assert result.loc[result.집계구 == "3201051001", "지역"].iloc[0] == "춘천"


class TestFlowDeviation:
    def test_deviation_is_zero_mean_per_oa(self):
        monthly_flow = pd.DataFrame(
            {
                "집계구": ["A", "A", "B", "B"],
                "STD_YM": ["202507", "202508", "202507", "202508"],
                "ln유동인구": [4.0, 6.0, 1.0, 3.0],
                "지역": ["서울", "서울", "춘천", "춘천"],
            }
        )

        result = flow_deviation(monthly_flow)

        a = result[result.집계구 == "A"].set_index("STD_YM")["ln유동인구_편차"]
        assert a["202507"] == pytest.approx(-1.0)
        assert a["202508"] == pytest.approx(1.0)
        b = result[result.집계구 == "B"].set_index("STD_YM")["ln유동인구_편차"]
        assert b["202507"] == pytest.approx(-1.0)
        assert b["202508"] == pytest.approx(1.0)


class TestTemperatureDeviation:
    def test_deviation_is_zero_mean_per_region(self):
        monthly_temp = pd.DataFrame(
            {
                "지역": ["서울", "서울", "춘천", "춘천"],
                "STD_YM": ["202507", "202512", "202507", "202512"],
                "평균기온": [26.0, -3.0, 21.0, -7.0],
            }
        )

        result = temperature_deviation(monthly_temp)

        seoul = result[result.지역 == "서울"].set_index("STD_YM")["평균기온_편차"]
        assert seoul["202507"] == pytest.approx(14.5)
        assert seoul["202512"] == pytest.approx(-14.5)


class TestFlowTracksTemperature:
    def test_detects_perfect_correlation(self):
        flow_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "ln유동인구_편차": [5.0, 4.0, 3.0, 1.0, -4.0, -9.0],
            }
        )
        temp_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6,
                "STD_YM": [f"2025{m:02d}" for m in range(7, 13)],
                "평균기온_편차": [10.0, 9.0, 6.0, -1.0, -9.0, -17.0],
            }
        )

        result = correlate_flow_with_temperature(flow_dev, temp_dev)

        assert result.loc["서울", "correlation"] == pytest.approx(1.0)
        assert result.loc["서울", "n"] == 6

    def test_separates_regions(self):
        months = [f"2025{m:02d}" for m in range(7, 13)]
        flow_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6 + ["춘천"] * 6,
                "STD_YM": months * 2,
                "ln유동인구_편차": [5.0, 4.0, 3.0, 1.0, -4.0, -9.0]
                + [1.0, -3.0, 2.0, -1.0, 4.0, -2.0],
            }
        )
        temp_dev = pd.DataFrame(
            {
                "지역": ["서울"] * 6 + ["춘천"] * 6,
                "STD_YM": months * 2,
                "평균기온_편차": [10.0, 9.0, 6.0, -1.0, -9.0, -17.0] * 2,
            }
        )

        result = correlate_flow_with_temperature(flow_dev, temp_dev)

        assert set(result.index) == {"서울", "춘천"}
        assert result.loc["서울", "correlation"] == pytest.approx(1.0)
        assert abs(result.loc["춘천", "correlation"]) < 1.0
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `uv run pytest tests/test_flow_temperature.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.features.flow_temperature'`

- [ ] **Step 3: 최소 구현**

`src/features/flow_temperature.py`를 새로 만든다:

```python
"""집계구 월별 유동인구와 지역 월평균기온의 관계를 검정.

12월 유동인구 감소가 기온(한파) 때문인지, 기온과 무관하게 지속되는
악화인지 구분하는 1차 진단이다. 집계구 자신의 6개월 평균 대비 편차와
지역 기온의 6개월 평균 대비 편차를 비교한다 — 집계구마다 규모가 달라도
"그 집계구 기준으로 평소보다 늘었는지 줄었는지"만 보게 된다.

한계: 이 상관은 "기온 효과"와 "월 자체의 추세(trend)"를 완전히 분리하지
못한다. 기온도 7월에서 12월로 갈수록 단조롭게 떨어지므로, 유동인구가
단조 감소 추세라면 기온과도 높은 상관이 나올 수 있다 — 상관계수 하나로
"이건 순수 계절효과다/아니다"를 확정하지 않는다. 또한 같은 집계구의
6개 관측치는 서로 독립이 아니어서(반복측정), 전체를 풀링한 p-value는
과장돼 보일 수 있다.
"""

import numpy as np
import pandas as pd
from scipy import stats

from src.features.risk_axes_v1 import total_flow

REGION_BY_PREFIX = {"11230": "서울", "32010": "춘천"}


def monthly_log_flow(panel: pd.DataFrame) -> pd.DataFrame:
    """집계구×월 패널에서 ln(총유동인구)와 지역을 뽑는다.

    반환 컬럼: 집계구, STD_YM, ln유동인구, 지역.
    """
    out = panel[["집계구", "STD_YM"]].copy()
    out["ln유동인구"] = np.log(total_flow(panel))
    out["지역"] = panel["집계구"].str[:5].map(REGION_BY_PREFIX)
    return out


def flow_deviation(monthly_flow: pd.DataFrame) -> pd.DataFrame:
    """집계구마다 자신의 평균 대비 ln유동인구 편차를 구한다."""
    out = monthly_flow.copy()
    out["ln유동인구_편차"] = out.groupby("집계구")["ln유동인구"].transform(lambda s: s - s.mean())
    return out


def temperature_deviation(monthly_temp: pd.DataFrame) -> pd.DataFrame:
    """지역마다 자신의 평균 대비 기온 편차를 구한다."""
    out = monthly_temp.copy()
    out["평균기온_편차"] = out.groupby("지역")["평균기온"].transform(lambda s: s - s.mean())
    return out


def correlate_flow_with_temperature(flow_dev: pd.DataFrame, temp_dev: pd.DataFrame) -> pd.DataFrame:
    """지역별로 ln유동인구 편차와 기온 편차의 Spearman 상관을 검정한다.

    반환: 지역을 인덱스로, correlation·p_value·n 컬럼을 가진 DataFrame.
    """
    merged = flow_dev.merge(temp_dev[["지역", "STD_YM", "평균기온_편차"]], on=["지역", "STD_YM"])
    rows = []
    for region, g in merged.groupby("지역"):
        r, p = stats.spearmanr(g["ln유동인구_편차"], g["평균기온_편차"])
        rows.append({"지역": region, "correlation": r, "p_value": p, "n": len(g)})
    return pd.DataFrame(rows).set_index("지역")
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `uv run pytest tests/test_flow_temperature.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: 커밋**

```bash
git add src/features/flow_temperature.py tests/test_flow_temperature.py
git commit -m "feat: 집계구 유동인구-기온 편차 상관 검정 함수 추가"
```

---

### Task 3: 실데이터로 검증 노트북 작성

**Files:**
- Create: `notebooks/261004_VERIFY_flow_temperature_seasonality.ipynb`

**Interfaces:**
- Consumes: `src.features.block_panel.{load_oa_boundaries, aggregate_to_block}`(기존), `src.data.weather.load_monthly_temperature`(Task 1), `src.features.flow_temperature.*`(Task 2)

- [ ] **Step 1: 노트북 셀 작성**

`notebooks/261004_VERIFY_flow_temperature_seasonality.ipynb`를 새로 만든다. 4개 셀:

**Cell 1 (markdown):**

```markdown
# [검증] 집계구 유동인구-기온 계절성 — 2026-10-04

- 작성자: 이정연 (`ljy`)
- 목적: 12월 SK 유동인구 감소가 기온(한파) 때문인지, 기온과 무관하게 지속되는 악화인지 1차 진단
- 입력: `data/raw/sk_통신인구_202507~202512_통합.csv`(6개월), `data/raw/reference_data/기상/`의 Open-Meteo ERA5 일별 기온
- 대상 시군구: 강남구(11230, 집계구 기준 "서울")·춘천시(32010, 집계구 기준 "춘천")
- **선행 분석**: `notebooks/260923_EDA_external_factors.ipynb`가 카드·기상·전철을 지역 단위로 결합했다. 이 노트북은 그 다음 단계를 SK 유동인구 + 집계구 단위로 수행한다.
- **한계**: 상관계수 하나로 "순수 계절효과다/아니다"를 확정하지 않는다. 기온도 7~12월 사이 단조 감소하므로, 유동인구가 기온과 무관한 이유로 단조 감소해도 비슷한 상관이 나올 수 있다. 같은 집계구의 6개 관측치는 독립이 아니라서 p-value는 참고용이다. ERA5 서울·춘천 지점은 구·시 전체의 대리변수이지 집계구별 관측이 아니다.
```

**Cell 2 (code):**

```python
from pathlib import Path

import pandas as pd

from src.data.weather import load_monthly_temperature
from src.features.block_panel import aggregate_to_block, load_oa_boundaries
from src.features.flow_temperature import (
    flow_deviation,
    monthly_log_flow,
    temperature_deviation,
    correlate_flow_with_temperature,
)

MONTHS = ["202507", "202508", "202509", "202510", "202511", "202512"]

repo_root = Path.cwd()
if not (repo_root / "data" / "raw").exists():
    repo_root = repo_root.parent
raw_dir = repo_root / "data" / "raw"

boundaries = load_oa_boundaries(raw_dir / "reference_data")
frames = [
    pd.read_csv(
        raw_dir / f"sk_통신인구_{month}_통합.csv",
        dtype={"STD_YM": "string", "BLOCK_CD": "string"},
    )
    for month in MONTHS
]
combined = pd.concat(frames, ignore_index=True)
panel = aggregate_to_block(combined, boundaries)
print(f"집계구×월 패널 행: {len(panel):,}, 고유 집계구 수: {panel['집계구'].nunique():,}")
```

Expected output: `집계구×월 패널 행: 10,170, 고유 집계구 수: 1,695`

**Cell 3 (code):**

```python
flow = monthly_log_flow(panel)
flow_dev = flow_deviation(flow)

temp = load_monthly_temperature(raw_dir / "reference_data" / "기상")
temp_dev = temperature_deviation(temp)
print("지역별 월평균기온(편차):")
print(temp_dev.round(2).to_string(index=False))

result = correlate_flow_with_temperature(flow_dev, temp_dev)
print("\n지역별 유동인구-기온 편차 Spearman 상관:")
print(result.round(4).to_string())
```

Expected output:

```
지역별 월평균기온(편차):
지역  STD_YM    평균기온  평균기온_편차
서울  202507  27.74   10.70
서울  202508  27.33   10.29
서울  202509  22.82    5.78
서울  202510  16.18   -0.86
서울  202511   7.86   -9.18
서울  202512   0.31  -16.73
춘천  202507  27.85   10.55
춘천  202508  27.74   10.43
춘천  202509  22.84    5.54
춘천  202510  16.20   -1.10
춘천  202511   8.14   -9.17
춘천  202512   1.04  -16.26

지역별 유동인구-기온 편차 Spearman 상관:
      correlation  p_value     n
지역
서울        0.2720   0.0000  6576
춘천        0.1760   0.0000  3594
```

**Cell 4 (markdown):**

```markdown
## 결론

- **서울(강남) r=0.272, 춘천 r=0.176 — 둘 다 양(+)의 상관이고 통계적으로 유의하지만, 크기는 약~중간 수준이다.** 기온이 유동인구와 같은 방향으로 움직이는 건 맞다(따뜻할수록 유동인구도 높은 경향) — 하지만 상관이 1에 가깝지 않다는 건, 12월 감소를 기온만으로 설명할 수 없는 부분이 상당히 남아있다는 뜻이다.
- **n이 커서(6,576 / 3,594) p-value가 사실상 0으로 나오지만, 이건 통계적 증거의 강도를 과장해서 보여준다.** 같은 집계구의 6개 관측치는 서로 독립이 아니라서(반복측정), 이 p-value를 "매우 강한 증거"로 읽으면 안 된다. 상관계수(0.17~0.27) 자체가 더 중요한 숫자다.
- **기온-월 공선성 한계는 여전히 남아있다**: 기온도 7월→12월로 단조 감소하고, 유동인구도 전반적으로 감소 경향이 있어서(이전 α 검증 작업에서 추세_위험 평균이 약한 음수였음), 이 상관이 "기온의 직접 효과"인지 "둘 다 그냥 연말로 갈수록 떨어지는 두 시계열"인지 이 분석만으로는 못 가른다.
- **잠정 결론**: 12월 감소를 전부 "한파 때문"으로 돌릴 근거는 약하다(상관이 완전하지 않음). 그렇다고 전부 "진짜 악화"라고 할 근거도 아니다(양의 상관 자체는 유의하게 있음). **"12월 스냅샷이냐 6개월 평균이냐"라는 질문에는, 이 결과가 평균 쪽에 아주 약간 더 힘을 실어준다** — 기온 영향이 일부 섞여 있다는 걸 확인했으니, 12월 단독 스냅샷보다는 여러 달을 보는 쪽이 이 교란을 희석시킨다.
- **다음 확인 필요**: 기온 대신 "월 순서(1~6)"를 바로 상관시켜서, 기온 상관(0.27/0.18)과 거의 같은 크기가 나오는지 비교하면 공선성 문제를 더 구체적으로 짚을 수 있다. 강수·적설도 아직 안 봤다.
```

- [ ] **Step 2: 노트북 실행**

Run: `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/261004_VERIFY_flow_temperature_seasonality.ipynb`
Expected: 에러 없이 완료, Cell 2·3의 출력이 위 Expected와 일치(소수점 반올림 차이는 허용)

- [ ] **Step 3: 커밋**

```bash
git add notebooks/261004_VERIFY_flow_temperature_seasonality.ipynb
git commit -m "feat: 집계구 유동인구-기온 계절성 검증 노트북 추가"
```

---

## Self-Review

**1. Spec coverage:** 기온 데이터 월별 집계(Task 1), 집계구 단위 편차 상관 검정(Task 2), 선행 노트북과 중복 없이 집계구+SK 유동인구에 한정한 실행(Task 3) — 전부 다룸.

**2. Placeholder 스캔:** 모든 Step에 실행 가능한 전체 코드와 실측 숫자를 넣었다. `TBD`/`TODO` 없음.

**3. 타입 일관성:** `load_monthly_temperature`(Task 1)가 반환하는 `지역`/`STD_YM`/`평균기온` 컬럼명이 Task 2의 `temperature_deviation` 입력과 Task 3 노트북에서 동일하게 쓰인다. `monthly_log_flow`의 `집계구`/`STD_YM`/`ln유동인구`/`지역`도 `flow_deviation`과 일치한다.

**4. Review Focus:** 5개 항목(부분 결측, 지역 매핑 실패, 반복측정 과장된 유의성, 기온-월 공선성, 지점이 지역 전체 대리변수) 모두 테스트(Task 2) 또는 노트북 결론(Task 3)에서 다뤄졌다.
