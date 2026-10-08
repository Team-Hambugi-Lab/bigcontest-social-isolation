"""matplotlib 공통 스타일 — 한글 폰트와 색약 친화 팔레트."""

import matplotlib
import matplotlib.pyplot as plt

# Okabe-Ito 색약 친화 팔레트
PALETTE = [
    "#0072B2",  # 파랑
    "#E69F00",  # 주황
    "#009E73",  # 청록
    "#CC79A7",  # 분홍
    "#56B4E9",  # 하늘
    "#D55E00",  # 주홍
    "#F0E442",  # 노랑
    "#666666",  # 회색
]

SGG_COLORS = {"서울 강남구": PALETTE[0], "강원 춘천시": PALETTE[1]}

_FONT_CANDIDATES = ("Malgun Gothic", "NanumGothic", "Pretendard", "AppleGothic")


def setup_style() -> str:
    """한글 폰트와 기본 rcParams를 적용하고 선택된 폰트명을 반환한다."""
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    font = next((f for f in _FONT_CANDIDATES if f in available), "DejaVu Sans")

    plt.rcParams["font.family"] = font
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 110
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["figure.figsize"] = (10, 6)
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["axes.prop_cycle"] = plt.cycler(color=PALETTE)
    return font
