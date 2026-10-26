"""복지·공공기관 원본을 에이전트 자원 DB(`institutions.csv`)로 정리한다.

원본은 `data/raw/reference_data/복지기관_수집/`에 다운로드한 파일 그대로 둔다.
범위는 수도권(서울·경기·인천)과 분석 지역 춘천시다. 태그 정의는
`docs/resource-tags.md`를 따른다.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import paths

RAW_DIR = paths.RAW_DIR / "reference_data" / "복지기관_수집"
OUTPUT_NAME = "institutions.csv"
MAPPING_NAME = "feature_tag_mapping.csv"
OUT_COLUMNS = [
    "INST_ID",
    "INST_NAME",
    "INST_TYPE",
    "SIDO",
    "SGG",
    "ADM_CD",
    "ADDRESS",
    "LON",
    "LAT",
    "PHONE",
    "TARGET_AGE",
    "SERVICES",
    "TAGS",
    "SOURCE",
    "SOURCE_URL",
    "AS_OF",
    "VALID_UNTIL",
]
SIDO_NAMES = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "경기": "경기도",
    "경기도": "경기도",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
}
CAPITAL_AREA = ("서울특별시", "경기도", "인천광역시")
DG = "https://www.data.go.kr/data/{}/fileData.do"
STD = "https://www.data.go.kr/data/{}/standard.do"
SEOUL = "https://data.seoul.go.kr/dataList/{}/S/1/datasetView.do"

# 유형 → (태그, 대상). 태그 어휘와 근거는 docs/resource-tags.md
TYPE_RULES: dict[str, tuple[str, str]] = {
    "자살예방센터": ("CRISIS_LINE;MENTAL_CARE", "ALL"),
    "광역정신건강복지센터": ("CRISIS_LINE;MENTAL_CARE", "ALL"),
    "기초정신건강복지센터": ("MENTAL_CARE", "ALL"),
    "중독관리통합지원센터": ("ADDICTION;MENTAL_CARE", "ALL"),
    "정신재활시설": ("MENTAL_CARE", "ALL"),
    "치매안심센터": ("DEMENTIA;HEALTH_MGMT", "60+"),
    "치매안심센터 분소": ("DEMENTIA;HEALTH_MGMT", "60+"),
    "건강증진센터": ("HEALTH_MGMT", "ALL"),
    "보건소": ("HEALTH_MGMT", "ALL"),
    "노인맞춤돌봄 수행기관": ("CARE_CHECK", "65+"),
    "노인복지관": ("SOCIAL_PART;LEARNING", "60+"),
    "경로당": ("SOCIAL_PART", "65+"),
    "노인일자리지원기관": ("JOB_INCOME;SOCIAL_PART", "60+"),
    "노인교실": ("SOCIAL_PART;LEARNING", "60+"),
    "고립예방 협력기관": ("ISOLATION_CARE", "ALL"),
    "노인보호전문기관": ("CASE_MGMT", "65+"),
    "사회복지관": ("CASE_MGMT;SOCIAL_PART;CARE_CHECK", "ALL"),
    "행정복지센터": ("CASE_MGMT", "ALL"),
    "장애인복지관": ("DISABILITY", "ALL"),
    "장애인주간이용시설": ("DISABILITY;SOCIAL_PART", "ALL"),
    "지역자활센터": ("JOB_INCOME", "ALL"),
    "고용복지플러스센터": ("JOB_INCOME", "ALL"),
    "주거복지센터": ("HOUSING", "ALL"),
    "쪽방상담소": ("HOUSING;CASE_MGMT", "ALL"),
    "노숙인종합지원센터": ("HOUSING;CASE_MGMT;MEAL", "ALL"),
    "가족센터": ("FAMILY", "ALL"),
    "무료급식소": ("MEAL", "ALL"),
    "푸드뱅크·푸드마켓": ("MEAL", "ALL"),
    "공공도서관": ("LEARNING", "ALL"),
    "평생학습관": ("LEARNING", "ALL"),
    "공공체육시설": ("PHYSICAL", "ALL"),
}
# 서울시 자치구 사회복지시설 목록의 시설종류명 → 표준 유형. 생활시설(요양·거주·보육)은 추천 대상이 아니라 뺀다.
SEOUL_FACILITY_TYPES = {
    "노인복지관": "노인복지관",
    "경로당": "경로당",
    "복합노인복지시설": "노인복지관",
    "노인일자리지원기관": "노인일자리지원기관",
    "지역노인보호전문기관": "노인보호전문기관",
    "사회복지관": "사회복지관",
    "장애인복지관": "장애인복지관",
    "장애인주간이용시설": "장애인주간이용시설",
    "지역자활센터": "지역자활센터",
    "정신건강복지+지역센터": "기초정신건강복지센터",
    "중독관리통합지원센터": "중독관리통합지원센터",
    "자살예방센터": "자살예방센터",
    "지역사회전환시설": "정신재활시설",
    "건강가정지원센터": "가족센터",
    "다문화가족지원센터": "가족센터",
    "쪽방상담소": "쪽방상담소",
    "노숙인종합지원센터": "노숙인종합지원센터",
}
# 위험 특징 → 기관 서비스 후보. NOTE의 조건은 추천 단계에서 확인한다.
FEATURE_TAG_MAPPING = [
    ("REL_NO_CONFIDANT", "SOCIAL_PART", 1, "정서적 관계를 넓히고 싶을 때 모임·프로그램 후보"),
    ("REL_NO_CONFIDANT", "ISOLATION_CARE", 2, "고립 지원을 원할 때. 현재 서울 기관만 확인됨"),
    ("REL_NO_ADVICE", "CASE_MGMT", 1, "생활·복지 문제의 조언이 필요할 때 상담 창구 후보"),
    ("REL_NO_ADVICE", "SOCIAL_PART", 2, "지속적인 관계를 만들고 싶을 때 참여 프로그램 후보"),
    ("REL_FAMILY_CONFLICT", "FAMILY", 1, "가족 관계 상담을 원할 때 가족센터 후보"),
    ("REL_NO_FAMILY", "SOCIAL_PART", 1, "가족 외 관계 형성을 원할 때 모임·프로그램 후보"),
    ("REL_NO_FAMILY", "CASE_MGMT", 2, "가족 대신 생활 지원·복지 상담이 필요할 때"),
    ("REL_LONELY", "SOCIAL_PART", 1, "외로움 완화를 위한 관계 형성 프로그램을 원할 때"),
    ("REL_LONELY", "MENTAL_CARE", 2, "정서적 고통으로 상담을 원할 때"),
    (
        "REL_NO_PRACTICAL_SUPPORT",
        "CARE_CHECK",
        1,
        "아플 때 생활 지원이 필요하면 안부·돌봄 서비스 확인",
    ),
    ("REL_NO_PRACTICAL_SUPPORT", "CASE_MGMT", 2, "생활 지원을 신청할 창구가 필요할 때"),
    ("REL_LOW_CONTACT", "SOCIAL_PART", 1, "교류를 늘리고 싶을 때 참여 프로그램 후보"),
    ("REL_LOW_CONTACT", "ISOLATION_CARE", 2, "고립 지원을 원할 때. 현재 서울 기관만 확인됨"),
    ("OUT_LONG_DURATION", "ISOLATION_CARE", 1, "장기 은둔·고립 지원 후보. 현재 서울 기관만 확인됨"),
    ("OUT_LONG_DURATION", "SOCIAL_PART", 2, "외부 활동을 시작할 의사가 있을 때 모임 후보"),
    ("OUT_NO_ACTIVITY", "SOCIAL_PART", 1, "일상 활동·교류를 시작하고 싶을 때"),
    ("OUT_NO_ACTIVITY", "LEARNING", 2, "학습·문화 활동을 원할 때"),
    ("OUT_NO_ACTIVITY", "PHYSICAL", 3, "신체활동을 원하고 건강상 가능할 때"),
    ("SOLO_LIVING", "CARE_CHECK", 1, "혼자 살며 안부 확인·생활 지원을 원할 때"),
    ("SOLO_LIVING", "SOCIAL_PART", 2, "일상 교류를 원할 때. 독거 자체를 고립으로 단정하지 않음"),
    ("SOLO_MEAL", "SOCIAL_PART", 1, "함께 식사하거나 교류할 프로그램을 원할 때"),
    ("SOLO_MEAL", "MEAL", 2, "식사·식품 확보의 어려움이 별도로 확인될 때만"),
    ("BODY_POOR_HEALTH", "HEALTH_MGMT", 1, "건강 상담·관리를 원할 때"),
    ("BODY_POOR_HEALTH", "DISABILITY", 2, "장애 관련 지원 필요와 이용 자격이 확인될 때만"),
    ("BODY_HYGIENE", "CARE_CHECK", 1, "위생 관리에 실제 도움이 필요할 때 돌봄 서비스 확인"),
    ("BODY_HYGIENE", "HEALTH_MGMT", 2, "위생 곤란의 건강 원인 상담이 필요할 때"),
    ("BODY_HOME_CARE", "CARE_CHECK", 1, "생활공간 정리·가사 지원이 필요할 때 서비스 범위 확인"),
    ("BODY_HOME_CARE", "CASE_MGMT", 2, "가사 지원 신청·연계 상담이 필요할 때"),
    ("BODY_SLEEP", "HEALTH_MGMT", 1, "수면 문제로 건강 상담을 원할 때"),
    ("BODY_MOBILITY_LIMIT", "CARE_CHECK", 1, "이동·외출 동행 등 실제 돌봄 범위를 확인할 때"),
    ("BODY_MOBILITY_LIMIT", "HEALTH_MGMT", 2, "이동 제한의 건강 원인 상담이 필요할 때"),
    ("MIND_POOR_MENTAL", "MENTAL_CARE", 1, "정신건강 상담·치료 연계를 원할 때"),
    ("MIND_HOPELESS", "MENTAL_CARE", 1, "절망감에 대한 상담을 원할 때. 자살 생각 여부는 별도 확인"),
    ("MIND_SOCIAL_ANXIETY", "MENTAL_CARE", 1, "대인 불안 상담을 원할 때"),
    (
        "MIND_SUICIDE_IDEA",
        "CRISIS_LINE",
        1,
        "위기 경로: 일반 추천을 건너뛰고 사람에게 즉시 이관하며 위기 상담 안내",
    ),
    ("MIND_SUICIDE_IDEA", "MENTAL_CARE", 2, "위기 이관 이후 지속 상담 연계"),
    (
        "MIND_SUICIDE_ATTEMPT",
        "CRISIS_LINE",
        1,
        "위기 경로: 일반 추천을 건너뛰고 사람에게 즉시 이관하며 위기 상담 안내",
    ),
    ("MIND_SUICIDE_ATTEMPT", "MENTAL_CARE", 2, "위기 이관 이후 지속 상담 연계"),
    (
        "ECON_NO_INCOME",
        "JOB_INCOME",
        1,
        "취업·자활을 원할 때. 은퇴·연금생활을 경제 위기로 단정하지 않음",
    ),
    ("ECON_NO_INCOME", "CASE_MGMT", 2, "생활비 부족 또는 복지 신청 필요가 별도로 확인될 때"),
    ("ECON_LOW_STATUS", "CASE_MGMT", 1, "경제적 어려움과 지원 필요를 확인한 뒤 복지 상담"),
    ("ECON_LOW_STATUS", "JOB_INCOME", 2, "취업·자활을 원할 때"),
    ("HOUSE_UNSTABLE", "HOUSING", 1, "주거 상담·지원 필요를 확인할 때"),
    ("HOUSE_UNSTABLE", "CASE_MGMT", 2, "주거 위기와 복합 생활 지원이 필요할 때"),
]
MENTAL_TYPES = {
    "MHW": "기초정신건강복지센터",
    "WDR": "광역정신건강복지센터",
    "AMS": "중독관리통합지원센터",
    "SUP": "자살예방센터",
}
# 같은 기관이 출처마다 "서울특별시강남구…", "강남구립 …"처럼 다르게 적혀 있어 비교 전에 걷어 낸다
NAME_NOISE = re.compile(
    r"\s|\(.*?\)|주민센터|행정복지센터|사무소|구립|시립|사회복지법인"
    r"|^(서울특별시|서울|경기도|인천광역시|인천|강원특별자치도|강원)"
)


def read_raw(name: str, **kwargs) -> pd.DataFrame:
    """원본 CSV를 인코딩(UTF-8 또는 CP949)을 가려 문자열로 읽는다."""
    path = RAW_DIR / name
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str, **kwargs)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="cp949", encoding_errors="replace", dtype=str, **kwargs)


def split_region(address: pd.Series) -> pd.DataFrame:
    """주소 앞 두 토큰으로 시도·시군구를 만든다. 시도 표기는 정식 명칭으로 맞춘다."""
    tokens = (
        address.fillna("").str.strip().str.split(r"\s+", n=2, expand=True).reindex(columns=[0, 1])
    )
    sido = tokens[0].map(SIDO_NAMES)
    return pd.DataFrame({"SIDO": sido, "SGG": tokens[1].where(sido.notna())}, index=address.index)


def frame(df: pd.DataFrame, source: str, url: str, as_of: str, **cols) -> pd.DataFrame:
    """원본 열 이름(또는 고정값)을 표준 열로 옮긴다. cols 값이 원본 열 이름이면 열, 아니면 상수."""
    out = pd.DataFrame(index=df.index)
    for key, value in cols.items():
        out[key] = df[value] if isinstance(value, str) and value in df.columns else value
    if "SIDO" not in cols or "SGG" not in cols:
        region = split_region(out["ADDRESS"])
        for key in ("SIDO", "SGG"):
            if key not in cols:
                out[key] = region[key]
    out["SIDO"] = out["SIDO"].map(lambda s: SIDO_NAMES.get(s, s))
    out["SOURCE"], out["SOURCE_URL"] = source, url
    if as_of in df.columns:
        out["AS_OF"] = df[as_of]
    else:
        out["AS_OF"] = as_of
    return out


def load_sources() -> list[pd.DataFrame]:
    """원본별로 표준 열을 만든다. 출처 기준일은 원본 열이 없으면 포털 수정일을 쓴다."""
    out = []

    d = read_raw("dg_15138421_dementia_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15138421",
            DG.format(15138421),
            "2026-01-29",
            INST_NAME="치매안심센터명",
            INST_TYPE="치매안심센터",
            SIDO="시도",
            SGG="시군구",
            ADDRESS="주소1",
            LAT="위도",
            LON="경도",
            PHONE="전화번호",
            ADM_CD="행정동코드",
        )
    )
    d = read_raw("dg_15145246_dementia_branch.csv")
    d["NAME"] = d["치매안심센터명"] + " " + d["분소명"]
    out.append(
        frame(
            d,
            "data.go.kr 15145246",
            DG.format(15145246),
            "2025-08-08",
            INST_NAME="NAME",
            INST_TYPE="치매안심센터 분소",
            SIDO="시도",
            SGG="시군구",
            ADDRESS="주소1",
            LAT="위도",
            LON="경도",
            PHONE="전화번호",
        )
    )
    d = read_raw("dg_15106561_mental_health_center.csv")
    d["TYPE"] = d["기관분류"].map(MENTAL_TYPES)
    d["ADDR"] = d["주소"].fillna("") + " " + d["상세주소"].fillna("")
    out.append(
        frame(
            d,
            "data.go.kr 15106561",
            DG.format(15106561),
            "2026-09-28",
            INST_NAME="기관명",
            INST_TYPE="TYPE",
            ADDRESS="ADDR",
            PHONE="기관번호1",
        )
    )
    d = read_raw("std_15021137_health_promotion_center.csv")
    d["TYPE"] = np.where(
        d["건강증진센터구분"].eq("정신보건"), "기초정신건강복지센터", "건강증진센터"
    )
    out.append(
        frame(
            d,
            "data.go.kr 15021137 (표준)",
            STD.format(15021137),
            "데이터기준일자",
            INST_NAME="건강증진센터명",
            INST_TYPE="TYPE",
            ADDRESS="소재지도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="운영기관전화번호",
            SERVICES="건강증진업무내용",
        )
    )
    d = read_raw("std_15021138_dementia_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15021138 (표준)",
            STD.format(15021138),
            "데이터기준일자",
            INST_NAME="치매센터명",
            INST_TYPE="치매안심센터",
            ADDRESS="소재지도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="운영기관전화번호",
            SERVICES="주요치매관리프로그램소개",
        )
    )
    d = read_raw("std_15107750_health_institution.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15107750 (표준)",
            STD.format(15107750),
            "데이터기준일자",
            INST_NAME="보건기관명",
            INST_TYPE="보건소",
            ADDRESS="소재지도로명주소",
            PHONE="전화번호",
            SERVICES="진료검진내용",
        )
    )
    d = read_raw("dg_15004317_elderly_care_agency.csv")
    d["SVC"] = "노인맞춤돌봄서비스" + np.where(
        d["특화서비스"].eq("해당"), "; 특화서비스(고립·우울 노인)", ""
    )
    d["UNTIL"] = d["위수탁기간"].str.extract(r"~\s*(\d{4}-\d{2}-\d{2})", expand=False)
    special = d["특화서비스"].eq("해당")
    f = frame(
        d,
        "data.go.kr 15004317",
        DG.format(15004317),
        "2024-04-23",
        INST_NAME="기관명",
        INST_TYPE="노인맞춤돌봄 수행기관",
        SIDO="시도",
        SGG="시군구",
        ADDRESS="주소",
        PHONE="기관 대표전화",
        SERVICES="SVC",
        VALID_UNTIL="UNTIL",
    )
    # 특화서비스는 사회적 고립·우울 노인 대상이라 정신건강 태그를 함께 단다
    f["EXTRA_TAGS"] = np.where(special, "MENTAL_CARE;SOCIAL_PART", "")
    out.append(f)

    seoul_files = sorted(RAW_DIR.glob("seoul_OA-20[34]*.csv"))
    d = pd.concat([read_raw(p.name) for p in seoul_files], ignore_index=True)
    detail = d["시설종류명(시설유형)"].str.replace(r"^\(.*?\)\s*", "", regex=True)
    d["TYPE"] = detail.map(SEOUL_FACILITY_TYPES)
    d = d[d["TYPE"].notna()].drop_duplicates("시설코드")
    out.append(
        frame(
            d,
            "서울 열린데이터광장 OA-20377~20401",
            SEOUL.format("OA-20399"),
            "2026-10-19",
            INST_NAME="시설명",
            INST_TYPE="TYPE",
            SIDO="서울특별시",
            SGG="시군구명",
            ADDRESS="시설주소",
            PHONE="전화번호",
        )
    )

    d = read_raw("dg_15044563_social_welfare_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15044563",
            DG.format(15044563),
            "2023-12-31",
            INST_NAME="기관명",
            INST_TYPE="사회복지관",
            ADDRESS="주소",
            PHONE="전화번호",
        )
    )
    d = read_raw("dg_15075529_disability_welfare_center.csv")
    d["ADDR"] = d["시도"] + " " + d["시설 주소"].fillna("")
    out.append(
        frame(
            d,
            "data.go.kr 15075529",
            DG.format(15075529),
            "2024-04-25",
            INST_NAME="시설명",
            INST_TYPE="장애인복지관",
            SIDO="시도",
            SGG="시군구",
            ADDRESS="ADDR",
            LON="엑스(X)좌표",
            LAT="와이(Y)좌표",
            PHONE="전화번호",
        )
    )
    d = read_raw("dg_15156714_self_support_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15156714",
            DG.format(15156714),
            "2025-09-19",
            INST_NAME="시설명(기업명)",
            INST_TYPE="지역자활센터",
            SIDO="시도",
            SGG="시군구",
            ADDRESS="주소",
            PHONE="전화번호",
        )
    )
    d = read_raw("dg_15066368_employment_welfare_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15066368",
            DG.format(15066368),
            "2026-07-01",
            INST_NAME="센터명",
            INST_TYPE="고용복지플러스센터",
            ADDRESS="소재지",
            PHONE="대표전화",
            SERVICES="관할구역",
        )
    )
    d = read_raw("dg_15091865_myhome_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15091865",
            DG.format(15091865),
            "2023-11-21",
            INST_NAME="상담센터명",
            INST_TYPE="주거복지센터",
            ADDRESS="주소",
            PHONE="대표전화번호",
            SERVICES="LH 마이홈 주거복지 상담",
        )
    )
    d = read_raw("dg_15059715_eupmyeondong_office.csv")
    d["NAME"] = d["읍면동"] + " 행정복지센터"
    out.append(
        frame(
            d,
            "data.go.kr 15059715",
            DG.format(15059715),
            "2025-12-31",
            INST_NAME="NAME",
            INST_TYPE="행정복지센터",
            SIDO="시도",
            SGG="시군구",
            ADDRESS="주소",
        )
    )
    d = read_raw("dg_15116896_gangnam_community_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15116896",
            DG.format(15116896),
            "기준일자",
            INST_NAME="주민센터명",
            INST_TYPE="행정복지센터",
            SIDO="서울특별시",
            SGG="강남구",
            ADDRESS="소재지",
            LAT="위도",
            LON="경도",
        )
    )

    d = read_raw("std_15114136_senior_center_village_hall.csv")
    d = d[d["시설유형"].str.contains("경로당", na=False) & d["영업상태명"].eq("영업")]
    out.append(
        frame(
            d,
            "data.go.kr 15114136 (표준)",
            STD.format(15114136),
            "데이터기준일자",
            INST_NAME="시설명",
            INST_TYPE="경로당",
            ADDRESS="소재지도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="전화번호",
        )
    )
    d = read_raw("std_15013107_free_meal.csv")
    d = d[d["운영종료일자"].isna()]
    d["SVC"] = (
        "대상: "
        + d["급식대상"].fillna("")
        + " / "
        + d["급식요일"].fillna("")
        + " "
        + d["급식시간"].fillna("")
    )
    f = frame(
        d,
        "data.go.kr 15013107 (표준)",
        STD.format(15013107),
        "데이터기준일자",
        INST_NAME="시설명",
        INST_TYPE="무료급식소",
        ADDRESS="소재지도로명주소",
        LAT="위도",
        LON="경도",
        PHONE="전화번호",
        SERVICES="SVC",
    )
    f["TARGET_AGE"] = np.where(
        d["급식대상"].str.contains(r"노인|어르신|60|65", na=False), "60+", "ALL"
    )
    out.append(f)
    d = read_raw("std_15129442_food_bank.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15129442 (표준)",
            STD.format(15129442),
            "데이터기준일자",
            INST_NAME="상호명",
            INST_TYPE="푸드뱅크·푸드마켓",
            SIDO="시도명",
            SGG="시군구명",
            ADDRESS="소재지도로명주소",
            PHONE="전화번호",
            SERVICES="센터구분",
        )
    )
    d = read_raw("std_15013109_library.csv")
    d = d[d["도서관유형"].isin(["공공도서관", "작은도서관", "장애인도서관"])]
    out.append(
        frame(
            d,
            "data.go.kr 15013109 (표준)",
            STD.format(15013109),
            "데이터기준일자",
            INST_NAME="도서관명",
            INST_TYPE="공공도서관",
            SIDO="시도명",
            SGG="시군구명",
            ADDRESS="소재지도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="도서관전화번호",
            SERVICES="도서관유형",
        )
    )
    d = read_raw("dg_15050130_lifelong_edu_institution.csv")
    d = d[d["기관유형대분류"].isin(["평생학습관", "시도평생교육진흥원"])]
    out.append(
        frame(
            d,
            "data.go.kr 15050130",
            DG.format(15050130),
            "2024-12-31",
            INST_NAME="기관명",
            INST_TYPE="평생학습관",
            ADDRESS="기관주소1",
            PHONE="기관대표 전화번호",
        )
    )
    d = read_raw("seoul_OA-21779.csv")
    d = d[d["시설유형"].eq("공공체육시설")]
    out.append(
        frame(
            d,
            "서울 열린데이터광장 OA-21779",
            SEOUL.format("OA-21779"),
            "2026-10-19",
            INST_NAME="시설명",
            INST_TYPE="공공체육시설",
            ADDRESS="시설주소",
            PHONE="연락처",
            SERVICES="시설규모",
        )
    )

    out += load_gyeonggi() + load_incheon() + load_gangwon() + [load_sihsc()]

    d = read_raw("dg_15074350_chuncheon_elderly_welfare_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15074350",
            DG.format(15074350),
            "데이터기준일자",
            INST_NAME="노인복지관명",
            INST_TYPE="노인복지관",
            ADDRESS="도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="연락처",
        )
    )
    d = read_raw("dg_15104614_chuncheon_mental_health_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15104614",
            DG.format(15104614),
            "데이터기준일자",
            INST_NAME="기관명",
            INST_TYPE="운영유형",
            ADDRESS="도로명주소",
            LAT="위도",
            LON="경도",
            PHONE="전화번호",
        )
    )
    d = read_raw("dg_15076325_chuncheon_admin_welfare_center.csv")
    d["NAME"] = d["읍면동명"] + " 행정복지센터"
    out.append(
        frame(
            d,
            "data.go.kr 15076325",
            DG.format(15076325),
            "데이터기준일",
            INST_NAME="NAME",
            INST_TYPE="행정복지센터",
            ADDRESS="소재지도로명주소",
            PHONE="대표전화번호",
        )
    )
    return out


def _first_address(d: pd.DataFrame, *cols: str, prefix: str = "") -> pd.Series:
    """여러 주소 열 중 처음으로 값이 있는 것을 고르고, 시도가 빠진 주소에는 prefix를 붙인다."""
    addr = d[list(cols)].bfill(axis=1).iloc[:, 0].fillna("").str.strip()
    return addr.where(addr.str.startswith(prefix.strip()) | addr.eq(""), prefix + addr)


def load_gyeonggi() -> list[pd.DataFrame]:
    """경기데이터드림 시트 다운로드 파일(WGS84 좌표 포함)."""
    url = "https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId={}&infSeq=1"
    specs = [  # 파일, infId, 유형, 이름 열, 기준일(포털 수정일)
        (
            "gg_senior_welfare_center.csv",
            "MGVBGBH0FKD48G8QQ4I827687767",
            "노인복지관",
            "시설명",
            None,
        ),
        (
            "gg_mental_health_center.csv",
            "DR5A9PI77Q1831V975Q1889283",
            "기초정신건강복지센터",
            "센터명",
            "2026-08-18",
        ),
        (
            "gg_suicide_prevention_center.csv",
            "4FGW2M1NM233Q9962116563284",
            "자살예방센터",
            "자살예방센터명",
            "2026-03-05",
        ),
        (
            "gg_addiction_center.csv",
            "VP6N5SJ9BHMEQ9RTWGAY15043133",
            "중독관리통합지원센터",
            "센터명",
            "2026-03-31",
        ),
        ("gg_health_center.csv", "302402102AS0TA1SY80R404746", "보건소", "사업장명", "2026-04-07"),
        (
            "gg_housing_welfare.csv",
            "3APMW0A2M7OBEP75EMM325586775",
            "주거복지센터",
            "기관명",
            "2026-01-12",
        ),
        (
            "gg_public_sports.csv",
            "6LMU5TBQ6RJJRBLAZWBC21105087",
            "공공체육시설",
            "시설명",
            "2026-05-14",
        ),
        (
            "gg_elderly_care_agency.csv",
            "AOY7I1SKRJ7IM0ZJQSN528372736",
            "노인맞춤돌봄 수행기관",
            "기관명",
            "2026-03-26",
        ),
    ]
    out = []
    for name, inf_id, inst_type, name_col, as_of in specs:
        d = read_raw(name)
        if "영업상태명" in d:
            d = d[d["영업상태명"].eq("영업중")]
        if "시설구분명" in d:  # 체육도장업은 민간 영업 신고라 공공 자원에서 뺀다
            d = d[d["시설구분명"].ne("체육도장업")]
        addr_cols = [
            c for c in ("소재지도로명주소", "도로명 주소", "도로명주소", "소재지지번주소") if c in d
        ]
        d["ADDR"] = _first_address(d, *addr_cols, prefix="경기도 ")
        d["ADDR"] = d["ADDR"].where(d["ADDR"].ne(""), "경기도 " + d["시군명"])
        is_wide = d[name_col].str.startswith("경기도", na=False)
        d["TYPE"] = inst_type
        if inst_type == "기초정신건강복지센터":
            d.loc[is_wide, "TYPE"] = "광역정신건강복지센터"
        svc = next((c for c in ("진료과목내용", "시설구분명") if c in d), None)
        out.append(
            frame(
                d,
                f"경기데이터드림 {inf_id}",
                url.format(inf_id),
                as_of or "2026-10-19",
                INST_NAME=name_col,
                INST_TYPE="TYPE",
                ADDRESS="ADDR",
                LAT="WGS84위도",
                LON="WGS84경도",
                PHONE="전화번호",
                SERVICES=svc or "",
            )
        )
    return out


INCHEON_TYPES = {
    "가족센터": "가족센터",
    "건강가정지원센터": "가족센터",
    "다문화가족지원센터": "가족센터",
    "노인복지관": "노인복지관",
    "노인대학(노인교실)": "노인교실",
    "노인보호전문기관": "노인보호전문기관",
    "노인일자리지원기관": "노인일자리지원기관",
    "장애인복지관": "장애인복지관",
    "주간이용시설": "장애인주간이용시설",
    "정신재활시설(주간재활)": "정신재활시설",
    "종합사회복지관": "사회복지관",
    "지역자활센터": "지역자활센터",
    "쪽방상담소": "쪽방상담소",
}
INCHEON_MENTAL_TYPES = {
    "정신건강복지센터": "기초정신건강복지센터",
    "정신재활시설": "정신재활시설",
    "치매안심센터": "치매안심센터",
    "광역치매센터": "치매안심센터",
    "중독관리통합지원센터": "중독관리통합지원센터",
    "광역자살예방센터": "자살예방센터",
}


def _incheon_address(gu: pd.Series, addr: pd.Series) -> pd.Series:
    """인천 파일 주소는 군구로 시작하거나 군구가 빠져 있다. 군구 열('시'는 시 직영)로 채운다."""
    addr = addr.fillna("").str.strip()
    gu = gu.fillna("").where(gu.ne("시"), "")
    has_gu = pd.Series([a.startswith(g) for a, g in zip(addr, gu)], index=addr.index)
    full = addr.where(has_gu, gu + " " + addr)
    return ("인천광역시 " + full).str.replace(r"\s+", " ", regex=True).str.strip()


def load_incheon() -> list[pd.DataFrame]:
    """인천광역시 data.go.kr 파일. 주소에 시도가 빠져 있어 붙인다."""
    out = []
    d = read_raw("dg_15045181_incheon_welfare_facility.csv")
    d["TYPE"] = d["시설종류"].map(INCHEON_TYPES)
    d["ADDR"] = _incheon_address(d["군구명"], d["주소"])
    out.append(
        frame(
            d,
            "data.go.kr 15045181",
            DG.format(15045181),
            "2025-12-02",
            INST_NAME="시설명",
            INST_TYPE="TYPE",
            ADDRESS="ADDR",
            PHONE="연락처",
        )
    )
    d = read_raw("dg_15064875_incheon_senior_leisure.csv")
    d["TYPE"] = d["비고"].map(
        {"경로당": "경로당", "노인복지관": "노인복지관", "노인대학": "노인교실"}
    )
    d["ADDR"] = _incheon_address(d["군구명"], d["주소"])
    out.append(
        frame(
            d,
            "data.go.kr 15064875",
            DG.format(15064875),
            "2026-03-20",
            INST_NAME="시설명",
            INST_TYPE="TYPE",
            ADDRESS="ADDR",
            PHONE="연락처",
        )
    )
    d = read_raw("dg_15104437_incheon_mental_facility.csv")
    d["TYPE"] = d["시설구분"].map(INCHEON_MENTAL_TYPES)
    d.loc[d["시설명_병(의)원명"].str.contains("광역정신", na=False), "TYPE"] = (
        "광역정신건강복지센터"
    )
    d["ADDR"] = _incheon_address(d["군구"], d["나머지 주소"])
    out.append(
        frame(
            d,
            "data.go.kr 15104437",
            DG.format(15104437),
            "2025-09-21",
            INST_NAME="시설명_병(의)원명",
            INST_TYPE="TYPE",
            ADDRESS="ADDR",
            PHONE="대표전화",
            SERVICES="제공내용",
        )
    )
    d = read_raw("dg_15132648_incheon_health_center.csv")
    out.append(
        frame(
            d,
            "data.go.kr 15132648",
            DG.format(15132648),
            "2025-09-19",
            INST_NAME="보건소명",
            INST_TYPE="보건소",
            ADDRESS="주소",
            LAT="위도",
            LON="경도",
        )
    )
    return out


# 서울시고립예방센터 협력기관 지도의 사업구분 → 추가 태그
SIHSC_ROLE_TAGS = {
    "서울연결처방": "ISOLATION_CARE;SOCIAL_PART",
    "고립가구 전담기구": "ISOLATION_CARE;CASE_MGMT;CARE_CHECK",
    "거부가구지원기관": "ISOLATION_CARE;CASE_MGMT",  # 화면 표기: 은둔거부가구 맞춤형 지원
    "아름다운 동행가게": "MEAL;CARE_CHECK",
    "지역밀착형 복지관": "SOCIAL_PART;CASE_MGMT",
}
SIHSC_URL = "https://sihsc.welfare.seoul.kr/knockseoul/030204/businessmap/list.do"


def sihsc_type(name: pd.Series) -> pd.Series:
    """협력기관 이름으로 기존 유형을 정해 같은 기관 행과 합쳐지게 한다. 복지관이 아니면 협력기관."""
    return pd.Series(
        np.select(
            [
                name.str.contains("장애인") & name.str.contains("복지관"),
                name.str.contains("노인|어르신") & name.str.contains("복지관"),
                name.str.contains("복지관"),
            ],
            ["장애인복지관", "노인복지관", "사회복지관"],
            "고립예방 협력기관",
        ),
        index=name.index,
    )


def load_sihsc() -> pd.DataFrame:
    """서울시고립예방센터 협력기관 지도 (scripts/collect_sihsc.py로 수집). 탭이 달라도 같은 SEQ는 한 기관."""
    d = read_raw("sihsc_businessmap.csv").drop_duplicates("SEQ")
    roles = d["BSNS_DIV"].fillna("").str.split("|")
    d["EXTRA"] = roles.map(
        lambda rs: ";".join(SIHSC_ROLE_TAGS[r] for r in rs if r in SIHSC_ROLE_TAGS)
    )
    d["SVC"] = "서울시고립예방센터 협력: " + d["BSNS_DIV"].str.replace(
        "거부가구지원기관", "은둔거부가구 맞춤형 지원"
    ).str.replace("|", ", ")
    d["TYPE"] = sihsc_type(d["NAME"])
    f = frame(
        d,
        "서울시고립예방센터 협력기관 지도",
        SIHSC_URL,
        "UPD_DT",
        INST_NAME="NAME",
        INST_TYPE="TYPE",
        ADDRESS="ADDR",
        LAT="LAT",
        LON="LON",
        PHONE="TEL",
        SERVICES="SVC",
    )
    f["EXTRA_TAGS"] = d["EXTRA"]
    # 센터 자체는 지도에 없어 사이트 하단 표기(주소·대표전화)로 한 행을 더한다
    center = frame(
        pd.DataFrame(
            [
                {
                    "N": "서울시고립예방센터",
                    "A": "서울특별시 성동구 왕십리로 135, 2층",
                    "T": "02-6353-0200",
                }
            ]
        ),
        "서울시고립예방센터 누리집",
        "https://sihsc.welfare.seoul.kr/knockseoul/main.do",
        "2026-10-20",
        INST_NAME="N",
        INST_TYPE="고립예방 협력기관",
        ADDRESS="A",
        PHONE="T",
        SERVICES="고립·은둔 예방 사업 총괄, 고립 상담 (대표전화 연결 후 1번 → 5번)",
    )
    center["EXTRA_TAGS"] = "CASE_MGMT"
    return pd.concat([f, center], ignore_index=True)


def load_gangwon() -> list[pd.DataFrame]:
    """강원특별자치도 파일 중 춘천시 행만 쓴다."""
    out = []
    d = read_raw("dg_15159040_gangwon_health_institution.csv")
    d = d[d["시군명"].eq("춘천시")].copy()
    d["TYPE"] = np.where(d["기관유형"].eq("건강생활지원센터"), "건강증진센터", "보건소")
    d["NAME"] = d["기관명"].where(
        d["기관명"].str.endswith(("소", "센터")), d["기관명"] + d["기관유형"]
    )
    out.append(
        frame(
            d,
            "data.go.kr 15159040",
            DG.format(15159040),
            "2026-07-15",
            INST_NAME="NAME",
            INST_TYPE="TYPE",
            SIDO="강원특별자치도",
            SGG="춘천시",
            ADDRESS="소재지 도로명주소",
            PHONE="전화번호",
            SERVICES="기관유형",
        )
    )
    d = read_raw("dg_15158913_gangwon_swimming_pool.csv")
    d = d[d["시군명"].eq("춘천시")].copy()
    d["ADDR"] = _first_address(d, "소재지 도로명주소", prefix="강원특별자치도 ")
    out.append(
        frame(
            d,
            "data.go.kr 15158913",
            DG.format(15158913),
            "데이터기준일자",
            INST_NAME="시설명",
            INST_TYPE="공공체육시설",
            ADDRESS="ADDR",
            PHONE="전화번호",
            SERVICES="경기장 규격",
        )
    )
    return out


def in_scope(df: pd.DataFrame) -> pd.Series:
    """수도권 전체와 춘천시만 남긴다."""
    return df["SIDO"].isin(CAPITAL_AREA) | (
        df["SIDO"].eq("강원특별자치도") & df["SGG"].eq("춘천시")
    )


def merge_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """같은 시군구·유형·이름(공백·괄호·센터 접미어 제거)이면 한 기관으로 합치고 태그와 출처를 모은다."""
    df = df.copy()
    df["_key"] = (
        df["SIDO"]
        + "|"
        + df["SGG"].fillna("")
        + "|"
        + df["INST_TYPE"]
        + "|"
        + (df["INST_NAME"].fillna("").str.replace(NAME_NOISE, "", regex=True))
    )
    # 좌표가 있는 행을 대표로 고른다
    df = df.sort_values(["_key", "LAT"], na_position="last")

    def union(values: pd.Series) -> str:
        items = sorted({t for v in values.dropna() for t in str(v).split(";") if t})
        return ";".join(items)

    agg = {
        c: "first"
        for c in OUT_COLUMNS
        if c in df.columns and c not in ("TAGS", "SOURCE", "SOURCE_URL")
    }
    agg.update({"TAGS": union, "SOURCE": union, "SOURCE_URL": union})
    return df.groupby("_key", sort=False).agg(agg).reset_index(drop=True)


def build_institutions() -> pd.DataFrame:
    """원본을 합쳐 범위를 거르고, 유형 규칙으로 태그를 달고, 중복을 합친다."""
    df = pd.concat(load_sources(), ignore_index=True)
    df = df[df["INST_TYPE"].notna() & df["INST_NAME"].notna()]
    df["ADDRESS"] = df["ADDRESS"].str.strip()
    df["SIDO"] = df["SIDO"].map(lambda s: SIDO_NAMES.get(s, s))
    # 시군구는 첫 토큰(경기 일반구는 시 단위로)만 쓰고, 도로명이 잘못 들어간 값은 비운다
    sgg = df["SGG"].fillna("").str.replace("특례시", "시").str.split().str[0]
    sgg = sgg.replace(
        {"ㅁ추홀구": "미추홀구", "깅화군": "강화군", "남구": "미추홀구"}
    )  # 원본 오타·옛 이름
    df["SGG"] = sgg.where(sgg.str.endswith(("시", "군", "구")) & ~sgg.isin(SIDO_NAMES.values()))
    df = df[in_scope(df)].copy()

    unknown = set(df["INST_TYPE"]) - set(TYPE_RULES)
    assert not unknown, f"TYPE_RULES에 없는 유형: {unknown}"
    rule = df["INST_TYPE"].map(TYPE_RULES)
    df["TAGS"] = rule.str[0] + ";" + df.get("EXTRA_TAGS", pd.Series("", index=df.index)).fillna("")
    df["TARGET_AGE"] = df["TARGET_AGE"].fillna(rule.str[1]) if "TARGET_AGE" in df else rule.str[1]
    for col in ("LAT", "LON"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["AS_OF"] = pd.to_datetime(df["AS_OF"], errors="coerce").dt.strftime("%Y-%m-%d")

    df = merge_duplicates(df)
    df["TAGS"] = df["TAGS"].str.strip(";")
    df = df.sort_values(["SIDO", "SGG", "INST_TYPE", "INST_NAME"]).reset_index(drop=True)
    df["INST_ID"] = [f"INST{i:06d}" for i in range(1, len(df) + 1)]
    return df.reindex(columns=OUT_COLUMNS)


PROGRAMS_NAME = "support_programs.csv"
# 지원사업 사업구분 → 서비스 태그 ('기타'는 태그 없음)
PROGRAM_CATEGORY_TAGS = {
    "동네모임": "SOCIAL_PART",
    "문화여가예술": "SOCIAL_PART;LEARNING",
    "자기치유": "MENTAL_CARE",
    "마음편의점": "MENTAL_CARE;SOCIAL_PART",
    "상담지원": "MENTAL_CARE;CASE_MGMT",
    "은둔거부가구": "ISOLATION_CARE",
    "서울연결처방": "ISOLATION_CARE;SOCIAL_PART",
    "안부확인": "CARE_CHECK",
    "생활지원": "CASE_MGMT",
}
SIHSC_PROGRAM_URL = "https://sihsc.welfare.seoul.kr/knockseoul/030203/bsns/list.do"


def build_programs(institutions: pd.DataFrame) -> pd.DataFrame:
    """서울시고립예방센터 지원사업을 사업 단위 표로 만들고, 운영기관을 기관 목록 INST_ID와 잇는다."""
    d = read_raw("sihsc_support_programs.csv")
    period = {
        k: d[col].str.extract(r"(\d{4}-\d{2}-\d{2})?\s*~\s*(\d{4}-\d{2}-\d{2})?")
        for k, col in (("APPLY", "모집기간"), ("RUN", "진행기간"))
    }
    tags = (
        d["사업구분"]
        .str.split("|")
        .map(
            lambda cs: ";".join(
                sorted({t for c in cs for t in PROGRAM_CATEGORY_TAGS.get(c, "").split(";") if t})
            )
        )
    )
    out = pd.DataFrame(
        {
            "PROG_ID": "SIHSC" + d["BSNS_SEQ"].str.zfill(3),
            "TITLE": d["TITLE"],
            "ORG_NAME": d["기관명"],
            "SIDO": "서울특별시",
            "SGG": d["자치구"]
            .str.split("|")
            .map(
                lambda gs: ";".join(g for g in gs if g.endswith("구")) or None
            ),  # '서울시' = 시 전역
            "CATEGORY": d["사업구분"].str.replace("|", ";"),
            "TARGET_GROUP": d["연령"].str.replace("|", ";"),
            "GENDER": d["성별"].str.replace("|", ";"),
            "APPLY_START": period["APPLY"][0],
            "APPLY_END": period["APPLY"][1],
            "RUN_START": period["RUN"][0],
            "RUN_END": period["RUN"][1],
            "CONTENT": d["CONTENT"],
            "TAGS": tags,
            "SOURCE_URL": SIHSC_PROGRAM_URL + "?bsns_seq=" + d["BSNS_SEQ"],
            "AS_OF": d["REG_DT"],
        }
    )
    key = lambda s: s.fillna("").str.replace(NAME_NOISE, "", regex=True)  # noqa: E731
    seoul = institutions[institutions["SIDO"].eq("서울특별시")]
    ids = dict(zip(key(seoul["INST_NAME"]), seoul["INST_ID"]))
    out.insert(3, "INST_ID", key(out["ORG_NAME"]).map(ids))
    return out


COLUMN_DEFINITIONS = {
    "INST_ID": (
        "기관 ID",
        "INST + 6자리 일련번호. 재생성하면 바뀔 수 있다. 지원사업은 결측 = 기관 목록에 없음",
    ),
    "INST_NAME": ("기관명", "출처 표기 그대로. 여러 출처가 합쳐지면 좌표가 있는 출처의 표기"),
    "INST_TYPE": ("기관 유형", "TYPE_RULES의 키 (31종)"),
    "SIDO": ("시도", "서울특별시, 경기도, 인천광역시, 강원특별자치도(춘천시만)"),
    "SGG": ("시군구", "경기 일반구가 있는 시는 시 단위. 지원사업은 결측 = 서울시 전역"),
    "ADM_CD": ("행정동코드", "출처에 있을 때만 (치매안심센터). 결측 = 출처에 없음"),
    "ADDRESS": ("주소", "도로명주소 우선, 없으면 지번주소"),
    "LON": ("경도 (WGS84)", "결측 = 출처에 좌표 없음. 지오코딩하지 않았다"),
    "LAT": ("위도 (WGS84)", "결측 = 출처에 좌표 없음"),
    "PHONE": ("대표 전화", "결측 = 출처에 없음"),
    "TARGET_AGE": (
        "주 이용 대상",
        "ALL, 60+, 65+ (유형 규칙 기준. 무료급식소는 급식대상 문구로 판정)",
    ),
    "SERVICES": ("서비스 설명", "출처의 업무·프로그램·대상 설명 열. 결측 = 출처에 설명 없음"),
    "TAGS": ("서비스 태그", "; 구분. docs/resource-tags.md의 16개 태그"),
    "SOURCE": ("출처 데이터셋", "; 구분. 중복 기관은 출처를 모두 남긴다"),
    "SOURCE_URL": ("출처 페이지", "; 구분"),
    "AS_OF": ("기준일", "원본 기준일 열, 없으면 포털 수정일 (YYYY-MM-DD)"),
    "VALID_UNTIL": (
        "위수탁 종료일",
        "노인맞춤돌봄 수행기관만. 지난 날짜면 현재 수행 여부 재확인 필요",
    ),
    "FEATURE_CODE": ("위험 특징 코드", "risk_feature_dictionary.csv의 24개 세부 코드"),
    "TAG": ("서비스 태그", "institutions.csv TAGS와 같은 어휘"),
    "PRIORITY": ("후보 검토 순서", "특징마다 1부터. 이용 자격·추천 확정 순서가 아님"),
    "NOTE": ("연결 근거·추가 확인 조건", "조건은 자동 판정되지 않으며 추천 전에 확인해야 함"),
    "N_INSTITUTIONS": (
        "해당 태그 전체 기관 수",
        "생성 시점 institutions.csv 기준. 지역·연령별 이용 가능 수가 아님",
    ),
    "PROG_ID": ("사업 ID", "SIHSC + 서울시고립예방센터 사업 번호"),
    "TITLE": ("사업명", "게시 제목 그대로"),
    "ORG_NAME": ("운영기관", "게시 표기 그대로. 여러 기관이면 쉼표로 이어짐"),
    "CATEGORY": (
        "사업구분",
        "; 구분. 동네모임, 자기치유, 문화여가예술, 은둔거부가구, 서울연결처방 등",
    ),
    "TARGET_GROUP": ("대상 연령층", "; 구분. 청년, 중장년, 어르신"),
    "GENDER": ("대상 성별", "; 구분"),
    "APPLY_START": ("모집 시작일", "결측 = 게시물에 없음"),
    "APPLY_END": ("모집 종료일", "지난 날짜면 모집 마감"),
    "RUN_START": ("진행 시작일", "결측 = 게시물에 없음"),
    "RUN_END": ("진행 종료일", "결측 = 게시물에 없음 (상시 사업 포함)"),
    "CONTENT": ("사업 본문", "게시물 본문 줄을 ' / '로 이음"),
}


def dictionary(table: pd.DataFrame) -> pd.DataFrame:
    """열 정의서를 만든다."""
    rows = [(c, *COLUMN_DEFINITIONS[c], int(table[c].isna().sum())) for c in table.columns]
    return pd.DataFrame(rows, columns=["COLUMN", "LABEL", "DESCRIPTION", "N_MISSING"])


def feature_tag_mapping(institutions: pd.DataFrame, risk: pd.DataFrame) -> pd.DataFrame:
    """24개 세부 특징과 실제 기관 태그를 검증한 뒤 후보 연결표를 만든다."""
    mapping = pd.DataFrame(FEATURE_TAG_MAPPING, columns=["FEATURE_CODE", "TAG", "PRIORITY", "NOTE"])
    if risk["FEATURE_CODE"].isna().any() or risk["FEATURE_CODE"].duplicated().any():
        raise ValueError("위험 특징 사전에 결측 또는 중복 코드가 있음")
    if not risk["IS_CRISIS"].isin(["Y", "N"]).all():
        raise ValueError("위험 특징 사전에 잘못된 IS_CRISIS 값이 있음")
    codes = set(risk["FEATURE_CODE"])
    mapped = set(mapping["FEATURE_CODE"])
    if codes != mapped:
        raise ValueError(
            f"매핑 코드 불일치: 누락={sorted(codes - mapped)}, 미등록={sorted(mapped - codes)}"
        )
    if (
        mapping[["FEATURE_CODE", "TAG", "NOTE"]].isna().any().any()
        or not mapping["NOTE"].str.strip().all()
    ):
        raise ValueError("매핑 코드·태그·근거에 빈값이 있음")
    if mapping.duplicated(["FEATURE_CODE", "TAG"]).any():
        raise ValueError("특징·태그 중복 연결")
    for code, rows in mapping.groupby("FEATURE_CODE", sort=False):
        if sorted(rows["PRIORITY"].tolist()) != list(range(1, len(rows) + 1)):
            raise ValueError(f"{code}: 우선순위는 1부터 중복 없이 이어져야 함")
    crisis_codes = set(risk.loc[risk["IS_CRISIS"].eq("Y"), "FEATURE_CODE"])
    for code in crisis_codes:
        first = mapping.loc[mapping["FEATURE_CODE"].eq(code)].sort_values("PRIORITY").iloc[0]
        if first["TAG"] != "CRISIS_LINE":
            raise ValueError(f"{code}: 위기 이관 태그가 1순위가 아님")
    counts = institutions["TAGS"].dropna().str.split(";").explode().value_counts()
    allowed_tags = {tag for value, _ in TYPE_RULES.values() for tag in value.split(";")}
    unknown_tags = set(mapping["TAG"]) - (set(counts.index) & allowed_tags)
    if unknown_tags:
        raise ValueError(f"기관 목록에 없는 태그: {sorted(unknown_tags)}")
    mapping["N_INSTITUTIONS"] = mapping["TAG"].map(counts)
    return mapping


def main(argv: list[str] | None = None) -> None:
    """기관 전체 또는 기존 기관 목록을 이용한 매핑만 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(paths.PROCESSED_DIR))
    parser.add_argument("--mapping-only", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    df = (
        pd.read_csv(paths.PROCESSED_DIR / OUTPUT_NAME)
        if args.mapping_only
        else build_institutions()
    )
    risk = pd.read_csv(paths.PROCESSED_DIR / "risk_feature_dictionary.csv")
    mapping = feature_tag_mapping(df, risk)
    tables = [(MAPPING_NAME, mapping)]
    if not args.mapping_only:
        tables = [(OUTPUT_NAME, df), *tables, (PROGRAMS_NAME, build_programs(df))]
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables:
        table.to_csv(out_dir / name, index=False, encoding="utf-8-sig")
        dictionary(table).to_csv(
            out_dir / name.replace(".csv", "_dictionary.csv"), index=False, encoding="utf-8-sig"
        )
        print(f"saved {name} rows={len(table)} cols={table.shape[1]}")


if __name__ == "__main__":
    main()
