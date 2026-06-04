#!/usr/bin/env python3
"""results_kr/eval/eval_*.json을 모두 모아 results_kr/comparison_<ts>.{json,xlsx} 생성.

benchmark.py --comparison-only을 외부 의존성 없이 대체. 동일 모델명에 대해 가장 최신
타임스탬프 파일을 채택한다 (eval_<safe>_<YYYYMMDD_HHMMSS>.json).
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

OUT_DIR = Path('_experiments/results_kr')
EVAL_DIR = OUT_DIR / 'eval'
TS_RE = re.compile(r'_(\d{8}_\d{6})\.json$')


def normalize_name(model: str, canonicals: set[str]) -> str:
    """eval json의 'model' 필드 (slash 또는 underscore form)를 canonical로 통일."""
    if model in canonicals:
        return model
    # underscore-form: canonical of form "X/Y.Z" encodes to "X_Y_Z"
    for c in canonicals:
        if c.replace('/', '_').replace('.', '_') == model:
            return c
    return model  # fallback (unknown model)


def main():
    files = sorted(EVAL_DIR.glob('eval_*.json'))
    if not files:
        print(f'No eval files in {EVAL_DIR}'); sys.exit(1)

    # 1st pass: collect canonicals (slash form)
    canonicals = set()
    parsed = []
    for fp in files:
        try:
            d = json.load(fp.open())
        except json.JSONDecodeError:
            continue
        model = d.get('model')
        if not model:
            continue
        m = TS_RE.search(fp.name)
        ts_key = m.group(1) if m else fp.name
        parsed.append((ts_key, fp, d, model))
        if '/' in model:
            canonicals.add(model)

    # 2nd pass: dedup by canonical, prefer latest file with total_cases==1258
    # (post-merge full result wins over partial 33-case re-experiments)
    latest_full = {}   # canonical -> (ts, fp, d)
    latest_any = {}    # canonical -> (ts, fp, d) — fallback if no full available
    for ts, fp, d, raw in parsed:
        cname = normalize_name(raw, canonicals)
        tc = d.get('total_cases', 0)
        if tc == 1258:
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
        # rewrite model field to canonical for downstream consistency
        chosen[cname] = dict(chosen[cname], model=cname)

    results = chosen
    n_full = sum(1 for r in results.values() if r.get('total_cases') == 1258)
    print(f'Aggregated {len(results)} unique models from {len(files)} eval files '
          f'({n_full} with total_cases=1258)')

    model_summaries = []
    for name, r in results.items():
        ov = r.get('overall', {})
        model_summaries.append({
            'model': name,
            'provider': r.get('provider', ''),
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

    cats = sorted({c for r in results.values() for c in r.get('by_category', {})})
    category_comparison = {}
    for cat in cats:
        cat_data = {}
        for name, r in results.items():
            cr = r.get('by_category', {}).get(cat, {})
            agg = cr.get('aggregated', {})
            cat_data[name] = {
                'avg_score': agg.get('avg_score', 0),
                'primary_tool_hit_rate': agg.get('primary_tool_hit_rate', 0),
                'avg_param_accuracy': agg.get('avg_param_accuracy', 0),
                'total': agg.get('total', 0),
                'elapsed_sec': cr.get('elapsed_sec', 0),
            }
        category_comparison[cat] = cat_data

    comparison = {
        'timestamp': datetime.now().isoformat(),
        'models': list(results.keys()),
        'model_summaries': model_summaries,
        'category_comparison': category_comparison,
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = OUT_DIR / f'comparison_{ts}.json'
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(f'JSON: {json_path}')

    try:
        import pandas as pd
        xlsx_path = OUT_DIR / f'comparison_{ts}.xlsx'
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as w:
            ms_df = pd.DataFrame(model_summaries).sort_values('avg_score', ascending=False)
            ms_df.to_excel(w, sheet_name='model_summaries', index=False)
            cat_rows = []
            for cat, mdata in category_comparison.items():
                for m, v in mdata.items():
                    cat_rows.append({'category': cat, 'model': m, **v})
            if cat_rows:
                pd.DataFrame(cat_rows).to_excel(w, sheet_name='by_category', index=False)
        print(f'XLSX: {xlsx_path}')
    except ImportError:
        print('pandas/openpyxl unavailable; XLSX skipped')

    n_full = sum(1 for m in model_summaries if m['total_cases'] == 1258)
    print(f'\nmodels with total_cases=1258: {n_full}/{len(model_summaries)}')


if __name__ == '__main__':
    main()
