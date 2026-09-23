#!/usr/bin/env python3
"""RQ4 cont. (Effect of Thinking Mode): per-pair single-turn and multi-turn deltas.

For every model the registry serves twice, once reasoning and once not, this
step reports the single-turn delta in h and the oracle multi-turn delta in the
turn-level mean tool hit, so the manuscript can cite both:
- single Delta h and multi Delta h_bar per pair
- the non-monotone effect of the thinking mode (it differs by family)

Metrics. **A case is correct when `h == 1`**, so single-turn h is the mean of the
per-case `h` and the multi-turn h_bar is the mean of `h` over the oracle turns.
Every number carries its n.

Pairing. In the serving registry the two arms are separate `config_id`s, so the
pairs come from `load.configs()`: two configurations that share a `model` and
differ in `reasoning_mode`, with the mode itself saying which arm reasons. No
list of model names is kept here, so nothing can drift from what was served. No
row is dropped from a mean without the output saying which and why, and a
registry pair with only one arm scored is reported as such rather than dropped
in silence.

Output (unchanged names, under `_experiments/results_RQ4`):
  - thinking_effect_per_pair.csv
  - thinking_effect_summary.json
  - fig_thinking_delta_single.{pdf,png}
  - fig_thinking_delta_multi.{pdf,png}
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, COL_NOTHINK, COL_THINK, FS_TICK, FS_LABEL,
                         FS_LEGEND, style_axes)

_SB = Path(__file__).resolve().parents[2]  # repository root
if str(_SB) not in sys.path:
    sys.path.insert(0, str(_SB))

from _experiments.scripts.analysis import load  # noqa: E402

OUT_DIR = _SB / '_experiments' / 'results_RQ4'
COLUMN = 'single'      # the main-table arm: Korean tool schema, Korean questions
SETTING = 'oracle'     # the multi-turn setting the manuscript reports beside it

# The registry's `reasoning_mode` vocabulary, split into the two arms of a
# toggle. `none` and `always_on` are not a toggle and are not in the map, so a
# model served under either one has no pair here.
THINKING_ARM = {'nothink': 'nothink', 'effort_low': 'nothink',
                'think': 'think', 'effort_high': 'think'}


def registry_pairs() -> list[dict]:
    """Configurations that share a model and differ in reasoning mode."""
    cfgs = load.configs()
    pairs = []
    for model, group in cfgs.groupby('model', sort=False):
        arms: dict[str, list] = {}
        for row in group.itertuples(index=False):
            arm = THINKING_ARM.get(row.reasoning_mode)
            if arm:
                arms.setdefault(arm, []).append(row)
        if len(arms.get('think', [])) != 1 or len(arms.get('nothink', [])) != 1:
            continue
        think, nothink = arms['think'][0], arms['nothink'][0]
        pairs.append({
            'model': model,
            'display': think.label.replace(' (T)', '').strip(),
            'nothink_config_id': nothink.config_id, 'think_config_id': think.config_id,
            'nothink_reasoning_mode': nothink.reasoning_mode,
            'think_reasoning_mode': think.reasoning_mode,
        })
    return pairs


def single_hits() -> dict:
    """config_id -> {h, n} over the single-turn cases."""
    cases = load.single(column=COLUMN)
    return {cid: {'h': float(g['h'].mean()), 'n': int(len(g))}
            for cid, g in cases.groupby('config_id')}


def multiturn_hits() -> dict:
    """config_id -> {h_bar, n} over the oracle turns.

    `h_bar` is the scorer's own aggregate: mean tool hit over the turns, as
    Section 3 defines it and as the manuscript tables print it. A mean of
    per-scenario means would weight a four-turn scenario like a six-turn one.
    """
    try:
        aggregates = load.aggregates(SETTING)
    except FileNotFoundError:
        return {}
    out = {}
    for cid, aggregate in aggregates.items():
        cell = aggregate.get('h') or {}
        out[cid] = {'h_bar': cell.get('mean'), 'n': int(cell.get('n') or 0)}
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = load.missing()
    n_registry = len(table)
    scored_single = set(table.loc[table[COLUMN], 'config_id'])
    scored_multi = set(table.loc[table[SETTING], 'config_id'])

    pairs = registry_pairs()
    complete = [p for p in pairs
                if p['nothink_config_id'] in scored_single
                and p['think_config_id'] in scored_single]
    incomplete = [
        {**p, 'missing_arm': [cid for cid in (p['nothink_config_id'], p['think_config_id'])
                              if cid not in scored_single]}
        for p in pairs if p not in complete
    ]

    print(f'Registry holds {len(pairs)} think/nothink pair(s); '
          f'{len(complete)} have both arms scored single-turn.')
    for p in complete:
        print(f"  {p['display']}: {p['nothink_config_id']} ({p['nothink_reasoning_mode']}) "
              f"vs {p['think_config_id']} ({p['think_reasoning_mode']})")
    for p in incomplete:
        print(f"  SKIPPED {p['display']}: not scored yet: {', '.join(p['missing_arm'])}")

    single = single_hits()
    multi = multiturn_hits()

    rows = []
    for pair in complete:
        nt, t = pair['nothink_config_id'], pair['think_config_id']
        s_nt, s_t = single.get(nt, {}), single.get(t, {})
        m_nt, m_t = multi.get(nt, {}), multi.get(t, {})
        h_nt, h_t = s_nt.get('h'), s_t.get('h')
        hb_nt, hb_t = m_nt.get('h_bar'), m_t.get('h_bar')
        rows.append({
            'model': pair['display'],
            'model_id': pair['model'],
            'nothink_config_id': nt,
            'think_config_id': t,
            'nothink_reasoning_mode': pair['nothink_reasoning_mode'],
            'think_reasoning_mode': pair['think_reasoning_mode'],
            'h_nothink': h_nt, 'h_think': h_t,
            'n_cases_nothink': s_nt.get('n'), 'n_cases_think': s_t.get('n'),
            'delta_h_single': (h_t - h_nt) if (h_nt is not None and h_t is not None) else None,
            'h_bar_nothink': hb_nt, 'h_bar_think': hb_t,
            'n_scenarios_nothink': m_nt.get('n'), 'n_scenarios_think': m_t.get('n'),
            'delta_h_multi': (hb_t - hb_nt) if (hb_nt is not None and hb_t is not None) else None,
        })

    if not rows:
        raise SystemExit('no thinking pair has both arms scored; nothing to report')

    with (OUT_DIR / 'thinking_effect_per_pair.csv').open('w', newline='',
                                                        encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def mean_with_n(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return (round(sum(vals) / len(vals), 4) if vals else None), len(vals)

    mean_single, n_single = mean_with_n('delta_h_single')
    mean_multi, n_multi = mean_with_n('delta_h_multi')

    cohort_note = (f'{len(rows)} of {len(pairs)} registry thinking pairs have both arms '
                   f'scored; {len(scored_single)} of {n_registry} configurations are '
                   f'scored single-turn')
    summary = {
        'cohort': {
            'n_registry': n_registry,
            'n_configs': len(scored_single),
            'n_configs_multiturn': len(scored_multi),
            'config_ids': sorted(scored_single),
            'missing_config_ids': table.loc[~table[COLUMN], 'config_id'].tolist(),
            'note': cohort_note,
        },
        'n_registry_pairs': len(pairs),
        'n_thinking_pairs': len(rows),
        'pairs_without_both_arms': incomplete,
        'pairs': rows,
        'mean_delta_single': mean_single,
        'n_pairs_delta_single': n_single,
        'mean_delta_multi': mean_multi,
        'n_pairs_delta_multi': n_multi,
        'note': ('Delta h = h(T) - h(NT) over the single-turn cases; '
                 'Delta h_bar = h_bar(T) - h_bar(NT) over the oracle turns, where '
                 'h_bar is the scorer\'s mean turn-level hit. '
                 'No pair is excluded from the means: every pair with both arms scored '
                 'is in them. ' + cohort_note),
    }
    with (OUT_DIR / 'thinking_effect_summary.json').open('w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    try:
        def bar_figure(key, ylabel, filename):
            present = [r for r in rows if r[key] is not None]
            if not present:
                print(f'  {filename}: no pair has {key}; figure skipped')
                return
            fig, ax = plt.subplots(figsize=(5, 3.2))
            deltas = [r[key] for r in present]
            names = [r['model'] for r in present]
            colors = [COL_THINK if d > 0 else COL_NOTHINK for d in deltas]
            ax.bar(range(len(names)), deltas, color=colors, alpha=0.85, width=0.65)
            ax.axhline(0, color='black', linewidth=0.5)
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, fontsize=FS_TICK, rotation=20, ha='right')
            ax.set_ylabel(ylabel, fontsize=FS_LABEL)
            ax.set_title(cohort_note, fontsize=FS_LEGEND - 2)
            # The label offsets follow the range of the bars rather than being
            # absolute, because an absolute offset puts every label of an
            # all-negative panel outside the axes. The limits leave room for them.
            span = max(abs(d) for d in deltas) or 1.0
            pad = 0.06 * span
            for i, d in enumerate(deltas):
                ax.text(i, d + (pad if d >= 0 else -pad), f'{d:+.3f}',
                        ha='center', va='bottom' if d >= 0 else 'top',
                        fontsize=FS_LEGEND - 1)
            lo, hi = min(deltas + [0.0]), max(deltas + [0.0])
            ax.set_ylim(lo - 3 * pad, hi + 3 * pad)
            style_axes(ax)
            plt.tight_layout()
            plt.savefig(OUT_DIR / f'{filename}.pdf', dpi=300, bbox_inches='tight')
            plt.savefig(OUT_DIR / f'{filename}.png', dpi=300, bbox_inches='tight')
            plt.close()

        bar_figure('delta_h_single', r'$\Delta h$ (think $-$ nothink, single)',
                   'fig_thinking_delta_single')
        bar_figure('delta_h_multi', r'$\Delta \bar{h}$ (think $-$ nothink, multi)',
                   'fig_thinking_delta_multi')
    except Exception as e:
        print(f'plot failed: {e}')

    print()
    print(f'[RQ4-thinking] {cohort_note}')
    def _num(value):
        return 'n/a' if value is None else f'{value:.4f}'

    def _delta(value):
        return 'n/a' if value is None else f'{value:+.4f}'

    for r in rows:
        print(f"  {r['model']:<16} "
              f"single {_num(r['h_nothink'])} -> {_num(r['h_think'])} "
              f"(d {_delta(r['delta_h_single'])}, n={r['n_cases_nothink']})   "
              f"multi {_num(r['h_bar_nothink'])} -> {_num(r['h_bar_think'])} "
              f"(d {_delta(r['delta_h_multi'])}, n={r['n_scenarios_nothink']})")
    print(f'  mean dh (single): {mean_single} over {n_single} pair(s)')
    print(f'  mean dh_bar (multi): {mean_multi} over {n_multi} pair(s)')


if __name__ == '__main__':
    main()
