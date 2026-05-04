#!/usr/bin/env python3
"""RQ5: BFCL v4 vs AML-Bench Spearman/Kendall correlation (21 BFCL × 29 AML).

BFCL 21 모델 직접 실행 결과 (data_overall.csv) + AML-Bench KR results_kr/eval/.
모델 이름 매칭 후 Spearman ρ, Kendall τ 산출.

산출:
  - results_RQ5/bfcl_aml_paired.json (n쌍 + 통계)
  - results_RQ5/bfcl_aml_paired.csv
  - figures/fig_bfcl_vs_aml.{pdf,png} (갱신)
"""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _plot_style import (plt, FS_TICK, FS_LABEL, FS_LEGEND, style_axes)

BFCL_CSV = Path('_paper/_experiments/bfcl_results/score/data_overall.csv')
AML_DIR = Path('_paper/_experiments/results_kr/eval')
OUT_DIR = Path('_paper/_experiments/results_RQ5')
FIG_DIR = Path('_paper/figures')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# BFCL display_name → AML model_id 매핑
# (think 변형 모델은 nothink로 매칭, AML key 우선순위 nothink > think)
BFCL_TO_AML = {
    'A.X-4.0 (Prompt)': 'skt/A.X-4.0',
    'A.X-4.0-Light (Prompt)': 'skt/A.X-4.0-Light',
    'EXAONE-4.0-1.2B (Prompt)': 'LGAI-EXAONE/EXAONE-4.0-1.2B',
    'EXAONE-4.0-32B (Prompt)': 'LGAI-EXAONE/EXAONE-4.0-32B',
    'Hermes-3-Llama-3.1-8B (Prompt)': 'NousResearch/Hermes-3-Llama-3.1-8B',
    'Llama-3.2-3B-Instruct (FC)': 'meta-llama/Llama-3.2-3B-Instruct',
    'Llama-3.3-70B-Instruct (FC)': 'meta-llama/Llama-3.3-70B-Instruct',
    'Ministral-3-3B-Instruct-2512 (Prompt)': 'mistralai/Ministral-3-3B-Instruct-2512',
    'Mistral-Small-3.2-24B (Prompt)': 'mistralai/Mistral-Small-3.2-24B-Instruct-2506',
    'Phi-4-mini-instruct (Prompt)': 'microsoft/Phi-4-mini-instruct',
    'Qwen3.5-27B (Prompt)': 'Qwen/Qwen3.5-27B__nothink',
    'Qwen3.5-4B (Prompt)': 'Qwen/Qwen3.5-4B__nothink',
    'xLAM-2-3b-fc-r (FC)': 'Salesforce/xLAM-2-3b-fc-r',
    'xLAM-2-70b-fc-r (FC)': 'Salesforce/Llama-xLAM-2-70b-fc-r',
}


def parse_pct(s):
    return float(s.rstrip('%')) if s and s != 'N/A' else None


def load_bfcl():
    out = {}
    with BFCL_CSV.open() as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if not row or not row[0].isdigit():
                continue
            rank, overall, name = int(row[0]), parse_pct(row[1]), row[2]
            out[name] = overall
    return out


def load_aml():
    # canonicalize: latest eval은 sanitized model name 사용
    targets = set(BFCL_TO_AML.values())
    safe_to_canonical = {m.replace('/', '_').replace('.', '_'): m for m in targets}
    out = {}
    for f in sorted(AML_DIR.glob('eval_*.json')):
        d = json.load(f.open())
        m = d.get('model')
        if m:
            m = safe_to_canonical.get(m, m)
            out[m] = (d.get('overall', {}).get('primary_tool_hit_rate'))
    return out


def short_name(aml_id):
    s = aml_id.split('/')[-1]
    return s.replace('__nothink', '').replace('__think', '')


