# System-prompt variants for the prompt ablation

The review-response ablation reported that listing the five reporting tools in
the system prompt moved single-turn regulatory-reporting h from .607 to .685
(+7.8pp, p = .0007) and cost Phi-4-mini 31.1pp under a forced instruction. The
code, the prompt variants and the checkpoints for that experiment were in no
repository, and the prompt to use for the rerun was undecided (R2C-004).

The evaluation prompt is now the arm prompt (`baseline`), and the variants live
here so the ablation can be re-run from tracked code on the final stack:

    python -m _experiments.scripts.benchmark --config <id> --tools-lang kr \
        --prompt-variant list_reporting_tools --out <fresh dir>

Each variant is a file of the form `<name>.<lang>.txt` whose content is appended
to the arm's system prompt. The variant name and the sha256 of the prompt the
model actually saw go into every run record, so two runs of the same
configuration under different prompts are never confused for each other.

| Variant | What it adds |
|---|---|
| `baseline` | nothing; the arm prompt as it ships |
| `list_reporting_tools` | one sentence naming the five reporting tools, which is the +7.8pp condition |
| `force_reporting_tools` | an instruction to use a reporting tool whenever the question is about reporting, which is the condition Phi-4-mini lost 31.1pp on |

The ablation is an appendix result, not a main-table one: the main table runs
`baseline` in every column.
