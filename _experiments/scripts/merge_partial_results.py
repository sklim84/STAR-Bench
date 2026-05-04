#!/usr/bin/env python3
"""부분 재실험 결과를 기존 checkpoint + eval JSON과 머지.

사용 시나리오:
  1. `benchmark.py --case-ids X,Y,Z --force-rerun` 으로 특정 케이스 재실험
     → checkpoint 파일에 신규 record append (case_id 중복 발생)
  2. 본 스크립트로:
     (a) checkpoint compact: 동일 (category, case_id) 중 최신 record만 유지하여 rewrite
     (b) eval JSON 재집계: by_category aggregated + overall 재계산
     (c) 신규 eval_<model>_<timestamp>.json 저장 + 비교용 백업

Usage:
    python merge_partial_results.py \\
        --output-dir _paper/_experiments/results_kr \\
        --models <m1> <m2> ...

  또는 모든 모델:
    python merge_partial_results.py --output-dir _paper/_experiments/results_kr --all

Options:
    --no-compact-checkpoint  체크포인트 compact 스킵 (재집계만)
    --dry-run                실제 파일 쓰지 않고 변경 요약만 출력
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# benchmark.py 의 aggregate_results / normalize_parse_fail_result 재사용
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from benchmark import (  # type: ignore
    aggregate_results,
    normalize_parse_fail_result,
    _sanitize_model_name,
)


def compact_checkpoint(ckpt_path: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """체크포인트 JSONL을 compact: 동일 (category, case_id)는 최신 record만 유지.

    Returns: (total_lines, unique_keys, duplicates_removed)
    """
    if not ckpt_path.exists():
        return 0, 0, 0
    records: dict[tuple[str, str], dict] = {}
    total = 0
    with ckpt_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
                key = (rec.get("category", ""), rec.get("case_id", ""))
                if not all(key):
                    continue
                if rec.get("error_type") == "parse_fail":
                    rec = normalize_parse_fail_result(rec)
                records[key] = rec  # 최신이 win
            except json.JSONDecodeError:
                continue
    duplicates = total - len(records)
    if duplicates > 0 and not dry_run:
        # 백업 후 rewrite
        backup = ckpt_path.with_suffix(ckpt_path.suffix + ".pre-compact.bak")
        shutil.copy2(ckpt_path, backup)
        with ckpt_path.open("w", encoding="utf-8") as f:
            for rec in records.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return total, len(records), duplicates


def find_latest_eval(output_dir: Path, model_safe: str) -> Path | None:
    eval_dir = output_dir / "eval"
    if not eval_dir.exists():
        return None
    candidates = sorted(eval_dir.glob(f"eval_{model_safe}_*.json"))
    return candidates[-1] if candidates else None


def reaggregate_eval(ckpt_path: Path, model_id: str, provider: str | None,
                     think: bool | None) -> dict:
    """compact된 체크포인트에서 eval payload 재구성."""
    by_cat_records: dict[str, list[dict]] = defaultdict(list)
    with ckpt_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cat = rec.get("category", "")
            if not cat:
                continue
            if rec.get("error_type") == "parse_fail":
                rec = normalize_parse_fail_result(rec)
            # benchmark.py 의 case_results 와 동일 형태로 dict 구성 (model/category 키 제거)
            case_dict = {k: v for k, v in rec.items()
                         if k not in ("model", "category")}
            by_cat_records[cat].append(case_dict)

    by_category = {}
    all_results: list[dict] = []
    for cat, records in by_cat_records.items():
        agg = aggregate_results(records)
        by_category[cat] = {
            "aggregated": agg,
            "per_case": records,
            "elapsed_sec": None,  # 재집계 시점에는 카테고리별 누적 elapsed 미보유
        }
        all_results.extend(records)
    overall = aggregate_results(all_results)
    return {
        "model": model_id,
        "provider": provider,
        "think": think,
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(all_results),
        "total_elapsed_sec": None,
        "by_category": by_category,
        "overall": overall,
        "_merged_from_partial": True,
    }


def merge_one_model(output_dir: Path, model_id: str,
                    compact: bool, dry_run: bool) -> dict:
    """단일 모델의 checkpoint compact + eval 재집계."""
    safe = _sanitize_model_name(model_id)
    ckpt = output_dir / "checkpoint" / f"checkpoint_{safe}.jsonl"
    if not ckpt.exists():
        return {"model": model_id, "skipped": "checkpoint not found"}

    # 1) checkpoint compact
    total_lines = unique = dups = 0
    if compact:
        total_lines, unique, dups = compact_checkpoint(ckpt, dry_run=dry_run)

    # 2) provider/think 정보는 기존 eval JSON에서 읽기
    prev_eval = find_latest_eval(output_dir, safe)
    provider = think = None
    if prev_eval and prev_eval.exists():
        try:
            d = json.loads(prev_eval.read_text(encoding="utf-8"))
            provider = d.get("provider")
            think = d.get("think")
        except Exception:
            pass

    # 3) eval 재집계
    new_eval = reaggregate_eval(ckpt, model_id, provider, think)

    # 4) 저장 (이전 eval은 *.pre-merge.bak 으로 백업)
    out_payload_path = None
    if not dry_run:
        if prev_eval:
            backup = prev_eval.with_suffix(prev_eval.suffix + ".pre-merge.bak")
            if not backup.exists():
                shutil.copy2(prev_eval, backup)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_payload_path = output_dir / "eval" / f"eval_{safe}_{ts}.json"
        out_payload_path.parent.mkdir(parents=True, exist_ok=True)
        out_payload_path.write_text(
            json.dumps(new_eval, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "model": model_id,
        "checkpoint_lines_before": total_lines,
        "checkpoint_unique_keys": unique,
        "checkpoint_duplicates_removed": dups,
        "previous_eval": str(prev_eval) if prev_eval else None,
        "new_eval": str(out_payload_path) if out_payload_path else None,
        "total_cases": new_eval["total_cases"],
        "overall_h": new_eval["overall"].get("primary_tool_hit_rate"),
    }


def discover_models(output_dir: Path) -> list[str]:
    """checkpoint 디렉토리에서 모델 ID 후보 추출.

    안전한 파일명에서 모델 ID는 정확히 복원되지 않으므로 한계 있음.
    이 함수는 sanitize 된 파일명을 그대로 모델 ID로 반환한다 (전달받은 측에서 매핑 필요).
    """
    ckpt_dir = output_dir / "checkpoint"
    if not ckpt_dir.exists():
        return []
    return sorted(p.stem.replace("checkpoint_", "") for p in ckpt_dir.glob("checkpoint_*.jsonl"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", required=True,
                    help="결과 디렉토리 (예: _paper/_experiments/results_kr)")
    ap.add_argument("--models", nargs="*", default=None,
                    help="대상 모델 ID. 미지정 시 --all 또는 직접 명시 필요.")
    ap.add_argument("--all", action="store_true",
                    help="checkpoint 디렉토리의 모든 모델 처리 (sanitize 된 이름 기준)")
    ap.add_argument("--no-compact-checkpoint", action="store_true",
                    help="checkpoint compact 단계 스킵 (eval 재집계만)")
    ap.add_argument("--dry-run", action="store_true",
                    help="파일 쓰지 않고 변경 요약만 출력")
    args = ap.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"[error] output_dir not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    models = args.models or []
    if args.all:
        models = discover_models(output_dir)
        if not models:
            print(f"[error] no checkpoint files in {output_dir}/checkpoint/",
                  file=sys.stderr)
            sys.exit(1)
    if not models:
        print("[error] specify --models or --all", file=sys.stderr)
        sys.exit(1)

    summaries = []
    for m in models:
        try:
            s = merge_one_model(
                output_dir, m,
                compact=not args.no_compact_checkpoint,
                dry_run=args.dry_run,
            )
        except Exception as e:
            s = {"model": m, "error": str(e)}
        summaries.append(s)
        print(json.dumps(s, ensure_ascii=False))

    print("\n=== 요약 ===")
    print(f"처리 모델: {len(summaries)}")
    print(f"성공: {sum(1 for s in summaries if 'new_eval' in s and s['new_eval'])}")
    print(f"스킵/오류: {sum(1 for s in summaries if 'error' in s or 'skipped' in s)}")


if __name__ == "__main__":
    main()
