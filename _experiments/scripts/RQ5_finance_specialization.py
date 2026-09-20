#!/usr/bin/env python3
"""RQ5: what finance-domain SFT changes, per AML sub-domain.

The metric is `h`, the primary tool hit (0/1): whether the configuration reached
for the right tool on the case. A sub-domain's number is the unweighted mean over
its tools' category means, and it carries the tool count and the case count
behind it.

A base comparison would pair each fine-tune with the model it was tuned from, and
the cohort does not support one: the two DragonLLM models were tuned from
`meta-llama/Llama-3.1-8B-Instruct` and `Qwen/Qwen3-8B`, and neither base is a
configuration in the serving registry. Picking some other 8B model as a stand-in
would make the conclusion a property of that one model. Hermes-3-8B sits at
regulatory h .3517 against .58 to .70 for the other 8B models, so putting it in
the base slot would inflate the apparent benefit of finance SFT. `base_comparison`
in the JSON therefore reports `available: false` and names the two absent bases,
and the comparison the cohort does support is emitted instead: the
finance-specialised configurations against the other registry groups, sub-domain
by sub-domain.

That comparison is between registry groups (`Finance-Specialized`,
`Korean-Specialized`, `General-Purpose`) rather than between a list of model
names, so it follows what the registry serves. Every output carries `n_configs`
and the ids still unscored, and the group sizes are in the JSON and on the
figure, because a group of one configuration supports a narrower claim than a
group of ten.

The sub-domain definitions below are the manuscript's tab:tool_suite mapping
rather than a cohort list. `sub_domain_tools_missing` reports any member tool
with no `category` in `load.single()`; `generate_str` is expected there, being
multi-turn only.

Manuscript: the finance-specialisation discussion in Section 5.

Outputs
    _experiments/results_RQ5/finance_vs_general_subdomain.csv
    _experiments/results_RQ5/finance_specialization.json
    _experiments/results_RQ5/fig_finance_specialization.{pdf,png}
"""
import csv
import json
import sys
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]   # repository root
for _p in (str(Path(__file__).resolve().parent), str(_SB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _experiments.scripts.analysis import load
from _plot_style import plt, FS_TICK, FS_LABEL, FS_LEGEND, style_axes  # noqa: E402
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / '_experiments' / 'results_RQ5'

# main.tex tab:tool_suite 매핑 (4 sub-domain). 코호트 목록이 아니라 도구 분류라서 남는다.
SUB_DOMAINS = {
    'Transaction Inquiry & Statistics': [
        'get_statistics', 'query_transactions', 'get_account_profile',
        'compare_periods', 'get_institution_report', 'get_fraud_type_summary',
        'get_receiving_account_profile',
    ],
    'Suspicious Activity Detection': [
        'predict_fraud', 'rank_risky_transactions',
        'score_account_risk', 'detect_monitoring_alerts',
    ],
    'Money Flow & Network Analysis': [
        'analyze_network', 'detect_aml_patterns', 'detect_smurfing_network',
        'detect_dormant_reactivation', 'analyze_cross_institution_flow',
        'get_trend_analysis', 'analyze_channel_risk',
    ],
    'Regulatory Reporting': [
        'detect_ctr_candidates', 'lookup_fiu_reference_types',
        'validate_str_fields', 'get_aml_glossary', 'generate_str',
    ],
}

# Provenance, not a cohort selection: which base each finance-specialised
# configuration was tuned from. Used only to name what the cohort does not have,
# never to pick rows. Neither base is in the serving registry.
BASE_OF = {
    'dragon-llama-fin': 'meta-llama/Llama-3.1-8B-Instruct',
    'dragon-qwen-fin': 'Qwen/Qwen3-8B',
}
FINANCE_GROUP = 'Finance-Specialized'
# The group the finance models are read against. General-Purpose is the registry's
# own name for "not specialised", which is the contrast the RQ is about.
CONTRAST_GROUP = 'General-Purpose'



def _subdomain_mean(rows, tools):
    """Mean tool hit over a sub-domain, the same unweighted mean per tool the
    cohort rows use, so a baseline row is comparable with a cohort row."""
    per_tool = rows.groupby("category")["h"].mean()
    hits = [per_tool[t] for t in tools if t in per_tool.index]
    return round(float(sum(hits) / len(hits)), 4) if hits else None


def cohort_note():
    """(n_configs, missing ids, one line saying so) for the scored cohort."""
    todo = load.missing()
    missing = sorted(todo.loc[~todo['single'], 'config_id'])
    n_total = len(todo)
    n_scored = n_total - len(missing)
    line = f'{n_scored} of {n_total} configurations scored'
    if missing:
        line += f'; {len(missing)} not scored yet'
    return n_scored, missing, n_total, line


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_configs, missing, n_total, note = cohort_note()

    cases = load.single()
    per_cat = (cases.groupby(['config_id', 'label', 'group', 'category'])
                    .agg(h_mean=('h', 'mean'), n_cases=('h', 'size')).reset_index())
    present = set(per_cat['category'])
    # Rule 4's sibling: a sub-domain that silently lost a tool is not reported as
    # the same sub-domain. generate_str is multi-turn only and is expected here.
    tools_missing = {sd: [t for t in tools if t not in present]
                     for sd, tools in SUB_DOMAINS.items()}
    tools_used = {sd: [t for t in tools if t in present] for sd, tools in SUB_DOMAINS.items()}

    per_config = {}
    rows = []
    for (config_id, label, group), block in per_cat.groupby(['config_id', 'label', 'group'],
                                                            sort=False):
        by_tool = dict(zip(block['category'], block['h_mean']))
        by_tool_n = dict(zip(block['category'], block['n_cases']))
        h_by_sd, n_by_sd, tools_by_sd = {}, {}, {}
        for sd, tools in tools_used.items():
            hits = [by_tool[t] for t in tools if t in by_tool]
            h_by_sd[sd] = round(float(sum(hits) / len(hits)), 4) if hits else None
            n_by_sd[sd] = int(sum(by_tool_n[t] for t in tools if t in by_tool_n))
            tools_by_sd[sd] = len(hits)
        per_config[config_id] = {'label': label, 'group': group, 'h': h_by_sd,
                                 'n_cases': n_by_sd, 'n_tools': tools_by_sd}
        rows.append({'config_id': config_id, 'label': label, 'group': group,
                     **h_by_sd,
                     **{f'n_cases_{sd}': n_by_sd[sd] for sd in SUB_DOMAINS},
                     **{f'n_tools_{sd}': tools_by_sd[sd] for sd in SUB_DOMAINS},
                     'n_configs': n_configs,
                     'configs_missing_from_28': ';'.join(missing)})

    # Groups come from the registry, ordered with the RQ's subject first and the
    # rest by name, so the order does not depend on a literal in this file.
    groups_present = sorted({r['group'] for r in rows})
    group_order = ([FINANCE_GROUP] if FINANCE_GROUP in groups_present else []) + \
                  [g for g in groups_present if g != FINANCE_GROUP]
    group_members = {g: sorted(cid for cid, v in per_config.items() if v['group'] == g)
                     for g in group_order}
    group_means, group_n_cases = {}, {}
    for g in group_order:
        members = [per_config[c] for c in group_members[g]]
        group_means[g] = {}
        group_n_cases[g] = {}
        for sd in SUB_DOMAINS:
            vals = [m['h'][sd] for m in members if m['h'][sd] is not None]
            group_means[g][sd] = round(sum(vals) / len(vals), 4) if vals else None
            group_n_cases[g][sd] = int(sum(m['n_cases'][sd] for m in members))

    rows.sort(key=lambda r: (group_order.index(r['group']), r['config_id']))
    with (OUT_DIR / 'finance_vs_general_subdomain.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    finance_vs_contrast = {}
    if FINANCE_GROUP in group_means and CONTRAST_GROUP in group_means:
        for sd in SUB_DOMAINS:
            a, b = group_means[FINANCE_GROUP][sd], group_means[CONTRAST_GROUP][sd]
            if a is not None and b is not None:
                finance_vs_contrast[sd] = round(a - b, 4)

    # Each fine-tune against the model it was tuned from. The bases are run on the
    # same benchmark and scored by the same code, and they sit outside the cohort
    # because a base model is a reference rather than a deployment candidate.
    scored_finance = group_members.get(FINANCE_GROUP, [])
    try:
        baseline_cases = load.baselines()
    except FileNotFoundError:
        baseline_cases = None

    if baseline_cases is None:
        base_comparison = {
            'available': False,
            'intended_pairs': {cid: BASE_OF[cid] for cid in sorted(BASE_OF)},
            'reason': 'The base models are not scored. Run them and score them into '
                      'runs/eval_baselines/ for this comparison to appear.',
            'finance_configs_scored': scored_finance,
        }
    else:
        by_base = {bid: grp for bid, grp in baseline_cases.groupby('config_id')}
        pairs = {}
        for baseline_id, meta in load.BASELINES.items():
            fine = meta['base_of']
            if baseline_id not in by_base or fine not in per_config:
                continue
            base_rows = by_base[baseline_id]
            base_sd = {sd: _subdomain_mean(base_rows, tools)
                       for sd, tools in SUB_DOMAINS.items()}
            fine_sd = per_config[fine]['h']
            pairs[fine] = {
                'base_config': baseline_id, 'base_label': meta['label'],
                'base_model': meta['model'],
                'fine_label': per_config[fine]['label'],
                'base_overall_h': round(float(base_rows['h'].mean()), 4),
                'fine_overall_h': round(float(cases[cases['config_id'] == fine]['h'].mean()), 4),
                'by_subdomain': {sd: {'base': base_sd[sd], 'fine': fine_sd.get(sd),
                                      'delta': (None if base_sd[sd] is None
                                                or fine_sd.get(sd) is None
                                                else round(fine_sd[sd] - base_sd[sd], 4))}
                                 for sd in SUB_DOMAINS},
            }
            pairs[fine]['overall_delta'] = round(
                pairs[fine]['fine_overall_h'] - pairs[fine]['base_overall_h'], 4)
        declines = [sd for sd in SUB_DOMAINS
                    if pairs and all((p['by_subdomain'][sd]['delta'] or 0) < 0
                                     for p in pairs.values())]
        base_comparison = {
            'available': bool(pairs),
            'pairs': pairs,
            'subdomains_where_every_pair_declines': declines,
            'finance_configs_scored': scored_finance,
        }

    summary = {
        'n_configs': n_configs,
        'configs_missing_from_28': missing,
        'cohort_note': note,
        'metric': 'h, primary tool hit (0/1): did the configuration reach for the right '
                  'tool on this case. A case is correct when h == 1.',
        'sub_domains': list(SUB_DOMAINS.keys()),
        'sub_domain_tools': {sd: list(tools) for sd, tools in SUB_DOMAINS.items()},
        'sub_domain_tools_used': tools_used,
        'sub_domain_tools_missing': {sd: t for sd, t in tools_missing.items() if t},
        'group_order': group_order,
        'group_labels': {g: f'{g} (n={len(group_members[g])})' for g in group_order},
        'group_members': group_members,
        'group_n_configs': {g: len(group_members[g]) for g in group_order},
        'group_means': group_means,
        'group_n_cases': group_n_cases,
        'per_config_subdomain_h': per_config,
        f'finance_vs_{CONTRAST_GROUP.lower().replace("-", "_")}_diff': finance_vs_contrast,
        'base_comparison': base_comparison,
        'note': 'A sub-domain value is the unweighted mean over its tools\' category means, '
                'and a group value the unweighted mean over its configurations. '
                f'positive diff = the {FINANCE_GROUP} group above the {CONTRAST_GROUP} group. '
                'The base-vs-SFT comparison is not available; see base_comparison.',
    }
    with (OUT_DIR / 'finance_specialization.json').open('w') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    try:
        import numpy as np
        import matplotlib as _mpl
        sds = list(SUB_DOMAINS.keys())
        fig, ax = plt.subplots(figsize=(8, 3.6))
        x = np.arange(len(sds))
        # 색감 통일: 그룹 수가 레지스트리에서 정해지므로 팔레트도 그 수에 맞춰 viridis에서 뽑는다.
        virid = _mpl.colormaps['viridis']
        colors = [virid(v) for v in np.linspace(0.25, 0.9, len(group_order))]
        width = 0.75 / len(group_order)
        offsets = np.linspace(-(0.75 - width) / 2, (0.75 - width) / 2, len(group_order))
        for g, color, off in zip(group_order, colors, offsets):
            vals = [group_means[g][sd] if group_means[g][sd] is not None else 0 for sd in sds]
            ax.bar(x + off, vals, width, label=summary['group_labels'][g],
                   color=color, alpha=0.85)
        import textwrap
        ax.set_xticks(x)
        # 두 줄로 접는다. 한 줄이면 이웃 라벨과 겹친다.
        ax.set_xticklabels([textwrap.fill(s, 18) for s in sds], fontsize=FS_TICK - 1)
        ax.set_ylabel(r'Mean tool hit $h$', fontsize=FS_LABEL)
        ax.set_ylim(0, 1.05)
        # 범례는 축 위로 뺀다. 그룹 수가 줄면서 lower left 에 두면 막대를 가린다.
        ax.legend(fontsize=FS_LEGEND, loc='lower center', bbox_to_anchor=(0.5, 1.0),
                  ncol=len(group_order), frameon=False)
        # Rule 4: the cohort travels with the figure.
        ax.text(0.0, 1.14, note, transform=ax.transAxes, fontsize=8,
                color='#555555', ha='left', va='bottom')
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_finance_specialization.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_finance_specialization.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as exc:                                   # pragma: no cover - plotting only
        print(f'plot failed: {exc}')

    print(f'[RQ5-finance] {note}')
    if missing:
        print(f'[RQ5-finance] not scored: {", ".join(missing)}')
    for g in group_order:
        print(f'  {g:20s} n={len(group_members[g])}  ' + '  '.join(
            f'{sd.split()[0]}={group_means[g][sd]}' for sd in SUB_DOMAINS))
    print(f'  finance vs {CONTRAST_GROUP} diff: {finance_vs_contrast}')
    bc = base_comparison
    if bc.get('available'):
        for fine, pair in bc['pairs'].items():
            deltas = ", ".join(f"{sd.split()[0]} {100 * (pair['by_subdomain'][sd]['delta'] or 0):+.1f}"
                               for sd in SUB_DOMAINS)
            print(f"  {pair['base_label']} -> {fine}: overall "
                  f"{100 * pair['overall_delta']:+.1f}pp  ({deltas})")
        print(f"  every pair declines in: "
              f"{', '.join(bc['subdomains_where_every_pair_declines']) or 'no sub-domain'}")
    else:
        print(f"  base comparison NOT available: {bc.get('reason', '')}")
    for sd, tools in summary['sub_domain_tools_missing'].items():
        print(f'  sub-domain tool with no category: {sd}: {", ".join(tools)}')


if __name__ == '__main__':
    main()
