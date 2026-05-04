#!/usr/bin/env python3
"""RQ1: validate_str_fields 실패 모드 분석.

29 KR baseline 모델 × 3 validate_str_fields 케이스 = 87 호출 단위에서
(i) 도구 미호출 / (ii) 정답 호출 / (iii) 다른 도구 mis-call 분류.

본문 인용 포인트:
- validate_str_fields의 h=0.195 저변에서 "도구 미호출"이 주된 실패 모드
- mis-call시 어느 도구로 가는지 (예: generate_str 등 인접 도구)
"""
import json, csv, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_BAD, COL_GOOD, COL_ACCENT, COL_PURPLE,
                          FS_TICK, FS_LABEL, FS_TITLE, FS_LEGEND, FS_ANNOT, style_axes)

EVAL_DIR = Path('_paper/_experiments/results_kr/eval')
OUT_DIR = Path('_paper/_experiments/results_RQ1')
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_MODELS = {
    "skt/A.X-4.0-Light", "skt/A.X-4.0",
    "LGAI-EXAONE/EXAONE-4.0-1.2B", "LGAI-EXAONE/EXAONE-4.0-32B",
    "kakaocorp/kanana-2-30b-a3b-instruct",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink",
    "kakaocorp/kanana-2-30b-a3b-thinking-2601__think",
    "DragonLLM/Llama-Open-Finance-8B", "DragonLLM/Qwen-Open-Finance-R-8B",
    "openai/gpt-oss-20b__nothink", "openai/gpt-oss-20b__think",
    "openai/gpt-oss-120b__nothink", "openai/gpt-oss-120b__think",
    "meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.3-70B-Instruct",
    "mistralai/Ministral-3-3B-Instruct-2512",
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
    "microsoft/Phi-4-mini-instruct",
    "Qwen/Qwen3.5-4B__nothink", "Qwen/Qwen3.5-4B__think",
    "Qwen/Qwen3.5-27B__nothink", "Qwen/Qwen3.5-27B__think",
    "Qwen/Qwen3.6-27B", "Qwen/Qwen3.6-35B-A3B",
    "Salesforce/xLAM-2-3b-fc-r", "Salesforce/Llama-xLAM-2-70b-fc-r",
    "google/gemma-4-E4B-it", "google/gemma-4-31B-it",
    "NousResearch/Hermes-3-Llama-3.1-8B",
}


_SAFE_TO_CANONICAL = {m.replace('/', '_').replace('.', '_'): m for m in TARGET_MODELS}
def _canonicalize(m): return _SAFE_TO_CANONICAL.get(m, m)
def extract_tool_names(called_tools):
    names = []
    for t in called_tools or []:
        if isinstance(t, dict):
            names.append(t.get('name', ''))
        else:
            names.append(str(t))
    return [n for n in names if n]

def classify_mode(tool_names):
    if not tool_names:
        return 'no_call'
    has_correct = 'validate_str_fields' in tool_names
    if has_correct and len(tool_names) == 1:
        return 'correct_only'
    if has_correct:
        return 'correct_with_extra'
    return 'miscall_only'

def main():
    files = sorted(EVAL_DIR.glob('eval_*.json'))
    rows = []
    mode_count = defaultdict(int)
    miscall_dist = defaultdict(int)
    per_model = defaultdict(lambda: defaultdict(int))

    for f in files:
        d = json.load(f.open())
        model = d['model']
        if _canonicalize(model) not in TARGET_MODELS:
            continue
        cat = d.get('by_category', {}).get('validate_str_fields', {})
        for c in cat.get('per_case', []):
            names = extract_tool_names(c.get('called_tools'))
            mode = classify_mode(names)
            mode_count[mode] += 1
            per_model[model][mode] += 1
            per_model[model]['total'] += 1
            if mode in ('miscall_only', 'correct_with_extra'):
                for n in names:
                    if n != 'validate_str_fields':
                        miscall_dist[n] += 1
            rows.append({
                'model': model, 'case_id': c.get('id'), 'mode': mode,
                'called_tools': '|'.join(names),
                'primary_tool_hit': c.get('primary_tool_hit'),
                'score': c.get('score'), 'error_type': c.get('error_type'),
            })

    with (OUT_DIR / 'validate_str_failure_modes.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    summary = {
        'total_call_units': sum(mode_count.values()),
        'mode_distribution': dict(mode_count),
        'mode_distribution_pct': {k: round(100 * v / sum(mode_count.values()), 1)
                                   for k, v in mode_count.items()},
        'miscalled_tools_distribution': dict(sorted(miscall_dist.items(), key=lambda x: -x[1])),
        'per_model_breakdown': {k: dict(v) for k, v in per_model.items()},
        'note': 'validate_str_fields = 3 cases × 29 models = 87 call units. '
                'no_call: 모델이 어떤 도구도 호출하지 않음. '
                'correct_only: validate_str_fields만 호출. '
                'correct_with_extra: validate_str_fields + 추가 도구. '
                'miscall_only: validate_str_fields 미호출, 다른 도구 호출.',
    }
    json.dump(summary, (OUT_DIR / 'validate_str_failure_modes.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        # Plot A: 실패 모드 분포
        modes = ['no_call', 'correct_only', 'correct_with_extra', 'miscall_only']
        labels = ['No call', 'Correct only', 'Correct+extra', 'Miscall only']
        counts = [mode_count.get(m, 0) for m in modes]
        colors = [COL_BAD, COL_GOOD, COL_ACCENT, COL_PURPLE]
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        ax.bar(range(len(labels)), counts, color=colors, alpha=0.85, width=0.65)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=FS_TICK, rotation=20, ha='right')
        ax.set_ylabel('Call units', fontsize=FS_LABEL)
        for i, c in enumerate(counts):
            ax.text(i, c + 1, str(c), ha='center', fontsize=FS_ANNOT)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_validate_str_modes.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_validate_str_modes.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: mis-called tools
        if miscall_dist:
            sorted_mis = sorted(miscall_dist.items(), key=lambda x: -x[1])[:8]
            fig, ax = plt.subplots(figsize=(4.5, 3.2))
            ax.barh([t for t, _ in sorted_mis][::-1],
                    [c for _, c in sorted_mis][::-1],
                    color=COL_PURPLE, alpha=0.85)
            ax.set_xlabel('Count', fontsize=FS_LABEL)
            style_axes(ax)
            plt.tight_layout()
            plt.savefig(OUT_DIR / 'fig_validate_str_miscalled.pdf', dpi=300, bbox_inches='tight')
            plt.savefig(OUT_DIR / 'fig_validate_str_miscalled.png', dpi=300, bbox_inches='tight')
            plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ1] completed: {len(rows)} call units')
    print(f'  modes: {dict(mode_count)}')
    print(f'  miscall: {dict(sorted(miscall_dist.items(), key=lambda x: -x[1])[:5])}')

if __name__ == '__main__':
    main()
