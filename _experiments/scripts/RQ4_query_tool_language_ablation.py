#!/usr/bin/env python3
"""RQ4 (a) 4-way 쿼리 언어 x 도구 정의 언어 ablation.

2x2 의 두 축은 질의 언어(KR/EN)와 **도구 정의 언어**(KR/EN)다. 2026-09 이전 판은
`results_kr` / `results_en` 을 KR 도구 칸으로 읽었는데, 그 실행들은 사실 영어
플랫폼 스키마로 돌린 것이었다(둘째 축이 영어 두 벌). 그래서 표는
`results_or_kr_tools_kr` 에서 가져오고 스크립트는 `results_kr` 을 읽는 불일치가
있었다(R2C-005). 기본 셀은 이렇게 정리한다:

  KR-KR  results_or_kr_tools_kr/eval   한국어 질의 x 한국어 도구 (tools_kr.py)
  EN-KR  results_or_en_tools_kr/eval   영어 질의   x 한국어 도구
  KR-EN  results_kr/eval               한국어 질의 x 영어 도구 (플랫폼 agent.TOOLS)
  EN-EN  results_en/eval               영어 질의   x 영어 도구

은퇴한 `results_kr_tools_en` / `results_en_tools_en` 는 더 이상 읽지 않는다.
`tools_en.py` 로 돌린 두 번째 영어 사본이라 KR-EN / EN-EN 과 같은 팔이다(D16).

재실행 뒤에는 네 칸을 인자로 지정한다:

    python -m _experiments.scripts.RQ4_query_tool_language_ablation \
        --kr-kr <dir>/single_krq_krt --en-kr <dir>/single_enq_krt \
        --kr-en <dir>/single_krq_ent --en-en <dir>/single_enq_ent \
        --out _experiments/results_RQ4

산출:
  - <out>/four_way_ablation.csv (per-model x cell h, h_param)
  - <out>/four_way_ablation_summary.json
  - <out>/fig_four_way_h_heatmap.{pdf,png}
  - <out>/fig_four_way_delta_decomposition.{pdf,png}
"""
import argparse, json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_NOTHINK, COL_THINK, COL_BAD, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes)

_SB = Path(__file__).resolve().parents[2]

# (cell, default results directory). The eval files are read from <dir>/eval when
# that subdirectory exists, so both the old layout and a rerun output directory
# can be named.
DEFAULT_CELLS = {
    'KR-KR': '_experiments/results_or_kr_tools_kr',
    'EN-KR': '_experiments/results_or_en_tools_kr',
    'KR-EN': '_experiments/results_kr',
    'EN-EN': '_experiments/results_en',
}
RETIRED = ('results_kr_tools_en', 'results_en_tools_en')

CELLS: dict = {}
OUT_DIR = _SB / '_experiments' / 'results_RQ4'


def _eval_dir(path: Path) -> Path:
    return path / 'eval' if (path / 'eval').is_dir() else path


