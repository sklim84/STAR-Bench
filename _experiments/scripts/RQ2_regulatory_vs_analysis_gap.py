#!/usr/bin/env python3
"""RQ2: 규제 출력 카테고리 vs 일반 분석 카테고리 평균 h 격차.

규제 출력 그룹 (4): validate_str_fields, lookup_fiu_reference_types, detect_ctr_candidates,
                     get_aml_glossary
일반 분석 그룹: 그 외 모든 도구별 카테고리 (multi_tool/missing_parameters 제외)

코호트는 본문과 같은 28-모델 세트다 (다른 분석 스크립트와 동일한 EXCLUDE_MODELS).

본문 인용 포인트:
- 두 그룹 평균 h 격차의 정량적 크기
- 도메인 특화 평가의 필요성 정량 근거
"""
import json, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_GOOD, COL_BAD, COL_PURPLE, FS_TICK, FS_LABEL,
                          FS_TITLE, FS_LEGEND, style_axes, short_name)

_SB = Path(__file__).resolve().parents[2]   # star-bench root (fix stale _paper/ path)
EVAL_DIR = _SB / '_experiments' / 'results_kr' / 'eval'
OUT_DIR = _SB / '_experiments' / 'results_RQ2'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Regulatory Reporting subdomain (single-turn tools; generate_str is multi-turn only)
REGULATORY = {'detect_ctr_candidates', 'lookup_fiu_reference_types', 'validate_str_fields', 'get_aml_glossary'}
# 카테고리 제외: 단일 도구가 아닌 합성 케이스군.
# (이름이 비슷한 EXCLUDE_MODELS와 혼동하지 말 것 — 아래는 카테고리, 그쪽은 모델이다.)
EXCLUDE_CATEGORIES = {'multi_tool', 'missing_parameters'}

# 28-모델 코호트: 구세대/중간크기 변형 8개 + 중복 Kanana 릴리스 제외.
# generate_new_figures.py, bootstrap_ranking_stability.py, RQ3_error_propagation.py,
# RQ_oracle_vs_real.py, RQ_str_generation_quality.py, generate_reg_vs_analysis.py,
# generate_fig4_scatter_v2.py 와 동일한 집합이며, 본문의 "28 configurations"와 맞는다.
EXCLUDE_MODELS = {
    "Qwen_Qwen3-30B-A3B-Instruct-2507", "Qwen_Qwen3-4B-Instruct-2507",
    "Qwen_Qwen3-8B", "Qwen_Qwen3_5-9B__nothink", "Qwen_Qwen3_5-9B__think",
    "Salesforce_Llama-xLAM-2-8b-fc-r", "Salesforce_xLAM-2-1b-fc-r",
    "Salesforce_xLAM-2-32b-fc-r",
    "kakaocorp/kanana-2-30b-a3b-instruct-2601",
}

# 표기 정규화 전용 (safe 파일명 -> 논문 표기). 코호트 선택에는 쓰지 않는다.
_CANONICAL_NAMES = {
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

_SAFE_TO_CANONICAL = {m.replace('/', '_').replace('.', '_'): m for m in _CANONICAL_NAMES}


def _canonicalize(m: str) -> str:
    return _SAFE_TO_CANONICAL.get(m, m)


def main():
    files = sorted(EVAL_DIR.glob('eval_*.json'))
    rows = []

    for f in files:
        d = json.load(f.open())
        raw = d['model']
        if raw in EXCLUDE_MODELS:
            continue
        model = _canonicalize(raw)
        if model in EXCLUDE_MODELS:
            continue
        reg_h = []; ana_h = []; per_cat = {}
        for cat_name, cat in d.get('by_category', {}).items():
            if cat_name in EXCLUDE_CATEGORIES:
                continue
            agg = cat.get('aggregated', {})
            h = agg.get('primary_tool_hit_rate', 0.0)
            per_cat[cat_name] = h
            if cat_name in REGULATORY:
                reg_h.append(h)
            else:
                ana_h.append(h)
        rh = sum(reg_h) / len(reg_h) if reg_h else 0
        ah = sum(ana_h) / len(ana_h) if ana_h else 0
        rows.append({
            'model': model,
            'regulatory_h_mean': round(rh, 4),
            'analysis_h_mean': round(ah, 4),
            'gap': round(ah - rh, 4),  # 분석 평균이 규제보다 얼마나 높은가
            **{f'cat_{k}': round(v, 4) for k, v in per_cat.items()},
        })

    with (OUT_DIR / 'regulatory_vs_analysis_gap.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    rh_all = [r['regulatory_h_mean'] for r in rows]
    ah_all = [r['analysis_h_mean'] for r in rows]
    summary = {
        'n_models': len(rows),
        'regulatory_categories': sorted(REGULATORY),
        'analysis_categories_count': len([k for k in rows[0] if k.startswith('cat_')]) - len(REGULATORY),
        'regulatory_h_mean_overall': round(sum(rh_all) / len(rh_all), 4),
        'analysis_h_mean_overall': round(sum(ah_all) / len(ah_all), 4),
        'gap_mean_overall': round(sum(r['gap'] for r in rows) / len(rows), 4),
        'gap_max': round(max(r['gap'] for r in rows), 4),
        'gap_min': round(min(r['gap'] for r in rows), 4),
        'top_5_largest_gap': sorted(rows, key=lambda x: -x['gap'])[:5],
        'note': 'gap = analysis_h - regulatory_h. positive gap = 규제 카테고리가 일반 분석 대비 낮은 적중률',
    }
    summary['top_5_largest_gap'] = [{'model': r['model'], 'gap': r['gap']}
                                     for r in summary['top_5_largest_gap']]
    json.dump(summary, (OUT_DIR / 'regulatory_vs_analysis_gap.json').open('w'),
              ensure_ascii=False, indent=2)

    try:
        # Plot A: 모델별 정렬 line plot
        sorted_rows = sorted(rows, key=lambda r: r['analysis_h_mean'])
        names = [short_name(r['model'], 18) for r in sorted_rows]
        x = range(len(sorted_rows))
        fig, ax = plt.subplots(figsize=(5.5, 4.2))
        ax.plot(x, [r['analysis_h_mean'] for r in sorted_rows], 'o-',
                label='Analysis (general)', color=COL_GOOD,
                markersize=5, linewidth=1.2, alpha=0.85)
        ax.plot(x, [r['regulatory_h_mean'] for r in sorted_rows], 's-',
                label='Regulatory output', color=COL_BAD,
                markersize=5, linewidth=1.2, alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=90, fontsize=7)
        ax.set_ylabel(r'Mean tool hit $h$', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND, loc='lower right')
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_regulatory_vs_analysis.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_regulatory_vs_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: 격차 히스토그램
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.hist([r['gap'] for r in rows], bins=15,
                color=COL_PURPLE, alpha=0.85, edgecolor='white')
        ax.axvline(summary['gap_mean_overall'], color=COL_BAD, linestyle='--',
                   linewidth=1.2, label=f"mean={summary['gap_mean_overall']:.3f}")
        ax.set_xlabel('Gap (analysis − regulatory)', fontsize=FS_LABEL)
        ax.set_ylabel('Models', fontsize=FS_LABEL)
        ax.legend(fontsize=FS_LEGEND)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_regulatory_gap_distribution.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_regulatory_gap_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f'plot failed: {e}')

    print(f'[RQ2-gap] completed: regulatory={summary["regulatory_h_mean_overall"]}, '
          f'analysis={summary["analysis_h_mean_overall"]}, '
          f'mean gap={summary["gap_mean_overall"]}')

if __name__ == '__main__':
    main()
