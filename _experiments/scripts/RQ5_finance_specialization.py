#!/usr/bin/env python3
"""RQ5: DragonLLM Finance vs 동급 8B 범용 모델 sub-domain별 비교.

DragonLLM 2종(Llama-Open-Finance-8B, Qwen-Open-Finance-R-8B)과
동급 크기의 범용 모델(Hermes-3-Llama-3.1-8B 등)의 5 sub-domain 평균 h 비교.

본문 인용 포인트:
- 금융 도메인 SFT가 AML FC에 우위인가, 또는 FC instruction tuning을 희생시키는가
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, FS_TICK, FS_LABEL, FS_TITLE, FS_LEGEND, style_axes)

EVAL_DIR = Path('_paper/_experiments/results_kr/eval')
OUT_DIR = Path('_paper/_experiments/results_RQ5')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# main.tex tab:tool_suite 매핑 (5 sub-domain)
SUB_DOMAINS = {
    'Transaction Stats & Inquiry': [
        'get_statistics', 'query_transactions', 'get_account_profile',
        'compare_periods', 'get_fraud_type_summary', 'get_institution_report',
    ],
    'AML Detection & Reporting': [
        'analyze_network', 'detect_aml_patterns', 'rank_risky_transactions',
        'predict_fraud', 'generate_str',
    ],
    'CTR, Risk & Monitoring': [
        'detect_ctr_candidates', 'score_account_risk', 'detect_monitoring_alerts',
    ],
    'Flow, Trend & Channel': [
        'detect_dormant_reactivation', 'detect_smurfing_network',
        'get_trend_analysis', 'analyze_channel_risk',
        'get_receiving_account_profile', 'analyze_cross_institution_flow',
    ],
    'AML Reference': [
        'lookup_fiu_reference_types', 'validate_str_fields', 'get_aml_glossary',
    ],
}

# 비교 대상 모델 (8B 클래스 + Finance specialization)
TARGET_MODELS = {
    'finance': [
        'DragonLLM/Llama-Open-Finance-8B',
        'DragonLLM/Qwen-Open-Finance-R-8B',
    ],
    'general_8b': [
        'NousResearch/Hermes-3-Llama-3.1-8B',  # Llama-3.1-8B base
    ],
    'small_general': [
        'meta-llama/Llama-3.2-3B-Instruct',
        'mistralai/Ministral-3-3B-Instruct-2512',
        'microsoft/Phi-4-mini-instruct',
    ],
    'specialized_kr': [
        'LGAI-EXAONE/EXAONE-4.0-1.2B',
        'skt/A.X-4.0-Light',
    ],
}

def per_subdomain_h(by_category):
    out = {}
    for sd, tools in SUB_DOMAINS.items():
        hs = []
        for t in tools:
            if t in by_category:
                agg = by_category[t].get('aggregated', {})
                hs.append(agg.get('primary_tool_hit_rate', 0))
        out[sd] = round(sum(hs) / len(hs), 4) if hs else None
    return out

def main():
    files = sorted(EVAL_DIR.glob('eval_*.json'))
    by_model = {}
    for f in files:
        d = json.load(f.open())
        by_model[d['model']] = per_subdomain_h(d.get('by_category', {}))

    rows = []
    flat_targets = []
    for grp, lst in TARGET_MODELS.items():
        for m in lst:
            if m in by_model:
                rows.append({'group': grp, 'model': m, **by_model[m]})
                flat_targets.append(m)

    with (OUT_DIR / 'finance_vs_general_subdomain.csv').open('w', newline='') as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader(); w.writerows(rows)

    # 그룹별 sub-domain 평균
    grp_means = {}
    for grp in TARGET_MODELS:
        models = [r for r in rows if r['group'] == grp]
        sd_avg = {}
        for sd in SUB_DOMAINS:
            vals = [r[sd] for r in models if r.get(sd) is not None]
            sd_avg[sd] = round(sum(vals) / len(vals), 4) if vals else None
        grp_means[grp] = sd_avg

    summary = {
        'sub_domains': list(SUB_DOMAINS.keys()),
        'group_definitions': {k: v for k, v in TARGET_MODELS.items()},
        'per_model_subdomain_h': by_model,
        'group_means': grp_means,
        'finance_vs_general_8b_diff': {
            sd: round((grp_means['finance'][sd] or 0) - (grp_means['general_8b'][sd] or 0), 4)
            for sd in SUB_DOMAINS
            if grp_means.get('finance', {}).get(sd) is not None
            and grp_means.get('general_8b', {}).get(sd) is not None
        },
        'note': '동급 8B 비교: DragonLLM Finance 2종 vs Hermes-3-8B (Llama-3.1-8B base 동일). '
                'positive diff = Finance가 우위, negative = 일반 8B가 우위.',
    }
    json.dump(summary, (OUT_DIR / 'finance_specialization.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        import numpy as np
        sds = list(SUB_DOMAINS.keys())
        fig, ax = plt.subplots(figsize=(8, 3.6))
        x = np.arange(len(sds))
        groups = ['finance', 'general_8b', 'small_general', 'specialized_kr']
        # main.tex 팔레트 일관 (Finance SFT=빨강, 8B 일반=파랑, 소형=회색, KR 특화=청록)
        colors = ['#E15759', '#4E79A7', '#BAB0AC', '#76B7B2']
        labels = ['Finance SFT (8B)', 'General 8B', 'Small general (1-4B)', 'KR-specialized small']
        w = 0.2
        for i, (g, c, lab) in enumerate(zip(groups, colors, labels)):
            vals = [grp_means.get(g, {}).get(sd) or 0 for sd in sds]
            ax.bar(x + (i - 1.5) * w, vals, w, label=lab, color=c, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace(' & ', '\n& ').replace(', ', ',\n') for s in sds],
                            fontsize=FS_TICK - 1)
        ax.set_ylabel(r'Mean tool hit $h$', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND, loc='lower left', ncol=2)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_finance_specialization.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_finance_specialization.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ5-finance] completed: {len(flat_targets)} target models')
    if 'finance_vs_general_8b_diff' in summary:
        print(f'  finance vs general_8b diff: {summary["finance_vs_general_8b_diff"]}')

if __name__ == '__main__':
    main()
