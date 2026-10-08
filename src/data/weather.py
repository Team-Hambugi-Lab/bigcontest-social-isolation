"""Open-Meteo ERA5 일별 기상 자료를 월평균으로 집계.

data/raw/reference_data/기상/2025_기상_자료_수집정보.md 참고: 파일 앞 2행은
격자 메타데이터, 3번째 행은 빈 행이라 skiprows=3으로 읽는다. 서울·춘천 지점은
구·시 내부 관측이 아니라 도시권 전체의 대리변수다.
"""

from pathlib import Path

import pandas as pd

WEATHER_FILES = {
    "서울": "OpenMeteo_ERA5_20250701_20251231_서울_ASOS108좌표.csv",
    "춘천": "OpenMeteo_ERA5_20250701_20251231_춘천_ASOS101좌표.csv",
}


def load_monthly_temperature(weather_dir: Path) -> pd.DataFrame:
    """지역별 일평균기온을 월평균으로 집계해 반환한다.

    반환 컬럼: 지역("서울"/"춘천"), STD_YM(YYYYMM 문자열), 평균기온(섭씨).
    """
    parts = []
    for region, filename in WEATHER_FILES.items():
        df = pd.read_csv(weather_dir / filename, skiprows=3)
        df["STD_YM"] = pd.to_datetime(df["time"]).dt.strftime("%Y%m")
        monthly = df.groupby("STD_YM", as_index=False)["temperature_2m_mean (°C)"].mean()
        monthly = monthly.rename(columns={"temperature_2m_mean (°C)": "평균기온"})
        monthly["지역"] = region
        parts.append(monthly)
    return pd.concat(parts, ignore_index=True)[["지역", "STD_YM", "평균기온"]]
