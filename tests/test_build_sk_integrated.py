"""SK 유동인구 통합 파일 병합 로직 단위 테스트."""

from pathlib import Path

import pandas as pd

from src.features.build_sk_integrated import merge_month


def _write_table(raw_dir: Path, table: str, month: str, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(raw_dir / f"flow_{table}_pop_{month}.csv", index=False)


class TestMergeMonth:
    def test_outer_join_preserves_grids_missing_in_one_table(self, tmp_path: Path):
        month = "202507"
        key = {"STD_YM": month, "BLOCK_CD": "B1", "X_COORD": 1.0, "Y_COORD": 1.0}
        only_in_age = {"STD_YM": month, "BLOCK_CD": "B2", "X_COORD": 2.0, "Y_COORD": 2.0}

        _write_table(
            tmp_path,
            "age",
            month,
            [{**key, "MAN_FLOW_POP_CNT_10G": 1.0}, {**only_in_age, "MAN_FLOW_POP_CNT_10G": 2.0}],
        )
        _write_table(tmp_path, "time", month, [{**key, "TMST_00": 3.0}])
        _write_table(tmp_path, "wkdy", month, [{**key, "FLOW_POP_CNT_MON": 4.0}])

        merged = merge_month(tmp_path, month)

        assert len(merged) == 2
        only_in_age_row = merged.loc[merged["BLOCK_CD"] == "B2"].iloc[0]
        assert pd.isna(only_in_age_row["TMST_00"])
        assert pd.isna(only_in_age_row["FLOW_POP_CNT_MON"])

    def test_duplicate_rows_removed_before_merge(self, tmp_path: Path):
        month = "202512"
        key = {"STD_YM": month, "BLOCK_CD": "B1", "X_COORD": 1.0, "Y_COORD": 1.0}

        _write_table(tmp_path, "age", month, [{**key, "MAN_FLOW_POP_CNT_10G": 1.0}])
        _write_table(
            tmp_path,
            "time",
            month,
            [{**key, "TMST_00": 3.0}, {**key, "TMST_00": 3.0}],  # 완전 중복
        )
        _write_table(tmp_path, "wkdy", month, [{**key, "FLOW_POP_CNT_MON": 4.0}])

        merged = merge_month(tmp_path, month)

        assert len(merged) == 1
        assert not merged.duplicated(["STD_YM", "BLOCK_CD", "X_COORD", "Y_COORD"]).any()
