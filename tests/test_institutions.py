"""복지·공공기관 자원 DB 정리 테스트."""

import numpy as np
import pandas as pd
import pytest

from src.features import institutions as inst


def _rule_tags() -> set[str]:
    return {t for tags, _ in inst.TYPE_RULES.values() for t in tags.split(";")}


def test_every_mapped_type_has_rule():
    mapped = set(inst.SEOUL_FACILITY_TYPES.values()) | set(inst.MENTAL_TYPES.values())
    assert mapped <= set(inst.TYPE_RULES)


def test_mapping_uses_only_defined_tags():
    assert {tag for _, tag, _, _ in inst.FEATURE_TAG_MAPPING} <= _rule_tags()


def test_feature_mapping_requires_matching_codes_tags_and_crisis_order(monkeypatch):
    risk = pd.DataFrame({"FEATURE_CODE": ["A", "B"], "IS_CRISIS": ["N", "Y"]})
    institutions = pd.DataFrame({"TAGS": ["SOCIAL_PART;CRISIS_LINE", "SOCIAL_PART"]})
    rows = [("A", "SOCIAL_PART", 1, "참여"), ("B", "CRISIS_LINE", 1, "이관")]
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", rows)
    result = inst.feature_tag_mapping(institutions, risk)
    assert result["N_INSTITUTIONS"].tolist() == [2, 1]
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", rows + [("A", "SOCIAL_PART", 2, "중복")])
    with pytest.raises(ValueError, match="중복"):
        inst.feature_tag_mapping(institutions, risk)
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", [("A", "SOCIAL_PART", 1, "참여")])
    with pytest.raises(ValueError, match="누락"):
        inst.feature_tag_mapping(institutions, risk)
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", [("A", "UNKNOWN", 1, "참여"), rows[1]])
    with pytest.raises(ValueError, match="기관 목록에 없는 태그"):
        inst.feature_tag_mapping(institutions, risk)
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", [rows[0], ("B", "SOCIAL_PART", 1, "이관")])
    with pytest.raises(ValueError, match="위기 이관"):
        inst.feature_tag_mapping(institutions, risk)


def test_mapping_only_does_not_rebuild_institutions_or_programs(tmp_path, monkeypatch):
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    pd.DataFrame({"TAGS": ["SOCIAL_PART;CRISIS_LINE"]}).to_csv(
        source / inst.OUTPUT_NAME, index=False
    )
    pd.DataFrame({"FEATURE_CODE": ["A"], "IS_CRISIS": ["N"]}).to_csv(
        source / "risk_feature_dictionary.csv", index=False
    )
    original = (source / inst.OUTPUT_NAME).read_bytes()
    monkeypatch.setattr(inst.paths, "PROCESSED_DIR", source)
    monkeypatch.setattr(inst, "FEATURE_TAG_MAPPING", [("A", "SOCIAL_PART", 1, "참여")])
    monkeypatch.setattr(inst, "build_institutions", lambda: pytest.fail("기관 재생성"))
    monkeypatch.setattr(inst, "build_programs", lambda _: pytest.fail("사업 재생성"))
    inst.main(["--mapping-only", "--out-dir", str(output)])
    assert sorted(p.name for p in output.iterdir()) == [
        "feature_tag_mapping.csv",
        "feature_tag_mapping_dictionary.csv",
    ]
    assert (source / inst.OUTPUT_NAME).read_bytes() == original


def test_split_region_normalizes_sido_and_drops_unknown():
    out = inst.split_region(
        pd.Series(
            ["서울 강남구 개포로 605", "강원특별자치도 춘천시 중앙로 131", "부산 해운대구 x", None]
        )
    )
    assert out["SIDO"].tolist()[:2] == ["서울특별시", "강원특별자치도"]
    assert out["SGG"].tolist()[:2] == ["강남구", "춘천시"]
    assert out["SIDO"].isna().tolist()[2:] == [True, True]


def test_in_scope_keeps_capital_area_and_chuncheon_only():
    df = pd.DataFrame(
        {
            "SIDO": ["경기도", "강원특별자치도", "강원특별자치도", "부산광역시"],
            "SGG": ["수원시", "춘천시", "원주시", "해운대구"],
        }
    )
    assert inst.in_scope(df).tolist() == [True, True, False, False]


def test_merge_duplicates_unions_tags_and_keeps_coordinates():
    df = pd.DataFrame(
        {
            "INST_NAME": [
                "서울특별시강남구치매안심센터",
                "강남구 치매안심센터",
                "강남구 치매안심센터",
            ],
            "INST_TYPE": ["치매안심센터", "치매안심센터", "보건소"],
            "SIDO": ["서울특별시"] * 3,
            "SGG": ["강남구"] * 3,
            "LAT": [np.nan, 37.51, np.nan],
            "LON": [np.nan, 127.05, np.nan],
            "TAGS": ["DEMENTIA", "HEALTH_MGMT", "HEALTH_MGMT"],
            "SOURCE": ["a", "b", "c"],
            "SOURCE_URL": ["u1", "u2", "u3"],
        }
    )
    out = inst.merge_duplicates(df)
    assert len(out) == 2  # 유형이 다르면 합치지 않는다
    merged = out[out["INST_TYPE"].eq("치매안심센터")].iloc[0]
    assert merged["TAGS"] == "DEMENTIA;HEALTH_MGMT"
    assert merged["SOURCE"] == "a;b"
    assert merged["LAT"] == 37.51


def test_sihsc_type_reuses_existing_types_for_welfare_centers():
    names = pd.Series(
        ["강남종합사회복지관", "성북장애인복지관", "양천어르신종합복지관", "사단법인 온기"]
    )
    assert inst.sihsc_type(names).tolist() == [
        "사회복지관",
        "장애인복지관",
        "노인복지관",
        "고립예방 협력기관",
    ]


def test_program_categories_use_defined_tags():
    tags = {t for v in inst.PROGRAM_CATEGORY_TAGS.values() for t in v.split(";")}
    role_tags = {t for v in inst.SIHSC_ROLE_TAGS.values() for t in v.split(";")}
    assert tags | role_tags <= _rule_tags()
