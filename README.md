# 집계구 기반 사회적 고립 조기 탐지와 지속 관리

**지역의 신호를 복지 지원으로 연결하는 AI 에이전트**

2026 빅콘테스트 AI데이터활용 분야 · 팀 햄부기 (김태은, 이정연, 진재언)

서울 강남구와 강원 춘천시의 집계구(약 200가구 단위) 1,698곳을 대상으로, 2025년 7~12월 SK텔레콤 유동인구와 SGIS 2024 통계를 결합해 사회적 고립 위험이 높은 지역을 찾고, 위험 특징별로 연결할 공공·복지 자원을 정리한 분석 코드입니다. 제공 데이터는 비식별 집계값이므로 **개인의 고립 여부를 판정하지 않고**, 지역 결과는 에이전트가 어디를 먼저 살필지 정하는 데만 씁니다.

## 분석 흐름

```text
위험 신호 탐지 → 위험 수준 판단 → 원인 분석 → 복지자원 추천 → 우선 지원 지역
```

| 구성 | 내용 | 근거 문서 |
|---|---|---|
| 축 1 노출 지수 | SGIS 2024 집계구 통계로 만든 고립 위험 지수 v3.3. 테마 A(고령 독거)·B(중장년 독거·주거 취약) 백분위와 5등급 | [지수 안내](docs/isolation_index_v3.md), [변수 정의](docs/isolation_index_v3_dictionary.md) |
| 축 2 활동 신호 | 연령대별 기대 유동 모델(OLS)의 잔차로 60대 이상 활동 저하가 6개월 중 지속되는 집계구 판정 | [보고서](reports/261017_REG_h4_activity_signal.md), [설계](docs/design/activity_signal_design.md) |
| 외부 검증 | 서울 시민생활 데이터(통신 관심집단·1인가구 통신정보)로 강남 22개 행정동 연관 검증 | [통신 검증](reports/261022_EDA_telecom_validation_v3.md), [강남 동 검증](reports/261023_REG_gangnam_dong_validation.md) |
| 위험 특징 사전 | 청년·고령 실태조사 근거로 정리한 24개 위험 특징과 위기(`IS_CRISIS`) 기준 | [위험 특징](docs/risk-features.md) |
| 복지자원 매핑 | 수도권·춘천 복지·공공기관 17,925곳의 서비스 태그와 위험 특징 44개 연결 | [서비스 태그](docs/resource-tags.md) |

문헌 검토와 고립 정의는 [연구 방법론](docs/methodology/README.md)에 있습니다.

## 환경

Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)를 사용합니다. 공간 조인에 geopandas가 필요하므로 `gis`를 함께 설치합니다.

```bash
uv sync --extra dev --extra gis
```

## 데이터 배치

데이터 파일은 Git에 넣지 않습니다. 대회 제공 데이터(SK텔레콤·신한카드)는 재배포하지 않으므로 각자 받은 파일을 아래 위치에 둡니다. 외부 데이터 원본은 제출물에 함께 첨부합니다.

```text
data/raw/
├── sk_telecom/                 # 제공 SK 유동인구 CSV (flow_{age,time,wkdy}_pop_YYYYMM.csv)
├── shinhan_card/               # 제공 신한카드 CSV 2개
└── reference_data/             # 외부 데이터 (아래 표)
```

폴더별 구성과 파일 크기는 [`data/raw/README.md`](data/raw/README.md), 열 정의와 결합 기준은 [제공·외부 데이터 명세](docs/data-overview.md)를 참고하세요.

## 재현 순서

저장소 루트에서 순서대로 실행합니다. 각 단계는 앞 단계의 산출물을 읽습니다.

| 단계 | 실행 | 주요 산출물 |
|---|---|---|
| 1. SK 월별 통합 | `uv run python -m src.features.build_sk_integrated` | `data/raw/sk_통신인구_YYYYMM_통합.csv` 6개 |
| 2. 집계구 공간 집계 | `notebooks/261005_GIS_skt_census_aggregation.ipynb`를 마지막 월별 통합 셀까지 실행 | `data/processed/sk_통합_집계구/` |
| 3. SGIS 결합·변수 선택 | `notebooks/261008_GIS_sgis2024_master_merge.ipynb` 전체 실행 ([실행 안내](docs/sgis_master_reproduction.md)) | `data/interim/1차 merge/master_sgis2024.csv` 외 2개, `data/processed/master_sgis2024_selected_no_industry_counts.csv` |
| 4. 분석 마스터 | `uv run python -m src.features.master_analysis` | `data/processed/master_analysis.csv` |
| 5. 노출 지수 v3.3 | `uv run python -m src.features.isolation_index_v3` (같은 계산의 설명용 노트북: `notebooks/261020_GIS_isolation_index_v3.ipynb`) | `data/interim/v3.3/isolation_index_v3.csv`, `isolation_index_v3_adm.csv` |
| 6. 활동 신호 | `uv run python -m src.modeling.h4_activity_signal` | `data/processed/h4_signal_oa.csv`, `h4_signal_dong.csv` |
| 7. 노출 × 활동 결합 | `uv run python -m src.modeling.h4_exposure_join` | `data/processed/h4_exposure_oa.csv`, `h4_exposure_combined_dong.csv` |
| 8. 통신 관심집단 검증 | `uv run python -m src.evaluation.telecom_validation` | `data/interim/gangnam22_v3_validation.csv` 외 |
| 9. 활동 신호 방향 검증 | `uv run python -m src.evaluation.h4_external_validation` | `data/interim/h4_external_validation.csv` |
| 10. 강남 동 검증 보완 | `notebooks/261015_GIS_isolation_index_prototype.ipynb` 실행 후 `uv run python -m src.features.seoul_comm` | `data/processed/validation_gangnam_*.csv`, `reports/261023_gangnam_prototype_scatter.png` |
| 11. 위험 특징 사전 | `uv run python -m src.features.risk_features_youth` → `uv run python -m src.features.risk_feature_dictionary` | `data/interim/risk_features_youth.csv`, `data/processed/risk_feature_dictionary.csv` |
| 12. 복지자원 DB | `uv run python -m src.features.institutions` (원본 없이 매핑만: `--mapping-only`) | `data/processed/institutions.csv`, `feature_tag_mapping.csv` |

