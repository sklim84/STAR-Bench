#!/usr/bin/env python3
"""RQ3: context_accuracy 모델별 분포 + 시나리오 완주율 상관 (n=22 한정).

50 멀티턴 시나리오 중 context_ref가 정의된 시나리오에서만 context_hit 측정.
모델별 context_accuracy 평균과 scenario_complete_rate 사이의 상관 분석.

본문 인용 포인트:
- 컨텍스트 참조 일관성이 시나리오 완주율의 독립 예측 변수인가?
- 표본 크기 명시: n_models × n_ctx_scenarios
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, get_color, COL_NEUTRAL, COL_ACCENT, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, FS_ANNOT, style_axes, short_name)

MT_DIR = Path('_paper/_experiments/results_mt')
OUT_DIR = Path('_paper/_experiments/results_RQ3')
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    files = sorted(MT_DIR.glob('multiturn_*.json'))
    rows = []
    for f in files:
        d = json.load(f.open())
        overall = d.get('overall', {})
        # 시나리오 단위로 context_accuracy 모음
        ctx_scs = []
        for sc in d.get('scenarios', []):
            ca = sc.get('context_accuracy')
            if ca is not None:
                ctx_scs.append(ca)
        ctx_mean = sum(ctx_scs) / len(ctx_scs) if ctx_scs else None
        rows.append({
            'model': d['model'], 'model_id': d.get('model_id'),
            'think': d.get('think'),
            'ctx_acc_mean': round(ctx_mean, 4) if ctx_mean is not None else None,
            'n_ctx_scenarios': len(ctx_scs),
            'scenario_complete_rate': overall.get('scenario_complete_rate'),
            'avg_score': overall.get('avg_score'),
            'avg_tool_hit': overall.get('avg_tool_hit'),
            'avg_param_accuracy': overall.get('avg_param_accuracy'),
        })

    with (OUT_DIR / 'context_accuracy_per_model.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    # 상관 분석 (ctx_acc가 None 아닌 모델만)
    valid = [r for r in rows if r['ctx_acc_mean'] is not None]
    try:
        from scipy.stats import spearmanr, pearsonr
        x = [r['ctx_acc_mean'] for r in valid]
        y = [r['scenario_complete_rate'] for r in valid]
        s_rho, s_p = spearmanr(x, y)
        p_r, p_p = pearsonr(x, y)
        # tool_hit과의 상관도 (싱글턴 성능 proxy)
        z = [r['avg_tool_hit'] for r in valid]
        s_rho2, s_p2 = spearmanr(x, z)
        # 부분 상관 (ctx_acc → complete | tool_hit 통제)
        # 간이: ctx_acc와 tool_hit의 잔차로부터 complete 상관
        try:
            import numpy as np
            x_a = np.array(x); y_a = np.array(y); z_a = np.array(z)
            # ctx_acc residual after tool_hit
            zx = np.polyfit(z_a, x_a, 1); resid_x = x_a - np.polyval(zx, z_a)
            zy = np.polyfit(z_a, y_a, 1); resid_y = y_a - np.polyval(zy, z_a)
            partial_rho, partial_p = spearmanr(resid_x, resid_y)
        except Exception:
            partial_rho, partial_p = None, None
    except Exception as e:
        s_rho = s_p = p_r = p_p = s_rho2 = s_p2 = partial_rho = partial_p = None
        print(f'scipy failed: {e}')

    summary = {
        'n_models_total': len(rows),
        'n_models_with_ctx': len(valid),
        'avg_n_ctx_scenarios_per_model': round(sum(r['n_ctx_scenarios'] for r in valid) / max(len(valid), 1), 1),
        'spearman_ctx_vs_complete': {'rho': round(s_rho, 4) if s_rho is not None else None, 'p': round(s_p, 4) if s_p is not None else None},
        'pearson_ctx_vs_complete': {'r': round(p_r, 4) if p_r is not None else None, 'p': round(p_p, 4) if p_p is not None else None},
        'spearman_ctx_vs_tool_hit': {'rho': round(s_rho2, 4) if s_rho2 is not None else None, 'p': round(s_p2, 4) if s_p2 is not None else None},
        'partial_spearman_ctx_complete_given_tool_hit': {'rho': round(partial_rho, 4) if partial_rho is not None else None, 'p': round(partial_p, 4) if partial_p is not None else None},
        'top_5_ctx_acc': sorted(valid, key=lambda x: x['ctx_acc_mean'] or 0, reverse=True)[:5],
        'bottom_5_ctx_acc': sorted(valid, key=lambda x: x['ctx_acc_mean'] or 0)[:5],
    }
    summary['top_5_ctx_acc'] = [{'model': r['model'], 'ctx_acc_mean': r['ctx_acc_mean'], 'complete': r['scenario_complete_rate']} for r in summary['top_5_ctx_acc']]
    summary['bottom_5_ctx_acc'] = [{'model': r['model'], 'ctx_acc_mean': r['ctx_acc_mean'], 'complete': r['scenario_complete_rate']} for r in summary['bottom_5_ctx_acc']]
    json.dump(summary, (OUT_DIR / 'context_accuracy_correlation.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        # Plot A: context vs completion
        fig, ax = plt.subplots(figsize=(5, 3.6))
        for r in valid:
            c = get_color(r['model'])
            ax.scatter(r['ctx_acc_mean'], r['scenario_complete_rate'],
                       s=50, alpha=0.85, c=c,
                       edgecolors='white', linewidths=0.5, zorder=3)
            ax.annotate(short_name(r['model'], 14),
                        (r['ctx_acc_mean'], r['scenario_complete_rate']),
                        fontsize=FS_ANNOT - 2, alpha=0.7,
                        xytext=(3, 3), textcoords='offset points')
        ax.set_xlabel(r'context\_accuracy (mean)', fontsize=FS_LABEL)
        ax.set_ylabel(r'scenario\_complete\_rate $c$', fontsize=FS_LABEL)
        style_axes(ax)
        if s_rho is not None:
            ax.text(0.05, 0.95, fr'Spearman $\rho$={s_rho:.3f} (p={s_p:.3f})',
                    transform=ax.transAxes, va='top', fontsize=FS_LEGEND,
                    bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_context_vs_completion.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_context_vs_completion.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: singleturn vs context
        fig, ax = plt.subplots(figsize=(5, 3.6))
        for r in valid:
            c = get_color(r['model'])
            ax.scatter(r['avg_tool_hit'], r['ctx_acc_mean'],
                       s=50, alpha=0.85, c=c,
                       edgecolors='white', linewidths=0.5, zorder=3)
        ax.set_xlabel(r'avg\_tool\_hit (singleturn $h$ proxy)', fontsize=FS_LABEL)
        ax.set_ylabel(r'context\_accuracy', fontsize=FS_LABEL)
        style_axes(ax)
        if s_rho2 is not None:
            ax.text(0.05, 0.95, fr'Spearman $\rho$={s_rho2:.3f} (p={s_p2:.3f})',
                    transform=ax.transAxes, va='top', fontsize=FS_LEGEND,
                    bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_singleturn_vs_context.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_singleturn_vs_context.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ3-ctx] completed: {len(valid)}/{len(rows)} models with ctx_acc, '
          f'spearman={summary["spearman_ctx_vs_complete"]}')

if __name__ == '__main__':
    main()
