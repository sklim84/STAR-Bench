"""One entry point that rebuilds every RQ output from a results directory.

    python -m _experiments.scripts.regenerate_analysis --list
    python -m _experiments.scripts.regenerate_analysis --all
    python -m _experiments.scripts.regenerate_analysis --only rq4_ablation,main_table
    python -m _experiments.scripts.regenerate_analysis --all \
        --results-root _experiments/runs
    python -m _experiments.scripts.regenerate_analysis --copy-to-manuscript ../STAR-Bench-manu/figures

The steps below are the whole analysis, in the order the paper reads them, so
regenerating a number does not depend on knowing which script to run and when.
A script that is not a step here produces nothing the manuscript reads.

Every step names what it produces and which manuscript object reads it, so a
number in the paper can be traced to the script that made it and the results
directory that fed it. Nothing is copied into the manuscript unless
`--copy-to-manuscript` asks for it.

Steps whose script does not accept `--results-root` read the directories named
in their own header; the report says so for each step, and a step whose inputs
are missing is reported as SKIPPED rather than silently producing nothing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
FIGURES = ROOT / "_experiments" / "figures"


@dataclass
class Step:
    key: str
    module: str
    what: str                       # what it produces, and for which manuscript object
    inputs: tuple[str, ...] = ()    # results directories it reads, relative to the root
    outputs: tuple[str, ...] = ()
    args: tuple[str, ...] = ()
    results_root_option: str | None = None   # the option that redirects its inputs, if it has one
    extra: dict = field(default_factory=dict)


# The order is the order of the paper: the main table, then RQ1..RQ5, then the
# figures that read what those steps wrote.
STEPS: tuple[Step, ...] = (
    Step("main_table", "generate_main_table",
         "tab:overall single-turn columns (h, r, p, a, o)",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/main_table_single_turn.tex",
                  "_experiments/results_RQ1/main_table_single_turn.csv")),
    Step("full_models_table", "generate_full_models_table",
         "tab:full_models, the appendix table of every configuration",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/mt_oracle"),
         outputs=("_experiments/results_RQ1/",)),
    Step("rq1_model_bar", "RQ1_model_bar",
         "RQ1 per-model h and a bar chart",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/",)),
    Step("rq1_confusion", "RQ1_confusion_heatmap",
         "RQ1 tool-confusion heatmap (which tool was called instead)",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/",)),
    Step("rq1_validate_str", "RQ1_validate_str_failure_modes",
         "RQ1 validate_str_fields failure modes",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/",)),
    Step("rq2_fiu_keywords", "RQ2_lookup_fiu_keyword_analysis",
         "RQ2 lookup_fiu_reference_types keyword accuracy",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ2/",)),
    Step("rq2_reg_gap", "RQ2_regulatory_vs_analysis_gap",
         "RQ2 regulatory vs analysis category means",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ2/",)),
    Step("rq2_reg_figure", "generate_reg_vs_analysis",
         "fig:reg_vs_anal, the regulatory/analysis dumbbell",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/figures/fig_regulatory_vs_analysis_v2.png",
                  "_experiments/figures/fig_regulatory_vs_analysis_v2.pdf")),
    Step("rq3_context", "RQ3_context_accuracy_analysis",
         "RQ3 context accuracy against scenario completion",
         inputs=("_experiments/runs/eval/mt_oracle", "_experiments/runs/eval/single"),
         outputs=("_experiments/results_RQ3/",)),
    Step("rq3_propagation", "RQ3_error_propagation",
         "RQ3 error propagation across turns",
         inputs=("_experiments/runs/eval/mt_oracle",),
         outputs=("_experiments/results_RQ3/",)),
    Step("oracle_vs_real", "RQ_oracle_vs_real",
         "the oracle/end-to-end comparison table",
         inputs=("_experiments/runs/eval/mt_oracle", "_experiments/runs/eval/mt_e2e"),
         outputs=("_experiments/results_RQ3/oracle_vs_real.csv",)),
    Step("e2e_error_rates", "e2e_error_rates",
         "the end-to-end error and empty-result rates by cause (appendix caption)",
         inputs=("_experiments/runs/mt_e2e",),
         outputs=("_experiments/results_RQ3/e2e_error_rates.json",
                  "_experiments/results_RQ3/e2e_error_rates.md"),
         results_root_option="--results"),
    Step("str_quality", "RQ_str_generation_quality",
         "the STR generation quality table",
         inputs=("_experiments/runs/eval/mt_oracle", "_experiments/runs/mt_oracle",
                 "benchmarks_multiturn"),
         outputs=("_experiments/results_RQ3/",)),
    Step("rq4_ablation", "RQ4_query_tool_language_ablation",
         "the 2x2 query-language x tool-language ablation",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/single_entools_krq",
                 "_experiments/runs/eval/single_krtools_enq", "_experiments/runs/eval/single_entools_enq"),
         outputs=("_experiments/results_RQ4/four_way_ablation.csv",
                  "_experiments/results_RQ4/four_way_ablation_summary.json"),
         results_root_option="--results-root"),
    Step("rq4_thinking", "RQ4_thinking_effect",
         "RQ4 thinking-mode effect",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/mt_oracle"),
         outputs=("_experiments/results_RQ4/",)),
    Step("rq5_finance", "RQ5_finance_specialization",
         "RQ5 finance-specialised models against their bases",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ5/",)),
    Step("rq5_bfcl", "RQ5_bfcl_aml_correlation",
         "tab:bfcl_aml, general function-calling rank against tool hit here",
         inputs=("_experiments/runs/eval/single", "_experiments/bfcl_results/score"),
         outputs=("_experiments/results_RQ5/",)),
    Step("rq5_subdomain", "RQ5_subdomain_grouped_bar",
         "RQ5 per-subdomain grouped bar",
         inputs=("_experiments/results_RQ5",),
         outputs=("_experiments/results_RQ5/",)),
    Step("teaser", "generate_teaser",
         "fig:teaser, single-turn tool hit against workflow completion",
         inputs=("_experiments/runs/eval/single",
                 "_experiments/runs/eval/mt_oracle"),
         outputs=("_experiments/figures/",)),
    Step("subdomain_radar", "generate_subdomain_radar",
         "the introduction teaser radar",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/figures/fig_subdomain_radar.png",)),
    Step("kr_en_scatter", "generate_fig4_scatter_v2",
         "fig4_kr_en_scatter",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/single_krtools_enq"),
         outputs=("_experiments/figures/fig4_kr_en_scatter.png",)),
    Step("other_figures", "generate_new_figures",
         "the remaining paper figures, including fig_turnwise_line",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/mt_oracle"),
         outputs=("_experiments/figures/",)),
    Step("wilson_ci", "per_tool_wilson_ci",
         "per-tool and per-difficulty Wilson intervals",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/",)),
    Step("ranking_stability", "bootstrap_ranking_stability",
         "bootstrap Kendall tau ranking stability",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ1/",)),
    Step("mcnemar", "mcnemar_think_mode",
         "McNemar's test on the thinking pairs",
         inputs=("_experiments/runs/eval/single",),
         outputs=("_experiments/results_RQ4/",)),
    # The paper's own tables, written from the results above. They come last because
    # they read what the RQ steps wrote.
    Step("text_figures", "analysis.text_figures",
         "the figures the paper states in prose, Sections 4.2 to 4.4 and Appendices A, C, F, H and I",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/mt_oracle",
                 "_experiments/runs/eval/mt_e2e", "_experiments/human_eval/round2",
                 "_experiments/results_RQ2/regulatory_vs_analysis_gap.json",
                 "_experiments/results_RQ3/str_generation_quality.json"),
         outputs=("_experiments/results_RQ1/text_figures.json",)),
    Step("completion_gap_ci", "analysis.completion_gap_ci",
         "Section 4.4, the paired bootstrap interval and McNemar test on the completion spread",
         inputs=("_experiments/runs/eval/single", "_experiments/runs/eval/mt_oracle"),
         outputs=("_experiments/results_RQ3/completion_gap_ci.json",)),
    Step("manuscript_tables", "analysis.manuscript_tables",
         "tab:overall, tab:2x2_ablation, tab:e2e_full and tab:str-quality",
         inputs=("_experiments/runs/eval", "_experiments/results_RQ3/str_generation_quality.csv"),
         outputs=("_experiments/paper_tables/",)),
    Step("bfcl_table", "analysis.bfcl_table",
         "tab:bfcl_aml, the BFCL against STAR-Bench ranking",
         inputs=("_experiments/results_RQ5/bfcl_aml_paired.json",),
         outputs=("_experiments/paper_tables/tab-bfcl-aml.tex",)),
    Step("str_section_coverage", "analysis.str_section_coverage",
         "tab:str_section_coverage, the gold STR narrative coverage",
         inputs=("benchmarks_multiturn/cases_str_workflow.json",),
         outputs=("_experiments/paper_tables/tab-str-section-coverage.tex",)),
    Step("str_human_agreement", "analysis.str_human_agreement",
         "tab:str_human_agreement and Appendix F, checker against the two expert raters",
         inputs=("_experiments/human_eval/round2",),
         outputs=("_experiments/human_eval/round2/agreement.json",
                  "_experiments/paper_tables/tab-str-human-agreement.tex"),
         args=("--mapping", "_experiments/human_eval/round2/str_eval_mapping.json",
               "--ratings", "_experiments/human_eval/round2/A.json",
               "_experiments/human_eval/round2/B.json",
               "--out", "_experiments/human_eval/round2/agreement.json", "--table")),
)

BY_KEY = {step.key: step for step in STEPS}


def _missing_inputs(step: Step, results_root: Path | None) -> list[str]:
    """The inputs a step needs and does not have.

    A step that accepts `--results-root` is handed that directory verbatim, so
    that directory is what has to exist; the rest read the directories named in
    their own header.
    """
    if results_root is not None and step.results_root_option:
        return [] if results_root.exists() else [str(results_root)]
    missing = []
    for rel in step.inputs:
        path = Path(rel)
        candidate = path if path.is_absolute() else ROOT / path
        if not candidate.exists():
            missing.append(str(path))
    return missing


def run_step(step: Step, *, results_root: Path | None, dry_run: bool, timeout: int) -> dict:
    argv = [sys.executable, "-m", f"_experiments.scripts.{step.module}", *step.args]
    if results_root is not None and step.results_root_option:
        argv += [step.results_root_option, str(results_root)]
    missing = _missing_inputs(step, results_root)
    row = {"step": step.key, "module": step.module, "what": step.what,
           "command": " ".join(argv), "inputs": list(step.inputs),
           "outputs": list(step.outputs),
           "takes_results_root": bool(step.results_root_option)}
    if missing:
        return {**row, "status": "skipped", "detail": f"missing input(s): {', '.join(missing)}"}
    if dry_run:
        return {**row, "status": "dry-run", "detail": ""}

    started = time.time()
    done = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    tail = (done.stdout.strip() + "\n" + done.stderr.strip()).strip().splitlines()[-3:]
    return {**row, "status": "ok" if done.returncode == 0 else "failed",
            "returncode": done.returncode, "elapsed_s": round(time.time() - started, 1),
            "detail": "\n".join(tail)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="run every step")
    ap.add_argument("--only", help="comma-separated step keys")
    ap.add_argument("--list", action="store_true", help="print the steps and what they produce")
    ap.add_argument("--results-root",
                    help="directory holding the run outputs. It is passed verbatim to the steps "
                         "whose script accepts it (the report says which); the others read the "
                         "directories named in their own header")
    ap.add_argument("--dry-run", action="store_true", help="print the commands and stop")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per step")
    ap.add_argument("--report", help="write the JSON report here")
    ap.add_argument("--copy-to-manuscript", metavar="DIR",
                    help="after the steps, copy _experiments/figures/*.{png,pdf} into DIR. "
                         "This is the only thing that writes outside this repository")
    args = ap.parse_args(argv)

    if args.list:
        for step in STEPS:
            print(f"{step.key:20s} {step.module:38s} {step.what}")
        return 0
    if not args.all and not args.only and not args.copy_to_manuscript:
        ap.error("pass --all, --only <keys>, --list or --copy-to-manuscript")

    keys = [k.strip() for k in args.only.split(",")] if args.only else list(BY_KEY)
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        print(f"unknown step(s): {', '.join(unknown)}; known: {', '.join(BY_KEY)}", file=sys.stderr)
        return 2

    results_root = Path(args.results_root) if args.results_root else None
    if results_root is not None and not results_root.is_absolute():
        results_root = ROOT / results_root

    rows = []
    if args.all or args.only:
        for key in keys:
            step = BY_KEY[key]
            row = run_step(step, results_root=results_root, dry_run=args.dry_run,
                           timeout=args.timeout)
            rows.append(row)
            mark = {"ok": "ok  ", "failed": "FAIL", "skipped": "SKIP", "dry-run": "--  "}[row["status"]]
            print(f"[{mark}] {step.key:20s} {step.what}")
            if row["status"] in ("failed", "skipped") and row["detail"]:
                print(f"         {row['detail'].splitlines()[0]}")

    copied = []
    if args.copy_to_manuscript:
        from _experiments.scripts._figure_out import copy_to_manuscript

        copied = copy_to_manuscript(args.copy_to_manuscript)
        print(f"copied {len(copied)} figure(s) into {args.copy_to_manuscript}")

    failed = [r for r in rows if r["status"] == "failed"]
    skipped = [r for r in rows if r["status"] == "skipped"]
    if rows:
        print(f"\n{len(rows) - len(failed) - len(skipped)} ok, {len(failed)} failed, "
              f"{len(skipped)} skipped")
        for row in failed:
            print(f"  FAILED {row['step']}: {row['command']}")

    if args.report:
        payload = {"results_root": str(results_root) if results_root else None,
                   "steps": rows, "copied_to_manuscript": copied}
        Path(args.report).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        print(f"report: {args.report}")
    return 1 if failed else 0


if __name__ == "__main__":
    if __package__ in (None, ""):
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
