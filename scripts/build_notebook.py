"""노트북을 코드로 생성하고 실행해 출력까지 저장하는 헬퍼.

Jupyter UI 없이 nbformat + nbclient로 처리한다.
"""

from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 모든 노트북 첫 셀에 들어가는 공통 준비 코드
BOOTSTRAP = """
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data import loaders, paths, regions
from src.features import card_cohort, isolation, sk_dong
from src.visualization.style import PALETTE, SGG_COLORS, setup_style

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")

FONT = setup_style()
print(f"한글 폰트: {FONT}")
print(f"pandas {pd.__version__} / numpy {np.__version__}")
"""


def md(text: str) -> nbformat.NotebookNode:
    """마크다운 셀을 만든다."""
    return nbformat.v4.new_markdown_cell(text.strip())


def code(src: str) -> nbformat.NotebookNode:
    """코드 셀을 만든다."""
    return nbformat.v4.new_code_cell(src.strip())


def build(cells: list, out_path: Path, timeout: int = 2400) -> Path:
    """셀 목록으로 노트북을 만들고 실행한 뒤 저장한다."""
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python (bigcontest)",
        "language": "python",
        "name": "bigcontest",
    }
    nb.metadata["language_info"] = {"name": "python"}
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="bigcontest",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
    )
    client.execute()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, out_path)
    return out_path


def check(out_path: Path) -> None:
    """실행된 노트북에 오류 출력이 있는지 확인하고 요약을 출력한다."""
    nb = nbformat.read(out_path, as_version=4)
    errors = [
        (i, o)
        for i, c in enumerate(nb.cells)
        for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    print(f"{out_path.name}: cells={len(nb.cells)} errors={len(errors)}")
    for i, o in errors:
        print(f"  cell {i}: {o.get('ename')}: {o.get('evalue')}")
    if errors:
        raise RuntimeError(f"{out_path.name} 실행 중 오류 {len(errors)}건")
