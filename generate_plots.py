"""
Generates high-resolution visualization charts summarizing the simulation findings.
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out_dir = r"C:\Users\vedan\.gemini\antigravity\scratch\ev_energy_framework"
csv_path = os.path.join(out_dir, "simulation_summary.csv")
df = pd.read_csv(csv_path)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Service Reliability Comparison across Clusters (Base Normal Scenario)
ax1 = axes[0, 0]
base_normal_df = df[df["Scenario"] == "Base Normal"]
clusters = base_normal_df["Cluster_ID"].tolist()
x = np.arange(len(clusters))
width = 0.35

ax1.bar(x - width/2, base_normal_df["Baseline_Reliability_%"], width, label="Baseline (Uncoordinated)", color="#e74c3c", alpha=0.85)
ax1.bar(x + width/2, base_normal_df["Optimized_Reliability_%"], width, label="AI-Optimized", color="#2ecc71", alpha=0.85)
ax1.axhline(89.7, color="#2980b9", linestyle="--", linewidth=1.5, label="Executive Target (89.7%)")
ax1.set_ylabel("Service Reliability (%)", fontsize=11, fontweight="bold")
ax1.set_title("Service Reliability by Metro Cluster (Base Regime)", fontsize=12, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(clusters, fontweight="bold")
ax1.set_ylim(60, 105)
ax1.legend(loc="lower right")

# 2. System Loss Reduction (Baseline vs Optimized)
ax2 = axes[0, 1]
ax2.bar(x - width/2, base_normal_df["Baseline_Loss_%"], width, label="Baseline Loss", color="#e67e22", alpha=0.85)
ax2.bar(x + width/2, base_normal_df["Optimized_Loss_%"], width, label="Optimized Loss", color="#3498db", alpha=0.85)
ax2.axhline(8.0, color="#27ae60", linestyle="--", linewidth=1.5, label="Loss Cap Target (8.0%)")
ax2.set_ylabel("Total System Losses (%)", fontsize=11, fontweight="bold")
ax2.set_title("Energy Storage & Conversion Losses (20% Target Reduction)", fontsize=12, fontweight="bold")
ax2.set_xticks(x)
ax2.set_xticklabels(clusters, fontweight="bold")
ax2.set_ylim(0, 13)
ax2.legend(loc="upper right")

# 3. EBITDA Margins Across Stress Scenarios
ax3 = axes[1, 0]
scenarios = df["Scenario"].unique()
sc_ebitda = df.groupby("Scenario")["Optimized_EBITDA_Margin_%"].mean()
colors = ["#1abc9c", "#34495e", "#9b59b6", "#e74c3c"]
bars = ax3.bar(sc_ebitda.index, sc_ebitda.values, color=colors, alpha=0.85, width=0.5)
ax3.axhline(12.0, color="#c0392b", linestyle="--", linewidth=2.0, label="Min Target (12.0%)")
ax3.set_ylabel("EBITDA Margin (%)", fontsize=11, fontweight="bold")
ax3.set_title("Cluster-Average EBITDA Margin Across Stress Regimes", fontsize=12, fontweight="bold")
ax3.set_ylim(0, 70)
for bar in bars:
    yval = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 1.2, f"{yval:.1f}%", ha='center', va='bottom', fontweight='bold')
ax3.legend(loc="upper right")
ax3.tick_params(axis='x', rotation=15)

# 4. Daily Network Revenue & EBITDA (INR Crore)
ax4 = axes[1, 1]
daily_rev_cr = df.groupby("Scenario")["Daily_Revenue_INR_Lakh"].sum() / 100.0 # Convert Lakh to Crore
daily_ebitda_cr = df.groupby("Scenario")["Daily_EBITDA_INR_Lakh"].sum() / 100.0
x_sc = np.arange(len(scenarios))
ax4.bar(x_sc - width/2, daily_rev_cr.values, width, label="Daily Revenue (₹ Cr)", color="#3498db", alpha=0.85)
ax4.bar(x_sc + width/2, daily_ebitda_cr.values, width, label="Daily EBITDA (₹ Cr)", color="#2ecc71", alpha=0.85)
ax4.set_ylabel("INR (Crores / Day)", fontsize=11, fontweight="bold")
ax4.set_title("Daily Financial Performance Across 1,200 MW Network", fontsize=12, fontweight="bold")
ax4.set_xticks(x_sc)
ax4.set_xticklabels(scenarios, rotation=15, fontweight="bold")
ax4.legend(loc="upper left")

plt.tight_layout()
chart_path = os.path.join(out_dir, "simulation_results_dashboard.png")
plt.savefig(chart_path, dpi=200)
plt.close()
print(f"Summary visualization saved successfully to {chart_path}")
