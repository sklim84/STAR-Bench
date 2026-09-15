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

__all__ = ["PromptBudget", "measure", "check"]

# Bytes per token, measured on the mixed Korean/English prompts of this benchmark
# under the Qwen and Llama tokenizers. Deliberately pessimistic.
_UTF8_BYTES_PER_TOKEN = 2.2

# Room a run needs for tool results and the answer on top of the prompt.
MIN_HEADROOM = 8000


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


def _tokenizer(model: str, revision: str | None):
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(model, revision=revision, local_files_only=True)
    except Exception:
        return None


def _estimate(text: str) -> int:
    return int(len(text.encode("utf-8")) / _UTF8_BYTES_PER_TOKEN) + 1


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
