#!/usr/bin/env python3
"""main.tex tab:overall (메인 대표 모델 테이블) LaTeX 생성.

results_kr (29 모델) + results_mt_oracle (29 모델)에서 KR baseline + multiturn 결과
추출하여 LaTeX rows 생성.

대표 모델 선정 기준:
- 한국어 특화 모델 그룹: Kanana-2-30B, EXAONE-4.0-32B, A.X-4.0, A.X-4.0-Light
- 계열별 대표 (think/nothink는 nothink 우선):
  - Qwen: Qwen3.6-27B, Qwen3.6-35B-A3B, Qwen3.5-27B__nothink, Qwen3.5-4B__nothink
  - Llama: Llama-3.2-3B, Llama-3.3-70B
  - Mistral: Ministral-3-3B, Mistral-Small-24B
  - Microsoft: Phi-4-mini
  - Hermes: Hermes-3-Llama-3.1-8B
  - Salesforce: xLAM-2-3b, Llama-xLAM-2-70b
  - Google: Gemma-4-E4B, Gemma-4-31B
  - openai: gpt-oss-20b__nothink, gpt-oss-120b__nothink
  - DragonLLM: Llama-Open-Finance-8B, Qwen-Open-Finance-R-8B
"""
import json
from pathlib import Path

EVAL_DIR = Path('_experiments/results_kr/eval')
MT_DIR = Path('_experiments/results_mt_oracle/eval')

# 대표 모델 + 표시 순서 (계열 그룹화)
DISPLAY_ORDER = [
    # 한국어 특화 (krmodel)
    ('skt/A.X-4.0-Light', 'A.X-4.0-Light (7B)', 'kr'),
    ('skt/A.X-4.0', 'A.X-4.0 (72B)', 'kr'),
    ('LGAI-EXAONE/EXAONE-4.0-1.2B', 'EXAONE-4.0-1.2B', 'kr'),
    ('LGAI-EXAONE/EXAONE-4.0-32B', 'EXAONE-4.0-32B', 'kr'),
    ('kakaocorp/kanana-2-30b-a3b-instruct', 'Kanana-2-30B', 'kr_check'),
    ('kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink', 'Kanana-2-Think (NT)', 'kr_check'),
    # DragonLLM Finance
    ('DragonLLM/Llama-Open-Finance-8B', 'Llama-Finance-8B', 'finance'),
    ('DragonLLM/Qwen-Open-Finance-R-8B', 'Qwen-Finance-R-8B', 'finance'),
    # Hermes
    ('NousResearch/Hermes-3-Llama-3.1-8B', 'Hermes-3-8B', 'general'),
    # gpt-oss
    ('openai/gpt-oss-20b__nothink', 'gpt-oss-20B (NT)', 'general'),
    ('openai/gpt-oss-120b__nothink', 'gpt-oss-120B (NT)', 'general'),
    # Llama
    ('meta-llama/Llama-3.2-3B-Instruct', 'Llama-3.2-3B', 'general'),
    ('meta-llama/Llama-3.3-70B-Instruct', 'Llama-3.3-70B', 'general'),
    # Mistral
    ('mistralai/Ministral-3-3B-Instruct-2512', 'Ministral-3-3B', 'general'),
    ('mistralai/Mistral-Small-3.2-24B-Instruct-2506', 'Mistral-Small-24B', 'general'),
    # Microsoft
    ('microsoft/Phi-4-mini-instruct', 'Phi-4-mini', 'general'),
    # Qwen
    ('Qwen/Qwen3.5-4B__nothink', 'Qwen3.5-4B (NT)', 'general'),
    ('Qwen/Qwen3.5-27B__nothink', 'Qwen3.5-27B (NT)', 'general'),
    ('Qwen/Qwen3.6-27B', 'Qwen3.6-27B', 'general'),
    ('Qwen/Qwen3.6-35B-A3B', 'Qwen3.6-35B-A3B', 'general'),
    # xLAM
    ('Salesforce/xLAM-2-3b-fc-r', 'xLAM-2-3B', 'general'),
    ('Salesforce/Llama-xLAM-2-70b-fc-r', 'xLAM-2-70B', 'general'),
    # Gemma
    ('google/gemma-4-E4B-it', 'Gemma-4-E4B', 'general'),
    ('google/gemma-4-31B-it', 'Gemma-4-31B', 'general_check'),
]

