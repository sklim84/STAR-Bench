"""Does the prompt fit, and how much room is left for tool results?

Phi-4-mini was registered at 12,288 tokens on a wrong diagnosis, which would have
left the Korean arm 90 to 160 tokens of headroom and scored almost every one of
its 866 tool cases as a model failure (C2-001). A model whose context is smaller
than its prompt is a configuration bug, and it is cheap to catch before a run.

The check renders system prompt + tool schema + the longest question with the
serving tokenizer when transformers can load it offline, and falls back to a
character-per-token estimate when it cannot, so it also runs on a machine with no
model cache.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

__all__ = ["PromptBudget", "measure", "check", "estimate_tokens", "truncate",
           "TOOL_RESULT_TOKENS", "MIN_HEADROOM"]

# Bytes per token when no tokenizer can be loaded. Latin text and JSON punctuation
# run about four bytes to the token; Korean syllables are three UTF-8 bytes and
# cost one to two tokens each. Both figures are the pessimistic end of what the
# Qwen, Llama and Mistral tokenizers produce on these prompts.
_ASCII_BYTES_PER_TOKEN = 3.0
_WIDE_BYTES_PER_TOKEN = 2.3

# Room a run needs on top of the prompt and the output budget: one tool result at
# the size the runner truncates to, plus slack for the assistant turns around it.
# Tool results are truncated to the same token count in every arm, so a long
# result is a bounded cost rather than a context overflow (L5-012).
TOOL_RESULT_TOKENS = 4000
MIN_HEADROOM = TOOL_RESULT_TOKENS + 2000


@dataclass
class PromptBudget:
    prompt_tokens: int
    max_model_len: int
    max_tokens: int
    headroom: int
    tokenizer: str
    longest_question_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.headroom >= MIN_HEADROOM

    def as_dict(self) -> dict:
        return {"prompt_tokens": self.prompt_tokens, "max_model_len": self.max_model_len,
                "max_tokens": self.max_tokens, "headroom": self.headroom,
                "tokenizer": self.tokenizer, "longest_question_id": self.longest_question_id,
                "ok": self.ok}


def estimate_tokens(text: str) -> int:
    """Upper-bound token count without a tokenizer, calibrated on these prompts."""
    return _estimate(text)


def truncate(text: str, max_tokens: int = TOOL_RESULT_TOKENS) -> tuple[str, bool]:
    """Cuts a tool result down to a token budget, identically in every arm.

    Returns the text to send and whether it was cut. The record keeps the full
    result; only what the model reads is bounded.
    """
    if estimate_tokens(text) <= max_tokens:
        return text, False
    # Binary search on characters: the byte/token ratio differs by script.
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_tokens(text[:mid]) <= max_tokens - 40:
            low = mid
        else:
            high = mid - 1
    notice = (f"\n... [truncated by the benchmark runner: first {low} of {len(text)} "
              f"characters, the same limit in every arm]")
    return text[:low] + notice, True


def _tokenizer(model: str, revision: str | None):
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(model, revision=revision, local_files_only=True)
    except Exception:
        return None


def _estimate(text: str) -> int:
    raw = text.encode("utf-8")
    ascii_bytes = sum(1 for b in raw if b < 0x80)
    wide_bytes = len(raw) - ascii_bytes
    return int(ascii_bytes / _ASCII_BYTES_PER_TOKEN + wide_bytes / _WIDE_BYTES_PER_TOKEN) + 1


def measure(*, arm, cases: list[dict], model: str, revision: str | None,
            max_model_len: int, max_tokens: int) -> PromptBudget:
    longest, longest_id = "", None
    for case in cases:
        question = case.get("question") or ""
        if len(question) > len(longest):
            longest, longest_id = question, case.get("id")
    tools_text = json.dumps(arm.tools, ensure_ascii=False)
    tok = _tokenizer(model, revision)
    if tok is not None:
        try:
            rendered = tok.apply_chat_template(
                [{"role": "system", "content": arm.system_prompt},
                 {"role": "user", "content": longest}],
                tools=arm.tools, tokenize=True, add_generation_prompt=True)
            prompt_tokens, name = len(rendered), f"{model} tokenizer"
        except Exception:
            prompt_tokens = len(tok.encode(arm.system_prompt + tools_text + longest))
            name = f"{model} tokenizer (no chat template)"
    else:
        prompt_tokens = _estimate(arm.system_prompt) + _estimate(tools_text) + _estimate(longest)
        name = "byte estimate (tokenizer unavailable offline)"
    headroom = max_model_len - prompt_tokens - max_tokens
    return PromptBudget(prompt_tokens=prompt_tokens, max_model_len=max_model_len,
                        max_tokens=max_tokens, headroom=headroom, tokenizer=name,
                        longest_question_id=longest_id)


def check(budget: PromptBudget) -> None:
    if not budget.ok:
        raise RuntimeError(
            f"the prompt leaves {budget.headroom} tokens for tool results and the answer "
            f"({budget.prompt_tokens} prompt + {budget.max_tokens} output against a context of "
            f"{budget.max_model_len}, measured with {budget.tokenizer}). At least {MIN_HEADROOM} "
            f"are needed; raise --max-model-len or lower the output budget.")
