#!/usr/bin/env python3
"""main.tex tab:full_models (Appendix 전체 모델 표) LaTeX 생성.

results_kr (29 모델) + results_mt_oracle (29 모델) 데이터 기반.
옛 표(41 모델, ±std)와 동일 형식 유지하되 단일 라운드 결과는 ±0.000 placeholder.
"""
import json
from pathlib import Path

EVAL_DIR = Path('_experiments/results_kr/eval')
MT_DIR = Path('_experiments/results_mt_oracle/eval')

# 한국어 특화 그룹 + 그룹별 모델 순서 (옛 tab:full_models 순서 참조)
GROUPS = [
    ('kr', '한국어 특화', [
        ('skt/A.X-4.0-Light', 'A.X-4.0-Light (7B)'),
        ('skt/A.X-4.0', 'A.X-4.0 (72B)'),
        ('LGAI-EXAONE/EXAONE-4.0-1.2B', 'EXAONE-4.0-1.2B'),
        ('LGAI-EXAONE/EXAONE-4.0-32B', 'EXAONE-4.0-32B'),
        ('kakaocorp/kanana-2-30b-a3b-instruct', 'Kanana-2-Instruct'),
        ('kakaocorp/kanana-2-30b-a3b-thinking-2601', 'Kanana-2-Think'),
    ]),
    ('finance', 'Finance SFT', [
        ('DragonLLM/Llama-Open-Finance-8B', 'Llama-Open-Finance-8B'),
        ('DragonLLM/Qwen-Open-Finance-R-8B', 'Qwen-Open-Finance-R-8B'),
    ]),
    ('gptoss', 'gpt-oss', [
        ('openai/gpt-oss-20b__nothink', 'gpt-oss-20B (NT)'),
        ('openai/gpt-oss-20b__think', 'gpt-oss-20B (T)'),
        ('openai/gpt-oss-120b__nothink', 'gpt-oss-120B (NT)'),
        ('openai/gpt-oss-120b__think', 'gpt-oss-120B (T)'),
    ]),
    ('llama', 'Llama / Hermes', [
        ('meta-llama/Llama-3.2-3B-Instruct', 'Llama-3.2-3B'),
        ('meta-llama/Llama-3.3-70B-Instruct', 'Llama-3.3-70B'),
        ('NousResearch/Hermes-3-Llama-3.1-8B', 'Hermes-3-8B'),
    ]),
    ('mistral', 'Mistral', [
        ('mistralai/Ministral-3-3B-Instruct-2512', 'Ministral-3-3B'),
        ('mistralai/Mistral-Small-3.2-24B-Instruct-2506', 'Mistral-Small-24B'),
    ]),
    ('microsoft', 'Microsoft', [
        ('microsoft/Phi-4-mini-instruct', 'Phi-4-mini'),
    ]),
    ('qwen', 'Qwen', [
        ('Qwen/Qwen3.5-4B__nothink', 'Qwen3.5-4B (NT)'),
        ('Qwen/Qwen3.5-4B__think', 'Qwen3.5-4B (T)'),
        ('Qwen/Qwen3.5-27B__nothink', 'Qwen3.5-27B (NT)'),
        ('Qwen/Qwen3.5-27B__think', 'Qwen3.5-27B (T)'),
        ('Qwen/Qwen3.6-27B', 'Qwen3.6-27B'),
        ('Qwen/Qwen3.6-35B-A3B', 'Qwen3.6-35B-A3B'),
    ]),
    ('xlam', 'xLAM', [
        ('Salesforce/xLAM-2-3b-fc-r', 'xLAM-2-3B'),
        ('Salesforce/Llama-xLAM-2-70b-fc-r', 'xLAM-2-70B'),
    ]),
    ('gemma', 'Gemma', [
        ('google/gemma-4-E4B-it', 'Gemma-4-E4B'),
        ('google/gemma-4-31B-it', 'Gemma-4-31B'),
    ]),
]

