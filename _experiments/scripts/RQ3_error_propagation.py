#!/usr/bin/env python3
"""RQ3: 멀티턴 초기 턴 오류 전파 분석.

각 모델의 50 시나리오에서 turn 1 결과(성공/실패)에 따른
turn 2~N의 hit 분포를 비교. 오류 전파(propagation)와 회복(recovery) 패턴 분석.

본문 인용 포인트:
- turn 1 실패 후 후속 turn 평균 hit가 얼마나 떨어지는가
- 모델별 회복 능력 차이
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_GOOD, COL_BAD, COL_PURPLE, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes, short_name)

MT_DIR = Path('_paper/_experiments/results_mt')
OUT_DIR = Path('_paper/_experiments/results_RQ3')
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    files = sorted(MT_DIR.glob('multiturn_*.json'))
    rows = []
    for f in files:
        d = json.load(f.open())
        model = d['model']
        n_total = 0; n_t1_fail = 0; n_t1_succ = 0
        subseq_hits_after_fail = []
        subseq_hits_after_succ = []
        n_recover = 0  # turn 1 fail → turn 2 hit
        n_after_fail_t2 = 0
        for sc in d.get('scenarios', []):
            turns = sc.get('turns') or []
            if not turns:
                continue
            t1 = turns[0]
            t1_hit = t1.get('tool_hit')
            if t1_hit is None:
                continue
            n_total += 1
            subseq = [t.get('tool_hit') for t in turns[1:] if t.get('tool_hit') is not None]
            if t1_hit < 1.0:
                n_t1_fail += 1
                subseq_hits_after_fail.extend(subseq)
                if len(turns) >= 2:
                    n_after_fail_t2 += 1
                    if (turns[1].get('tool_hit') or 0) >= 1.0:
                        n_recover += 1
            else:
                n_t1_succ += 1
                subseq_hits_after_succ.extend(subseq)
        rows.append({
            'model': model, 'model_id': d.get('model_id'),
            'n_scenarios_total': n_total,
            'n_t1_fail': n_t1_fail, 'n_t1_succ': n_t1_succ,
            't1_hit_rate': round(n_t1_succ / n_total, 4) if n_total else 0,
            'subseq_hit_after_t1_fail': round(sum(subseq_hits_after_fail) / len(subseq_hits_after_fail), 4) if subseq_hits_after_fail else None,
            'subseq_hit_after_t1_succ': round(sum(subseq_hits_after_succ) / len(subseq_hits_after_succ), 4) if subseq_hits_after_succ else None,
            'n_subseq_after_fail': len(subseq_hits_after_fail),
            'n_subseq_after_succ': len(subseq_hits_after_succ),
            'recovery_rate_t2': round(n_recover / n_after_fail_t2, 4) if n_after_fail_t2 else None,
            'n_t1_fail_with_t2': n_after_fail_t2,
            'gap_succ_minus_fail': None,  # 채움
        })
        if rows[-1]['subseq_hit_after_t1_succ'] is not None and rows[-1]['subseq_hit_after_t1_fail'] is not None:
            rows[-1]['gap_succ_minus_fail'] = round(
                rows[-1]['subseq_hit_after_t1_succ'] - rows[-1]['subseq_hit_after_t1_fail'], 4)

    with (OUT_DIR / 'error_propagation_per_model.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    # 전체 요약
    valid = [r for r in rows if r['gap_succ_minus_fail'] is not None]
    summary = {
        'n_models_total': len(rows),
        'n_models_with_both_outcomes': len(valid),
        'mean_gap_succ_minus_fail': round(sum(r['gap_succ_minus_fail'] for r in valid) / len(valid), 4) if valid else None,
        'mean_t1_hit_rate': round(sum(r['t1_hit_rate'] for r in rows) / len(rows), 4),
        'mean_subseq_after_fail': round(sum(r['subseq_hit_after_t1_fail'] for r in rows if r['subseq_hit_after_t1_fail'] is not None) / max(sum(1 for r in rows if r['subseq_hit_after_t1_fail'] is not None), 1), 4),
        'mean_subseq_after_succ': round(sum(r['subseq_hit_after_t1_succ'] for r in rows if r['subseq_hit_after_t1_succ'] is not None) / max(sum(1 for r in rows if r['subseq_hit_after_t1_succ'] is not None), 1), 4),
        'mean_recovery_rate': round(sum(r['recovery_rate_t2'] for r in rows if r['recovery_rate_t2'] is not None) / max(sum(1 for r in rows if r['recovery_rate_t2'] is not None), 1), 4),
        'top_5_largest_gap': sorted(valid, key=lambda x: -x['gap_succ_minus_fail'])[:5],
        'top_5_smallest_gap_robust': sorted(valid, key=lambda x: x['gap_succ_minus_fail'])[:5],
        'note': 'gap_succ_minus_fail = subseq_hit_after_t1_succ - subseq_hit_after_t1_fail. '
                'large gap = 초기 오류가 후속에 강하게 전파. '
                'small/negative gap = 회복 능력 또는 전파 적음.',
    }
    summary['top_5_largest_gap'] = [{'model': r['model'], 'gap': r['gap_succ_minus_fail'], 'n_t1_fail': r['n_t1_fail']} for r in summary['top_5_largest_gap']]
    summary['top_5_smallest_gap_robust'] = [{'model': r['model'], 'gap': r['gap_succ_minus_fail'], 'n_t1_fail': r['n_t1_fail']} for r in summary['top_5_smallest_gap_robust']]
    json.dump(summary, (OUT_DIR / 'error_propagation_summary.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        # Plot A: error propagation per model
        sorted_rows = sorted(valid, key=lambda r: r['gap_succ_minus_fail'])
        names = [short_name(r['model'], 18) for r in sorted_rows]
        x = range(len(sorted_rows))
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(x, [r['subseq_hit_after_t1_succ'] for r in sorted_rows], 'o-',
                color=COL_GOOD, label='After t1 succ',
                markersize=4, linewidth=1.2, alpha=0.85)
        ax.plot(x, [r['subseq_hit_after_t1_fail'] for r in sorted_rows], 's-',
                color=COL_BAD, label='After t1 fail',
                markersize=4, linewidth=1.2, alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=90, fontsize=7)
        ax.set_ylabel(r'Subsequent turn $h$', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND, loc='lower right')
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_error_propagation.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_error_propagation.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: recovery rate distribution
        rec = [r['recovery_rate_t2'] for r in rows if r['recovery_rate_t2'] is not None]
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.hist(rec, bins=15, color=COL_PURPLE, alpha=0.85, edgecolor='white')
        if rec:
            mean = sum(rec) / len(rec)
            ax.axvline(mean, color=COL_BAD, linestyle='--', linewidth=1.2,
                       label=f'mean={mean:.3f}')
        ax.set_xlabel(r'Turn-2 recovery rate ($h$ | t1 fail)', fontsize=FS_LABEL)
        ax.set_ylabel('Models', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_recovery_distribution.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_recovery_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ3-prop] completed: {len(valid)} models, mean gap={summary["mean_gap_succ_minus_fail"]}')

if __name__ == '__main__':
    main()
