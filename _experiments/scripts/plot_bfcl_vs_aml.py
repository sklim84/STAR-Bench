"""BFCL v4 vs AML-Bench 상관 scatter plot 생성.

입력: /tmp/bfcl_aml_paired.json
출력: _experiments/figures/fig_bfcl_vs_aml.png (그리고 pdf)
"""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

with open('/tmp/bfcl_aml_paired.json') as f:
    data = json.load(f)

pairs = data['pairs']
rho = data['spearman_rho']
p_rho = data['spearman_p']
tau = data['kendall_tau']
p_tau = data['kendall_p']
n = data['n']

# Family color mapping
def family_color(name):
    if 'xLAM' in name:
        return '#E15759'  # red
    if 'Qwen3.5' in name:
        return '#4E79A7'  # blue
    if 'Qwen3' in name:
        return '#F28E2B'  # orange
    return '#59A14F'

# Compact figure ~0.5 linewidth → 4.2 inch square works well
fig, ax = plt.subplots(figsize=(5.5, 4.2))

# Plot points
x_all, y_all = [], []
for p in pairs:
    bf = p['bfcl_acc']
    am = p['aml_score'] * 100  # scale to %
    name = p['aml_name'].replace(' \\nothinkmark', '').replace(' \\thinkmark', '')
    color = family_color(name)
    ax.scatter(bf, am, c=color, s=70, edgecolors='black', linewidths=0.5, zorder=3)
    x_all.append(bf); y_all.append(am)

# Explicit axis limits with padding so labels stay INSIDE plot box
x_min, x_max = min(x_all), max(x_all)
y_min, y_max = min(y_all), max(y_all)
x_pad = (x_max - x_min) * 0.18
y_pad = (y_max - y_min) * 0.22
ax.set_xlim(x_min - x_pad, x_max + x_pad)
ax.set_ylim(y_min - y_pad, y_max + y_pad)

# Label key outliers — offsets & alignment designed so label stays inside plot box
# Format: name → (dx, dy, ha, va)
outliers_to_label = {
    'xLAM-2-32B': (-8, -4, 'right', 'top'),     # right-top → label to left-below (inward)
    'xLAM-2-70B': (-8, 6,  'right', 'bottom'),  # right-mid → label to left-above (inward)
    'xLAM-2-8B':  (-8, 6,  'right', 'bottom'),  # right-upper → label to left-above
    'xLAM-2-3B':  (-8, -4, 'right', 'top'),     # mid-lower → label to left-below
    'xLAM-2-1B':  (8,  6,  'left',  'bottom'),  # left-bottom → label to right-above (inward)
    'Qwen3.5-9B': (8, -4,  'left',  'top'),     # mid-top → label to right-below (inward)
}
for p in pairs:
    name = p['aml_name'].replace(' \\nothinkmark', '').replace(' \\thinkmark', '')
    if name in outliers_to_label:
        dx, dy, ha, va = outliers_to_label[name]
        bf = p['bfcl_acc']
        am = p['aml_score'] * 100
        ax.annotate(name, (bf, am), xytext=(dx, dy), textcoords='offset points',
                    fontsize=10, ha=ha, va=va)

ax.set_xlabel('BFCL v4 Overall Accuracy (%)', fontsize=13)
ax.set_ylabel('AML-Bench ST KR Tool Hit $h$ (%)', fontsize=13)
ax.tick_params(labelsize=12)
ax.grid(True, alpha=0.3)

# Statistics는 LaTeX 캡션에 이미 포함되므로 plot 내부에 두지 않는다 (clutter 방지).

# Legend for families — 우하단 (lower-right): 해당 영역은 empty zone (데이터 포인트 없음)
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#E15759', edgecolor='black', label='xLAM-2'),
    Patch(facecolor='#4E79A7', edgecolor='black', label='Qwen3.5'),
    Patch(facecolor='#F28E2B', edgecolor='black', label='Qwen3'),
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=11, framealpha=0.95)

plt.tight_layout()
# bbox_inches='tight' 제거 - 동일 figsize의 다른 서브피겨와 saved image 크기 동일하게 유지
plt.savefig('_experiments/figures/fig_bfcl_vs_aml.png', dpi=300)
plt.savefig('_experiments/figures/fig_bfcl_vs_aml.pdf')
print('Saved: _experiments/figures/fig_bfcl_vs_aml.{png,pdf} @ 300 DPI')
