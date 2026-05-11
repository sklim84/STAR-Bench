#!/usr/bin/env python3
"""RQ4 cont. (Effect of Thinking Mode): 새 5쌍 thinking pair 데이터로 figure 재생성.

5 thinking pair: Qwen3.5-4B, Qwen3.5-27B, gpt-oss-20b, gpt-oss-120b, kanana-2-30b-a3b-thinking-2601.

본문 인용 포인트:
- single Δh, multi Δh_bar per pair
- thinking 모드의 비단조 효과 (계열별 상이)
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_NOTHINK, COL_THINK, COL_BAD, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes, short_name)

EVAL_DIR = Path('_paper/_experiments/results_kr/eval')
MT_DIR = Path('_paper/_experiments/results_mt/eval')
OUT_DIR = Path('_paper/_experiments/results_RQ4')
OUT_DIR.mkdir(parents=True, exist_ok=True)

THINKING_PAIRS = [
    # 동일 모델 enable_thinking 토글 4쌍.
    # Kanana-2-Think (thinking-2601)는 always-thinking 특성으로 토글 미지원이라 제외.
    # Kanana sibling-variant pair (Inst-2601 ↔ Think-2601) 비교는 본문에서 별도 보고.
    ('Qwen/Qwen3.5-4B', 'Qwen3.5-4B'),
    ('Qwen/Qwen3.5-27B', 'Qwen3.5-27B'),
    ('openai/gpt-oss-20b', 'gpt-oss-20B'),
    ('openai/gpt-oss-120b', 'gpt-oss-120B'),
]

OUTLIERS = set()

def load_kr():
    out = {}
    for f in sorted(EVAL_DIR.glob('eval_*.json')):
        d = json.load(f.open())
        out[d['model']] = d.get('overall', {})
    return out

def load_mt():
    out = {}
    for f in MT_DIR.glob('multiturn_*.json'):
        d = json.load(f.open())
        out[d.get('model_id') or d['model']] = d.get('overall', {})
    return out

def main():
    kr = load_kr()
    mt = load_mt()

    rows = []
    for base, display in THINKING_PAIRS:
        nt_id = f'{base}__nothink'
        t_id = f'{base}__think'
        nt = kr.get(nt_id, {})
        t = kr.get(t_id, {})
        nt_mt = mt.get(nt_id, {})
        t_mt = mt.get(t_id, {})
        h_nt = nt.get('primary_tool_hit_rate')
        h_t = t.get('primary_tool_hit_rate')
        hb_nt = nt_mt.get('avg_tool_hit')
        hb_t = t_mt.get('avg_tool_hit')
        rows.append({
            'model': display, 'base_id': base,
            'h_nothink': h_nt, 'h_think': h_t,
            'delta_h_single': (h_t - h_nt) if (h_nt is not None and h_t is not None) else None,
            'h_bar_nothink': hb_nt, 'h_bar_think': hb_t,
            'delta_h_multi': (hb_t - hb_nt) if (hb_nt is not None and hb_t is not None) else None,
            'is_outlier': base in OUTLIERS,
        })

    with (OUT_DIR / 'thinking_effect_per_pair.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    summary = {
        'n_thinking_pairs': len(rows),
        'pairs': rows,
        'mean_delta_single': round(sum(r['delta_h_single'] for r in rows if r['delta_h_single'] is not None and not r['is_outlier']) / max(sum(1 for r in rows if r['delta_h_single'] is not None and not r['is_outlier']), 1), 4),
        'mean_delta_multi': round(sum(r['delta_h_multi'] for r in rows if r['delta_h_multi'] is not None and not r['is_outlier']) / max(sum(1 for r in rows if r['delta_h_multi'] is not None and not r['is_outlier']), 1), 4),
        'note': 'Δh = h(T) - h(NT). Kanana-Think는 평가 이상치(h≈0.126)로 평균에서 제외.',
    }
    json.dump(summary, (OUT_DIR / 'thinking_effect_summary.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        import numpy as np
        # Plot A: per-pair Δh single
        fig, ax = plt.subplots(figsize=(5, 3.2))
        labels = [r['model'] for r in rows]
        deltas_s = [r['delta_h_single'] if r['delta_h_single'] is not None else 0 for r in rows]
        colors = [COL_BAD if r['is_outlier'] else (COL_THINK if d > 0 else COL_NOTHINK) for r, d in zip(rows, deltas_s)]
        bars = ax.bar(range(len(labels)), deltas_s, color=colors, alpha=0.85, width=0.65)
        ax.axhline(0, color='black', linewidth=0.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=FS_TICK, rotation=20, ha='right')
        ax.set_ylabel(r'$\Delta h$ (think $-$ nothink, single)', fontsize=FS_LABEL)
        for i, (d, r) in enumerate(zip(deltas_s, rows)):
            tag = '*' if r['is_outlier'] else ''
            ax.text(i, d + (0.002 if d >= 0 else -0.005), f'{d:+.3f}{tag}',
                    ha='center', fontsize=FS_LEGEND - 1)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_thinking_delta_single.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_thinking_delta_single.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: per-pair Δh_bar multi
        fig, ax = plt.subplots(figsize=(5, 3.2))
        deltas_m = [r['delta_h_multi'] if r['delta_h_multi'] is not None else 0 for r in rows]
        colors = [COL_BAD if r['is_outlier'] else (COL_THINK if d > 0 else COL_NOTHINK) for r, d in zip(rows, deltas_m)]
        ax.bar(range(len(labels)), deltas_m, color=colors, alpha=0.85, width=0.65)
        ax.axhline(0, color='black', linewidth=0.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=FS_TICK, rotation=20, ha='right')
        ax.set_ylabel(r'$\Delta \bar{h}$ (think $-$ nothink, multi)', fontsize=FS_LABEL)
        for i, (d, r) in enumerate(zip(deltas_m, rows)):
            tag = '*' if r['is_outlier'] else ''
            ax.text(i, d + (0.002 if d >= 0 else -0.005), f'{d:+.3f}{tag}',
                    ha='center', fontsize=FS_LEGEND - 1)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_thinking_delta_multi.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_thinking_delta_multi.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ4-thinking] completed: {len(rows)} pairs')
    print(f'  mean Δh (single, ex. outlier): {summary["mean_delta_single"]}')
    print(f'  mean Δh̄ (multi, ex. outlier): {summary["mean_delta_multi"]}')

if __name__ == '__main__':
    main()
