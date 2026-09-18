#!/usr/bin/env python3
"""RQ4 (a) 2x2 question-language x tool-schema-language ablation.

The two axes are the language of the question and the language of the **tool
schema**. Before the rerun this step read four separate results directories, and
two of them turned out to be the same arm: `results_kr` / `results_en` were run
against the English platform schema, so the second axis was English twice
(R2C-005, D16). The rerun serves the four cells as four columns of one scored
tree, and `load.COLUMNS` says which is which:

  KR-KR  load.single()                       Korean question x Korean schema (tools_kr.py)
  EN-KR  load.single("krtools_enq")          English question x Korean schema
  KR-EN  load.single("entools_krq")           Korean question x English schema
  EN-EN  load.single("entools_enq")           English question x English schema

Cell name reads query-language first, tool-language second.

Porting note (PORTING.md rule 1). This step never thresholded the weighted
`score`; it read `overall.primary_tool_hit_rate`, which is now the mean of `h`,
and `avg_param_accuracy`, which is now the mean of `a`. Recorded here for the
same reason the sibling steps record it: **`score >= 0.9` became `h == 1`**
across this analysis, and `h` is the number in every cell below. Rule 2 applies
to `a`: it is null for a case with no parameter checks rather than 1.0, so the
mean is taken over the non-null rows and the output carries that n next to it.

Cohort (rules 3 and 4). The `TARGETS` list of twelve model ids is deleted, along
with the id-normalising helpers it needed. The rows are the configurations that
have all four cells scored, which today is 6 of the 28 in the registry: the
three extra arms were only run for those. The ablation is over those 6 and the
CSV, the JSON and both figures say so.

Output (unchanged names, under `_experiments/results_RQ4`):
  - <out>/four_way_ablation.csv (per-configuration x cell h and a, with their n)
  - <out>/four_way_ablation_summary.json
  - <out>/fig_four_way_h_heatmap.{pdf,png}
  - <out>/fig_four_way_delta_decomposition.{pdf,png}

    python -m _experiments.scripts.RQ4_query_tool_language_ablation \
        --results-root _experiments/results_2026rerun --out _experiments/results_RQ4
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_NOTHINK, COL_THINK, COL_ACCENT, FS_TICK, FS_LABEL,
                         FS_LEGEND, style_axes)

_SB = Path(__file__).resolve().parents[2]  # repository root
if str(_SB) not in sys.path:
    sys.path.insert(0, str(_SB))

from _experiments.scripts.analysis import load  # noqa: E402

# cell (query language - tool language) -> the column of the scored tree
CELLS = {
    'KR-KR': 'single',
    'EN-KR': 'krtools_enq',
    'KR-EN': 'entools_krq',
    'EN-EN': 'entools_enq',
}
CELL_ORDER = ['KR-KR', 'EN-KR', 'KR-EN', 'EN-EN']


def _rel(path: Path) -> str:
    """A path as the repository prints it; a checkout path is a machine property."""
    return str(path.relative_to(_SB)) if path.is_relative_to(_SB) else str(path)


def _resolve_eval_root(given: str | None) -> Path | None:
    """`--results-root` names the run tree or its eval directory; either works."""
    if not given:
        return None
    path = Path(given)
    if not path.is_absolute():
        path = _SB / path
    return path / 'eval' if (path / 'eval').is_dir() else path


def configure(argv=None) -> tuple[Path | None, Path]:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--results-root',
                    help='the scored run tree holding the four columns, or its eval '
                         f'directory (default {load.DEFAULT_EVAL_ROOT.relative_to(_SB)})')
    ap.add_argument('--out', help='output directory (default _experiments/results_RQ4)')
    args = ap.parse_args(argv)

    eval_root = _resolve_eval_root(args.results_root)
    out_dir = Path(args.out) if args.out else (_SB / '_experiments' / 'results_RQ4')
    if not out_dir.is_absolute():
        out_dir = _SB / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    return eval_root, out_dir


def load_cell(column: str, eval_root: Path | None) -> dict:
    """config_id -> {h, n_h, a, n_a, label} for one cell.

    `a` is null for a case with no parameter checks (rule 2), so its mean is over
    the non-null rows and carries its own n.
    """
    cases = load.single(column=column, eval_root=eval_root)
    out = {}
    for config_id, group in cases.groupby('config_id'):
        a = group['a'].dropna()
        out[config_id] = {
            'label': group['label'].iloc[0],
            'group': group['group'].iloc[0],
            'h': float(group['h'].mean()), 'n_h': int(len(group)),
            'a': float(a.mean()) if len(a) else None, 'n_a': int(len(a)),
        }
    return out


def main(argv=None):
    eval_root, out_dir = configure(argv)

    cells = {}
    for name in CELL_ORDER:
        column = CELLS[name]
        try:
            cells[name] = load_cell(column, eval_root)
        except FileNotFoundError as exc:
            cells[name] = {}
            print(f'  {name}: no scored configuration ({exc})')
            continue
        directory = (eval_root or load.DEFAULT_EVAL_ROOT) / load.COLUMNS[column][0]
        print(f'  {name}: {len(cells[name])} configurations from {directory}')

    table = load.missing(eval_root=eval_root)
    n_registry = len(table)
    # The 2x2 needs a configuration in all four cells; only those rows are the
    # ablation, and the outputs name them.
    full4_ids = [cid for cid in table['config_id']
                 if all(cid in cells[name] for name in CELL_ORDER)]
    per_cell_missing = {
        name: table.loc[~table[CELLS[name]], 'config_id'].tolist() for name in CELL_ORDER
    }

    rows = []
    for cid in full4_ids:
        first = cells['KR-KR'][cid]
        row = {'model': first['label'], 'config_id': cid, 'group': first['group']}
        for name in CELL_ORDER:
            cd = cells[name][cid]
            row[f'h_{name}'] = cd['h']
            row[f'n_h_{name}'] = cd['n_h']
            row[f'a_{name}'] = cd['a']
            row[f'n_a_{name}'] = cd['n_a']
        h_kk, h_ek = row['h_KR-KR'], row['h_EN-KR']
        h_ke, h_ee = row['h_KR-EN'], row['h_EN-EN']
        row['delta_query_tool_kr'] = h_ek - h_kk   # question EN, schema stays KR
        row['delta_tool_query_kr'] = h_ke - h_kk   # schema EN, question stays KR
        row['delta_both'] = h_ee - h_kk
        rows.append(row)
    rows.sort(key=lambda r: -r['h_KR-KR'])

    if not rows:
        raise SystemExit('no configuration has all four cells scored; nothing to ablate')

    csv_path = out_dir / 'four_way_ablation.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def mean_or_none(vals):
        v = [x for x in vals if x is not None]
        return round(sum(v) / len(v), 4) if v else None

    cohort_note = (f'{len(rows)} of {n_registry} configurations have all four cells; '
                   f'the ablation is over those {len(rows)}')
    summary = {
        'cohort': {
            'n_registry': n_registry,
            'n_configs': len(rows),
            'config_ids': [r['config_id'] for r in rows],
            'labels': [r['model'] for r in rows],
            'missing_config_ids_per_cell': per_cell_missing,
            'note': cohort_note,
        },
        'cells': {
            name: {
                'column': CELLS[name],
                'query_lang': load.COLUMNS[CELLS[name]][2],
                'tools_lang': load.COLUMNS[CELLS[name]][1],
                'eval_dir': _rel((eval_root or load.DEFAULT_EVAL_ROOT)
                                 / load.COLUMNS[CELLS[name]][0]),
                'n_configs_scored': len(cells[name]),
            } for name in CELL_ORDER
        },
        'n_configs': len(rows),
        'cell_means_h': {name: mean_or_none([r[f'h_{name}'] for r in rows])
                         for name in CELL_ORDER},
        'cell_means_a': {name: mean_or_none([r[f'a_{name}'] for r in rows])
                         for name in CELL_ORDER},
        'cell_n_a': {name: sum(r[f'n_a_{name}'] for r in rows) for name in CELL_ORDER},
        'cell_n_h': {name: sum(r[f'n_h_{name}'] for r in rows) for name in CELL_ORDER},
        'mean_delta_query_only': mean_or_none([r['delta_query_tool_kr'] for r in rows]),
        'mean_delta_tool_only': mean_or_none([r['delta_tool_query_kr'] for r in rows]),
        'mean_delta_both': mean_or_none([r['delta_both'] for r in rows]),
        'rows': rows,
        'note': ('h = mean primary tool hit, a = mean parameter accuracy over the cases '
                 'that have parameter checks (a is null, not 1.0, where there is nothing '
                 'to check). Delta = cell - KR-KR. The cell name reads query language '
                 'first, tool schema language second. ' + cohort_note),
    }
    with (out_dir / 'four_way_ablation_summary.json').open('w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    try:
        import numpy as np
        labels = [r['model'] for r in rows]

        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        mat = np.array([[r[f'h_{c}'] for c in CELL_ORDER] for r in rows])
        # The pre-audit window was a fixed 0.3-0.85, which clips every cell of the
        # rerun and draws the whole grid one colour. The window follows the data,
        # rounded out to a twentieth, and the cell annotations carry the values.
        lo = float(np.floor(mat.min() * 20) / 20)
        hi = float(np.ceil(mat.max() * 20) / 20)
        im = ax.imshow(mat, cmap='viridis', aspect='auto', vmin=lo, vmax=hi)
        ax.set_xticks(range(len(CELL_ORDER)))
        ax.set_xticklabels(CELL_ORDER, fontsize=FS_TICK)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=FS_TICK)
        for i in range(len(labels)):
            for j in range(len(CELL_ORDER)):
                v = mat[i, j]
                txt_col = 'white' if v < lo + 0.45 * (hi - lo) else 'black'
                ax.text(j, i, f'{v:.3f}', ha='center', va='center',
                        fontsize=FS_LEGEND - 1, color=txt_col)
        ax.set_xlabel('Query lang -- Tool lang', fontsize=FS_LABEL)
        ax.set_title(cohort_note, fontsize=FS_LEGEND - 1)
        cbar = fig.colorbar(im, ax=ax, fraction=0.04)
        cbar.set_label(r'$h$ (primary tool hit)', fontsize=FS_LABEL - 1)
        plt.tight_layout()
        plt.savefig(out_dir / 'fig_four_way_h_heatmap.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(out_dir / 'fig_four_way_h_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()

        fig, ax = plt.subplots(figsize=(5.5, 4.2))
        x = np.arange(len(rows))
        w = 0.27
        ax.bar(x - w, [r['delta_query_tool_kr'] for r in rows], w,
               label='Query EN (tool KR)', color=COL_NOTHINK, alpha=0.85)
        ax.bar(x, [r['delta_tool_query_kr'] for r in rows], w,
               label='Tool EN (query KR)', color=COL_THINK, alpha=0.85)
        # COL_BAD is the same hex as COL_THINK in _plot_style, which drew this
        # series in the previous series' colour; COL_ACCENT is the same palette.
        ax.bar(x + w, [r['delta_both'] for r in rows], w,
               label='Both EN', color=COL_ACCENT, alpha=0.85)
        ax.axhline(0, color='black', linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=FS_TICK, rotation=30, ha='right')
        ax.set_ylabel(r'$\Delta h$ vs KR--KR', fontsize=FS_LABEL)
        ax.set_title(cohort_note, fontsize=FS_LEGEND - 1)
        ax.legend(fontsize=FS_LEGEND - 1, loc='best', frameon=False)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(out_dir / 'fig_four_way_delta_decomposition.pdf', dpi=300,
                    bbox_inches='tight')
        plt.savefig(out_dir / 'fig_four_way_delta_decomposition.png', dpi=300,
                    bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ4-4way] {cohort_note}')
    print(f'  configurations: {", ".join(r["config_id"] for r in rows)}')
    print(f'  cell means h: {summary["cell_means_h"]}')
    print(f'  cell means a: {summary["cell_means_a"]} (n {summary["cell_n_a"]})')
    print(f'  mean dh query-only: {summary["mean_delta_query_only"]}')
    print(f'  mean dh tool-only : {summary["mean_delta_tool_only"]}')
    print(f'  mean dh both      : {summary["mean_delta_both"]}')
    print(f'  wrote {_rel(csv_path)} and four_way_ablation_summary.json')


if __name__ == '__main__':
    main()
