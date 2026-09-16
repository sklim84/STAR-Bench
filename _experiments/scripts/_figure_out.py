"""Where a figure script is allowed to write.

Six figure scripts carried a copied header that redirected matplotlib's savefig
to two directories at once, one of them a manuscript checkout outside this
repository. Running a superseded script therefore replaced a figure the paper
builds from, under the same file name, with no sign that it had happened
(R2C-007): `RQ3_turnwise_real.py` overwrote `fig_turnwise_line.png` with a
six-model plot, and `generate_bfcl_comparison.py` wrote a different correlation
under the name the manuscript uses.

A figure script now writes inside this repository only. Copying into the
manuscript is one explicit step:

    python -m _experiments.scripts.regenerate_analysis --copy-to-manuscript ../STAR-Bench-manu/figures

`$STAR_BENCH_FIGURE_COPY` does the same for a script run by hand, so the copy is
something a person asks for rather than a side effect of plotting.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

__all__ = ["FIGURES", "install", "copy_to_manuscript"]

FIGURES = Path(__file__).resolve().parents[1] / "figures"


def install(subdir: str | None = None) -> Path:
    """Redirects every savefig into `_experiments/figures[/subdir]` by file name."""
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure

    target = FIGURES if not subdir else FIGURES / subdir
    target.mkdir(parents=True, exist_ok=True)

    original_plt, original_fig = plt.savefig, Figure.savefig

    def destinations(name: str) -> list[str]:
        base = Path(str(name)).name
        out = [str(target / base)]
        extra = os.environ.get("STAR_BENCH_FIGURE_COPY")
        if extra:
            Path(extra).mkdir(parents=True, exist_ok=True)
            out.append(str(Path(extra) / base))
        return out

    def save_plt(name, *args, **kwargs):
        for path in destinations(name):
            original_plt(path, *args, **kwargs)

    def save_fig(self, name, *args, **kwargs):
        for path in destinations(name):
            original_fig(self, path, *args, **kwargs)

    plt.savefig = save_plt
    Figure.savefig = save_fig
    return target


def copy_to_manuscript(destination: Path | str, names: list[str] | None = None) -> list[str]:
    """Copies figures into the manuscript directory, the one explicit step."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(FIGURES.glob("*")):
        if path.is_dir() or (names and path.name not in names):
            continue
        shutil.copy2(path, destination / path.name)
        copied.append(path.name)
    return copied
