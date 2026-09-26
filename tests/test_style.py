"""시각화 공통 스타일 테스트."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from src.visualization import style  # noqa: E402


def test_setup_style_sets_korean_font():
    font = style.setup_style()
    assert font in plt.rcParams["font.family"] or font == plt.rcParams["font.family"][0]
    assert plt.rcParams["axes.unicode_minus"] is False


def test_palette_is_colorblind_safe_length():
    assert len(style.PALETTE) == 8
    assert all(c.startswith("#") and len(c) == 7 for c in style.PALETTE)


def test_sgg_colors_cover_both_regions():
    assert set(style.SGG_COLORS) == {"서울 강남구", "강원 춘천시"}


def test_korean_label_renders_without_error(tmp_path):
    style.setup_style()
    fig, ax = plt.subplots()
    ax.set_title("행정동별 유동인구")
    ax.set_xlabel("연령대")
    out = tmp_path / "t.png"
    fig.savefig(out)
    plt.close(fig)
    assert out.stat().st_size > 1000
