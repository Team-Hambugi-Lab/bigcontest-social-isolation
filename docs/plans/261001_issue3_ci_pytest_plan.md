# 이슈 #3: CI 실데이터 의존 테스트 분리 계획

## 목적

GitHub Actions에는 `data/raw` 원본 데이터가 없으므로, 실데이터에 의존하는 테스트를 CI에서 제외한다. 실데이터가 필요 없는 단위 테스트는 계속 실행하고, 로컬에서는 기존처럼 전체 테스트를 실행할 수 있어야 한다.

## 전제

- 실데이터 의존 테스트는 현재 `main`이 아니라 PR #2 브랜치에 있다.
- 따라서 공통 pytest·CI 설정을 `main`에 먼저 반영하고, 테스트 마커는 PR #2 브랜치에서 적용한다.
- `pytest -m "not requires_data"`로 제외한 테스트는 `skipped`가 아니라 `deselected`로 집계된다.

## 1단계: 공통 pytest·CI 설정

현재 `main` 기반 브랜치에서 다음 파일만 변경한다.

### `pyproject.toml`

`requires_data` 커스텀 마커를 등록한다.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
markers = [
    "requires_data: 실제 원본 데이터가 필요한 테스트",
]
```

### `.github/workflows/ci.yml`

CI의 pytest 명령에서 실데이터 의존 테스트를 제외한다.

```yaml
uv run pytest tests/ -m "not requires_data" -v --tb=short --cov=src --cov-report=term-missing
```

이 변경은 별도 PR로 `main`에 먼저 병합한다.

## 2단계: PR #2 테스트 분류

1단계가 병합된 뒤 PR #2 브랜치에 최신 `main`을 반영하고 마커를 추가한다.

### 파일 전체가 실데이터에 의존

다음 파일에는 모듈 수준 마커를 적용한다.

```python
pytestmark = pytest.mark.requires_data
```

- `tests/test_card_cohort.py`
- `tests/test_cluster_stability.py`
- `tests/test_external.py`
- `tests/test_loaders.py`
- `tests/test_sk_quantum.py`

### 일부 테스트만 실데이터에 의존

다음 파일에는 원본 데이터를 읽는 테스트에만 `@pytest.mark.requires_data`를 적용한다. 순수 로직 테스트는 CI에 남긴다.

- `tests/test_contact.py`
- `tests/test_isolation.py`
- `tests/test_paths.py`
- `tests/test_regions.py`
- `tests/test_sk_dong.py`

### 변경하지 않는 테스트

- `tests/test_build_sk_integrated.py`: `tmp_path`에 테스트 데이터를 직접 생성한다.
- `tests/test_features.py`: 실데이터를 읽지 않는다.
- `tests/test_style.py`: 실데이터를 읽지 않는다.

## 검증

### CI와 같은 조건

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/ -m "not requires_data" -v --tb=short --cov=src --cov-report=term-missing
```

확인 사항:

- 원본 데이터가 없어도 `FileNotFoundError` 없이 통과한다.
- 실데이터가 필요 없는 테스트는 계속 실행된다.
- `requires_data` 테스트는 결과에 `deselected`로 집계된다.
- 미등록 마커 경고가 발생하지 않는다.

### 실데이터가 있는 로컬 환경

```bash
uv run pytest tests/ -v
```

전체 테스트가 기존과 동일하게 통과하는지 확인한다.

## 작업 순서

1. 현재 브랜치에서 `pyproject.toml`과 `.github/workflows/ci.yml`을 변경한다.
2. 린트, 포맷 검사, 데이터 제외 테스트를 실행한다.
3. 별도 PR을 만들어 `main`에 병합한다.
4. PR #2 브랜치에 최신 `main`을 반영한다.
5. 실데이터 의존 테스트에 마커를 적용한다.
6. 데이터 제외 테스트와 로컬 전체 테스트를 실행한다.
7. PR #2의 GitHub Actions 통과를 확인한다.

## 완료 조건

- CI에서 실데이터 의존 테스트가 `deselected`로 명확히 집계된다.
- CI에서 나머지 단위 테스트가 통과한다.
- 실데이터가 있는 로컬 환경에서 전체 테스트가 통과한다.
- PR #2의 `lint-and-test` 작업이 통과한다.
