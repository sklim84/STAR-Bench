#!/usr/bin/env python3
"""RQ2: the Regulatory Reporting tools against every other tool, per configuration.

The metric is `h`, the primary tool hit (0/1): did the configuration reach for
the right tool on this case. The pre-audit step read
`by_category[t].aggregated.primary_tool_hit_rate`; that key is gone together with
the weighted score it sat beside (D02), and `h` is the same quantity under the
scorer's own name (PORTING rule 1). `load.single().groupby("category")["h"].mean()`
and `load.aggregates("single")[cfg]["by_category"][t]["h"]["mean"]` agree.

Regulatory Reporting is four single-turn tools: STR-field validation
(`validate_str_fields`), CTR-candidate detection (`detect_ctr_candidates`), FIU
reference-type lookup (`lookup_fiu_reference_types`) and AML glossary lookup
(`get_aml_glossary`). `generate_str` belongs to the subdomain in the manuscript's
tool table but is multi-turn only, so no single-turn category carries it.
Analysis is every other tool category. `multi_tool` and `missing_parameters` are
case groups rather than tools and are on neither side.

Each side is the unweighted mean over its category means, the definition the
manuscript states, and the gap is analysis minus regulatory: a positive gap means
the regulatory tools were harder. Every row and the summary carry the number of
categories and cases behind the mean (rule 2), and both outputs carry `n_configs`
with the configuration ids still unscored (rule 4).

The cohort is the serving registry through `load.single()`. The `EXCLUDE_MODELS`
and `_CANONICAL_NAMES` literals this step used to carry are gone (rule 3):
display names come from `label`, grouping from `group`.

Manuscript: the numbers behind fig:reg_vs_anal and the "reporting tools are
consistently harder than analysis tools" paragraph in Section 4.

Outputs
    _experiments/results_RQ2/regulatory_vs_analysis_gap.csv
    _experiments/results_RQ2/regulatory_vs_analysis_gap.json
    _experiments/results_RQ2/fig_regulatory_vs_analysis.{pdf,png}
    _experiments/results_RQ2/fig_regulatory_gap_distribution.{pdf,png}
"""
import csv
import json
import sys
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]   # repository root
for _p in (str(Path(__file__).resolve().parent), str(_SB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _plot_style import (plt, COL_GOOD, COL_BAD, COL_PURPLE, FS_LABEL,  # noqa: E402
                         FS_LEGEND, style_axes)
from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / '_experiments' / 'results_RQ2'

# Regulatory Reporting subdomain (single-turn tools; generate_str is multi-turn only).
REGULATORY = {'detect_ctr_candidates', 'lookup_fiu_reference_types',
              'validate_str_fields', 'get_aml_glossary'}
# Not tools: synthetic case groups. Excluded from both sides, as before.
EXCLUDE_CATEGORIES = {'multi_tool', 'missing_parameters'}


def cohort_note():
    """(n_configs, missing ids, one line saying so) for the scored cohort.

    Rule 4: a figure that draws 18 rows under a caption that says 28 is the
    failure this exists to prevent, so the count travels with every output.
    """
    todo = load.missing()
    missing = sorted(todo.loc[~todo['single'], 'config_id'])
    n_total = len(todo)
    n_scored = n_total - len(missing)
    line = f'{n_scored} of {n_total} configurations scored'
    if missing:
        line += f'; {len(missing)} not scored yet'
    return n_scored, missing, line


def per_config_means():
    """One row per configuration: the two side means, their n, and per-category h."""
    cases = load.single()
    per_cat = (cases.groupby(['config_id', 'label', 'group', 'category'])
                    .agg(h_mean=('h', 'mean'), n_cases=('h', 'size')).reset_index())
    per_cat = per_cat[~per_cat['category'].isin(EXCLUDE_CATEGORIES)]

    rows = []
    for (config_id, label, group), block in per_cat.groupby(['config_id', 'label', 'group'],
                                                            sort=False):
        reg = block[block['category'].isin(REGULATORY)]
        ana = block[~block['category'].isin(REGULATORY)]
        if reg.empty or ana.empty:
            continue
        rows.append({
            'config_id': config_id,
            'label': label,
            'group': group,
            'regulatory_h_mean': round(float(reg['h_mean'].mean()), 4),
            'n_regulatory_categories': int(len(reg)),
            'n_regulatory_cases': int(reg['n_cases'].sum()),
            'analysis_h_mean': round(float(ana['h_mean'].mean()), 4),
            'n_analysis_categories': int(len(ana)),
            'n_analysis_cases': int(ana['n_cases'].sum()),
            # positive gap = the regulatory tools were harder than the analysis tools
            'gap': round(float(ana['h_mean'].mean() - reg['h_mean'].mean()), 4),
            **{f'cat_{cat}': round(float(value), 4)
               for cat, value in zip(block['category'], block['h_mean'])},
        })
    rows.sort(key=lambda r: -r['gap'])
    return rows


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_configs, missing, note = cohort_note()
    rows = per_config_means()
    if not rows:
        raise SystemExit('no scored configuration carries both sides')

    missing_field = ';'.join(missing)
    csv_rows = [{**r, 'n_configs': n_configs, 'configs_missing_from_28': missing_field}
                for r in rows]
    with (OUT_DIR / 'regulatory_vs_analysis_gap.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    gaps = [r['gap'] for r in rows]
    reg_all = [r['regulatory_h_mean'] for r in rows]
    ana_all = [r['analysis_h_mean'] for r in rows]
    worse = [r for r in rows if r['gap'] > 0]
    better = [r for r in rows if r['gap'] <= 0]
    analysis_categories = sorted({k[4:] for r in rows for k in r if k.startswith('cat_')}
                                 - REGULATORY)
    summary = {
        'n_configs': n_configs,
        'configs_missing_from_28': missing,
        'cohort_note': note,
        'metric': 'h, primary tool hit (0/1). The pre-audit primary_tool_hit_rate under '
                  'the scorer\'s own name; the weighted score is gone (D02).',
        'regulatory_categories': sorted(REGULATORY),
        'analysis_categories': analysis_categories,
        'analysis_categories_count': len(analysis_categories),
        'excluded_categories': sorted(EXCLUDE_CATEGORIES),
        'regulatory_h_mean_overall': round(sum(reg_all) / len(reg_all), 4),
        'analysis_h_mean_overall': round(sum(ana_all) / len(ana_all), 4),
        'gap_mean_overall': round(sum(gaps) / len(gaps), 4),
        'gap_mean_overall_pp': round(100 * sum(gaps) / len(gaps), 1),
        'gap_max': round(max(gaps), 4),
        'gap_min': round(min(gaps), 4),
        'n_configs_worse_on_regulatory': len(worse),
        'n_configs_better_on_regulatory': len(better),
        'configs_better_on_regulatory': [{'config_id': r['config_id'], 'label': r['label'],
                                          'gap_pp': round(100 * r['gap'], 1)} for r in better],
        'top_5_largest_gap': [{'config_id': r['config_id'], 'label': r['label'],
                               'gap': r['gap']} for r in rows[:5]],
        'note': 'gap = analysis_h - regulatory_h, each side the unweighted mean over its '
                'category means. A positive gap means the regulatory tools were harder. '
                f'Averaged over {n_configs} scored configurations, not over 28.',
    }
    with (OUT_DIR / 'regulatory_vs_analysis_gap.json').open('w') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    try:
        # Plot A: per-configuration pair, sorted by the analysis mean
        sorted_rows = sorted(rows, key=lambda r: r['analysis_h_mean'])
        names = [r['label'] for r in sorted_rows]
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
        ax.set_title(note, fontsize=7, loc='left', color='#555555')
        ax.legend(fontsize=FS_LEGEND, loc='lower right')
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_regulatory_vs_analysis.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_regulatory_vs_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot B: the distribution of the gap
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.hist(gaps, bins=15, color=COL_PURPLE, alpha=0.85, edgecolor='white')
        ax.axvline(summary['gap_mean_overall'], color=COL_BAD, linestyle='--',
                   linewidth=1.2, label=f"mean={summary['gap_mean_overall']:.3f}")
        ax.set_xlabel('Gap (analysis − regulatory)', fontsize=FS_LABEL)
        ax.set_ylabel('Configurations', fontsize=FS_LABEL)
        ax.set_title(note, fontsize=7, loc='left', color='#555555')
        ax.legend(fontsize=FS_LEGEND)
        style_axes(ax)
        plt.tight_layout()
        plt.savefig(OUT_DIR / 'fig_regulatory_gap_distribution.pdf', dpi=300, bbox_inches='tight')
        plt.savefig(OUT_DIR / 'fig_regulatory_gap_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as exc:                                   # pragma: no cover - plotting only
        print(f'plot failed: {exc}')

    print(f'[RQ2-gap] {note}')
    if missing:
        print(f'[RQ2-gap] not scored: {", ".join(missing)}')
    print(f'[RQ2-gap] regulatory={summary["regulatory_h_mean_overall"]} '
          f'analysis={summary["analysis_h_mean_overall"]} '
          f'mean gap={summary["gap_mean_overall_pp"]}pp '
          f'(worse on regulatory: {len(worse)}/{n_configs})')


if __name__ == '__main__':
    main()
