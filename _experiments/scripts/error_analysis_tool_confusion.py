#!/usr/bin/env python3
"""
Tool Confusion Matrix Analysis for AML-Bench wrong_func errors.

Analyzes round1 (KR) checkpoint data across all 44 models to understand
which tools get confused with which, and whether confusions are universal
or model-specific.

Output: _experiments/results/error_analysis_tool_confusion.json
"""

import json
import glob
import os
from collections import Counter, defaultdict
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parents[2]
CKPT_DIR = BASE / "_experiments" / "results" / "round1" / "checkpoint"
OUT_PATH = BASE / "_experiments" / "results" / "error_analysis_tool_confusion.json"

TOTAL_CASES = 1258  # benchmark case count


def load_all_records():
    """Load all checkpoint records, deduplicating by keeping last entry per (model, case_id)."""
    files = sorted(CKPT_DIR.glob("checkpoint_*.jsonl"))
    print(f"Found {len(files)} checkpoint files")

    all_records = []
    for fpath in files:
        # Deduplicate: keep last entry per case_id within a file
        seen = {}
        with open(fpath) as f:
            for line in f:
                rec = json.loads(line.strip())
                seen[rec["case_id"]] = rec
        records = list(seen.values())
        all_records.extend(records)
        model = records[0]["model"] if records else fpath.stem
        if len(records) != TOTAL_CASES:
            print(f"  WARN: {fpath.name} has {len(records)} unique cases (expected {TOTAL_CASES})")

    print(f"Total records loaded: {len(all_records)}")
    return all_records


