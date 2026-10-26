# SGIS 2024 결합 마스터 재현

이슈 #32의 **SK 집계구 집계 결과 + SGIS 2024 결합 → 마스터 생성** 단계다.
실행 파일은 [`261008_GIS_sgis2024_master_merge.ipynb`](../notebooks/261008_GIS_sgis2024_master_merge.ipynb)다.
2026-10-14에 실행한 노트북의 병합·변수 선택 계산과 기본 설정을 유지하고 입출력 경로를 현재 저장소에 맞췄다.

## 1. 선행 단계와 환경

1. `src/features/build_sk_integrated.py`로 2025년 7~12월 SK 월별 통합 CSV를 만든다.
2. `notebooks/261005_GIS_skt_census_aggregation.ipynb`를 **마지막 월별 결과 통합 셀까지** 실행한다.
   `data/processed/sk_통합_집계구/sk_통신인구_전체_집계구.csv`가 입력이다.
3. 아래 SGIS 원본과 코드표를 배치한 뒤 이 문서의 결합 노트북을 실행한다.

Python 3.11 이상과 저장소의 잠금 파일을 사용한다.

```bash
uv sync --locked --extra dev
```

`.xls` 코드표를 읽는 `xlrd`는 기본 의존성이다. 노트북 실행용 Jupyter는 `dev`에 포함된다.
앞선 공간 집계도 실행할 때는 `--extra gis`를 추가한다.

## 2. 입력 배치

```text
data/
├── processed/
│   └── sk_통합_집계구/
│       └── sk_통신인구_전체_집계구.csv
└── raw/reference_data/
    ├── ref_code/
    │   └── 3. 제공용 코드(statistics_code).xls
    └── sgis2024/
        ├── population/   # 인구 CSV 14개
        ├── household/    # 가구 CSV 4개
        ├── housing/      # 주택 CSV 8개
        └── business/     # 사업체·종사자 CSV 12개
```

| 기존 SGIS 다운로드 폴더 | 저장소 안 배치 위치 |
|---|---|
| `_census_reqdoc_1791091305499`의 CSV | `data/raw/reference_data/sgis2024/population/` |
| `_census_reqdoc_1791091269174`의 CSV | `data/raw/reference_data/sgis2024/household/` |
| `_census_reqdoc_1791091231424`의 CSV | `data/raw/reference_data/sgis2024/housing/` |
| `_census_reqdoc_1791091177542`의 CSV | `data/raw/reference_data/sgis2024/business/` |

SGIS 통계 원본은 [SGIS](https://sgis.kostat.go.kr)의 자료제공에서 받은 2024년 자료이며,
제공용 코드표는 같은 자료의 코드 설명 파일이다. 기존 수령 원본의 파일명과 4열 구조를 유지한다.
데이터와 실행 결과는 Git에 넣지 않는다. 제공 데이터의 재배포·제출 범위는 대회 안내를 따른다.

## 3. 실행

저장소 루트에서 실행한다. 노트북의 상대경로 탐색은 루트와 `notebooks/` 작업 폴더를 모두 지원한다.

```bash
uv run jupyter nbconvert --to notebook --execute \
  notebooks/261008_GIS_sgis2024_master_merge.ipynb \
  --ExecutePreprocessor.timeout=600 \
  --output 261008_GIS_sgis2024_master_merge.executed.ipynb \
  --output-dir data/processed/sgis_master_validation
```

또는 저장소의 Python 환경을 커널로 선택하고 노트북의 모든 셀을 순서대로 실행한다.
다른 폴더 구조를 쓰면 2절 경로 셀의 입력 위치만 변경한다.

## 4. 산출물과 후속 코드

| 파일 | 위치 | 현재 자료의 행 × 열 |
|---|---|---:|
| `master_sgis2024.csv` | `data/interim/1차 merge/` | 10,188 × 491 |
| `sgis2024_value_status.csv` | 동일 | 1,698 × 298 |
| `sgis2024_variable_dictionary.csv` | 동일 | 297 × 12 |
| `master_sgis2024_selected_no_industry_counts.csv` | `data/processed/` | 10,188 × 203 |

`src/data/paths.py`의 `master_files()`가 앞의 3개 파일을 찾는다.
`master_analysis.py`·`seoul_comm.py` 등은 이 자료를 쓰고, v3.3 지수 생성기는 마지막 203열 마스터를 사용한다.

중간 289열 선택 결과, 변수별 유지·제외 목록, 선택된 변수 설명표, `merge_report.json`·`selection_report.json`은
`data/processed/sgis_master_validation/`에 저장한다. 재실행하면 위 이름의 생성 산출물을 갱신한다.
원본 SK·SGIS·코드표 파일은 수정하지 않는다. 다른 출력 경로를 쓰려면 경로 셀의 세 출력 디렉터리를 변경한다.

## 5. 계산과 검증 범위

- 키는 `STD_YM` 6자리와 `TOT_OA_CD` 14자리 문자열이다. 원본 중복 키는 합치거나 첫 행을 고르지 않고 중단한다.
- SGIS를 집계구별 297개 변수로 펼친 뒤 SK 마스터에 `many_to_one` 왼쪽 결합한다.
  2024년의 같은 통계값을 2025년 각 월에 붙이며 SK의 기존 셀·행 순서를 보존한다.
- `numeric`, `source_na`(원본 `N/A`), `no_record`(원본 행 없음)를 상태표에 구분한다.
  비공개값과 기록 없음을 0으로 채우지 않는다.
- 사업체·종사자 코드는 제공용 코드표의 **11차 산업분류**를 연결한다.
  건축연도 구간 제목과 2024년 항목의 표기 차이는 변수 설명표의 메모에 남긴다.
- 기존 선택 조건대로 491열에서 SGIS 113열과 SK 품질 중복·상수 89열을 제외해 289열을 만든 뒤,
  업종별 사업체 수 86열을 제외해 203열을 남긴다. 중복·전부 공백·전부 0 조건을 실제 입력에서 재검사한다.
- 저장 후 다시 읽어 행·열 순서와 셀 내용을 검사한다. 집계구 코드 일치는 확인하지만,
  서로 다른 연도의 **공간 경계가 동일하다는 검증은 하지 않는다.**

원본 배치부터의 전체 재현에는 선행 SK 공간 집계 입력도 필요하다.
이 노트북은 이미 생성된 SK 집계구 통합 CSV부터 SGIS 결합·변수 선택 단계까지 담당한다.

## 6. 2026-10-26 재현 확인

저장소 잠금 환경(Python 3.11.11, pandas 3.0.2, xlrd 2.0.2)에서 실제 Jupyter 커널로 전체 셀을 실행했다.
기존 SK 집계구 통합 CSV·SGIS 원본 CSV 38개·코드표를 입력으로 사용했으며,
SK 원시 격자에서 집계구로 공간 집계하는 선행 단계는 이번 비교에서 다시 실행하지 않았다.

위 4개 산출물은 2026-10-14 실행 때 보관한 파일과 행·열 순서와 모든 셀 값이 같고,
**파일 바이트도 모두 일치**했다. 최종 203열 파일은 이전 v3.3 지수 재현에 사용한 공유본과도 셀 단위로 일치했다.
출력 경로만 저장소 기준으로 옮겼으며, 원래 결합·선택 결과는 유지된다.
