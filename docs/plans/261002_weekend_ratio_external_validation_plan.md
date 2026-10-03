# 주말비(weekend_ratio) 외부검증 재실행 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 진재언의 "주말비"(weekend_ratio = 주말 평균 ÷ 평일 평균) 공식을 김태은의 행정동 단위 외부검증 파이프라인에 재구현하고, 기존 `test_external.py`와 동일한 방법(Spearman 상관, 강남/춘천 분리)으로 충돌 #3("주말비 방향이 맞는지 불확실하다")을 검증한다.

**Architecture:** 새 모듈은 만들지 않는다. `src/features/sk_dong.py`에 요일 분할 상수 2개를 추가하고, `src/features/isolation.py`의 `space_indicators()`에 `weekend_ratio` 컬럼 하나를 추가한다. 두 곳 모두 이미 존재하는 동일 패턴(`SENIOR_COLS`/`NIGHT_COLS`가 `sk_dong.py`에 있고 `isolation.py`가 그걸 가져와 쓰는 구조)을 그대로 따른다. 검증은 `tests/test_external.py`의 기존 `joined` fixture에 자동으로 흘러들어오므로, 거기에 pinned 테스트 2개만 추가한다.

**Tech Stack:** Python 3.11, pandas, pytest (`@pytest.mark.requires_data`), uv.

**Spec:** 이 저장소에는 별도 spec 문서가 없다. 아래를 spec으로 삼는다:
- `tests/test_external.py` 자체 — 이미 같은 방법론으로 `wkdy_cv`/`night_share`의 방향을 검증·고정해 둔 선례(이 파일의 docstring: "검증 결과를 여기에 고정한다").
- `src/features/risk_axes_v1.py`의 `weekend_ratio()`/`align_risk_direction()` — 진재언 보고서 서술을 재구성한 공식과, "주말비는 원값 그대로 쓴다"는 아직 미확정 가정.
- `/Users/leejungyeon/Workspace/projects/jeongni-vault/work/active/bigcontest-social-isolation/제안 - 위험지수 설계 다음 단계 (2026-10-01).md` — 충돌 #3이 2순위 논의 항목으로 남아 있다는 기록.

## Global Constraints

- weekend_ratio 공식은 `risk_axes_v1.weekend_ratio`와 동일하다: 주말(토·일) 평균 ÷ 평일(월~금) 평균. `WKDY_COLS`의 각 칸은 이미 "해당 요일의 일평균"이므로 `sum`이 아니라 `mean`을 쓴다.
- 공간 단위는 행정동(`dong_cd`, 47개) — 김태은의 기존 파이프라인(`sk_dong.build_space_panel`, `isolation.space_indicators`, `external.census_dong_panel`)을 그대로 재사용한다. 진재언의 집계구(13자리, 1,639개) 단위가 아니다 — 서로 다른 공간 단위에서 나온 결과라는 점을 결론에 명시한다.
- `weekend_ratio`를 `tests/test_external.py`의 `AXES = ["wkdy_cv", "night_share", "peak_ratio"]`나 `isolation.composite`의 `score` 계산에 포함하지 않는다. 포함하면 `score`가 바뀌어 `test_axes_do_not_work_in_gangnam` 등 기존 pinned 테스트가 깨진다.
- 실데이터 의존 테스트는 `@pytest.mark.requires_data`를 따른다(`tests/test_external.py`는 이미 파일 전체에 `pytestmark = pytest.mark.requires_data`가 걸려 있어 새 함수도 자동 상속된다).
- 커밋 메시지는 Conventional Commits, 콜론 뒤 설명은 한국어, `Co-Authored-By` 트레일러는 추가하지 않는다(`AGENTS.md`).
- vault·GitHub 이슈 반영은 이 플랜의 범위 밖이다 — 검증 결과가 나온 뒤 별도로 사용자 확인을 받아 진행한다.

## Review Focus

- **AXES/score 오염**: `weekend_ratio`를 실수로 `AXES`에 넣으면 `score` 값이 바뀌어 `test_axes_do_not_work_in_gangnam`·`test_sk_senior_flow_tracks_census_senior_ratio` 등 기존 pinned 테스트가 조용히 깨질 수 있다 — Task 3에서 `AXES` 리스트를 수정하지 않는다.
- **분모 0 (평일 평균이 0인 동)**: 평일 유동인구가 0인 동이 있으면 `weekend_ratio`가 `inf`/`NaN`이 되어 이후 `corr` 계산이 깨진다 — Task 2 테스트의 `notna().all()`과 `(> 0).all()` 체크로 47개 전부 유효한지 확인한다.
- **표본 크기(n=22/25)의 한계**: 강남·춘천 각각 22개/25개 동으로 Spearman 상관의 유의성이 약할 수 있다 — 이미 이 파일의 다른 모든 테스트가 같은 n으로 운영 중이므로 동일 기준을 적용하되, 결론에 표본 크기를 명시한다.
- **CI 제외 상속**: 새 테스트 2개가 파일 레벨 `pytestmark`를 통해 `requires_data`로 자동 제외되는지 — Task 3 Step에서 `-m "not requires_data"`로 한 번 더 확인한다.
- **진재언 가정과의 일치 여부**: `risk_axes_v1.align_risk_direction`은 "주말비는 원값 그대로 쓴다(뒤집지 않는다)"고 가정해 두었다 — 이번 행정동 단위 검증 결과(양의 상관 확인)가 이 가정과 같은 방향인지를 Task 4에서 문서에 명시한다.

