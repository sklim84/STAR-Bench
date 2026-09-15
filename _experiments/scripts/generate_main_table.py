#!/usr/bin/env python3
"""main.tex tab:overall 의 단일턴 열(h, r, p, a, o) 생성.

results_kr/eval 에서 본문 28설정 코호트의 overall 지표를 읽어, 원고 표와 같은 순서·표기로
행을 만든다. 열마다 1위는 \\textbf, 2위는 \\underline 으로 표시한다(원고 캡션 규칙).

멀티턴 열(h-bar, a-bar, c)은 여기서 만들지 않는다. 원고의 멀티턴 열은 results_mt_oracle 을
재채점한 값이라(원고 커밋 9f9b448) 이 스크립트가 읽는 overall 과 다르다.

2026-09-15 개정: 금키 재실행(results_kr, 커밋 4bddc4c) 반영. 이전 판은 T 설정 4개가 빠진
24행이었고, eval 의 model 필드 표기(원래 이름 / sanitize 이름)가 섞이면서 CSV 조회가
어긋났다. 표기는 _norm 으로 맞춘다.

출력: _experiments/results_RQ1/main_table_single_turn.{tex,csv}
"""
import csv
import json
from pathlib import Path

_SB = Path(__file__).resolve().parents[2]
EVAL_DIR = _SB / '_experiments' / 'results_kr' / 'eval'
OUT_DIR = _SB / '_experiments' / 'results_RQ1'

# (eval model id, 원고 표기, 원고 그룹) — 원고 table/tab-exp-oveall.tex 의 행 순서
ROWS = [
    ('skt/A.X-4.0-Light', 'A.X-4.0-Light (7B)', 'Korean-Specialized'),
    ('skt/A.X-4.0', 'A.X-4.0 (72B)', 'Korean-Specialized'),
    ('LGAI-EXAONE/EXAONE-4.0-1.2B', 'EXAONE-4.0-1.2B', 'Korean-Specialized'),
    ('LGAI-EXAONE/EXAONE-4.0-32B', 'EXAONE-4.0-32B', 'Korean-Specialized'),
    ('kakaocorp/kanana-2-30b-a3b-instruct', 'Kanana-2-Instruct', 'Korean-Specialized'),
    ('kakaocorp/kanana-2-30b-a3b-thinking-2601', 'Kanana-2-Think', 'Korean-Specialized'),
    ('DragonLLM/Llama-Open-Finance-8B', 'Llama-Open-Finance-8B', 'Finance-Specialized'),
    ('DragonLLM/Qwen-Open-Finance-R-8B', 'Qwen-Open-Finance-R-8B', 'Finance-Specialized'),
    ('openai/gpt-oss-20b__nothink', 'gpt-oss-20B (NT)', 'General-Purpose'),
    ('openai/gpt-oss-20b__think', 'gpt-oss-20B (T)', 'General-Purpose'),
    ('openai/gpt-oss-120b__nothink', 'gpt-oss-120B (NT)', 'General-Purpose'),
    ('openai/gpt-oss-120b__think', 'gpt-oss-120B (T)', 'General-Purpose'),
    ('meta-llama/Llama-3.2-3B-Instruct', 'Llama-3.2-3B', 'General-Purpose'),
    ('meta-llama/Llama-3.3-70B-Instruct', 'Llama-3.3-70B', 'General-Purpose'),
    ('NousResearch/Hermes-3-Llama-3.1-8B', 'Hermes-3-8B', 'General-Purpose'),
    ('mistralai/Ministral-3-3B-Instruct-2512', 'Ministral-3-3B', 'General-Purpose'),
    ('mistralai/Mistral-Small-3.2-24B-Instruct-2506', 'Mistral-Small-24B', 'General-Purpose'),
    ('microsoft/Phi-4-mini-instruct', 'Phi-4-mini', 'General-Purpose'),
    ('Qwen/Qwen3.5-4B__nothink', 'Qwen3.5-4B (NT)', 'General-Purpose'),
    ('Qwen/Qwen3.5-4B__think', 'Qwen3.5-4B (T)', 'General-Purpose'),
    ('Qwen/Qwen3.5-27B__nothink', 'Qwen3.5-27B (NT)', 'General-Purpose'),
    ('Qwen/Qwen3.5-27B__think', 'Qwen3.5-27B (T)', 'General-Purpose'),
    ('Qwen/Qwen3.6-27B', 'Qwen3.6-27B', 'General-Purpose'),
    ('Qwen/Qwen3.6-35B-A3B', 'Qwen3.6-35B-A3B', 'General-Purpose'),
    ('Salesforce/xLAM-2-3b-fc-r', 'xLAM-2-3B', 'General-Purpose'),
    ('Salesforce/Llama-xLAM-2-70b-fc-r', 'xLAM-2-70B', 'General-Purpose'),
    ('google/gemma-4-E4B-it', 'Gemma-4-E4B', 'General-Purpose'),
    ('google/gemma-4-31B-it', 'Gemma-4-31B', 'General-Purpose'),
]