def configure(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    for cell in DEFAULT_CELLS:
        ap.add_argument(f'--{cell.lower()}', dest=cell.replace('-', '_'),
                        help=f'results directory for the {cell} cell '
                             f'(default {DEFAULT_CELLS[cell]})')
    ap.add_argument('--results-root', help='parent directory holding the four cells')
    ap.add_argument('--out', help=f'output directory (default _experiments/results_RQ4)')
    args = ap.parse_args(argv)

    global CELLS, OUT_DIR
    for cell, default in DEFAULT_CELLS.items():
        given = getattr(args, cell.replace('-', '_'))
        if given:
            path = Path(given)
        elif args.results_root:
            path = Path(args.results_root) / Path(default).name
        else:
            path = _SB / default
        if not path.is_absolute():
            path = _SB / path
        if any(name in str(path) for name in RETIRED):
            raise SystemExit(f'{cell}: {path} is a retired tools_en arm; it is the same arm as '
                             f'the platform English schema (D16). Name the rerun directory.')
        CELLS[cell] = _eval_dir(path)
    OUT_DIR = Path(args.out) if args.out else (_SB / '_experiments' / 'results_RQ4')
    if not OUT_DIR.is_absolute():
        OUT_DIR = _SB / OUT_DIR
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return args


TARGETS = [
    ('google/gemma-4-31B-it', 'Gemma-4-31B'),
    ('meta-llama/Llama-3.3-70B-Instruct', 'Llama-3.3-70B'),
    ('openai/gpt-oss-20b__nothink', 'gpt-oss-20B (NT)'),
    ('openai/gpt-oss-20b__think', 'gpt-oss-20B (T)'),
    ('openai/gpt-oss-120b__nothink', 'gpt-oss-120B (NT)'),
    ('openai/gpt-oss-120b__think', 'gpt-oss-120B (T)'),
    ('Qwen/Qwen3.5-27B__nothink', 'Qwen3.5-27B (NT)'),
    ('Qwen/Qwen3.5-27B__think', 'Qwen3.5-27B (T)'),
    ('Qwen/Qwen3.6-27B', 'Qwen3.6-27B'),
    ('Qwen/Qwen3.6-35B-A3B', 'Qwen3.6-35B-A3B'),
    ('LGAI-EXAONE/EXAONE-4.0-32B', 'EXAONE-32B'),
    ('skt/A.X-4.0', 'A.X-4.0'),
]
OUTLIERS = set()

# The cells come from different runners: the KR-tool arms were run through the
# OpenRouter gateway, which lower-cases model slugs, and the EN-tool arms
# locally. Model ids are matched on a normalised key so the same model is one
# row rather than two half-empty ones.


def _key(model_id: str) -> str:
    return model_id.lower().replace('/', '_').replace('.', '_').replace('-', '_')


_BY_KEY = {_key(mid): mid for mid, _ in TARGETS}


def _canonicalize(m: str) -> str:
    return _BY_KEY.get(_key(m), m)


def load_cell(cell_dir):
    """Load latest eval per model (model_id -> overall dict)."""
    if not cell_dir.exists():
        return {}
    by_model = {}
    for f in sorted(cell_dir.glob('eval_*.json')):
        d = json.load(f.open())
        m = d.get('model')
        if not m:
            continue
        m = _canonicalize(m)
        # keep latest by timestamp in filename
        if m not in by_model or f.name > by_model[m]['_file']:
            o = d.get('overall', {})
            by_model[m] = {
                'h': o.get('primary_tool_hit_rate'),
                'p_acc': o.get('avg_param_accuracy'),
                'recall': o.get('avg_tool_recall'),
                '_file': f.name,
            }
    return by_model


def main(argv=None):
    configure(argv)
    cells = {name: load_cell(path) for name, path in CELLS.items()}
    for name, path in CELLS.items():
        print(f'  {name}: {len(cells[name])} models loaded from {path}')
    missing = [n for n, c in cells.items() if not c]
    if missing:
        print(f'  WARNING: no eval files for {", ".join(missing)}; '
              f'those cells stay empty in the table')

    rows = []
    for mid, display in TARGETS:
        row = {'model': display, 'model_id': mid, 'is_outlier': mid in OUTLIERS}
        for cell in CELLS:
            cd = cells[cell].get(mid, {})
            row[f'h_{cell}'] = cd.get('h')
            row[f'p_{cell}'] = cd.get('p_acc')
        # deltas
        h_kk, h_ek = row['h_KR-KR'], row['h_EN-KR']
        h_ke, h_ee = row['h_KR-EN'], row['h_EN-EN']
        row['delta_query_tool_kr'] = (h_ek - h_kk) if (h_kk is not None and h_ek is not None) else None
        row['delta_tool_query_kr'] = (h_ke - h_kk) if (h_kk is not None and h_ke is not None) else None
        row['delta_both'] = (h_ee - h_kk) if (h_kk is not None and h_ee is not None) else None
        rows.append(row)

    csv_path = OUT_DIR / 'four_way_ablation.csv'
    with csv_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    full4 = [r for r in rows if all(r[f'h_{c}'] is not None for c in CELLS)]
    full4_clean = [r for r in full4 if not r['is_outlier']]

    def mean_or_none(vals):
        v = [x for x in vals if x is not None]
        return round(sum(v) / len(v), 4) if v else None

    summary = {
        'cells': {name: str(path) for name, path in CELLS.items()},
        'n_targets': len(rows),
        'n_full_4way': len(full4),
        'n_full_4way_ex_outlier': len(full4_clean),
        'cell_means_ex_outlier': {
            cell: mean_or_none([r[f'h_{cell}'] for r in full4_clean])
            for cell in CELLS
        },
        'mean_delta_query_only_ex_outlier': mean_or_none([r['delta_query_tool_kr'] for r in full4_clean]),
        'mean_delta_tool_only_ex_outlier': mean_or_none([r['delta_tool_query_kr'] for r in full4_clean]),
        'mean_delta_both_ex_outlier': mean_or_none([r['delta_both'] for r in full4_clean]),
        'rows': rows,
        'note': ('h = primary_tool_hit_rate. Delta = cell - KR-KR. '
                 'KR 도구 칸은 tools_kr.py 로 돌린 실행(results_or_*_tools_kr), '
                 'EN 도구 칸은 플랫폼 agent.TOOLS 로 돌린 실행이다. '
                 '네 칸이 모두 있는 모델만 평균에 들어간다.')
    }
    with (OUT_DIR / 'four_way_ablation_summary.json').open('w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    try:
        import numpy as np
        # Heatmap (rows=models, cols=cells)
        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        cells_order = ['KR-KR', 'EN-KR', 'KR-EN', 'EN-EN']
        labels = [r['model'] for r in rows]
        mat = np.array([[r[f'h_{c}'] if r[f'h_{c}'] is not None else np.nan
                         for c in cells_order] for r in rows])
        im = ax.imshow(mat, cmap='viridis', aspect='auto', vmin=0.3, vmax=0.85)
        ax.set_xticks(range(len(cells_order)))
        ax.set_xticklabels(cells_order, fontsize=FS_TICK)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=FS_TICK)
        for i in range(len(labels)):
            for j in range(len(cells_order)):
                v = mat[i, j]
                if not np.isnan(v):
                    txt_col = 'white' if v < 0.55 else 'black'
                    ax.text(j, i, f'{v:.3f}', ha='center', va='center',
                            fontsize=FS_LEGEND - 1, color=txt_col)
                else:
                    ax.text(j, i, '--', ha='center', va='center',
                            fontsize=FS_LEGEND, color='grey')
        ax.set_xlabel('Query lang -- Tool lang', fontsize=FS_LABEL)
        cbar = fig.colorbar(im, ax=ax, fraction=0.04)
        cbar.set_label(r'$h$ (primary tool hit)', fontsize=FS_LABEL - 1)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_four_way_h_heatmap.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_four_way_h_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Delta decomposition (full4 only, exclude outlier from bars)
        if full4_clean:
            fig, ax = plt.subplots(figsize=(5.5, 4.2))
            x = np.arange(len(full4_clean))
            w = 0.27
            d_q = [r['delta_query_tool_kr'] for r in full4_clean]
            d_t = [r['delta_tool_query_kr'] for r in full4_clean]
            d_b = [r['delta_both'] for r in full4_clean]
            ax.bar(x - w, d_q, w, label='Query EN (tool KR)', color=COL_NOTHINK, alpha=0.85)
            ax.bar(x,     d_t, w, label='Tool EN (query KR)', color=COL_THINK, alpha=0.85)
            ax.bar(x + w, d_b, w, label='Both EN', color=COL_BAD, alpha=0.85)
            ax.axhline(0, color='black', linewidth=0.5)
            ax.set_xticks(x)
            ax.set_xticklabels([r['model'] for r in full4_clean], fontsize=FS_TICK,
                               rotation=30, ha='right')
            ax.set_ylabel(r'$\Delta h$ vs KR--KR', fontsize=FS_LABEL)
            ax.legend(fontsize=FS_LEGEND - 1, loc='best', frameon=False)
            style_axes(ax)
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'fig_four_way_delta_decomposition.pdf', dpi=300, bbox_inches='tight')
            plt.savefig(OUT_DIR / 'fig_four_way_delta_decomposition.png', dpi=300, bbox_inches='tight')
            plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ4-4way] {len(rows)} targets, {len(full4)} full 4-way, {len(full4_clean)} ex-outlier')
    print(f'  cell means (ex-outlier): {summary["cell_means_ex_outlier"]}')
    print(f'  mean Δh query-only (ex-outlier):  {summary["mean_delta_query_only_ex_outlier"]}')
    print(f'  mean Δh tool-only  (ex-outlier):  {summary["mean_delta_tool_only_ex_outlier"]}')
    print(f'  mean Δh both       (ex-outlier):  {summary["mean_delta_both_ex_outlier"]}')


if __name__ == '__main__':
    main()