---

### Task 1: `sk_dong.py`에 요일 분할 상수 추가

**Files:**
- Modify: `src/features/sk_dong.py:18-22`
- Test: `tests/test_sk_dong.py:9-15`

**Interfaces:**
- Consumes: 기존 `WKDY_COLS` (7개, `src/features/sk_dong.py:18`)
- Produces: `WEEKDAY_COLS: list[str]` (5개, 월~금), `WEEKEND_COLS: list[str]` (2개, 토·일) — Task 2가 이 두 상수를 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_sk_dong.py`의 `test_column_group_sizes`를 아래로 교체한다:

```python
def test_column_group_sizes():
    assert len(sk_dong.AGE_COLS) == 12
    assert len(sk_dong.TIME_COLS) == 24
    assert len(sk_dong.WKDY_COLS) == 7
    assert len(sk_dong.SENIOR_COLS) == 2
    assert len(sk_dong.NIGHT_COLS) == 8
    assert len(sk_dong.WEEKDAY_COLS) == 5
    assert len(sk_dong.WEEKEND_COLS) == 2
    assert set(sk_dong.WEEKDAY_COLS) | set(sk_dong.WEEKEND_COLS) == set(sk_dong.WKDY_COLS)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `uv run pytest tests/test_sk_dong.py::test_column_group_sizes -v`
Expected: FAIL — `AttributeError: module 'src.features.sk_dong' has no attribute 'WEEKDAY_COLS'`

- [ ] **Step 3: 최소 구현**

`src/features/sk_dong.py:18` (`WKDY_COLS` 정의) 바로 뒤에 추가한다:

```python
WKDY_COLS = [f"FLOW_POP_CNT_{d}" for d in ("MON", "TUS", "WED", "THU", "FRI", "SAT", "SUN")]
WEEKDAY_COLS = [f"FLOW_POP_CNT_{d}" for d in ("MON", "TUS", "WED", "THU", "FRI")]
WEEKEND_COLS = [f"FLOW_POP_CNT_{d}" for d in ("SAT", "SUN")]
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `uv run pytest tests/test_sk_dong.py::test_column_group_sizes -v`
Expected: PASS — 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/features/sk_dong.py tests/test_sk_dong.py
git commit -m "feat: SK 요일 패널에 평일·주말 분할 상수 추가"
```

---

### Task 2: `isolation.space_indicators`에 weekend_ratio 지표 추가

**Files:**
- Modify: `src/features/isolation.py:10,51-55`
- Test: `tests/test_isolation.py:69-83`

**Interfaces:**
- Consumes: `sk_dong.WEEKDAY_COLS`, `sk_dong.WEEKEND_COLS` (Task 1 산출물)
- Produces: `isolation.space_indicators(panel)`가 반환하는 DataFrame에 `"weekend_ratio"` 컬럼 추가(동 단위 float, 0보다 큼) — Task 3이 `test_external.py`의 `joined` fixture를 통해 이 컬럼을 그대로 쓴다. fixture 코드 자체는 수정하지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_isolation.py`의 `test_space_indicators_columns_and_range`(69번째 줄)를 아래로 교체한다:

```python
@pytest.mark.requires_data
def test_space_indicators_columns_and_range():
    from src.features import sk_dong

    panel = sk_dong.build_space_panel()
    ind = isolation.space_indicators(panel)
    assert ind["dong_cd"].nunique() == 47
    for c in (
        "wkdy_cv",
        "time_entropy",
        "night_share",
        "peak_ratio",
        "weekend_ratio",
        "senior_share",
    ):
        assert c in ind.columns
        assert ind[c].notna().all()
    assert ind["night_share"].between(0, 1).all()
    assert ind["senior_share"].between(0, 1).all()
    assert ind["peak_ratio"].between(0, 1).all()
    assert (ind["weekend_ratio"] > 0).all()
    # 24개 구간 균등분포의 엔트로피 상한은 log(24)
    assert (ind["time_entropy"] <= np.log(24) + 1e-9).all()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `uv run pytest tests/test_isolation.py::test_space_indicators_columns_and_range -v`
