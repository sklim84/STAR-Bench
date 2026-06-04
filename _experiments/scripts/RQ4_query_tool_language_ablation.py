#!/usr/bin/env python3
"""RQ4 (a) 4-way 쿼리 언어 × 도구 정의 언어 ablation.

4 셀: KR-KR (results_kr) / EN-KR (results_en) / KR-EN (results_kr_tools_en) / EN-EN (results_en_tools_en).

Full 4-way 커버 모델:
  EXAONE-32B, Qwen3.5-27B (NT/T), Qwen3.6-27B, Gemma-4-31B, Llama-3.3-70B (6 모델)
A.X-4.0은 KR-EN 미실시 (3-way: KR-KR/EN-KR/EN-EN).

산출:
  - results_RQ4/four_way_ablation.csv (per-model x cell h, h_param)
  - results_RQ4/four_way_ablation_summary.json
  - results_RQ4/fig_four_way_h_heatmap.{pdf,png}
  - results_RQ4/fig_four_way_delta_decomposition.{pdf,png}
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_NOTHINK, COL_THINK, COL_BAD, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes)

CELLS = {
    'KR-KR': Path('_experiments/results_kr/eval'),
    'EN-KR': Path('_experiments/results_en/eval'),
    'KR-EN': Path('_experiments/results_kr_tools_en/eval'),
    'EN-EN': Path('_experiments/results_en_tools_en/eval'),
}
OUT_DIR = Path('_experiments/results_RQ4')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ('LGAI-EXAONE/EXAONE-4.0-32B', 'EXAONE-32B'),
    ('Qwen/Qwen3.5-27B__nothink', 'Qwen3.5-27B (NT)'),
    ('Qwen/Qwen3.5-27B__think', 'Qwen3.5-27B (T)'),
    ('Qwen/Qwen3.6-27B', 'Qwen3.6-27B'),
    ('google/gemma-4-31B-it', 'Gemma-4-31B'),
    ('meta-llama/Llama-3.3-70B-Instruct', 'Llama-3.3-70B'),
    ('skt/A.X-4.0', 'A.X-4.0'),
]
# Gemma-4-31B-it는 2026-05-02 parser hermes→gemma4 fix로 정상화 (h=0.940) → outlier 해제
OUTLIERS = set()

# 파일 저장 시 sanitize (`/`→`_`, `.`→`_`)된 model 필드를 canonical(슬래시)로 역매핑.
# 동일 모델이 슬래시·언더스코어 두 키로 중복 등록되어 latest 선택이 빗나가는 것 방지.
_SAFE_TO_CANONICAL = {
    mid.replace('/', '_').replace('.', '_'): mid for mid, _ in TARGETS
}


def _canonicalize(m: str) -> str:
    return _SAFE_TO_CANONICAL.get(m, m)


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


def main():
    cells = {name: load_cell(p) for name, p in CELLS.items()}
    for name, c in cells.items():
        print(f'  {name}: {len(c)} models loaded')

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
        'note': ('h = primary_tool_hit_rate. Delta=cell-KR-KR. '
                 'Gemma-4-31B는 KR-tool 셀 평가 이상치(h≈0.126)로 평균 제외. '
                 'A.X-4.0 KR-EN 미실시.')
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
