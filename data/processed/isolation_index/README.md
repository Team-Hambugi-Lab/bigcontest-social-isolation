# 고립 위험 지수 프로토타입 결과

[이슈 #13](https://github.com/Team-Hambugi-Lab/bigcontest-social-isolation/issues/13)의 외부 검증용으로 공유한 결과다. 사용자가 제공한 CSV를 값이나 행을 수정하지 않고 저장했다. 노트북 경로 수정 후 새로 계산한 결과는 아니다.

## 공유 파일

| 파일 | 설정 | 행·열 |
| --- | --- | --- |
| [isolation_index_prototype.csv](isolation_index_prototype.csv) | 노후주택 포함, 6개 차원 등가중 | 1,649행 × 24열 |
| [isolation_index_no_oldho.csv](isolation_index_no_oldho.csv) | 노후주택 가중치 0, 나머지 5개 차원 등가중 | 1,649행 × 24열 |

두 파일은 강남구 1,055개, 춘천시 594개 집계구를 포함한다. 노후주택 제외 파일에도 `p_oldho`, `z_p_oldho` 열은 참고용으로 남아 있지만 종합점수의 가중치는 0이다.

## 산출 기준

원본 [프로토타입 노트북](../../../notebooks/261015_GIS_isolation_index_prototype.ipynb)의 설정과 계산식을 기록했다. 확정된 고립 판정 기준이 아니다.

| 차원 | 원본 산식 | 위험 점수 방향 |
| --- | --- | --- |
| 독거 | 1인가구 / 일반가구 수 | 높을수록 증가 |
| 고령 | 65세 이상 인구 / 총인구 | 높을수록 증가 |
| 중장년 남성 | 50~64세 남성 / 총인구 | 높을수록 증가 |
| 주거취약 | (주택이외 거처 + 비주거용 건물내 주택 + 20㎡ 이하 주택) / (총주택 + 주택이외 거처) | 높을수록 증가 |
| 노후주택 | 1989년 이전 주택 / 총주택 | 높을수록 증가 |
| 거주자당 유동 | log(1 + 요일별 유동인구 평균의 6개월 평균 / 총인구) | 낮을수록 증가 |

- 데이터 기간: SGIS 2024년, 통신인구 2025년 7~12월.
- 결측 처리: 원본 프로토타입은 SGIS 결측을 모두 0으로 대체한다. `source_na`와 `no_record`를 구분하지 않은 잠정 가정이다.
- 점수화: 차원별 표준화(`pandas.std()` 기본값 `ddof=1`) 후 방향을 맞추고 z-score를 -3~3으로 절단한다. 가중 평균 점수를 계산한다.
- 등급: 포함된 강남구·춘천시 집계구를 합친 전체 점수의 백분위를 20% 단위로 나눈다. 지역별 백분위가 아니며, 5등급이 상대적으로 높은 점수다.
- 제외 기준: 원본은 총인구·일반가구·총주택이 모두 양수이고, 첫 달의 `HAS_SK_POINTS`가 참인 집계구를 포함한다.
- 제공된 CSV에는 제외된 49개 집계구의 행이나 제외 사유 열이 없다. 이슈에서 요청한 전체 집계구별 제외 사유는 별도 보완 대상이다.
- 주거취약 분자는 주택유형과 면적 구간을 함께 더하므로 중복 집계 가능성이 있는 원본 산식이다. 이번 변경은 경로 정리와 결과 공유이며 산식을 수정하거나 외부 타당성을 검증하지 않았다.

## 실행 및 읽기

저장소 루트에서 `uv sync --extra dev --extra gis`로 실행 환경을 준비한다. 노트북은 저장소 루트 또는 `notebooks/`를 작업 폴더로 실행할 수 있다.

입력 자료는 다음 상대경로에 배치한다.

```text
data/processed/master_sgis2024_selected_no_industry_counts.csv
data/raw/reference_data/강남_집계구경계/bnd_oa_11230_2025_2Q.shp
data/raw/reference_data/춘천_집계구경계/bnd_oa_32010_2025_2Q.shp
```

경계 파일은 지도·공간 파일 저장 셀에서 사용한다. `.shp`뿐 아니라 `.shx`, `.dbf`, `.prj` 등 구성 파일도 같은 폴더에 둔다. 노트북은 입력 마스터를 별도로 준비해야 하며, 결과 CSV 두 개가 입력 마스터를 대체하지 않는다.

CSV, 지도 이미지, 공간 파일의 저장 위치는 모두 이 폴더다. 노트북을 다시 실행하면 같은 이름의 결과 파일을 갱신한다. Git에서는 명시적으로 공유한 CSV 두 개와 이 안내만 추적한다.

CSV에는 자료형 정보가 없으므로 집계구·행정동 코드를 문자열로 지정해서 읽는다.

```python
from pathlib import Path
import pandas as pd

# 저장소 루트에서 실행
result_dir = Path("data/processed/isolation_index")
result = pd.read_csv(
    result_dir / "isolation_index_prototype.csv",
    dtype={"TOT_OA_CD": str, "ADM_CD": str},
    encoding="utf-8-sig",
)
```