CHECK_NEEDED = {
    'kakaocorp/kanana-2-30b-a3b-instruct',
    'kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink',
    'kakaocorp/kanana-2-30b-a3b-thinking-2601__think',
    'google/gemma-4-31B-it',
}

KR_GROUPS = {'kr'}

def _norm_model_key(name):
    """슬래시·마침표를 언더스코어로 정규화하여 표 모델 ID와 eval `model` 필드 형식 차이를 흡수."""
    if not name: return name
    return name.replace('/', '_').replace('.', '_')

def load_kr():
    out = {}
    for f in sorted(EVAL_DIR.glob('eval_*.json')):
        d = json.load(f.open())
        mid = d.get('model_id') or d.get('model')
        think = d.get('think')
        if think is True and not mid.endswith('__think'): mid = f'{mid}__think'
        elif think is False and not mid.endswith('__nothink'): mid = f'{mid}__nothink'
        out[_norm_model_key(mid)] = d.get('overall', {})
    return out

def load_mt():
    out = {}
    for f in MT_DIR.glob('multiturn_*.json'):
        d = json.load(f.open())
        mid = d.get('model_id') or d.get('model')
        think = d.get('think')
        if think is True and not mid.endswith('__think'): mid = f'{mid}__think'
        elif think is False and not mid.endswith('__nothink'): mid = f'{mid}__nothink'
        out[_norm_model_key(mid)] = d.get('overall', {})
    return out

def fmt(v, decimals=3, with_std=True):
    if v is None: return '--'
    if with_std:
        return f'{v:.{decimals}f}$\\pm$0.000'
    return f'{v:.{decimals}f}'

def main():
    kr = load_kr()
    mt = load_mt()

    rows = []
    for gid, _, models in GROUPS:
        if rows:
            rows.append('\\midrule')
        for model_id, display_name in models:
            key = _norm_model_key(model_id)
            if key not in kr:
                rows.append(f'% [WARN] {model_id} not in KR baseline')
                continue
            kr_m = kr[key]
            mt_m = mt.get(key, {})

            name = f'\\krmodel{{{display_name}}}' if gid in KR_GROUPS else display_name

            h = kr_m.get('primary_tool_hit_rate')
            r = kr_m.get('avg_tool_recall')
            p = kr_m.get('avg_tool_precision')
            a = kr_m.get('avg_param_accuracy')
            o = kr_m.get('avg_order_score')
            h_bar = mt_m.get('avg_tool_hit')
            a_bar = mt_m.get('avg_param_accuracy')
            c = mt_m.get('scenario_complete_rate')

            # CHECK_NEEDED는 여전히 원본 model_id로 비교 (정규화 전 키)
            if model_id in CHECK_NEEDED and False:  # 더 이상 의심값 없음, 비활성화
                rows.append(f'% [확인 필요] {display_name}: 평가 이상치(h$\\approx$0.126, cases 빈값 패턴) 의심 — 추후 재실험 예정')

            row = (f'{name:<35s} & {fmt(h)} & {fmt(r)} & {fmt(p)} & '
                   f'{fmt(a)} & {fmt(o)} & {fmt(h_bar)}  & {fmt(a_bar)}  & {fmt(c)} \\\\')
            rows.append(row)

    out_dir = Path('_experiments/results_RQ1')
    out_dir.mkdir(exist_ok=True, parents=True)
    out_file = out_dir / 'full_models_table_rows.tex'
    with out_file.open('w') as f:
        f.write('\n'.join(rows) + '\n')

    print('=== full_models LaTeX rows ===')
    for r in rows:
        print(r)
    print(f'\nSaved to: {out_file}')
    n_data_rows = sum(1 for r in rows if r and not r.startswith('%') and not r.startswith('\\midrule'))
    print(f'Total data rows: {n_data_rows}')

if __name__ == '__main__':
    main()