Expected: FAIL — `AssertionError: assert 'weekend_ratio' in Index([...])`

- [ ] **Step 3: 최소 구현**

`src/features/isolation.py:10`의 import를 교체한다:

```python
from src.features.sk_dong import (
    AGE_COLS,
    NIGHT_COLS,
    SENIOR_COLS,
    TIME_COLS,
    WEEKDAY_COLS,
    WEEKEND_COLS,
    WKDY_COLS,
)
```

`src/features/isolation.py:51`(`df["peak_ratio"] = ...` 바로 다음 줄)에 추가하고, 같은 함수의 `cols` 리스트(54번째 줄)를 교체한다:

```python
    df["peak_ratio"] = time.mean(axis=1) / time.max(axis=1)
    # 생활 리듬: 주말(토·일) 평균 유동인구 ÷ 평일(월~금) 평균 유동인구
    df["weekend_ratio"] = wkdy[WEEKEND_COLS].mean(axis=1) / wkdy[WEEKDAY_COLS].mean(axis=1)
    df["senior_share"] = df[SENIOR_COLS].sum(axis=1) / df["total"]

    cols = [
        "wkdy_cv",
        "time_entropy",
        "night_share",
        "peak_ratio",
        "weekend_ratio",
        "senior_share",
        "total",
    ]
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `uv run pytest tests/test_isolation.py::test_space_indicators_columns_and_range -v`
Expected: PASS — 1 passed

- [ ] **Step 5: 커밋**

```bash
git add src/features/isolation.py tests/test_isolation.py
git commit -m "feat: space_indicators에 weekend_ratio(주말 평균/평일 평균) 지표 추가"
```

---

### Task 3: `test_external.py`에 주말비 방향검증 pinned 테스트 추가

이 Task는 Task 1·2와 달리 "구현을 이끄는 RED"가 아니라 **이미 구현된 지표의 실측값을 고정하는(pin) 테스트**다. `weekend_ratio`는 Task 2에서 이미 `joined` fixture에 흘러들어오므로, 아래 테스트는 작성 즉시 통과한다 — 이것이 비정상이 아니라 이 파일의 다른 방향검증 테스트들(`test_night_share_direction_holds_in_chuncheon` 등)과 동일한 성격이다. 아래 상관값은 플랜 작성 시점에 실데이터로 미리 계산해 확인한 실측치다(강남 n=22, 춘천 n=25, 둘 다 Spearman):

| 구분 | vs senior_ratio | vs elderly_dependency |
|---|---:|---:|
| 서울 강남구 | 0.196 | 0.251 |
| 강원 춘천시 | 0.570 | 0.665 |

**Files:**
- Modify: `tests/test_external.py:86-101` (기존 `test_wkdy_cv_direction_is_rejected`와 `test_axes_do_not_work_in_gangnam` 사이·내부)

**Interfaces:**
- Consumes: `joined` fixture(`tests/test_external.py:22-30`, 수정하지 않음)가 제공하는 `weekend_ratio` 컬럼(Task 2 산출물)
- Produces: 없음(이 Task가 마지막 코드 변경 지점)

- [ ] **Step 1: 춘천 방향확인 테스트 작성**

`tests/test_external.py`의 `test_wkdy_cv_direction_is_rejected` 함수(93번째 줄) 바로 다음, `test_axes_do_not_work_in_gangnam` 함수(96번째 줄) 바로 앞에 추가한다:

```python
def test_weekend_ratio_direction_holds_in_chuncheon(joined):
    """weekend_ratio 방향 가정(risk_axes_v1.align_risk_direction의 '원값 그대로 위험')이
    춘천에서 확인된다.

    고령 인구 비율이 높은 동일수록 주말 상대활동(weekend_ratio = 주말평균/평일평균)이
    높다 — 평일 활동이 적고 주말(가족 방문 등)에만 상대적으로 늘어나는 패턴으로 보인다.
    실측 춘천(n=25) senior_ratio r=0.570, elderly_dependency r=0.665(둘 다 스피어만).
    """
    cc = joined[joined.sgg_name == "강원 춘천시"]
    assert cc.weekend_ratio.corr(cc.senior_ratio, method="spearman") > 0.4
    assert cc.weekend_ratio.corr(cc.elderly_dependency, method="spearman") > 0.5