def main():
    bfcl = load_bfcl()
    aml = load_aml()
    print(f'BFCL: {len(bfcl)} models, AML: {len(aml)} models')

    pairs = []
    for bf_name, aml_id in BFCL_TO_AML.items():
        bf = bfcl.get(bf_name)
        am = aml.get(aml_id)
        if bf is None or am is None:
            print(f'  miss: {bf_name} / {aml_id} (bfcl={bf}, aml={am})')
            continue
        pairs.append({
            'bfcl_name': bf_name,
            'aml_id': aml_id,
            'aml_name': short_name(aml_id),
            'bfcl_acc': bf,
            'aml_score': am,
        })
    pairs.sort(key=lambda p: -p['bfcl_acc'])
    print(f'  paired: {len(pairs)}')

    try:
        from scipy import stats
        x = [p['bfcl_acc'] for p in pairs]
        y = [p['aml_score'] for p in pairs]
        rho, p_rho = stats.spearmanr(x, y)
        tau, p_tau = stats.kendalltau(x, y)
        pearson_r, p_p = stats.pearsonr(x, y)
    except ImportError:
        rho = p_rho = tau = p_tau = pearson_r = p_p = None

    out = {
        'n': len(pairs),
        'spearman_rho': round(float(rho), 4) if rho is not None else None,
        'spearman_p': round(float(p_rho), 6) if p_rho is not None else None,
        'kendall_tau': round(float(tau), 4) if tau is not None else None,
        'kendall_p': round(float(p_tau), 6) if p_tau is not None else None,
        'pearson_r': round(float(pearson_r), 4) if pearson_r is not None else None,
        'pearson_p': round(float(p_p), 6) if p_p is not None else None,
        'pairs': pairs,
        'note': '21 BFCL × 29 AML 매칭. Qwen3.5-27B/4B는 BFCL이 nothink만 평가하므로 AML도 nothink 매칭. xLAM-2-32B/8B/1B/Qwen3-* 시리즈는 AML 미실시로 제외.'
    }
    with (OUT_DIR / 'bfcl_aml_paired.json').open('w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with (OUT_DIR / 'bfcl_aml_paired.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['bfcl_name', 'aml_id', 'aml_name', 'bfcl_acc', 'aml_score'])
        w.writeheader()
        w.writerows(pairs)

    print(f'  Spearman rho={out["spearman_rho"]} p={out["spearman_p"]}')
    print(f'  Kendall  tau={out["kendall_tau"]} p={out["kendall_p"]}')
    print(f'  Pearson  r={out["pearson_r"]} p={out["pearson_p"]}')

    # Plot
    try:
        from matplotlib.patches import Patch

        def family_color(name):
            if 'xLAM' in name:
                return '#E15759'
            if 'Qwen3.5' in name:
                return '#4E79A7'
            if 'EXAONE' in name or 'A.X' in name:
                return '#76B7B2'
            if 'Llama' in name:
                return '#F28E2B'
            if 'Mistral' in name or 'Ministral' in name:
                return '#B07AA1'
            return '#59A14F'

        fig, ax = plt.subplots(figsize=(5.5, 4.2))
        for p in pairs:
            color = family_color(p['aml_name'])
            ax.scatter(p['bfcl_acc'], p['aml_score'] * 100,
                       c=color, s=70, edgecolors='black', linewidths=0.5, zorder=3)

        # Annotate select outliers
        outliers = {
            'xLAM-2-3B': (8, -4, 'left', 'top'),
            'xLAM-2-70B': (8, 6, 'left', 'bottom'),
            'A.X-4.0-Light': (8, 6, 'left', 'bottom'),
            'EXAONE-4.0-32B': (-8, 6, 'right', 'bottom'),
            'Llama-3.3-70B': (-8, -4, 'right', 'top'),
            'Llama-3.2-3B': (8, 6, 'left', 'bottom'),
            'Ministral-3-3B': (-8, -4, 'right', 'top'),
            'Phi-4-mini': (8, -4, 'left', 'top'),
        }
        for p in pairs:
            n = p['aml_name']
            if n in outliers:
                dx, dy, ha, va = outliers[n]
                ax.annotate(n, (p['bfcl_acc'], p['aml_score'] * 100),
                            xytext=(dx, dy), textcoords='offset points',
                            fontsize=FS_LEGEND - 1, ha=ha, va=va)

        ax.set_xlabel(r'BFCL v4 Overall Accuracy (\%)', fontsize=13)
        ax.set_ylabel(r'AML-Bench KR Tool Hit $h$ (\%)', fontsize=13)
        ax.tick_params(labelsize=12)
        ax.grid(True, alpha=0.3)

        legend_elements = [
            Patch(facecolor='#E15759', edgecolor='black', label='xLAM-2'),
            Patch(facecolor='#4E79A7', edgecolor='black', label='Qwen3.5'),
            Patch(facecolor='#76B7B2', edgecolor='black', label='Korean (EXAONE/A.X)'),
            Patch(facecolor='#F28E2B', edgecolor='black', label='Llama'),
            Patch(facecolor='#B07AA1', edgecolor='black', label='Mistral'),
            Patch(facecolor='#59A14F', edgecolor='black', label='Other'),
        ]
        ax.legend(handles=legend_elements, loc='lower right', fontsize=11, framealpha=0.95)
        # 4면 spine + grid (fig:subdomain_grouped_bar과 시각 통일)
        plt.tight_layout()
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        # bbox_inches='tight' 제거 - 동일 figsize의 다른 서브피겨와 saved image 크기 동일하게 유지
        plt.savefig(FIG_DIR / 'fig_bfcl_vs_aml.pdf', dpi=300)
        plt.savefig(FIG_DIR / 'fig_bfcl_vs_aml.png', dpi=300)
        plt.close()
        print(f'  saved: {FIG_DIR}/fig_bfcl_vs_aml.{{pdf,png}}')
    except Exception as e:
        print(f'  plot failed: {e}')


if __name__ == '__main__':
    main()
