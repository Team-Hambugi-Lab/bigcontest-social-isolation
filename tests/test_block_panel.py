"""집계구 패널 집계 단위 테스트."""

import pandas as pd

from src.features.block_panel import aggregate_to_block


class TestAggregateToBlock:
    def test_sums_grids_sharing_block_prefix(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["1123051010102000001", "1123051010102000002"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [1.0, 2.0],
            }
        )

        result = aggregate_to_block(df)

        assert len(result) == 1
        assert result.loc[0, "집계구"] == "1123051010102"
        assert result.loc[0, "TMST_00"] == 3.0

    def test_excludes_non_target_sigungu(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507"],
                "BLOCK_CD": ["4111351010102000001"],
                "X_COORD": [1.0],
                "Y_COORD": [1.0],
                "TMST_00": [5.0],
            }
        )

        result = aggregate_to_block(df)

        assert len(result) == 0

    def test_all_missing_group_stays_nan_not_zero(self):
        df = pd.DataFrame(
            {
                "STD_YM": ["202507", "202507"],
                "BLOCK_CD": ["1123051010102000001", "1123051010102000002"],
                "X_COORD": [1.0, 2.0],
                "Y_COORD": [1.0, 2.0],
                "TMST_00": [float("nan"), float("nan")],
            }
        )

        result = aggregate_to_block(df)

        assert pd.isna(result.loc[0, "TMST_00"])
