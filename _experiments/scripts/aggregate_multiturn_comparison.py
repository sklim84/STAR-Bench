#!/usr/bin/env python3
"""results_mt/eval/multiturn_<model>.json 29개를 단일 comparison_<ts>.{json,xlsx}로 통합.

benchmark.py --comparison-only가 싱글턴 결과만 처리하므로 멀티턴용 별도 통합 스크립트.
results_kr/results_en의 comparison_*.json 구조와 유사한 단일 통합본 생성.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path('_experiments/results_mt/eval')
OUT_DIR = Path('_experiments/results_mt')


def main():
    files = sorted(EVAL_DIR.glob('multiturn_*.json'))
    if not files:
        print(f'No multiturn results found in {EVAL_DIR}')
        sys.exit(1)

    rows = []
    by_sub_cat = {}
    for f in files:
        d = json.load(f.open())
        model_id = d.get('model_id') or d.get('model')
        overall = d.get('overall', {})
        rows.append({
            'model': model_id,
            'provider': d.get('provider'),
            'think': d.get('think'),
            'timestamp': d.get('timestamp'),
            'total_scenarios': d.get('total_scenarios'),
            'total_elapsed_sec': d.get('total_elapsed_sec'),
            'avg_score': overall.get('avg_score'),
            'avg_tool_hit': overall.get('avg_tool_hit'),
            'avg_param_accuracy': overall.get('avg_param_accuracy'),
            'context_accuracy': overall.get('context_accuracy'),
            'scenario_complete_rate': overall.get('scenario_complete_rate'),
        })
        for sub_cat, m in d.get('by_sub_category', {}).items():
            by_sub_cat.setdefault(sub_cat, {})[model_id] = m

    rows.sort(key=lambda r: -(r['avg_tool_hit'] or 0))

    summary = {
        'generated_at': datetime.now().isoformat(),
        'n_models': len(rows),
        'eval_dir': str(EVAL_DIR),
        'rows': rows,
        'by_sub_category': by_sub_cat,
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = OUT_DIR / f'comparison_{ts}.json'
    with json_path.open('w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'JSON saved: {json_path}')

    try:
        import pandas as pd
        xlsx_path = OUT_DIR / f'comparison_{ts}.xlsx'
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df_overall = pd.DataFrame(rows)
            df_overall.to_excel(writer, sheet_name='overall', index=False)
            sub_cat_table = []
            for sub_cat, model_metrics in sorted(by_sub_cat.items()):
                for model, m in model_metrics.items():
                    sub_cat_table.append({
                        'sub_category': sub_cat,
                        'model': model,
                        **{k: v for k, v in m.items() if not isinstance(v, (dict, list))},
                    })
            if sub_cat_table:
                pd.DataFrame(sub_cat_table).to_excel(writer, sheet_name='by_sub_category', index=False)
        print(f'XLSX saved: {xlsx_path}')
    except ImportError:
        print('pandas/openpyxl not installed; XLSX skipped')

    print(f'\n=== summary (n={len(rows)}) ===')
    print(f"{'model':<55} {'h_bar':>7} {'a_bar':>7} {'ctx':>7} {'c':>7}")
    for r in rows:
        print(f"{r['model']:<55} "
              f"{(r['avg_tool_hit'] or 0):>7.4f} "
              f"{(r['avg_param_accuracy'] or 0):>7.4f} "
              f"{(r['context_accuracy'] or 0):>7.4f} "
              f"{(r['scenario_complete_rate'] or 0):>7.4f}")


if __name__ == '__main__':
    main()
