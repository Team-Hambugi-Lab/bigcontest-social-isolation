# 노트북 작성 규칙

## 파일명

```text
YYMMDD_유형_주제.ipynb
```

- 날짜는 작성 시작일을 `YYMMDD`로 기록합니다.
- 유형은 아래 약어를 사용합니다.
- 주제는 영문 소문자 `snake_case`로 간결하게 작성합니다.

| 유형 | 약어 |
| --- | --- |
| 탐색적 데이터 분석 | `EDA` |
| 머신러닝 | `ML` |
| 회귀·인과추론 | `REG` |
| 시계열 | `TS` |
| 지리공간 분석 | `GIS` |
| 시각화 | `VIZ` |

예시:

```text
260920_EDA_shinhan_payment.ipynb
260920_GIS_sk_region_mapping.ipynb
260920_ML_isolation_risk.ipynb
```

## 제목

노트북 첫 번째 셀은 다음 형식의 Markdown H1 제목으로 작성합니다.

```text
# [유형] 주제 — YYYY-MM-DD
```

파일명과 제목은 같은 유형·주제를 나타내야 합니다.

```text
260920_EDA_shinhan_payment.ipynb
# [EDA] 신한카드 결제 데이터 탐색 — 2026-09-20
```

## 상단 기록 항목

제목 다음에는 분석 목적, 데이터 파일명과 기간, 주요 파라미터, 난수 시드, 실행 환경을 기록합니다. 집계 데이터의 해석 범위와 알려진 한계도 함께 명시합니다.

상세 출력 규칙은 [`.claude/rules/04_output_format.md`](../.claude/rules/04_output_format.md)를 따릅니다.
