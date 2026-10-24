# [GIS] 고립 위험 지수 v2 저장소 실행 안내 — 2026-10-20

[이슈 #24](https://github.com/Team-Hambugi-Lab/bigcontest-social-isolation/issues/24)의 v2 기준 코드다. 사용자가 제공한 `isolation_index_v2.ipynb`의 입력·출력 경로를 저장소 구조로 옮겼다. 보류 완화와 테마 A/B 분리 등 v3 개선은 아직 적용되지 않았다.

## 파일과 경로

| 구분 | 저장소 루트 기준 경로 |
|---|---|
| 실행 노트북 | `notebooks/261020_GIS_isolation_index_v2.ipynb` |
| 입력 마스터 | `data/processed/master_sgis2024_selected_no_industry_counts.csv` |
| 결과 CSV | `data/interim/isolation_index_v2.csv` |
| QGIS 자료형 | `data/interim/isolation_index_v2.csvt` |
| 결과 열 설명 | `data/interim/isolation_index_v2_dictionary.csv` |

입력은 팀 드라이브에서 별도로 받아 위 위치에 배치한다. `src.data.paths`의 `PROCESSED_DIR`, `INTERIM_DIR`을 사용하므로 저장소 루트와 `notebooks/` 아래에서 같은 파일을 참조한다. 데이터 파일은 기존 `.gitignore` 규칙대로 Git으로 추적하지 않는다. 결과 CSV와 열 설명·QGIS 보조파일은 실행 후 드라이브 `data/interim/`에 공유한다.

## 실행

저장소 루트에서 환경을 준비한다.

```bash
uv sync --extra dev
```

그다음 저장소 Python 환경을 노트북 커널로 사용하거나 아래 명령으로 실행한다. 실행 출력 노트북은 Git 제외 패턴인 `.nbconvert.ipynb`로 저장한다.

```bash
uv run jupyter nbconvert --to notebook --execute notebooks/261020_GIS_isolation_index_v2.ipynb --output 261020_GIS_isolation_index_v2.nbconvert.ipynb
```

입력은 SGIS 2024년 통계이고 `STD_YM` 첫 달만 사용한다. 집계구·행정동·월 코드는 문자열로 읽는다. 입력 파일이 없으면 필요한 상대경로를 오류 메시지에 표시한다. 난수는 사용하지 않는다.

## 유지한 분석과 공유 범위

- 원본의 5개 차원, 결측 대치, 등가중, 지역별 표준화·백분위, 보류 임계값, 민감도 계산을 유지했다.
- 종사자/거주자 1 초과 또는 인구/가구 5 초과면 등급 0이다. 인구·가구·주택이 모두 양수인 행만 계산하므로 제외된 행과 등급 0은 다르다. 상단 설명을 실제 코드에 맞췄다.
- 점수와 백분위는 보류 플래그를 제외하기 전에 계산되고 마지막에 해당 행의 등급만 0으로 바뀐다. v3에서 바꿀 경우 비교 기준을 분리해야 한다.
- `solo50`·`oldho`의 곱셈은 집계값으로 만든 대리지표다. 실제 연령×가구형태 또는 노후×주택유형의 교차 분포를 직접 관측한 값으로 표현하지 않는다.
- 지수는 지역 집계 신호다. 개인 고립 판정이나 개인 티어 상승의 직접 근거로 쓰지 않는다.
- 원본에 실행 출력이 없어 결과를 포함하지 않았다. 입력 마스터가 현재 작업 환경에 없어 실데이터 전체 재실행·본문 수치 재현은 수행하지 않았다.

## 경로 변경 검증

구문 검사, 원본 분석 셀의 AST 일치, 루트·노트북 폴더에서의 공통 경로 해석, 입력 미보유 안내, CSV·QGIS 보조파일·열 설명의 출력 경로 및 코드 문자열 보존을 확인했다. 경로와 입출력에 대한 검증이며 통계 모델 타당성 검증은 별도다.


- 노트북 형식과 모든 코드 셀의 구문 검사 통과.
- 실행 오류 관련 Ruff 검사(`E9,F63,F7,F82`) 통과.
- 원본의 분석 셀 5개와 분석 파라미터의 동일성 확인.
- 저장소 루트·`notebooks/`·하위 폴더에서 경로와 입력 미보유 안내 확인.
- 저장 전용 테스트 자료 2행으로 CSV 26열, QGIS `.csvt`의 26개 자료형, 열 설명 26행×5열을 확인했다. 이 테스트 자료는 실제 분석 결과가 아니며 저장 후 제거했다.
