"""집계구 패널 집계 단위 테스트."""

import pandas as pd
import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Polygon  # noqa: E402

from src.features.block_panel import aggregate_to_block, assign_oa  # noqa: E402


def _square_boundaries() -> gpd.GeoDataFrame:
    poly_a = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    poly_b = Polygon([(10, 0), (20, 0), (20, 10), (10, 10)])
    return gpd.GeoDataFrame(
        {"TOT_OA_CD": ["11230510010001", "11230510010002"]},
        geometry=[poly_a, poly_b],
        crs="EPSG:5179",
    )


class TestAssignOa:
    def test_points_assigned_to_containing_polygon(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["x", "y"],
                "X_COORD": [5.0, 15.0],
                "Y_COORD": [5.0, 5.0],
                "TMST_00": [1.0, 2.0],
            }
        )

        result = assign_oa(df, _square_boundaries())

        assert sorted(result["집계구"]) == ["11230510010001", "11230510010002"]

    def test_points_outside_all_polygons_are_dropped(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507"],
                "BLOCK_CD": ["z"],
                "X_COORD": [100.0],
                "Y_COORD": [100.0],
                "TMST_00": [5.0],
            }
        )

        result = assign_oa(df, _square_boundaries())

        assert len(result) == 0


class TestAggregateToBlock:
    def test_sums_grids_sharing_polygon(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["x", "y"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [1.0, 2.0],
            }
        )

        result = aggregate_to_block(df, _square_boundaries())

        assert len(result) == 1
        assert result.loc[0, "집계구"] == "11230510010001"
        assert result.loc[0, "TMST_00"] == 3.0

    def test_points_in_different_polygons_stay_separate(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["x", "y"],
                "X_COORD": [1.0, 15.0],
                "Y_COORD": [1.0, 5.0],
                "TMST_00": [1.0, 2.0],
            }
        )

        result = aggregate_to_block(df, _square_boundaries())

        assert len(result) == 2
        assert set(result["집계구"]) == {"11230510010001", "11230510010002"}

    def test_all_missing_group_stays_nan_not_zero(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["x", "y"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [float("nan"), float("nan")],
            }
        )

        result = aggregate_to_block(df, _square_boundaries())

        assert pd.isna(result.loc[0, "TMST_00"])
