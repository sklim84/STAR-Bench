"""Post-rescore 체크포인트 → eval JSON 오프라인 집계.

기존 eval_*.json 파일을 체크포인트(리스코어링 반영)에서 재생성한다.
벤치마크 재실행 없이 현행 checkpoint 데이터만으로 aggregation을 다시 수행하여
figure 생성 스크립트(_experiments/figures/generate_*.py)가 사용할 최신 eval JSON을 만든다.

Usage:
    python -m _experiments.scripts.aggregate_checkpoints_to_eval
"""
from __future__ import annotations
import json
import glob
import os
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

_SB = Path(__file__).resolve().parents[2]  # star-bench root
PROJECT_ROOT = _SB
BENCHMARKS = PROJECT_ROOT / 'benchmarks'

# Condition별 eval output 경로
CONDITIONS = {
    'round1': PROJECT_ROOT / '_experiments' / 'results' / 'round1',
    'round2': PROJECT_ROOT / '_experiments' / 'results' / 'round2',
    'round3': PROJECT_ROOT / '_experiments' / 'results' / 'round3',
    'round1_en': PROJECT_ROOT / '_experiments' / 'results' / 'round1_en',
    'round2_en': PROJECT_ROOT / '_experiments' / 'results' / 'round2_en',
    'round3_en': PROJECT_ROOT / '_experiments' / 'results' / 'round3_en',
}


def load_case_metadata():
    """benchmarks/cases_*.json 에서 case_id → category 매핑 구축."""
    id_to_cat = {}
    for p in sorted(BENCHMARKS.glob('cases_*.json')):
        # 파일명: cases_<category>.json
        m = re.match(r'cases_(.+)\.json', p.name)
        cat = m.group(1) if m else p.stem
        with open(p) as f:
            for c in json.load(f):
                id_to_cat[c['id']] = cat
    return id_to_cat


def aggregate_metric_list(records: list[dict]) -> dict:
    """공통 aggregation 로직 (per-category, overall 둘 다 사용)."""
    if not records:
        return {}
    n = len(records)

    def m(k, default=0.0):
        return sum(r.get(k, default) or default for r in records) / n

    hit = sum(1 for r in records if r.get('primary_tool_hit')) / n
    hallu = sum(int(r.get('hallucinated_param_count', 0) or 0) for r in records)

    by_diff = defaultdict(list)
    for r in records:
        by_diff[r.get('difficulty', 'unknown')].append(r.get('score', 0.0) or 0.0)
    diff_out = {
        k: {'count': len(v), 'avg_score': round(sum(v) / len(v), 4)}
        for k, v in by_diff.items()
    }

    err_counts = defaultdict(int)
    for r in records:
        err_counts[r.get('error_type', 'unknown')] += 1

    return {
        'total': n,
        'avg_score': round(m('score'), 4),
        'primary_tool_hit_rate': round(hit, 4),
        'avg_tool_recall': round(m('tool_recall'), 4),
        'avg_tool_precision': round(m('tool_precision'), 4),
        'avg_param_accuracy': round(m('param_accuracy'), 4),
        'avg_param_key_accuracy': round(m('param_key_accuracy'), 4),
        'avg_order_score': round(m('order_score'), 4),
        'total_hallucinated_params': hallu,
        'by_difficulty': diff_out,
        'by_error_type': dict(err_counts),
    }


def aggregate_checkpoint(checkpoint_path: Path, id_to_cat: dict) -> dict:
    """단일 체크포인트 → eval dict."""
    records = []
    with open(checkpoint_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # 모델명/provider 추출
    model_id = records[0].get('model', 'unknown') if records else 'unknown'

    # Category 그룹핑
    by_cat_records = defaultdict(list)
    for r in records:
        cat = id_to_cat.get(r.get('id'), 'unknown')
        by_cat_records[cat].append(r)

    by_category = {}
    for cat, recs in sorted(by_cat_records.items()):
        by_category[cat] = {
            'aggregated': aggregate_metric_list(recs),
            # per_case는 figure에서 사용 안 하므로 생략 (파일 크기 절약)
        }

    overall = aggregate_metric_list(records)

    return {
        'model': model_id,
        'provider': 'vllm',  # 대부분 vLLM; 원본 eval 파일에서 추출 가능하지만 단순화
        'think': None,
        'timestamp': datetime.now().isoformat(),
        'total_cases': len(records),
        'total_elapsed_sec': 0.0,  # 오프라인 집계라 의미 없음
        'by_category': by_category,
        'overall': overall,
    }


def main():
    id_to_cat = load_case_metadata()
    print(f"Loaded {len(id_to_cat)} case IDs")

    total_written = 0
    for cond_name, cond_dir in CONDITIONS.items():
        ckpt_dir = cond_dir / 'checkpoint'
        eval_dir = cond_dir / 'eval'
        if not ckpt_dir.is_dir():
            print(f"[{cond_name}] checkpoint 디렉토리 없음, skip")
            continue
        eval_dir.mkdir(exist_ok=True)

        # 기존 eval_*.json 백업 (한 번만)
        existing = sorted(eval_dir.glob('eval_*.json'))
        if existing and not any('_old.json' in str(p) for p in existing):
            for p in existing:
                p.rename(p.with_suffix('.json.old'))

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        written = 0
        for ckpt in sorted(ckpt_dir.glob('checkpoint_*.jsonl')):
            safe = ckpt.stem.replace('checkpoint_', '')
            try:
                eval_data = aggregate_checkpoint(ckpt, id_to_cat)
                out_path = eval_dir / f'eval_{safe}_{ts}.json'
                with open(out_path, 'w') as f:
                    json.dump(eval_data, f, ensure_ascii=False)
                written += 1
            except Exception as e:
                print(f"  [{cond_name}] {safe}: ERROR {e}")

        print(f"[{cond_name}] {written} eval files written")
        total_written += written

    print(f"\nTotal: {total_written} eval files regenerated from post-rescore checkpoints")


if __name__ == '__main__':
    main()
