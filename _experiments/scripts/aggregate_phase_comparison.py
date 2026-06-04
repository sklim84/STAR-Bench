#!/usr/bin/env python3
"""KR/EN/MT phase별 comparison 정본 통합 생성기.

KR/EN: eval_*.json (singleton). MT: multiturn_*.json (멀티턴).
모델명 slash/underscore 양식 정규화 + partial(33-case)보다 full 우선 채택.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TS_RE = re.compile(r'_(\d{8}_\d{6})\.json$')


def normalize_name(model: str, canonicals: set[str]) -> str:
    if model in canonicals:
        return model
    for c in canonicals:
        if c.replace('/', '_').replace('.', '_') == model:
            return c
    return model


def aggregate_phase(phase: str):
    out_dir = PROJECT_ROOT / f'_experiments/results_{phase}'
    eval_dir = out_dir / 'eval'
    if not eval_dir.exists():
        print(f'[{phase}] eval dir missing: {eval_dir}')
        return None
    if phase == 'mt':
        glob = 'multiturn_*.json'
        expected_total = 50
        total_field = 'total_scenarios'
    else:
        glob = 'eval_*.json'
        expected_total = 1258
        total_field = 'total_cases'

    files = sorted(eval_dir.glob(glob))
    if not files:
        print(f'[{phase}] no eval files'); return None

    # 1st pass: collect canonicals
    canonicals = set()
    parsed = []
    for fp in files:
        try:
            d = json.load(fp.open())
        except json.JSONDecodeError:
            continue
        model = d.get('model') or d.get('model_id')
        if not model:
            continue
        m = TS_RE.search(fp.name)
        ts_key = m.group(1) if m else fp.name
        parsed.append((ts_key, fp, d, model))
        if '/' in model:
            canonicals.add(model)

    # dedup with partial-vs-full preference
    latest_full = {}
    latest_any = {}
    for ts, fp, d, raw in parsed:
        cname = normalize_name(raw, canonicals)
        tc = d.get(total_field, 0)
        if tc == expected_total:
            prev = latest_full.get(cname)
            if prev is None or ts > prev[0]:
                latest_full[cname] = (ts, fp, d)
        prev_any = latest_any.get(cname)
        if prev_any is None or ts > prev_any[0]:
            latest_any[cname] = (ts, fp, d)

    chosen = {}
    for cname in latest_any:
        chosen[cname] = (latest_full[cname][2] if cname in latest_full
                         else latest_any[cname][2])
        chosen[cname] = dict(chosen[cname], model=cname)

    n_full = sum(1 for r in chosen.values() if r.get(total_field) == expected_total)
    print(f'[{phase}] {len(chosen)} models ({n_full} full)')

    # build comparison
    if phase == 'mt':
        rows = []
        by_sub_cat = {}
        for name, r in chosen.items():
            ov = r.get('overall', {})
            rows.append({
                'model': name, 'provider': r.get('provider'),
                'think': r.get('think'),
                'total_scenarios': r.get('total_scenarios'),
                'total_elapsed_sec': r.get('total_elapsed_sec'),
                'avg_score': ov.get('avg_score'),
                'avg_tool_hit': ov.get('avg_tool_hit'),
                'avg_param_accuracy': ov.get('avg_param_accuracy'),
                'context_accuracy': ov.get('context_accuracy'),
                'scenario_complete_rate': ov.get('scenario_complete_rate'),
            })
            for sub, m in r.get('by_sub_category', {}).items():
                by_sub_cat.setdefault(sub, {})[name] = m
        rows.sort(key=lambda r: -(r['avg_tool_hit'] or 0))
        comparison = {
            'generated_at': datetime.now().isoformat(),
            'n_models': len(rows),
            'rows': rows,
            'by_sub_category': by_sub_cat,
        }
    else:
        model_summaries = []
        for name, r in chosen.items():
            ov = r.get('overall', {})
            model_summaries.append({
                'model': name, 'provider': r.get('provider', ''),
                'total_cases': r.get('total_cases', 0),
                'avg_score': ov.get('avg_score', 0),
                'primary_tool_hit_rate': ov.get('primary_tool_hit_rate', 0),
                'avg_tool_recall': ov.get('avg_tool_recall', 0),
                'avg_tool_precision': ov.get('avg_tool_precision', 0),
                'avg_param_accuracy': ov.get('avg_param_accuracy', 0),
                'avg_param_key_accuracy': ov.get('avg_param_key_accuracy', 0),
                'total_hallucinated_params': ov.get('total_hallucinated_params', 0),
                'total_elapsed_sec': r.get('total_elapsed_sec', 0),
                'by_error_type': ov.get('by_error_type', {}),
                'by_difficulty': ov.get('by_difficulty', {}),
            })
        cats = sorted({c for r in chosen.values() for c in r.get('by_category', {})})
        category_comparison = {}
        for cat in cats:
            cd = {}
            for name, r in chosen.items():
                cr = r.get('by_category', {}).get(cat, {})
                agg = cr.get('aggregated', {})
                cd[name] = {
                    'avg_score': agg.get('avg_score', 0),
                    'primary_tool_hit_rate': agg.get('primary_tool_hit_rate', 0),
                    'avg_param_accuracy': agg.get('avg_param_accuracy', 0),
                    'total': agg.get('total', 0),
                    'elapsed_sec': cr.get('elapsed_sec', 0),
                }
            category_comparison[cat] = cd
        comparison = {
            'timestamp': datetime.now().isoformat(),
            'models': list(chosen.keys()),
            'model_summaries': model_summaries,
            'category_comparison': category_comparison,
        }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = out_dir / f'comparison_{ts}.json'
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(f'  JSON: {json_path}')

    try:
        import pandas as pd
        xlsx_path = out_dir / f'comparison_{ts}.xlsx'
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as w:
            if phase == 'mt':
                pd.DataFrame(comparison['rows']).to_excel(w, sheet_name='overall', index=False)
                cat_rows = []
                for sub, models in comparison['by_sub_category'].items():
                    for m, v in models.items():
                        cat_rows.append({'sub_category': sub, 'model': m,
                                         **{k: v for k, v in v.items() if not isinstance(v, (dict, list))}})
                if cat_rows:
                    pd.DataFrame(cat_rows).to_excel(w, sheet_name='by_sub_category', index=False)
            else:
                ms = pd.DataFrame(comparison['model_summaries']).sort_values('avg_score', ascending=False)
                ms.to_excel(w, sheet_name='model_summaries', index=False)
                cat_rows = []
                for cat, mdata in comparison['category_comparison'].items():
                    for m, v in mdata.items():
                        cat_rows.append({'category': cat, 'model': m, **v})
                if cat_rows:
                    pd.DataFrame(cat_rows).to_excel(w, sheet_name='by_category', index=False)
        print(f'  XLSX: {xlsx_path}')
    except ImportError:
        print('  pandas/openpyxl not available; XLSX skipped')

    return comparison


def main():
    phases = sys.argv[1:] if len(sys.argv) > 1 else ['kr', 'en', 'mt']
    for p in phases:
        if p not in ('kr', 'en', 'mt'):
            print(f'invalid phase: {p}'); continue
        aggregate_phase(p)


if __name__ == '__main__':
    main()
