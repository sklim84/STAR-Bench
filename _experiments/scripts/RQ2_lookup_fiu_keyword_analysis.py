#!/usr/bin/env python3
"""RQ2: lookup_fiu_reference_types 키워드 추출 정확도 분석 (n=8 case study).

29 KR baseline 모델 × 8 lookup_fiu 케이스 = 232 호출 단위에서
도구 적중률 vs 키워드 파라미터 정확도 격차를 사례 단위로 측정.

본문 인용 포인트:
- p_mean이 도구 적중률 대비 현저히 낮은 패턴 (도구는 찾되 코드값 못 채움)
- 어느 키워드/케이스에서 격차가 큰지 case study 인용
"""
import json, csv, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_GOOD, COL_BAD, COL_PURPLE, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes, short_name)

EVAL_DIR = Path('_paper/_experiments/results_kr/eval')
OUT_DIR = Path('_paper/_experiments/results_RQ2')
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

def main():
    files = sorted(EVAL_DIR.glob('eval_*.json'))
    rows = []
    case_agg = defaultdict(lambda: {'hit': [], 'param_acc': [], 'cnt': 0})
    model_agg = defaultdict(lambda: {'hit': [], 'param_acc': []})

    for f in files:
        d = json.load(f.open())
        model = d['model']
        if model not in TARGET_MODELS:
            continue
        cat = d.get('by_category', {}).get('lookup_fiu_reference_types', {})
        for c in cat.get('per_case', []):
            cid = c.get('id')
            hit = float(c.get('primary_tool_hit') or 0)
            pa = float(c.get('param_accuracy') or 0)
            case_agg[cid]['hit'].append(hit)
            case_agg[cid]['param_acc'].append(pa)
            case_agg[cid]['cnt'] += 1
            model_agg[model]['hit'].append(hit)
            model_agg[model]['param_acc'].append(pa)
            rows.append({
                'model': model, 'case_id': cid,
                'primary_tool_hit': hit, 'param_accuracy': pa,
                'param_check_details': json.dumps(c.get('param_check_details', []),
                                                   ensure_ascii=False),
                'called_tools': json.dumps(c.get('called_tools', []), ensure_ascii=False),
                'error_type': c.get('error_type'),
                'score': c.get('score'),
            })

    with (OUT_DIR / 'lookup_fiu_per_case.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    case_summary = {}
    for cid, v in sorted(case_agg.items()):
        n = v['cnt']
        h = sum(v['hit']) / n if n else 0
        p = sum(v['param_acc']) / n if n else 0
        case_summary[cid] = {'n_models': n, 'hit_mean': round(h, 3),
                             'param_acc_mean': round(p, 3), 'gap': round(h - p, 3)}

    model_summary = {}
    for m, v in model_agg.items():
        n = len(v['hit'])
        h = sum(v['hit']) / n
        p = sum(v['param_acc']) / n
        model_summary[m] = {'n_cases': n, 'hit_mean': round(h, 3),
                            'param_acc_mean': round(p, 3), 'gap': round(h - p, 3)}

    summary = {
        'total_cases': len(case_agg), 'total_models': len(model_agg),
        'total_call_units': len(rows),
        'overall_hit_mean': round(sum(r['primary_tool_hit'] for r in rows) / len(rows), 3),
        'overall_param_acc_mean': round(sum(r['param_accuracy'] for r in rows) / len(rows), 3),
        'per_case_summary': case_summary,
        'per_model_summary': dict(sorted(model_summary.items(),
                                          key=lambda x: x[1]['gap'], reverse=True)),
        'note': 'lookup_fiu_reference_types n=8 case study. '
                'gap = hit - param_accuracy (도구 찾고도 키워드 못 채운 정도).',
    }
    json.dump(summary, (OUT_DIR / 'lookup_fiu_keyword_analysis.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        # Plot A: case-level hit vs param_acc
        cids = list(case_summary.keys())
        hits = [case_summary[c]['hit_mean'] for c in cids]
        pacs = [case_summary[c]['param_acc_mean'] for c in cids]
        x = range(len(cids))
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.bar([i - 0.2 for i in x], hits, 0.4, label=r'Tool hit $h$',
               color=COL_GOOD, alpha=0.85)
        ax.bar([i + 0.2 for i in x], pacs, 0.4, label=r'Param acc. $a$',
               color=COL_BAD, alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(cids, rotation=30, ha='right', fontsize=FS_TICK)
        ax.set_ylabel('Score', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_lookup_fiu_per_case.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_lookup_fiu_per_case.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: model gap top-15
        sorted_models = sorted(model_summary.items(), key=lambda x: -x[1]['gap'])[:15]
        fig, ax = plt.subplots(figsize=(5, 3.6))
        ax.barh([short_name(m) for m, _ in sorted_models][::-1],
                [v['gap'] for _, v in sorted_models][::-1],
                color=COL_PURPLE, alpha=0.85)
        ax.set_xlabel(r'Gap $h - a$', fontsize=FS_LABEL)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_lookup_fiu_model_gap.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_lookup_fiu_model_gap.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ2-lookup_fiu] completed: {len(rows)} units, '
          f'overall hit={summary["overall_hit_mean"]}, '
          f'param_acc={summary["overall_param_acc_mean"]}')

if __name__ == '__main__':
    main()