COLS = [
    ('h', 'primary_tool_hit_rate'),
    ('r', 'avg_tool_recall'),
    ('p', 'avg_tool_precision'),
    ('a', 'avg_param_accuracy'),
    ('o', 'avg_order_score'),
]


def _norm(name):
    """슬래시·마침표를 언더스코어로 정규화."""
    return name.replace('/', '_').replace('.', '_')


def load_kr():
    """eval JSON 로드. think 플래그가 있는데 접미사가 없으면 붙인다."""
    out = {}
    for f in sorted(EVAL_DIR.glob('eval_*.json')):
        d = json.load(f.open())
        mid = d.get('model_id') or d.get('model')
        think = d.get('think')
        if think is True and not mid.endswith('__think'):
            mid = f'{mid}__think'
        elif think is False and not mid.endswith('__nothink'):
            mid = f'{mid}__nothink'
        out[_norm(mid)] = d.get('overall', {})
    return out


def fmt(v):
    """원고 표기: 소수 셋째 자리, 앞자리 0 생략(.544)."""
    return f'{v:.3f}'.lstrip('0') if v is not None else '--'


def rank_marks(values):
    """열 하나의 값 목록 -> 표시 목록. 반올림한 값이 1위와 같으면 모두 굵게, 2위 값은 밑줄."""
    shown = sorted({fmt(v) for v in values}, reverse=True)
    first, second = shown[0], (shown[1] if len(shown) > 1 else None)
    marks = []
    for v in values:
        s = fmt(v)
        marks.append(f'\\textbf{{{s}}}' if s == first else f'\\underline{{{s}}}' if s == second else s)
    return marks


def main():
    kr = load_kr()
    missing = [mid for mid, _, _ in ROWS if _norm(mid) not in kr]
    if missing:
        raise SystemExit(f'results_kr/eval 에 없는 설정: {missing}')

    table = {key: [kr[_norm(mid)].get(key) for mid, _, _ in ROWS] for _, key in COLS}
    marked = {key: rank_marks(vals) for key, vals in table.items()}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, (mid, name, group) in enumerate(ROWS):
        cells = ' & '.join(marked[key][i] for _, key in COLS)
        lines.append(f'{name:<24s} & {cells} \\\\')
    (OUT_DIR / 'main_table_single_turn.tex').write_text('\n'.join(lines) + '\n')

    with (OUT_DIR / 'main_table_single_turn.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model_id', 'display_name', 'group'] + [c for c, _ in COLS])
        for i, (mid, name, group) in enumerate(ROWS):
            w.writerow([mid, name, group] + [round(table[key][i], 4) for _, key in COLS])

    print('\n'.join(lines))
    print(f'\n{len(ROWS)} rows -> {OUT_DIR / "main_table_single_turn.tex"}')


if __name__ == '__main__':
    main()
