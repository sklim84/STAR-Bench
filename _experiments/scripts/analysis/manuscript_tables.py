"""The manuscript's data tables, written from the scored runs.

The four tables that carry numbers are generated rather than transcribed, so a
value in the paper and the value in the runs cannot disagree.

    python -m _experiments.scripts.analysis.manuscript_tables
    python -m _experiments.scripts.analysis.manuscript_tables --out <dir>

Written (default `_experiments/paper_tables/`, never over the manuscript):

    tab-exp-oveall.tex     tab:overall        h r p a o | h_bar a_bar c
    tab-2x2-ablation.tex   tab:2x2_ablation   tool schema x question language
    tab-e2e-subset.tex     tab:e2e-subset     oracle against end-to-end, 5 rows
    tab-e2e-full.tex       app:e2e_full       oracle against end-to-end, every row

A configuration the cohort has not scored yet is a row with dashes and its name,
not a row that quietly disappears: the caption says how many of the 28 are in,
and `--strict` refuses to write while any are out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _experiments.scripts.analysis import load  # noqa: E402
from _experiments.scripts.runner import registry  # noqa: E402

DEFAULT_OUT = _ROOT / "_experiments" / "paper_tables"
GROUP_ORDER = ("Korean-Specialized", "Finance-Specialized", "General-Purpose")
MISSING = "--"

# The bibliography key for each model, so a generated row cites what the hand-kept
# one cited. A model with no entry is a model the paper does not cite.
CITE = {
    "exaone-1.2b": "bae2025exaone", "exaone-32b": "bae2025exaone",
    "gpt-oss-20b-nt": "openai2025gptoss", "gpt-oss-20b-t": "openai2025gptoss",
    "gpt-oss-120b-nt": "openai2025gptoss", "gpt-oss-120b-t": "openai2025gptoss",
    "hermes-3-8b": "teknium2024hermes3",
    "kanana-2-inst": "kakao2025kanana", "kanana-2-think": "kakao2025kanana",
    "llama-3.2-3b": "grattafiori2024llama3", "llama-3.3-70b": "grattafiori2024llama3",
    "ministral-3b": "liu2026ministral3", "mistral-small": "mistral2025small",
    "phi-4-mini": "microsoft2025phi4mini",
    "xlam-3b": "prabhakar2025apigenmt", "xlam-70b": "prabhakar2025apigenmt",
    # Four Qwen configurations are evaluated and ref.bib carries all three cards;
    # without these keys they were the only served family the paper never cited.
    "qwen35-4b-nt": "qwen3.5", "qwen35-4b-t": "qwen3.5",
    "qwen35-27b-nt": "qwen3.5", "qwen35-27b-t": "qwen3.5",
    "qwen36-27b": "qwen3.6-27b", "qwen36-35b-a3b": "qwen36_35b_a3b",
}


def _fmt(value: float | None, places: int = 3) -> str:
    """A metric as the manuscript writes it: a dash when absent.

    The leading zero is kept. These columns reach 1.000, and a table that prints
    1.000 beside .906 reads as two conventions rather than one.
    """
    if value is None or value != value:
        return MISSING
    return f"{value:.{places}f}"


def _signed(value: float | None) -> str:
    if value is None or value != value:
        return MISSING
    text = _fmt(abs(value))
    return f"$-${text}" if value < 0 else text


def _rank_marks(values: dict[str, float], higher_is_better: bool = True) -> dict[str, str]:
    """Best in bold, second underlined, the way every column of tab:overall is set."""
    present = {k: v for k, v in values.items() if v is not None and v == v}
    if len(present) < 2:
        return {}
    order = sorted(present, key=lambda k: present[k], reverse=higher_is_better)
    marks = {order[0]: "textbf"}
    if len(order) > 1:
        marks[order[1]] = "underline"
    return marks


def _cell(value: float | None, mark: str | None) -> str:
    text = _fmt(value)
    return f"\\{mark}{{{text}}}" if mark and text != MISSING else text


def _label(config_id: str, labels: dict[str, str], *, cite: bool = True) -> str:
    text = labels.get(config_id, config_id).replace("&", "\\&")
    key = CITE.get(config_id)
    return f"{text}~\\cite{{{key}}}" if cite and key else text


def _means(frame, column: str, by: str = "config_id") -> dict[str, float]:
    """Mean over the rows that have the metric, which is not every row."""
    grouped = frame.groupby(by)[column]
    return {k: (None if v != v else float(v)) for k, v in grouped.mean().items()}


def _scored(setting: str, metric: str) -> dict[str, float]:
    """A multi-turn metric as the scorer wrote it.

    h_bar is "mean turn-level hit" (Section 4), so it is the mean over the 219
    turns and not over the 50 scenario means; those differ in the third decimal
    because scenarios hold different numbers of turns. Taking it from the
    scorer's own aggregate keeps one definition in the paper.
    """
    out = {}
    for config_id, aggregate in load.aggregates(setting).items():
        value = (aggregate.get(metric) or {}).get("mean")
        out[config_id] = None if value is None else float(value)
    return out


def _cohort_note(present: list[str]) -> str:
    total = len(registry.CONFIGS)
    if len(present) == total:
        return f"All {total} configurations are scored."
    absent = [c.config_id for c in registry.CONFIGS if c.config_id not in present]
    return (f"{len(present)} of {total} configurations are scored; "
            f"{', '.join(absent)} are still running and their rows are blank.")


def _table(lines: list[str], *, caption: str, label: str, spec: str, header: list[str],
           note: str, wrap: str | None = None, size: str = "footnotesize") -> str:
    """The table as the manuscript inputs it; `wrap` makes it a wraptable of that width."""
    open_env = f"\\begin{{wraptable}}{{r}}{{{wrap}}}" if wrap else "\\begin{table}[t]"
    close_env = "\\end{wraptable}" if wrap else "\\end{table}"
    pre = ["\\vspace{-12pt}"] if wrap else []
    post = ["\\vspace{-8pt}"] if wrap else []
    return "\n".join([
        f"% generated by _experiments/scripts/analysis/manuscript_tables.py",
        f"% {note}",
        open_env, *pre, "\\centering", f"\\{size}",
        "\\setlength{\\tabcolsep}{3pt}" if wrap else "",
        f"\\caption{{{caption}}}", f"\\label{{{label}}}",
        # A wrapped table is held to the width it declares: its natural width is a
        # few points wider, and wrapfig does not clip, it overprints the margin.
        "\\resizebox{\\linewidth}{!}{%" if wrap else "",
        f"\\begin{{tabular}}{{{spec}}}", "\\toprule", *header, "\\midrule",
        *lines, "\\bottomrule", "\\end{tabular}", "}" if wrap else "",
        *post, close_env, ""])


def main_table(out: Path) -> str:
    cases = load.single()
    oracle, _ = load.multiturn("oracle")
    labels = {c.config_id: c.label for c in registry.CONFIGS}
    groups = {c.config_id: c.group for c in registry.CONFIGS}
    present = sorted(set(cases["config_id"]))

    columns = {
        "h": _means(cases, "h"), "r": _means(cases, "r"), "p": _means(cases, "p"),
        "a": _means(cases, "a"), "o": _means(cases, "o"),
        "hbar": _scored("oracle", "h"), "abar": _scored("oracle", "a"),
        "c": _scored("oracle", "c"),
    }
    marks = {name: _rank_marks(values) for name, values in columns.items()}

    lines = []
    for group in GROUP_ORDER:
        members = [c.config_id for c in registry.CONFIGS if c.group == group]
        if not members:
            continue
        lines.append(f"\\multicolumn{{9}}{{l}}{{\\textbf{{{group}}}}} \\\\")
        lines.append("\\addlinespace[2pt]")
        members.sort(key=lambda cid: -(columns["h"].get(cid) or -1))
        for config_id in members:
            cells = [_cell(columns[name].get(config_id), marks[name].get(config_id))
                     for name in ("h", "r", "p", "a", "o", "hbar", "abar", "c")]
            # No per-row citation here: the main table is read for the numbers, and
            # every model it names is cited in the appendix tables that repeat it.
            lines.append(f"{_label(config_id, labels, cite=False)} & " + " & ".join(cells) + " \\\\")
        if group != GROUP_ORDER[-1]:
            lines.append("\\midrule")

    header = [
        "\\multicolumn{1}{c}{\\multirow{2}{*}{\\textbf{Model}}} & "
        "\\multicolumn{5}{c}{\\textbf{Single-turn}} & \\multicolumn{3}{c}{\\textbf{Multi-turn}} \\\\",
        "\\cmidrule(lr){2-6} \\cmidrule(lr){7-9}",
        " & $h$ & $r$ & $p$ & $a$ & $o$ & $\\bar{h}$ & $\\bar{a}$ & $c$ \\\\",
    ]
    text = _table(lines, spec="l ccccc ccc", header=header, label="tab:overall",
                  caption=("Overall per-model performance on \\method{} for all models (Korean "
                           "prompts). (T) and (NT) denote thinking mode on and off. Per column, "
                           "the best value is in \\textbf{bold} and the second is "
                           "\\underline{underlined}."),
                  note=_cohort_note(present))
    (out / "tab-exp-oveall.tex").write_text(text, encoding="utf-8")
    return f"tab-exp-oveall.tex: {len(present)} rows scored, {len(registry.CONFIGS)} in the cohort"


def ablation_table(out: Path) -> str:
    cells = {name: load.single(column=name) for name in load.COLUMNS}
    labels = {c.config_id: c.label for c in registry.CONFIGS}
    groups = {c.config_id: c.group for c in registry.CONFIGS}
    means = {name: _means(frame, "h") for name, frame in cells.items()}
    complete = sorted(set.intersection(*(set(m) for m in means.values())))

    lines = []
    for group in GROUP_ORDER:
        members = [cid for cid in complete if groups.get(cid) == group]
        if not members:
            continue
        lines.append(f"\\multicolumn{{5}}{{l}}{{\\textbf{{{group}}}}} \\\\")
        lines.append("\\addlinespace[2pt]")
        members.sort(key=lambda cid: -(means["single"].get(cid) or -1))
        for config_id in members:
            # The column head reads query language first, tool language second, which
            # is how Section 5 reads the table: "with Korean tool definitions,
            # English queries reach ... within 0.6 points" is columns one and two.
            cells_text = [_fmt(means[name].get(config_id))
                          for name in ("single", "krtools_enq", "entools_krq", "entools_enq")]
            lines.append(f"{_label(config_id, labels)} & " + " & ".join(cells_text) + " \\\\")
        if group != GROUP_ORDER[-1]:
            lines.append("\\midrule")

    header = ["\\multicolumn{1}{c}{\\textbf{Model}} & \\textbf{KR-KR} & \\textbf{EN-KR} & "
              "\\textbf{KR-EN} & \\textbf{EN-EN} \\\\"]
    text = _table(lines, spec="lcccc", header=header, label="tab:2x2_ablation",
                  caption=("Tool hit $h$ across query language $\\times$ tool definition language "
                           "(KR/EN), for the configurations run on all four cells; within each "
                           "group rows are sorted by the KR-KR baseline. (T)/(NT) denote thinking "
                           "mode on/off."),
                  note=f"{len(complete)} configurations have all four cells: {', '.join(complete)}")
    (out / "tab-2x2-ablation.tex").write_text(text, encoding="utf-8")
    return f"tab-2x2-ablation.tex: {len(complete)} configurations with all four cells"


def e2e_tables(out: Path, subset_rows: int = 5) -> str:
    oracle, _ = load.multiturn("oracle")
    e2e, _ = load.multiturn("e2e")
    labels = {c.config_id: c.label for c in registry.CONFIGS}
    windows = {c.config_id: c.model_window for c in registry.CONFIGS}
    o_h, o_c = _scored("oracle", "h"), _scored("oracle", "c")
    e_h, e_c = _scored("e2e", "h"), _scored("e2e", "c")
    scenarios = int(oracle["scenario_id"].nunique())

    ordered = sorted(o_h, key=lambda cid: -o_h[cid])
    no_e2e = [cid for cid in ordered if cid not in e_h]

    full = []
    for config_id in ordered:
        delta = None if config_id not in e_h else e_h[config_id] - o_h[config_id]
        full.append(f"{_label(config_id, labels)} & {_fmt(o_h[config_id])} & "
                    f"{_fmt(e_h.get(config_id))} & {_signed(delta)} & "
                    f"{_fmt(o_c[config_id])} & {_fmt(e_c.get(config_id))} \\\\")
    both = [cid for cid in ordered if cid in e_h]
    avg = lambda table, keys: sum(table[k] for k in keys) / len(keys) if keys else None
    full.append("\\midrule")
    full.append(f"Avg.\\ ({len(both)} configs) & {_fmt(avg(o_h, both))} & {_fmt(avg(e_h, both))} & "
                f"{_signed(avg(e_h, both) - avg(o_h, both))} & {_fmt(avg(o_c, both))} & "
                f"{_fmt(avg(e_c, both))} \\\\")

    reason = ""
    if no_e2e:
        named = ", ".join(f"{_label(cid, labels)} ({windows.get(cid)} tokens)" for cid in no_e2e)
        reason = (f" {len(no_e2e)} configurations have no end-to-end column because their context "
                  f"window is under the setting's: {named}.")
    header_full = ["\\multicolumn{1}{c}{\\textbf{Configuration}} & \\textbf{Oracle $\\bar{h}$} & "
                   "\\textbf{E2E $\\bar{h}$} & \\textbf{$\\Delta\\bar{h}$} & "
                   "\\textbf{Oracle $c$} & \\textbf{E2E $c$} \\\\"]
    (out / "tab-e2e-full.tex").write_text(
        _table(full, spec="lccccc", header=header_full, label="tab:e2e_full",
               caption=(f"Oracle versus end-to-end (E2E) evaluation over the {scenarios} "
                        f"multi-turn STR scenarios, sorted by oracle $\\bar{{h}}$.{reason}"),
               note=_cohort_note(sorted(o_h))), encoding="utf-8")

    top = both[:subset_rows]
    subset = [f"{_label(cid, labels)} & {_fmt(o_h[cid])} & {_fmt(e_h[cid])} & "
              f"{_fmt(o_c[cid])} & {_fmt(e_c[cid])} \\\\" for cid in top]
    subset.append("\\midrule")
    subset.append(f"Avg.\\ ({len(both)} configs) & {_fmt(avg(o_h, both))} & {_fmt(avg(e_h, both))} & "
                  f"{_fmt(avg(o_c, both))} & {_fmt(avg(e_c, both))} \\\\")
    header_subset = [
        " & \\multicolumn{2}{c}{$\\bar{h}$} & \\multicolumn{2}{c}{$c$} \\\\",
        "\\cmidrule(lr){2-3}\\cmidrule(l){4-5}",
        "\\multicolumn{1}{c}{\\textbf{Model}} & Oracle & E2E & Oracle & E2E \\\\",
    ]
    (out / "tab-e2e-subset.tex").write_text(
        _table(subset, spec="@{}lcccc@{}", header=header_subset, label="tab:e2e-subset",
               caption=(f"Oracle versus end-to-end (E2E) execution on the {scenarios} STR-writing "
                        f"scenarios for the highest-scoring models. "
                        f"Appendix~\\ref{{app:e2e_full}} reports every configuration."),
               note=_cohort_note(sorted(o_h))), encoding="utf-8")
    return (f"tab-e2e-full.tex / tab-e2e-subset.tex: {len(ordered)} oracle rows, "
            f"{len(both)} with end-to-end, {scenarios} scenarios")


def str_quality_table(out: Path) -> str:
    """tab:str-quality, from the step that scores the generated reports.

    The table shows a few configurations rather than all of them, chosen for what
    each one demonstrates: the best report quality, the best workflow completion,
    both finance-specialised models, and the two highest single-turn models, which
    are there because reaching the writing step at all is most of the difficulty.
    """
    import csv
    source = _ROOT / "_experiments" / "results_RQ3" / "str_generation_quality.csv"
    if not source.is_file():
        return "tab-str-quality.tex: results_RQ3/str_generation_quality.csv is missing"
    rows = {r["config_id"]: r for r in csv.DictReader(source.open(encoding="utf-8"))}
    labels = {c.config_id: c.label for c in registry.CONFIGS}
    cases = load.single()
    single = cases.groupby("config_id")["h"].mean()
    oracle = load.aggregates("oracle")

    def number(row, key):
        value = row.get(key)
        return float(value) if value not in (None, "") else None

    picked, why = [], {}
    def take(config_id, reason):
        if config_id in rows and config_id not in why:
            picked.append(config_id); why[config_id] = reason
    take(max(rows, key=lambda k: number(rows[k], "str_overall") or -1), "best report quality")
    take(max(oracle, key=lambda k: oracle[k]["c"]["mean"]), "best workflow completion")
    for config_id in ("dragon-llama-fin", "dragon-qwen-fin"):
        take(config_id, "finance-specialised")
    for config_id in sorted(single.index, key=lambda k: -single[k])[:2]:
        take(config_id, "highest single-turn tool hit")

    picked.sort(key=lambda k: -(number(rows[k], "str_overall") or -1))
    lines = []
    for config_id in picked:
        row = rows[config_id]
        cells = [_fmt(number(row, k)) for k in ("str_production_rate", "field_coverage",
                                                "grounding", "terminology", "hallucination",
                                                "str_overall")]
            # A body table: read for the numbers, and every model it names is cited
            # in the appendix tables that repeat it.
        lines.append(f"{_label(config_id, labels, cite=False)} & " + " & ".join(cells) + " \\\\")
    header = ["\\multicolumn{1}{c}{\\textbf{Model}} & \\textbf{Rate} & \\textbf{Field} & "
              "\\textbf{Ground.} & \\textbf{Term} & \\textbf{Halluc.} & \\textbf{Overall} \\\\"]
    turns = rows[picked[0]].get("n_str_turn", "45")
    # Six rows and seven narrow columns: a wraptable beside the prose that reads it,
    # so the body spends a float on it without spending a third of a page.
    text = _table(lines, spec="lcccccc", header=header, label="tab:str-quality",
                  wrap="0.55\\textwidth", size="scriptsize",
                  caption=(f"STR generation quality over the {turns} scenarios whose gold ends in "
                           f"report writing. Rate is the production rate; Field, Ground., Term and "
                           f"Halluc.\\ are required-field completeness, evidence grounding, "
                           f"terminology use and the unsupported-fact rate. The quality columns are "
                           f"penalised so that a scenario without a report scores zero."),
                  note="; ".join(f"{labels.get(k, k)}: {why[k]}" for k in picked))
    (out / "tab-str-quality.tex").write_text(text, encoding="utf-8")
    return f"tab-str-quality.tex: {len(picked)} representative rows of {len(rows)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true",
                        help="refuse to write while a configuration is unscored")
    args = parser.parse_args(argv)

    missing = load.missing()
    unscored = missing.loc[~missing["single"], "config_id"].tolist()
    if unscored and args.strict:
        print(f"refusing: {len(unscored)} configurations are not scored: {', '.join(unscored)}",
              file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for line in (main_table(args.out), ablation_table(args.out), e2e_tables(args.out),
                 str_quality_table(args.out)):
        print(line)
    if unscored:
        print(f"note: {len(unscored)} configurations are not scored yet: {', '.join(unscored)}")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
