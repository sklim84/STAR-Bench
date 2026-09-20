# System-prompt variants for the prompt ablation

The system prompt is part of the experimental condition, not a detail of the harness:
naming the five reporting tools in it moves single-turn regulatory-reporting h from
.607 to .685 (+7.8pp, p = .0007), and an instruction that forces a reporting tool costs
Phi-4-mini 31.1pp. The variants are therefore tracked here, so the ablation runs from the
same code as every other result and the prompt behind a number can be read back:

    python -m _experiments.scripts.benchmark --config <id> --tools-lang kr \
        --prompt-variant list_reporting_tools --out <fresh dir>

The evaluation prompt is the arm prompt (`baseline`). Each variant is a file of the form
`<name>.<lang>.txt` whose content is appended to the arm's system prompt. The variant name
and the sha256 of the prompt the model actually saw go into every run record, so two runs
of the same configuration under different prompts are never confused for each other.

| Variant | What it adds |
|---|---|
| `baseline` | nothing; the arm prompt as it ships |
| `list_reporting_tools` | one sentence naming the five reporting tools, which is the +7.8pp condition |
| `force_reporting_tools` | an instruction to use a reporting tool whenever the question is about reporting, which is the condition Phi-4-mini lost 31.1pp on |

The ablation is an appendix result, not a main-table one: the main table runs
`baseline` in every column.
