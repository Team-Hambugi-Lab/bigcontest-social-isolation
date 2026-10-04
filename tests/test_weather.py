"""기상 월별 집계 테스트."""

from src.data.weather import load_monthly_temperature

SEOUL_CSV = """latitude,longitude,elevation,utc_offset_seconds,timezone,timezone_abbreviation
37.5,127.0,70.0,32400,Asia/Seoul,GMT+9

time,temperature_2m_mean (°C),temperature_2m_min (°C),temperature_2m_max (°C),precipitation_sum (mm),snowfall_sum (cm)
2025-07-01,25.0,20.0,30.0,0.0,0.0
2025-07-02,27.0,22.0,32.0,0.0,0.0
2025-12-01,-2.0,-5.0,1.0,0.0,0.0
2025-12-02,-4.0,-7.0,-1.0,0.0,0.0
"""

CHUNCHEON_CSV = """latitude,longitude,elevation,utc_offset_seconds,timezone,timezone_abbreviation
38.0,127.75,76.0,32400,Asia/Seoul,GMT+9

time,temperature_2m_mean (°C),temperature_2m_min (°C),temperature_2m_max (°C),precipitation_sum (mm),snowfall_sum (cm)
2025-07-01,20.0,15.0,25.0,0.0,0.0
2025-07-02,22.0,17.0,27.0,0.0,0.0
2025-12-01,-6.0,-9.0,-3.0,0.0,0.0
2025-12-02,-8.0,-11.0,-5.0,0.0,0.0
"""


def test_monthly_mean_by_region(tmp_path):
    (tmp_path / "OpenMeteo_ERA5_20250701_20251231_서울_ASOS108좌표.csv").write_text(
        SEOUL_CSV, encoding="utf-8"
    )
    (tmp_path / "OpenMeteo_ERA5_20250701_20251231_춘천_ASOS101좌표.csv").write_text(
        CHUNCHEON_CSV, encoding="utf-8"
    )

    result = load_monthly_temperature(tmp_path)

    assert set(result.columns) == {"지역", "STD_YM", "평균기온"}
    assert len(result) == 4  # 2개 지역 x 2개월

    seoul = result[result.지역 == "서울"].set_index("STD_YM")["평균기온"]
    assert seoul["202507"] == 26.0  # (25.0 + 27.0) / 2
    assert seoul["202512"] == -3.0  # (-2.0 + -4.0) / 2

    chuncheon = result[result.지역 == "춘천"].set_index("STD_YM")["평균기온"]
    assert chuncheon["202507"] == 21.0
    assert chuncheon["202512"] == -7.0