def analyze_confusion(records):
    """Build confusion matrix and derive all analysis outputs."""

    # ── 1. Filter wrong_func records ──
    wrong_func = [r for r in records if r["error_type"] == "wrong_func"]
    print(f"\nwrong_func records: {len(wrong_func)} out of {len(records)} total")

    # ── 2. Build confusion matrix: expected -> called -> count ──
    confusion_matrix = defaultdict(Counter)
    # Also track per-model confusion
    per_model_confusion = defaultdict(lambda: defaultdict(Counter))

    no_call_count = 0
    for rec in wrong_func:
        expected = rec["category"]
        called_tools = rec["called_tools"]
        model = rec["model"]

        if not called_tools:
            # No tool was called at all
            called = "<no_call>"
            no_call_count += 1
        else:
            called = called_tools[0]

        confusion_matrix[expected][called] += 1
        per_model_confusion[model][expected][called] += 1

    print(f"  Records with no tool call: {no_call_count}")

    # ── 3. Top-20 confusion pairs ──
    pair_counts = Counter()
    for expected, called_counts in confusion_matrix.items():
        for called, cnt in called_counts.items():
            pair_counts[(expected, called)] += cnt

    top20 = pair_counts.most_common(20)
    total_wrong = len(wrong_func)

    print("\n" + "=" * 80)
    print("TOP-20 CONFUSION PAIRS (expected -> called)")
    print("=" * 80)
    print(f"{'Rank':<5} {'Expected Tool':<35} {'Called Tool':<35} {'Count':>6} {'%':>7}")
    print("-" * 90)
    top20_list = []
    for i, ((exp, cal), cnt) in enumerate(top20, 1):
        pct = cnt / total_wrong * 100
        print(f"{i:<5} {exp:<35} {cal:<35} {cnt:>6} {pct:>6.1f}%")
        top20_list.append({
            "rank": i,
            "expected": exp,
            "called": cal,
            "count": cnt,
            "pct_of_wrong_func": round(pct, 2)
        })

    # ── 4. Per-category: most confused tools ──
    print("\n" + "=" * 80)
    print("PER-CATEGORY CONFUSION BREAKDOWN")
    print("=" * 80)
    per_category = {}
    all_categories = sorted(set(r["category"] for r in records))

    for cat in all_categories:
        if cat not in confusion_matrix:
            continue
        total_cat_wrong = sum(confusion_matrix[cat].values())
        top_confused = confusion_matrix[cat].most_common(5)
        per_category[cat] = {
            "total_wrong_func": total_cat_wrong,
            "top_confusions": [
                {"called": c, "count": n, "pct": round(n / total_cat_wrong * 100, 1)}
                for c, n in top_confused
            ]
        }
        top_str = ", ".join(f"{c}({n})" for c, n in top_confused[:3])
        print(f"  {cat:<35} wrong={total_cat_wrong:>5}  top: {top_str}")

    # ── 5. Confusion clusters ──
    # Build undirected weighted graph of confusions, find connected components
    # where both directions have significant confusion
    print("\n" + "=" * 80)
    print("CONFUSION CLUSTERS (bidirectional confusion pairs)")
    print("=" * 80)

    # Find bidirectional pairs
    bidir_pairs = []
    all_tools = set()
    for (exp, cal), cnt in pair_counts.items():
        if cal == "<no_call>":
            continue
        reverse_cnt = pair_counts.get((cal, exp), 0)
        if reverse_cnt > 0 and exp < cal:  # avoid duplicates
            bidir_pairs.append({
                "tool_a": exp,
                "tool_b": cal,
                "a_to_b": cnt,
                "b_to_a": reverse_cnt,
                "total": cnt + reverse_cnt
            })
            all_tools.add(exp)
            all_tools.add(cal)

    bidir_pairs.sort(key=lambda x: x["total"], reverse=True)

    # Build adjacency for clustering (union-find)
    parent = {}
    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Only cluster tools with significant bidirectional confusion (>= 5 total)
    CLUSTER_THRESHOLD = 5
    for p in bidir_pairs:
        if p["total"] >= CLUSTER_THRESHOLD:
            union(p["tool_a"], p["tool_b"])

    clusters = defaultdict(set)
    for t in all_tools:
        root = find(t)
        if root != t or any(find(p["tool_a"]) == find(t) or find(p["tool_b"]) == find(t) for p in bidir_pairs if p["total"] >= CLUSTER_THRESHOLD):
            clusters[find(t)].add(t)

    # Filter to clusters with >1 member
    cluster_list = []
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        # Get internal confusion pairs
        internal = [p for p in bidir_pairs if p["tool_a"] in members and p["tool_b"] in members]
        cluster_list.append({
            "tools": sorted(members),
            "internal_pairs": internal,
            "total_confusion": sum(p["total"] for p in internal)
        })
    cluster_list.sort(key=lambda x: x["total_confusion"], reverse=True)

    for i, cl in enumerate(cluster_list, 1):
        tools_str = ", ".join(cl["tools"])
        print(f"\n  Cluster {i} (total confusions: {cl['total_confusion']}):")
        print(f"    Tools: {tools_str}")
        for p in sorted(cl["internal_pairs"], key=lambda x: x["total"], reverse=True)[:5]:
            print(f"      {p['tool_a']} <-> {p['tool_b']}: {p['a_to_b']} + {p['b_to_a']} = {p['total']}")

    # ── 6. Universal vs model-specific confusions ──
    print("\n" + "=" * 80)
    print("UNIVERSAL vs MODEL-SPECIFIC CONFUSIONS")
    print("=" * 80)

    all_models = sorted(set(r["model"] for r in records))
    n_models = len(all_models)

    # For top-20 pairs, check how many models exhibit this confusion
    pair_model_counts = defaultdict(set)
    for model, cat_data in per_model_confusion.items():
        for expected, called_counts in cat_data.items():
            for called, cnt in called_counts.items():
                pair_model_counts[(expected, called)].add(model)

    print(f"\nTotal models: {n_models}")
    print(f"\n{'Expected':<35} {'Called':<35} {'Models':>7} {'Universal?':<12} {'Count':>6}")
    print("-" * 100)

    universal_pairs = []
    model_specific_pairs = []

    for (exp, cal), cnt in pair_counts.most_common(30):
        n_model_with = len(pair_model_counts[(exp, cal)])
        pct_models = n_model_with / n_models * 100
        is_universal = pct_models >= 50
        label = "UNIVERSAL" if is_universal else f"specific ({n_model_with})"
        print(f"  {exp:<35} {cal:<35} {n_model_with:>3}/{n_models:<3} {label:<12} {cnt:>6}")

        entry = {
            "expected": exp,
            "called": cal,
            "count": cnt,
            "model_count": n_model_with,
            "model_pct": round(pct_models, 1)
        }
        if is_universal:
            universal_pairs.append(entry)
        else:
            model_specific_pairs.append(entry)

    # ── 6b. Which models have the most unique confusions? ──
    print("\n" + "-" * 60)
    print("MODELS WITH MOST UNIQUE CONFUSION PATTERNS")
    print("-" * 60)

    model_unique = {}
    for model in all_models:
        unique_count = 0
        for expected, called_counts in per_model_confusion[model].items():
            for called, cnt in called_counts.items():
                if len(pair_model_counts[(expected, called)]) == 1:
                    unique_count += cnt
        model_unique[model] = unique_count

    for model, cnt in sorted(model_unique.items(), key=lambda x: x[1], reverse=True)[:10]:
        total_model_wrong = sum(
            sum(cc.values()) for cc in per_model_confusion[model].values()
        )
        print(f"  {model:<50} unique={cnt:>4}  total_wrong={total_model_wrong:>5}")

    # ── 7. Full confusion matrix (for JSON output) ──
    matrix_dict = {}
    for exp in all_categories:
        row = {}
        for cal, cnt in confusion_matrix.get(exp, {}).items():
            row[cal] = cnt
        if row:
            matrix_dict[exp] = row

    # ── Assemble output ──
    output = {
        "summary": {
            "total_records": len(records),
            "total_wrong_func": total_wrong,
            "wrong_func_pct": round(total_wrong / len(records) * 100, 2),
            "no_call_count": no_call_count,
            "n_models": n_models,
            "n_categories": len(all_categories)
        },
        "top20_confusion_pairs": top20_list,
        "per_category_breakdown": per_category,
        "confusion_clusters": [
            {
                "tools": cl["tools"],
                "total_confusion": cl["total_confusion"],
                "pairs": [
                    {"a": p["tool_a"], "b": p["tool_b"],
                     "a_to_b": p["a_to_b"], "b_to_a": p["b_to_a"]}
                    for p in sorted(cl["internal_pairs"], key=lambda x: x["total"], reverse=True)
                ]
            }
            for cl in cluster_list
        ],
        "universality": {
            "universal_pairs_gte50pct_models": universal_pairs,
            "model_specific_pairs_lt50pct": model_specific_pairs[:20],
        },
        "confusion_matrix": matrix_dict,
    }

    return output


def main():
    records = load_all_records()
    output = analyze_confusion(records)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {OUT_PATH}")


if __name__ == "__main__":
    main()
