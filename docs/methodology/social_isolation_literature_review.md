# 사회적 고립 위험 지역 지표 — 선행연구 리뷰

> 작성: 2026-10-15
> 범위: 지역 단위(집계구·행정동·구)로 사회적 고립·고독사 위험을 추정한 연구. 개인 설문 기반 정의는 변수 선택 근거로만 요약.
> 표기: 원문을 직접 확인하지 못한 세부는 **(확인 필요)**. URL은 실제 확인된 것만 기재.

---

## 1. 왜 지역 단위인가

마스터 데이터는 집계구 1,698개(강남구 1,098 + 춘천시 600) × 6개월(2025.07~12)의 지역 집계 패널이다. SGIS 2024 센서스(가구·주택·성연령)는 월별 동일한 스냅샷이고, SK 유동인구(성×연령·시간대·요일)만 월별로 변한다. 개인 설문 문항(도움받을 사람 유무, 외출 빈도)은 없으므로 개인 단위 고립 정의를 직접 적용할 수 없다.

따라서 지표는 **"사회적 고립 위험이 높은 집계구를 식별하고, 그 지역의 위험군 인구 규모를 추정하는"** 생태학적 위험 지수로 설계한다. 같은 계열의 선례: 영국 Age UK/ONS 외로움 위험 지수(2016), 미국 America's Health Rankings 고립 위험 지수(2018~), 일본 東京都 孤独死 공간통계(2013), 국내 김소연 외(2024)·대구보건대(2026). 보건복지부 제1차 고독사 예방 기본계획(2023)도 "다세대·고시원 밀집지역, 공공임대 단지"를 고위험 지역으로 명시해 지역 표적화를 정책 단위로 채택했다.

주의: Wigfield & Alden(2018)은 지역 지수 단독으로는 다면적 고립을 포착하기 부족하다고 결론했고, ONS(2021)는 소표본 지역 간 순위 비교를 금지했다. 지수는 "위험 노출이 큰 지역"을 가리킬 뿐 개인의 고립을 단정하지 않는다(생태학적 오류).

---

## 2. 변수 선택의 근거: 개인 단위 정의 요약

지역 지수의 차원은 개인 단위 선행연구에서 반복 확인된 고립 요인에서 가져온다. 국내외 정의는 거의 예외 없이 고립을 **객관적 상태**(관계·접촉의 양이 적음)로 보고 외로움(주관)과 분리한다(NASEM 2020, WHO 2025, KIHASA 2022).