# 평가 이상치 의심 모델 (h≈0.126, cases 빈값 패턴) — 결과는 표에 두되 주석 표시
CHECK_NEEDED = {
    'kakaocorp/kanana-2-30b-a3b-instruct',
    'kakaocorp/kanana-2-30b-a3b-thinking-2601__nothink',
    'google/gemma-4-31B-it',
}

def _norm_model_key(name):
    """슬래시·마침표를 언더스코어로 정규화."""
    if not name: return name
    return name.replace('/', '_').replace('.', '_')

def load_kr():
    """eval JSON 로드 — model 필드 형식 차이(슬래시/언더스코어) 정규화."""
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

def fmt(v, decimals=3):
    if v is None: return '--'
    return f'{v:.{decimals}f}'

def main():
    kr = load_kr()
    mt = load_mt()

    rows = []
    last_group = None
    for model_id, display_name, group in DISPLAY_ORDER:
        key = _norm_model_key(model_id)
        if key not in kr:
            print(f'WARN: {model_id} not in KR')
            continue
        kr_m = kr[key]
        mt_m = mt.get(key, {})

        # group 구분선 (\midrule)
        # check 그룹은 별도 midrule로 분리하지 않고 같은 그룹 내 끝에 배치
        normal_group = group.replace('_check', '')
        if last_group is not None and normal_group != last_group.replace('_check', ''):
            rows.append('\\midrule')
        last_group = group

        if normal_group == 'kr':
            name = f'\\krmodel{{{display_name}}}'
        else:
            name = display_name

        # 평가 이상치 의심 모델은 위에 LaTeX 주석으로 표시
        if model_id in CHECK_NEEDED:
            rows.append(f'% [확인 필요] {display_name}: 평가 이상치(h≈0.126, cases 빈값 패턴) 의심 — 추후 재실험 예정')

        h = kr_m.get('primary_tool_hit_rate')
        r = kr_m.get('avg_tool_recall')
        p = kr_m.get('avg_tool_precision')
        a = kr_m.get('avg_param_accuracy')
        o = kr_m.get('avg_order_score')
        h_bar = mt_m.get('avg_tool_hit')
        a_bar = mt_m.get('avg_param_accuracy')
        c = mt_m.get('scenario_complete_rate')

        row = (f'{name:<30s} & {fmt(h)} & {fmt(r)} & {fmt(p)} & '
               f'{fmt(a)} & {fmt(o)} & {fmt(h_bar)} & {fmt(a_bar)} & {fmt(c)} \\\\')
        rows.append(row)

    # LaTeX table body
    print('=== LaTeX rows ===')
    for r in rows:
        print(r)

    # 파일 저장
    out_dir = Path('_experiments/results_RQ1')
    out_dir.mkdir(exist_ok=True, parents=True)
    with (out_dir / 'main_table_rows.tex').open('w') as f:
        f.write('\n'.join(rows) + '\n')

    # CSV 형식 저장
    import csv
    with (out_dir / 'main_table_data.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model_id', 'display_name', 'group',
                    'h', 'r', 'p', 'a', 'o', 'h_bar', 'a_bar', 'c'])
        for model_id, display_name, group in DISPLAY_ORDER:
            if model_id not in kr: continue
            kr_m = kr[model_id]
            mt_m = mt.get(model_id, {})
            w.writerow([model_id, display_name, group,
                        kr_m.get('avg_primary_tool_hit'),
                        kr_m.get('avg_tool_recall'),
                        kr_m.get('avg_tool_precision'),
                        kr_m.get('avg_param_accuracy'),
                        kr_m.get('avg_order_score'),
                        mt_m.get('avg_tool_hit'),
                        mt_m.get('avg_param_accuracy'),
                        mt_m.get('scenario_complete_rate')])

    print(f'\nGenerated {len(rows)} lines')
    print(f'Saved to: results_RQ1/main_table_rows.tex')

if __name__ == '__main__':
    main()