```

- [ ] **Step 2: 강남 무관성 확인을 기존 테스트에 추가**

`test_axes_do_not_work_in_gangnam`(96~101번째 줄)을 아래로 교체한다. `AXES` 리스트 자체는 건드리지 않는다(Global Constraints 참고):

```python
def test_axes_do_not_work_in_gangnam(joined):
    """강남에서는 모든 축이 외부 지표와 무관하다. 한계를 고정한다."""
    gn = joined[joined.sgg_name == "서울 강남구"]
    for c in AXES + ["score"]:
        r = abs(gn[c].corr(gn.senior_ratio, method="spearman"))
        assert r < 0.45, f"{c} 상관 {r:.3f} — 강남에서 관계가 생겼다면 문서를 갱신할 것"
    # weekend_ratio는 score 계산(AXES)에는 포함되지 않지만(충돌 #3 전용 축),
    # 강남 무관성 한계는 동일하게 적용된다. 실측 강남(n=22) r=0.196.
    r_weekend = abs(gn.weekend_ratio.corr(gn.senior_ratio, method="spearman"))
    assert r_weekend < 0.3, f"weekend_ratio 상관 {r_weekend:.3f}"
```

- [ ] **Step 3: 새 테스트와 전체 파일이 통과하는지 확인**

Run: `uv run pytest tests/test_external.py -v`
Expected: PASS — 11 passed (기존 10개 + `test_weekend_ratio_direction_holds_in_chuncheon` 1개, `test_axes_do_not_work_in_gangnam`은 교체됐을 뿐 개수는 그대로)

- [ ] **Step 4: CI 제외 마커가 상속되는지 확인**

Run: `uv run pytest tests/test_external.py -m "not requires_data" -v`
Expected: PASS — 0 passed, 11 deselected (파일 레벨 `pytestmark`가 새 테스트에도 적용됨)

- [ ] **Step 5: 커밋**

```bash
git add tests/test_external.py
git commit -m "test: 주말비(weekend_ratio) 방향 가정을 춘천·강남에서 외부검증"
```

---

### Task 4: `risk_axes_v1.py` 문서화 — 충돌 #3 해결 기록

**Files:**
- Modify: `src/features/risk_axes_v1.py:117-125`

**Interfaces:**
- Consumes: Task 3의 실측 결과(춘천 양의 상관 확인, 강남 무관)
- Produces: 없음(문서 전용, 로직 변경 없음)

- [ ] **Step 1: `align_risk_direction`의 docstring 갱신**

`src/features/risk_axes_v1.py:117-125`를 아래로 교체한다(로직은 변경하지 않는다 — `"주말비_위험": block_level["주말비"]`는 그대로 둔다):

```python
def align_risk_direction(block_level: pd.DataFrame) -> pd.DataFrame:
    """5개 변수를 모두 '높을수록 위험' 방향으로 정렬한다.

    평탄도는 낮을수록 위험(평탄함)이므로 부호를 뒤집는다. 추세는 더 많이
    감소할수록(기울기가 더 음수일수록) 위험이므로 부호를 뒤집는다. 야간비중·
    고령비중은 원값 그대로가 이미 '높을수록 위험'이다. 주말비는 원값 그대로
    쓴다 — 충돌 #3이었던 이 방향은 행정동 단위 외부검증으로 확인됐다
    (`tests/test_external.py::test_weekend_ratio_direction_holds_in_chuncheon`,
    춘천에서 고령비율과 양의 상관 0.570, 고령부양비와 0.665, 강남에서는 무관
    0.196). 집계구 단위에서도 같은 방향인지는 재언 님 원 코드 확인 전까지는
    열린 질문이다.
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
```

- [ ] **Step 2: 기존 테스트가 여전히 통과하는지 확인**

Run: `uv run pytest tests/test_risk_axes_v1.py -v`
Expected: PASS — 23 passed (로직 변경 없음, docstring만 바뀜)

- [ ] **Step 3: 커밋**

```bash
git add src/features/risk_axes_v1.py
git commit -m "docs: 주말비 방향 가정 충돌 #3 해결 기록을 align_risk_direction에 반영"
```

---

## Self-Review

**1. Spec coverage:** `test_external.py`의 기존 방법론(Spearman, 강남/춘천 분리, pinned test) → Task 3에서 그대로 재사용. `risk_axes_v1.weekend_ratio`의 공식 → Task 2에서 동일하게 구현(공식만 가져오고 집계구 단위가 아니라 행정동 단위로 재계산). 충돌 #3 기록 반영 → Task 4. 빠진 항목 없음.

**2. Placeholder 스캔:** 모든 Step에 실행 가능한 전체 코드와 실측 숫자를 넣었다. `TBD`/`TODO`/"나중에" 없음.

**3. 타입 일관성:** `WEEKDAY_COLS`/`WEEKEND_COLS`는 Task 1에서 `list[str]`로 정의되고 Task 2에서 그 이름 그대로 import된다. `weekend_ratio` 컬럼명은 Task 2~4에서 동일하게 쓰인다.

**4. Review Focus:** 5개 항목(AXES/score 오염, 분모 0, 표본 크기, CI 제외 상속, 진재언 가정과의 일치) 모두 Task 2~4의 테스트나 문서화로 다뤄졌다.