| 차원 | 개인 단위 대표 문항 | 출처 | 집계구 대리변수 |
| --- | --- | --- | --- |
| 동거·혼인 | 1인가구 / 미혼·비동거 | Berkman-Syme 1979, Steptoe 2013, UK Biobank 2018, NHATS 2020 | 1인가구율 |
| 연령·성별 | 65세+; 고독사 사망자 남성 81.7%, 50~60대 62.9% | [2024 고독사 실태조사](https://www.newsis.com/view/NISX20251127_0003419323), LSNS, AHR | 65세+ 비율, 50~64세 남성 비율 |
| 주거 | 원룸·오피스텔 19.6%, 고시원 4.8%, 모텔 4.2%에서 고독사; 위험군 월세 66.9%, 다가구 47% | 2024 실태조사, [서울시 고립 1인가구 조사](https://www.dailian.co.kr/news/view/1251658/), [기본계획](https://newstomato.com/ReadNews.aspx?no=1188100) | 주택이외 거처·비주거용·20㎡ 이하 비율, 노후주택 비율 |
| 접촉·외출 | 가족·친구 접촉 월 1회 미만; 외출 거의 없음 6개월+ | Steptoe 2013, 일본 孤独・孤立 조사, 내각부 히키코모리, 서울시 2022 | 유동인구 기반 대리변수 (간접) |
| 지지체계 | 아플 때·돈·이야기 상대 도움받을 사람 없음 | 통계청 사회조사, [KIHASA 김성아·노현주 2024](https://kihasa.re.kr/api/kihasa/file/download?seq=26347) | 측정 불가 |
| 사회참여 | 종교·단체 참여 없음 | Berkman-Syme, Steptoe, NHATS | 측정 불가 (사업체 밀도는 접근성 대리) |

개인 단위 라벨링 규칙 중 지역 지수 점수화 방식에 직접 참고한 것: Steptoe ELSA 지수(5항목 중 ≥2 = 고립), UK Biobank(3항목 중 ≥2), Berkman-Syme SNI(4항목 중 0~1). 모두 **결핍 항목 합산 → 임계값** 구조다.

---

## 3. 국내 지역 단위 연구

고독사·고립을 결과변수로 두고 지역 단위로 위험을 추정한 국내 연구는 구·행정동 수준 두·세 건이다. 집계구 수준 연구는 취약계층 분포·접근성에 머물고, 통신 데이터는 서울 시민생활 데이터가 유일한 공개 산출물이다.

| 자료 | 저자·기관·연도 | 단위 | 변수 | 위험 판정 | 검증 |
| --- | --- | --- | --- | --- | --- |
| [빅데이터 기반 고독사 고위험 지역 탐지](https://koreascience.kr/article/JAKO202431805382113.page) | 김소연·김수형·이봉규, 2024 | 서울 25개 구 | 65세+ 남성, 수급자, 의료시설 근접성, 다세대·연립 밀집도, 폭염·한파 일수 | 인구>경제>사회>건강>환경 가중 점수 × 실제 고독사율에 K-means(K=4) → HH 군집 6개 구 | 고독사 상위 6구 중 5구 일치 (통계적 검증 없음) |
| [대구 행정동 고독사 위험군 공간 군집](https://www.imaeil.com/page/view/2026030612145070587) | 대구보건대 강상훈 팀, 2026 | 142개 행정동 | 1인가구·고령자 비율, 수급자 비율, 단독·다가구·영구임대 | 동별 위험군/인구 → 공간 군집 → 상관. 수급자 1%p↑ → 위험군 약 8명↑ | 없음 (보도, 확인 필요) |
| [대구고립보고서 행정동 위험군 지도](https://www.imaeil.com/page/view/2025122614012107521) | 매일신문, 2025 | 142개 행정동 | 위험군 10,682명 / 인구 1천 명 | 상위 4개 동 평균 23.2 vs 전체 5.2. 오피스텔·원룸·영구임대 밀집 | 없음 |
| 서울시복지재단 고독사 다발 동 시범사업 ([프레시안](https://www.pressian.com/pages/articles/183654), [서울시](https://mediahub.seoul.go.kr/archives/2001466)) | 송인주, 2016·2021 | 사망 사례 → 동 | 연령·성별, 원룸·고시원·다가구 | 고독사 '확실'(독거·자택·3일+)/'위험' → 다발 동(대학동·가산동·하계1동) | 기술통계 |
| [취약계층 밀집지역의 안전여건 차이](https://scholar.kyobobook.co.kr/article/detail/4010028273696) | 오후, 2021 | 청주시 **집계구** | 취약계층 지표(세부 확인 필요) | LISA HH형 = 밀집지역 → 로지스틱 | 미기재 |
| [고령인구 보행속도 고려 공공서비스 접근성](https://www.kais99.org/jkais/journal/Vol25No01/vol25no01p32.pdf) | 전병윤·이창효·송학주, 2024 | 대전 3,014개 **집계구** | 65세+ 인구, 15분 서비스권 | Moran's I → 이변량 LISA | p<.05만 |
| [지방소멸 시기 노인돌봄 수요·자원 불일치](https://www.kihasa.re.kr/api/kihasa/file/download?seq=32676) | 조성아, 2026 | 1km 격자(SGIS) | 65세+·85세+ 비율, 돌봄시설 거리 | 네트워크 거리 커버리지 | — |
| [서울 시민생활 데이터](https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do) ([보도](https://mediahub.seoul.go.kr/archives/2005487)) | 서울시·SKT·서울시립대, 2022~ | 424개 행정동 × 성·연령 | SKT 통신 29종(통화대상자 수, 체류시간, 이동거리) | 야간 상주지 → 로지스틱으로 1인가구 확률 → 동 합산. 관심집단: 저이동 집단, 은둔형외톨이(가칭) | 통계청 1인가구 대비 +10.3% |
| 전력·통신 이상감지 ([서울](https://www.ajunews.com/view/20240205135404944), [경기](https://m.go.seoul.co.kr/news/2024/03/28/20240328500096), [서초](https://m.go.seoul.co.kr/news/2024/06/07/20240607500093)) | 2023~2026 | 가구 | 전력·통화·데이터 급감 | 임계값 미공개 | 미공개 |
| [한국사회보장정보원 고독사 위기대응 시스템](https://www.kukinews.com/article/view/kuk202602260082) | 복지부·정보원, 2026 | 개인 | 27종 위기정보 | AI 모형(비공개) | 미공개 |

실태조사가 제시하는 지역 위험요인:

- [2024년 고독사 실태조사](https://www.newsis.com/view/NISX20251127_0003419323): 남성 81.7%, 50~60대 62.9%. 주거 — 주택 48.9%, 아파트 19.7%, **원룸·오피스텔 19.6%(2020년 4.0%에서 급증)**, 고시원 4.8%, 모텔 4.2%.
- [제1차 기본계획](https://newstomato.com/ReadNews.aspx?no=1188100): 위험군 152.5만(1인가구의 21.3%). **다세대·고시원 밀집지역, 공공임대 단지 = 고위험 지역**.
- [서울시 고립 1인가구 실태조사](https://www.dailian.co.kr/news/view/1251658/): 위험군 주거 — 월세 66.9%, 지상 다가구 30.2%, 임대아파트 21.4%, 지하 다가구 17%.
- [인천시 고독사 위험계층 조사](https://newsseoul.co.kr/news/view/179591195892192): 사망자 주거 다가구 37.8%, 단독 30.6%, 임대아파트 13.8%.
- [대구시 중장년 1인가구 조사](https://www.twig24.com/news/health-welfare/2025/07/02/20250702500199): 위험군 7.6%. 쪽방·여관 24.5%, 고시원 22.1%, 원룸 15.2%; 수급자 31.7% vs 비수급 5.5%.

---

## 4. 해외 지역 단위 연구

영국이 가장 풍부하다. Age UK/ONS는 설문(ELSA) 회귀계수를 센서스 마이크로데이터에 적용해 소지역 유병률을 추정하고, 지자체 지수들은 센서스 변수를 z-score 또는 등가중 합산한다. 미국 AHR은 ACS 6변수 z-score 평균. 외부 결과(고독사·입원)로 검증한 사례는 확인되지 않았고, 일본 東京都監察医務院의 구별 孤独死 통계가 유일한 공식 결과변수다.

| 자료 | 기관·연도 | 단위 | 변수 | 점수화 | 검증 |
| --- | --- | --- | --- | --- | --- |
| Risk of Loneliness Index ([방법론](https://auk-cms-web1.ageuk.org.uk/contentassets/972087f6d82841569c55d96a86e0dd87/age_uk_loneliness_risk_index_summary-july2015.pdf), [모형 논문](https://www.ageuk.org.uk/siteassets/documents/reports-and-publications/reports-and-briefings/health--wellbeing/predicting_the_prevalence_of_loneliness_at_older_ages.pdf), [데이터](https://data.london.gov.uk/dataset/probability-of-loneliness-for-those-aged-65-and-over)) | Age UK·ONS, 2015~2017 | OA→LSOA→MSOA→LA, 65세+ | 센서스 4변수: 연령 75~79, 사별·이혼, **비독거 −0.968**, 자가건강 fair/bad **+2.317**; 상수 −4.550 | ELSA 로지스틱 계수를 센서스 10% 마이크로데이터에 적용 → 지역 평균 log-odds → 유병률 | 부트스트랩 Spearman 0.396, R² 0.172. 격차 LSOA 25배, OA 82배 |
| [Social Isolation in Gloucestershire](https://www.gloucestershire.gov.uk/media/b3fb3t0b/social_isolation_in_gloucestershire-16.pdf) | Gloucestershire CC (Essex 2013 방법), 2013 | LSOA + 가구 | 16개: 65~74/75+, 1인가구, 저학력, 정신건강, 무차량, 이웃대화 월 1회 미만, 지원망 부재, 저소득 | 가중 1~5 실험 후 차이 미미 → **비가중 합산 → 5분위** | 가중/비가중 비교만 |
| [Somerset Social Isolation](https://www.somersetintelligence.org.uk/social-isolation.html) | Somerset Intelligence, 2015 | LSOA | 15개(65+, 1인가구, 저소득, 무차량, 건강, 우울·불안) | 등가중 합산 순위 | IMD와 일치 점검 |
| [Isle of Wight Social Isolation Index 2023](https://iwc.iow.gov.uk/documentlibrary/download/social-isolation-index-2023) | IoW·Hampshire, 2023 | LSOA (65세+) | 센서스 2021 8개: 65+ 비율, 건강, 장애, 이혼·사별, 무급돌봄, **66+ 1인가구**, 결핍 | z-score 합 → 10분위(1~3 = 고위험) | 없음 |
| [GLA Propensity for Social Exclusion of Older People](https://www.data.gov.uk/dataset/propensity-for-social-exclusion-of-older-people-in-london-report1) | GLA, 2015 | LSOA | 6 driver: 경제, 교통, 가구유대(65+ 독거), 이웃유대(인구 churn), 건강, 안전 | 합산 방식 확인 필요 | — |
| [Loneliness Prescription Index](https://datasciencecampus.ons.gov.uk/developing-a-loneliness-prescription-index) | ONS Data Science Campus, 2019 | GP → MSOA | 알츠하이머·우울·고혈압·불안·불면 처방 비율 | z-score 합 → IDW → LISA | 센서스 요인이 분산 9%만 설명 |
| [Community Needs Index](https://ocsi.uk/2019/10/21/community-needs-index-measuring-social-and-cultural-factors/) ([2023](https://ocsi.uk/?p=7730)) | Local Trust·OCSI, 2019·2023 | ward → LSOA | 자산 밀도, 접근성, 자기보고 외로움, 시민참여, **인구회전율** | 등가중 → 2023 요인분석 가중 | — |
| [Mapping loneliness during the pandemic](https://www.ons.gov.uk/peoplepopulationandcommunity/wellbeing/articles/mappinglonelinessduringthecoronaviruspandemic/2021-04-07) | ONS, 2021 | Local Authority | OPN "often/always lonely" | 16~24세↑·실업↑ → 외로움↑ | **소표본 순위 비교 금지** 경고 |
| [Wigfield & Alden 2018](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6244537/) | Univ. of Leeds | 지자체 지수 질적 검증 | — | — | 지수 단독 불충분 |
| Risk of Social Isolation 65+ ([지표](https://www.americashealthrankings.org/explore/measures/isolationrisk_sr_b/CO), [카운티 분석](https://www.americashealthrankings.org/publications/articles/risk-of-social-isolation-among-older-adults-a-county-level-view)) | America's Health Rankings·AARP, 2018~ | 카운티 | ACS 6변수(65+): 빈곤, **독거**, 이혼·사별, 미혼, 장애, 독립생활 곤란 | **6개 z-score 등가중 평균 → 백분위 5등급** | 외부검증 없음 |
| [CDC/ATSDR SVI 2022](https://www.atsdr.cdc.gov/place-health/media/pdfs/2024/10/SVI2022Documentation.pdf) | CDC | census tract | 4테마 16변수(65+, 장애, 한부모, 10+세대 건물, 과밀, 무차량, group quarters) | 백분위 합 → 테마 재순위; ≥90 flag | 독거 변수 없음 |
| [東京都23区 孤独死 지역격차 통계](https://www.hws-kyokai.or.jp/images/ronbun/all/201307-01.pdf) 厚生の指標 60(7) | 金涌佳雅 외, 2013 | 23구 | 監察医務院 단신세대 자택 이상사 / 国勢調査 | 성·연령조정 孤独死율, FleXScan 클러스터 | 남성 동부 7구 클러스터 |
| [東京都監察医務院 孤独死統計](https://www.hokeniryo.metro.tokyo.lg.jp/kansatsu/kodokushitoukei/kodokushitoukei.html) | 東京都, 2003~ | 23구 | 단신세대 자택 사망 건수·율 | 공식 결과변수 | — |
| [JAGES 고립 기준](https://www.jstage.jst.go.jp/article/jph/62/3/62_14-071/_article/-char/ja/) | Saito et al., 2015 | 개인(10년 코호트) | 별거가족·친구 접촉 **주 1회 미만** | 요개호·사망 HR 1.3~1.45 | 지역 호혜성↑ → 고립↓ (contextual effect) |
| [Understanding neighborhood isolation through spatial interaction network analysis](https://geography.wisc.edu/geods/wp-content/uploads/sites/28/2022/05/2019_EPA_neighborhoodisolation.pdf) | Prestby, App, Kang & Gao, 2019 | block group | SafeGraph 스마트폰 이동 | 근린 간 방문흐름 단절 = 고립 | **지역 고립을 이동 흐름으로 정의한 드문 사례** |
| [수동센싱 외로움 탐지](https://mhealth.jmir.org/2019/7/e13209/) | Doryab et al., 2019 | 개인 160명 | GPS·Bluetooth·Fitbit | **주말 저녁 외부 체류 적음 ↔ 고외로움**, 정확도 80.2% | 개인 수준 |
| [GPS 이동특성과 외로움](https://maplab.stanford.edu/publications/mobility-behaviors/investigating-relationships-between-mobility-behaviours-and) | Muller et al., 2020 | 개인 1,765명 | 이동 불규칙성, 사회적 장소 체류 | 불규칙성↑ → 외로움↑; 이동거리 무관 | 개인 수준 |
| [호주 SA3 베이지안 공간 지도](https://flosse.dss.gov.au/bitstreams/9337affe-e116-4844-bd4a-baaa8915708b/download) | Earnest et al., 2026 | SA3 335개 | HILDA 고립(독거+월 1회 미만) + IRSAD, 원격성, 보행성 | Poisson + CAR 공간효과 → RR | MCMC 수렴만 |
| [사회생태학적 요인 scoping review](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10636946/) | Meehan et al., 2023 | 리뷰 | 지역 18요인: 근린 안전, 제3의 장소, 보행성·교통, 서비스 접근, 밀도 | — | 변수 선택 근거 |

---

## 5. 레시피 비교와 우리 데이터 적용

공개 산식이 완전한 것은 Age UK/ONS(계수 공개)와 AHR(z-score 평균). 영국 지자체는 등가중 합산이 표준이며, Gloucestershire는 가중치를 바꿔도 결과가 거의 달라지지 않았다고 보고했다.

| 레시피 | 변수 | 점수화 | 우리 데이터 재현 |
| --- | --- | --- | --- |
| Age UK/ONS (UK 2016) | 연령, 혼인, 독거, 자가건강 | 설문 회귀계수 → 센서스 적용 | 부분 — KIHASA 2024 사회조사 연령·독거별 고립률을 집계구 구성에 적용 가능 |
| AHR (US 2018~) | 빈곤, 독거, 이혼·사별, 미혼, 장애, 독립생활 곤란 | z-score 등가중 평균 → 백분위 5등급 | **가능 — 기본안으로 채택** |
| Gloucestershire·Somerset (UK) | 1인가구, 65+, 저소득, 무차량, 건강 | 비가중 합산 → 5분위 | 가능 |
| Isle of Wight (UK 2023) | 65+, 66+ 1인가구, 이혼·사별 | z-score 합 → 10분위 | 가능 |
| CDC SVI (US) | 4테마 16변수 | 백분위 → 테마 재순위, ≥90 flag | 가능 — 테마별 재순위 구조 |
| 김소연 외 (KR 2024) | 고령 남성, 수급자, 다세대, 의료 접근 | 가중 점수 × 고독사율 K-means | 고독사율 없으면 점수만 |
| Prestby 외 (US 2019) | 근린 간 이동 흐름 | 네트워크 단절 | **SK 유동인구로 응용** |

우리 데이터 적용 차원:

| 차원 | 집계구 변수 | 근거 |
| --- | --- | --- |
| 독거 | 1인가구 / 총가구 (ga_sd_005 / to_ga_001) | AHR, Age UK, 영국 지자체, 복지부 위험군 |
| 고령 | 65세+ / 총인구 | AHR, Isle of Wight, 김소연 외 |
| 중장년 남성 | 50~64세 남성 / 총인구 (in_age_041~043) | 2024 고독사 실태조사, 金涌 2013 |
| 주거취약 | (주택이외 거처 + 비주거용 + 20㎡ 이하) / (총주택 + 주택이외 거처) | 기본계획, 2024 실태조사, SVI |
| 노후주택 | 1989년 이전 / 총주택 | 서울시 위험군, 대구보건대 |
| 외부 유입·활동 | 유동인구 / 총인구; 주말·저녁 유동 비율 | Prestby 2019, Doryab 2019, 서울 시민생활 데이터 |
| 접근성 | 사업체·종사자 밀도 | 김소연 외, CNI |

점수화: AHR 방식(차원별 z-score 등가중 평균 → 백분위 5등급) 기본, 가중 방식 바꿔 민감도 점검. 위험 노출 인구 = 고위험 집계구의 1인가구 수.

검증 후보: ① 강남 vs 춘천 분포가 알려진 차이(춘천 1인가구율 중앙값 31% vs 강남 18%)와 일치하는지; ② 복지부 고위험 지역 유형(다세대·고시원·임대단지)이 상위 등급에 들어오는지; ③ 행정동별 고독사 위험군 수(지자체 정보공개)와 상관. 외부 결과로 검증한 해외 사례가 없어 ③이 가능하면 그 자체로 기여.

---

## 6. 프로토타입 실행 결과 (2026-10-15)

6개 차원 z-score 등가중 평균, 백분위 5등급. 포함 1,649개 집계구(인구·가구·주택 0 또는 SK 없음 49개 제외). 결측은 소량 비공개로 보고 0 대치.

| 지역 | 1등급 | 2 | 3 | 4 | 5등급 | 5등급 1인가구 수 |
| --- | --- | --- | --- | --- | --- | --- |
| 강남구 | 236 | 238 | 229 | 203 | 149 | 10,597 |
| 춘천시 | 93 | 92 | 101 | 127 | 181 | 23,374 |

5등급 330개 집계구에 1인가구 33,971가구(전체의 27%), 인구 16만 명. 상위 10개 중 9개가 춘천(1인가구 50~80%, 65세+ 30~54%), 강남은 고시원·오피스텔 밀집 집계구가 상위권.

관찰:

1. **SGIS '총주택'은 주택이외 거처를 포함하지 않는다.** 주택 104호 vs 주택이외 거처 449개인 집계구가 42개 있어 주거취약 분모를 '총주택 + 주택이외 거처'로 써야 한다.
2. **결측 처리는 결과를 거의 바꾸지 않는다** (0 vs 2 대치 Spearman 0.98, 5등급 93% 일치).
3. **변수 선택이 훨씬 중요하다.** 유동인구 제외 0.90(5등급 78% 일치), 가중 0.88, 인구 3차원만 0.78.
4. **차원 간 긴장.** ① 1인가구율과 50~64세 남성 비율이 음의 상관(−0.27) — 강남 1인가구는 청년. SGIS '1인가구 × 연령' 교차표 필요. ② 거주자당 유동인구가 1인가구율과 양의 상관(+0.42) — 1인가구 밀집지(오피스텔·상업지)는 유동이 많다. 유동 변수는 재정의(주말/평일비, 야간 체류)하거나 보조 지표로 분리 검토.

코드: `isolation_index_prototype.ipynb` (pandas·numpy·scipy).