- 11단계의 고령·중장년 근거표(`data/interim/risk_features_senior.csv`, `proposed_senior_features.csv`)는 문헌을 직접 읽고 작성한 입력이라 생성 코드가 없습니다. 제출물에 함께 첨부하며, 근거 쪽수는 [위험 특징](docs/risk-features.md)에 있습니다.
- 12단계의 서울시고립예방센터 원본은 `uv run python scripts/collect_sihsc.py`로 다시 받습니다.
- 8·10단계의 부트스트랩 난수는 시드 42로 고정했습니다.

## 외부 데이터

모두 무료 공개 데이터입니다. 원본은 `data/raw/reference_data/` 구조 그대로 제출물에 첨부합니다.

| 자료 | 출처 | 사용 단계 |
|---|---|---|
| SGIS 2024 집계구 통계(인구·가구·주택·사업체)와 제공용 코드표 | [SGIS 통계지리정보서비스](https://sgis.kostat.go.kr) 자료제공 | 3 |
| 집계구·행정동 경계(2025년 2분기) | 같은 곳 | 2, 5 |
| 서울 행정동 10개 관심집단수(2025.07~12) | [서울 열린데이터광장 OA-22266](https://data.seoul.go.kr/dataList/OA-22266/F/1/datasetView.do) | 8 |
| 서울 행정동 29개 통신정보(2025.07~12) | [서울 열린데이터광장 OA-22267](https://data.seoul.go.kr/dataList/OA-22267/F/1/datasetView.do) | 9, 10 |
| 보건복지부 2023 고립·은둔 청년 실태조사 | 보건복지부 | 11 |
| 서울시 2022 고립·은둔 청년 실태조사 집계표 | 서울특별시, [서울연구원 보고서](https://www.si.re.kr/sites/default/files/smallresearch/small-23-03.pdf) | 11 |
| 고독사 예방 기본계획·고독사 실태조사·노인실태조사 등 | 보건복지부·관계부처 (출처 S1~S6) | 11 |
| 복지·공공기관 목록 | 공공데이터포털, 서울 열린데이터광장, 경기데이터드림, 서울시고립예방센터 (기관별 출처 URL은 `institutions.csv`에 기록) | 12 |

## LLM 활용

- **에이전트 설계:** 위험 수준 판단과 자원 추천은 규칙이 하고, LLM은 사용자와의 대화와 결과 설명만 맡습니다. 위기 신호(자살 생각·시도)는 LLM이 판단하지 않고 사람에게 바로 넘깁니다. 이번 제출물에서 에이전트는 코드로 구현하지 않고 설계와 시연 흐름으로 제시합니다.
- **합성 데이터:** 개인 단위 시연에 쓴 인물과 대화는 가상의 페르소나입니다. 연결한 기관과 지원사업은 `institutions.csv`의 실제 행입니다.
- **개발 보조:** 코드 작성·검토와 발표자료 초안에 AI 도구를 사용했고, 수치와 문장은 팀원이 보고서·산출물과 대조해 확인했습니다.

자세한 활용 방법은 **[확인 필요: 에이전트 설계 문서의 LLM 활용 절 링크]**를 참고하세요.

## 디렉터리 구조

```text
├── data/                 # raw(원본) · interim(중간) · processed(최종). 파일은 Git 제외
├── docs/
│   ├── data-overview.md            # 제공·외부 데이터 명세
│   ├── sgis_master_reproduction.md # 3단계 실행 안내
│   ├── isolation_index_v3*.md      # 노출 지수 산식·변수 정의
│   ├── risk-features.md            # 위험 특징 사전
│   ├── resource-tags.md            # 기관 서비스 태그와 매핑
│   ├── design/                     # 활동 신호·외부 검증 설계
│   └── methodology/                # 문헌 검토와 연구 틀
├── notebooks/            # 집계구 집계(261005), SGIS 결합(261008), 프로토타입(261015), 지수 v3(261020)
├── reports/              # 활동 신호, 통신 검증, 강남 동 검증 보고서
├── scripts/              # 서울시고립예방센터 수집, 활동 신호 입력 점검
├── src/
│   ├── data/             # 경로·로더·외부 데이터
│   ├── features/         # 마스터, 지수, 위험 특징, 기관 DB
│   ├── modeling/         # 활동 신호, 노출 결합
│   └── evaluation/       # 외부 검증
└── tests/
```

## 검증

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/ -v
```

데이터 파일이 필요한 테스트는 `requires_data` 표시가 있으며, 데이터가 없으면 `uv run pytest -m "not requires_data"`로 나머지만 실행합니다.

## 한계

- 제공 데이터와 SGIS는 집계값이라 개인의 고립을 판정할 수 없습니다. 결과는 관찰 우선 지역을 고르는 데만 씁니다.
- 외부 검증은 서울 자료만 있어 강남 22개 행정동에서만 했고, 춘천은 검증하지 못했습니다.
- SGIS는 2024년, SK는 2025년 자료라 시점이 다르며, 연도별 집계구 경계가 같은지는 검증하지 않았습니다.
- 활동 신호의 임계값(`tau=0.1`)은 분석 선택값이며 검증된 개인 고립 기준이 아닙니다.
