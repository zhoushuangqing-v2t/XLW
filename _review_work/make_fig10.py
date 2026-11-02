# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(9.4, 4.9), dpi=300)
ax.set_xlim(0, 9.4)
ax.set_ylim(0, 4.9)
ax.axis("off")

def box(x, y, w, h, color, lines, title_size=11, body_size=9.2):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0.02,rounding_size=0.10",
                       linewidth=0.9, edgecolor="#7F7F7F", facecolor=color,
                       zorder=2)
    ax.add_patch(p)
    ax.text(x + w/2, y + h - 0.26, lines[0], ha="center", va="top",
            fontsize=title_size, fontweight="bold", color="#1F1F1F", zorder=3)
    if len(lines) > 1:
        ax.text(x + w/2, y + h/2 - 0.10, "\n".join(lines[1:]), ha="center", va="center",
                fontsize=body_size, color="#1F1F1F", linespacing=1.45, zorder=3)

# Three scenario boxes
box(0.20, 2.55, 2.65, 1.55, "#DCE9F7",
    ["S1  无限行矩阵", "共同固定基准", "9,996.04 元/日"])
box(3.38, 2.55, 2.65, 1.55, "#FCE4D6",
    ["S2  日间限行矩阵", "同一固定基准", "10,333.05 元/日"])
box(6.56, 2.42, 2.65, 1.80, "#E2EFDA",
    ["S3  日间限行", "GA + 有向2-opt", "候选中心可启用（主算例未启用）", "9,641.84 元/日"])

# Arrows and labels
def arrow(x1, x2, y, label):
    a = FancyArrowPatch((x1, y), (x2, y), arrowstyle="-|>", mutation_scale=13,
                        linewidth=1.2, color="#404040", zorder=4)
    ax.add_patch(a)
    ax.text((x1 + x2)/2, y + 0.20, label, ha="center", va="bottom",
            fontsize=8.8, color="#1F1F1F", zorder=6,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.2))

arrow(2.88, 3.35, 3.32, "+337.01 元/日（+3.37%）")
arrow(6.06, 6.53, 3.32, "−691.2 元/日（−6.69%）")

# Bottom decomposition box
p = FancyBboxPatch((0.20, 0.30), 9.01, 1.55,
                   boxstyle="round,pad=0.02,rounding_size=0.10",
                   linewidth=0.9, edgecolor="#A6A6A6", facecolor="#F2F2F2", zorder=2)
ax.add_patch(p)
ax.text(4.705, 1.55, "S3 − S1 = −354.20 元/日（−3.54%）",
        ha="center", va="center", fontsize=10.0, fontweight="bold", color="#1F1F1F", zorder=3)
ax.text(4.705, 1.02,
        "S3 − S2 分解：GA 88.03 元/日（0.85%）＋ 有向2-opt 603.18 元/日（5.84%）",
        ha="center", va="center", fontsize=9.2, color="#1F1F1F", zorder=3)
ax.text(4.705, 0.63,
        "有向2-opt 占 S3 − S2 的 87.3%；成本改善主要来自路径层局部搜索，而非候选中心启用",
        ha="center", va="center", fontsize=9.2, color="#1F1F1F", zorder=3)

plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
out = r"C:\Users\Administrator\Desktop\xlwcc\_review_work\fig10_scenario_logic.png"
plt.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
print("saved", out)
