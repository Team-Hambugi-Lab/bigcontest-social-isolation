# #18 위험 특징 24개와 기관 서비스 태그 연결 설계

> 작성일: 2026-10-24 · 상태: 구현·검증 및 Drive 반영 완료 · 기준: #18 worktree `d089e19`와 2026-10-24에 내려받은 기관 산출물

## 목적

[#17 위험 특징 사전](../agent/risk-features.md)의 **24개 `FEATURE_CODE`**를 [#18 기관 서비스 태그](../agent/resource-tags.md) **16종**에 세부 특징별로 연결한다. 24개는 태그 수가 아니라 사람의 상태를 나타내는 위험 특징 수다. 연결 결과는 기관의 제공 서비스에 맞는 **추천 후보와 순서**이며, 개인의 위험 등급이나 기관 이용 자격을 판정하지 않는다.

## 현재 상태와 입력

| 항목 | 2026-10-24 확인 결과 | 작업에서의 역할 |
|---|---|---|
| `data/processed/risk_feature_dictionary.csv` | 세부 특징 24행. 작업 전 `INSTITUTION_TAGS` 24행 공란 → 로컬 작업 후 24행 모두 후보 태그 반영 | 확정 코드·정의·`AGE_PATTERN`·`IS_CRISIS` 기준 |
| `src/features/institutions.py`의 `FEATURE_TAG_MAPPING` | 작업 전 7개 범주와 `CRISIS`의 26행 임시 연결 → 24개 세부 코드의 44행 후보 연결 | 코드별 조건과 우선순위 검토 결과 |
| `data/interim/feature_tag_mapping_a2_draft.csv` | 세부 코드 12개에 대한 39행 후보 | 적용 조건·오연결 경고 참고. 최종 승인본으로 간주하지 않음 |
| `src/features/risk_feature_dictionary.py` | 작업 전 병합할 때 `INSTITUTION_TAGS`를 비웠음 → 검증된 매핑에서 다시 채우도록 수정 | 재생성 시 후보 태그 유지 |
| 로컬 기관 데이터 경로 | `data/raw/reference_data`는 메인 체크아웃을 가리킨다. `복지기관_수집/` 원본 폴더는 미확인. Drive의 기관 목록·매핑·지원사업 CSV와 각 열 정의서 6개는 메인 체크아웃 `data/processed/`에 내려받고 이 worktree에 심볼릭 링크로 연결함(2026-10-24) | 매핑 수정은 기존 로컬 산출물을 입력으로 진행. 원본 재수집 여부는 별도 확인 |
| Drive `processed` | 프로젝트 [공유 폴더](https://drive.google.com/drive/folders/1ZJSRH3QHwyCUBdIqnYVmvJlQCZgtUHWp)에 `institutions.csv` 17,925행, `support_programs.csv` 60행이 있음. `feature_tag_mapping.csv`는 작업 전 26행에서 44행으로 갱신함(2026-10-24) | 기관 태그 가용성과 갱신 결과의 공유 위치 |

로컬 파일을 다시 읽어 `institutions.csv`의 `INST_ID` 17,925개가 중복 없이 존재하고 `TAGS`에서 16종 태그가 나오는 것을 확인했다. `TARGET_AGE`는 `ALL` 6,539행, `65+` 10,636행, `60+` 750행이다. 작업 전 매핑은 `CRISIS`와 7개 범주명이었고, 현재 로컬 매핑은 24개 세부 코드에 44행이다. 이 중 실제 연결에 쓰인 태그는 14종이다. `ADDICTION`과 `DEMENTIA`는 대응하는 직접 특징이 없어 연결하지 않았다. `N_INSTITUTIONS`는 전체 기관 수이므로 특정 지역·연령에서 이용 가능한 기관 수로 해석하지 않는다.

GitHub 이슈 #18의 최신 본문은 이번 점검에서 커넥터 404로 확인하지 못했다. 구현 전에 접근 가능한 원문·댓글이 있으면 현재 범위와 달라진 결정이 있는지 대조한다.

2026-10-24에 연결된 Google Drive의 [프로젝트 원본 `reference_data` 폴더](https://drive.google.com/drive/folders/1iQ9s3oTOousAR2PPUsljMCspVV77Vsr9)(19개 항목)도 확인했다. 그 지정된 공유 위치에서 `복지기관_수집` 폴더와 코드가 요구하는 대표 CSV는 확인되지 않았다. 이는 드라이브 전체에 파일이 없다는 뜻은 아니다.

### 전수 검토할 코드

| 범주 | 코드 |
|---|---|
| REL (7) | `REL_NO_CONFIDANT`, `REL_NO_ADVICE`, `REL_FAMILY_CONFLICT`, `REL_NO_FAMILY`, `REL_LONELY`, `REL_NO_PRACTICAL_SUPPORT`, `REL_LOW_CONTACT` |
| OUT (2) | `OUT_LONG_DURATION`, `OUT_NO_ACTIVITY` |
| SOLO (2) | `SOLO_LIVING`, `SOLO_MEAL` |
| BODY (5) | `BODY_POOR_HEALTH`, `BODY_HYGIENE`, `BODY_HOME_CARE`, `BODY_SLEEP`, `BODY_MOBILITY_LIMIT` |
| MIND (5) | `MIND_POOR_MENTAL`, `MIND_HOPELESS`, `MIND_SOCIAL_ANXIETY`, `MIND_SUICIDE_IDEA`, `MIND_SUICIDE_ATTEMPT` |
| ECON (2) | `ECON_NO_INCOME`, `ECON_LOW_STATUS` |
| HOUSE (1) | `HOUSE_UNSTABLE` |

## 입출력 계약

| 자료 | 역할 | 유지·변경 범위 |
|---|---|---|
| `data/processed/risk_feature_dictionary.csv` | 24개 `FEATURE_CODE`, 정의, 연령별 양상, 위기 여부의 기준 | 24행과 기존 정의를 보존하고 `INSTITUTION_TAGS`만 최종 후보 태그로 채움 |
| `data/processed/institutions.csv` | 16종 태그와 `N_INSTITUTIONS`의 기준 | 읽기 전용. 기관 행과 유형별 태그를 이번 작업에서 재생성하지 않음 |
| `src/features/institutions.py`의 `FEATURE_TAG_MAPPING` | 검토한 코드·태그·우선순위·조건의 단일 원본 | 범주 코드 26행을 세부 코드 기준으로 교체 |
| `data/processed/feature_tag_mapping.csv` | 에이전트가 확인할 긴 형태의 연결표 | 기존 5열 `FEATURE_CODE`, `TAG`, `PRIORITY`, `NOTE`, `N_INSTITUTIONS` 유지. 행 수는 코드별 검토 결과에 따름 |
| `data/processed/feature_tag_mapping_dictionary.csv`, `risk_feature_dictionary_dictionary.csv` | 각 열의 의미와 결측 설명 | `FEATURE_CODE`와 `INSTITUTION_TAGS` 설명을 세부 코드·후보 의미로 고침 |

`FEATURE_TAG_MAPPING`의 한 행은 **특징과 서비스의 후보 연결**이다. `PRIORITY`는 같은 특징 안에서 후보를 살펴볼 순서이며 위험 점수나 서비스의 적격 판정이 아니다. `NOTE`에는 왜 연결했는지와 추가 확인 조건을 남긴다. `N_INSTITUTIONS`는 `institutions.csv`의 `TAGS`를 분리해 계산하며, 특정 특징에 실제로 적합한 기관 수를 뜻하지 않는다.

`INSTITUTION_TAGS`는 같은 매핑에서 특징별 `PRIORITY` 순으로 태그를 `;`로 이은 **후보 요약**이다. 이 열만 읽어 자동 추천을 확정하지 않는다. 추천 단계에서는 긴 형태 매핑의 `NOTE`, 기관의 실제 서비스·대상 연령·지역·운영 상태, 본인 의사를 확인한다. 구조화된 조건 판정 로직이 없는 현재 단계에서는 조건부 후보도 자동으로 통과시키지 않는다. 검토 후 연결 근거가 없는 코드는 빈칸을 유지하고 문서에 미매핑 사유를 명시한다.

### 생성 경로

기존 `python -m src.features.institutions`는 `build_institutions()`부터 실행해 미확인인 `복지기관_수집/` 원본을 요구한다. 추가한 **매핑 전용 경로**는 로컬 `data/processed/institutions.csv`를 읽어 `feature_tag_mapping.csv`와 열 정의서만 만든다. 이 경로는 `institutions.csv`와 `support_programs.csv`를 쓰지 않는다. `risk_feature_dictionary.py`는 같은 매핑을 읽어 `INSTITUTION_TAGS`를 채우며, 매핑이 없거나 코드·태그 검증에 실패하면 기존 사전을 덮어쓰기 전에 중단한다.

실행 인터페이스는 다음처럼 한 번의 임시 출력 위치를 공유한다. `--mapping-only`는 기관·지원사업 재생성을 건너뛰고, `--mapping-path`는 방금 검증한 매핑을 사전에 반영한다.

```text
uv run python -m src.features.institutions --mapping-only --out-dir <임시_출력_위치>
uv run python -m src.features.risk_feature_dictionary --mapping-path <임시_출력_위치>/feature_tag_mapping.csv --out-dir <임시_출력_위치>
```

공유 `data/processed/`가 다른 체크아웃과 연결돼 있으므로 새 CSV는 먼저 별도 출력 위치에서 생성·검증한 뒤 기존 파일과 교체했다. 기존 사전과 새 사전의 12개 열 중 `INSTITUTION_TAGS` 외 값·행 순서가 같은지도 확인했다. 교체 전 로컬 CSV 4개는 임시 백업에 보존했다. Drive의 해당 CSV 4개도 기존 파일 ID를 유지한 채 갱신했고, 연결된 파일을 다시 읽어 로컬 결과와 내용이 같음을 확인했다.

## 매핑 검토 기준

1. **24개 코드 전수 검토:** 코드 이름만으로 범주 규칙을 복사하지 않는다. 사전의 `DEFINITION`, `AGE_PATTERN`, `IS_CRISIS`, 기존 태그 정의, A-2 후보의 `NOTE`를 함께 읽는다. 근거가 부족한 코드도 검토 결과를 기록하고, 임의 태그를 채우지 않는다.
2. **특징과 서비스의 직접 관련성:** 해당 특징만으로 필요한 서비스와, 추가 확인이 있어야 적합한 서비스를 구분한다. 예를 들어 `REL_NO_CONFIDANT`만으로 `FAMILY`, `MIND_POOR_MENTAL`만으로 `ADDICTION`, 고령 또는 신체 어려움만으로 `DEMENTIA`를 자동 연결하지 않는다.
3. **대상·지역·이용 조건:** `TARGET_AGE`, 지역 내 실제 기관 유무, 기관의 서비스·운영 상태와 본인 의사를 추천 시 확인한다. `ISOLATION_CARE`는 현재 문서상 서울에만 있으므로 다른 지역의 대체 후보를 검토한다. `NOTE`의 자연어 조건만으로 자동 필터가 구현된 것처럼 표현하지 않는다.
4. **위기 처리 분리:** `MIND_SUICIDE_IDEA`, `MIND_SUICIDE_ATTEMPT`는 사전의 `IS_CRISIS=Y`를 유지한다. `CRISIS_LINE`은 사람에게 이관할 때 함께 안내하는 자원으로 다루고, 일반 추천 우선순위만으로 위기 대응을 대신하지 않는다.
5. **우선순위:** 특징별 1부터 시작하는 순서를 검토한다. 여러 조건부 후보가 있더라도, 조건이 확인되지 않으면 그 후보를 확정 추천하지 않는다.

## 작업 순서

1. **기준 고정:** 24개 `FEATURE_CODE`의 중복·결측과 `IS_CRISIS` 값을 다시 확인한다. 로컬 `institutions.csv`의 키·열·16종 태그와 기존 매핑 26행을 기준 자료로 고정한다. `복지기관_수집/` 원본 위치 확인은 기관 목록 전체 재생성과 관련된 별도 과제로 남긴다.
2. **코드별 매핑표 검토:** 각 특징에 대해 기존 범주 연결과 A-2 후보를 대조해 유지·제외·조건부 추가를 결정한다. 판단 근거와 적용 조건을 `NOTE`에 남기고, 연결하지 않는 코드는 이유를 검토 기록에 남긴다. 24개 코드 모두 검토됐는지 확인한다.
3. **생성 경로 반영:** `institutions.py`에 기존 기관 목록을 읽는 매핑 전용 실행 경로를 추가한다. `risk_feature_dictionary.py`는 검증된 매핑을 읽어 `INSTITUTION_TAGS`를 채운다. `institutions.csv`·`support_programs.csv`의 재생성을 요구하지 않으며, 사전을 다시 만들어도 태그가 공란으로 돌아가지 않게 한다.
4. **정의서·문서 동기화:** 두 CSV의 열 정의서에서 `FEATURE_CODE`와 `INSTITUTION_TAGS`의 뜻·결측 설명을 갱신한다. `docs/agent/resource-tags.md`의 임시 범주 표·설명을 세부 코드 기준으로 바꾸고, `docs/agent/risk-features.md`의 미완료 설명을 실제 결과에 맞춘다. 조건부 연결과 미매핑 코드를 명시한다.
5. **검증:** 작은 합성 자료 테스트로 24개 코드 전수 검토, 알 수 없는 코드·태그 거부, 중복된 코드·태그와 잘못된 우선순위 검출, 두 위기 코드의 이관 태그, 사전 재생성 시 태그 보존을 확인한다. 로컬 실제 CSV로 코드 집합·태그 집합·빈값·기관 수를 대조하고, 매핑 전용 실행 전후의 기관 목록·지원사업 파일 해시가 같음을 확인한다. 관련 린트·포맷·테스트 결과를 보고한다.

## 완료 기준

- 24개 코드 각각에 **연결 행 또는 미매핑 사유**가 있다. `feature_tag_mapping.csv`에는 검토를 통과한 연결만 들어간다.
- 매핑의 모든 코드는 사전에, 모든 태그는 기관 태그 16종 정의에 존재한다. 특징별 우선순위와 `NOTE`의 적용 조건이 검토됐다.
- `risk_feature_dictionary.csv`의 `INSTITUTION_TAGS`가 같은 최종 매핑을 반영하며, 생성 명령을 다시 실행해도 결과가 유지된다. 의도적으로 미매핑인 코드와 누락 오류를 구분할 수 있다.
- 문서, 생성 코드, 테스트, 실제 산출물의 코드 집합과 의미가 일치한다. 로컬 기관 목록으로 태그별 기관 수를 검증하고, `institutions.csv`와 `support_programs.csv`의 내용은 바뀌지 않는다.

## 이번 설계의 범위

기관 16종 태그 어휘나 기관 유형별 태그를 재설계하지 않았다. 지역 지수로 개인의 특징을 판정하거나, 서비스 조건 확인 없이 자동 추천을 확정하는 로직은 추가하지 않았다. 로컬과 Drive의 매핑·위험 특징 사전 CSV를 갱신했다. #19 추천 로직은 이 작업 범위에 포함하지 않았다.

## 2026-10-24 구현 검증

- 로컬 결과: `feature_tag_mapping.csv` 44행·5열, `risk_feature_dictionary.csv` 24행·12열. 모든 특징에 후보가 있어 미매핑 코드는 없다.
- 기존 위험 특징 사전의 `INSTITUTION_TAGS` 외 11개 열과 행 순서가 동일하다. 두 생성 명령을 다시 실행한 결과도 바이트 단위로 동일하다.
- `institutions.csv`(17,925행)와 `support_programs.csv`(60행)는 수정 전후 SHA-256이 같다.
- Drive `processed`의 매핑·위험 특징 사전 CSV 및 각 열 정의서 4개를 기존 파일 ID로 갱신하고, 읽어온 내용이 로컬 파일과 같은지 확인했다.
- `uv run --extra dev python -m ruff check src/ tests/`, `uv run --extra dev python -m ruff format --check src/ tests/`를 통과했다. 전체 테스트 재실행 결과 264개 모두 통과했다.
