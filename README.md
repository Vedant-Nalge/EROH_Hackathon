# ⚡ VoltGrid AI — National EV Energy Optimization Framework

<div align="center">

**🌐 LIVE DEMO → [https://vedant-nalge.github.io/EROH_Hackathon](https://vedant-nalge.github.io/EROH_Hackathon)**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-GitHub%20Pages-brightgreen)](https://vedant-nalge.github.io/EROH_Hackathon)

**An AI-powered decision framework for real-time energy allocation, storage optimization, and dynamic bidding across a 1,200 MW / 600 MWh national EV charging & battery-swap network**

*5 Indian Metro Clusters · 4 Stress-Test Regimes · 98.1% Service Reliability · +INR 1,784 Cr/yr EBITDA*

</div>

---

## 🌐 Run the Website (No Install Needed)

> **Judges / Reviewers** — just click the live link below, nothing to install:

### 👉 [https://vedant-nalge.github.io/EROH_Hackathon](https://vedant-nalge.github.io/EROH_Hackathon)

**Dashboard features:**
- 📊 24-hour Energy Dispatch Stack (Solar / Wind / BESS / Grid)
- 🏙️ Switch between 5 metro clusters: `DEL` `BOM` `BLR` `HYD` `MAA`
- 🔋 Battery Storage SoC curves over 24h
- 💰 Dynamic Pricing slider (±20% regulatory band)
- ▶️ **"Run Scenario"** button — animated solver walkthrough demo

---

## 📄 Technical Report (PDF)

> The full 17-page technical report is here:

### 👉 [`latex/report.pdf`](latex/report.pdf)

**Report covers:**
- Complete mathematical formulation (26 equations, MILP model)
- AI/ML forecasting architecture (Temporal Fusion Transformer)
- Multi-regime simulation results (4 scenarios × 5 clusters)
- Economic feasibility (+INR 1,784 Crore/yr EBITDA bridge)
- Battery degradation model, risk matrix, OCPP 2.0.1 integration

---

## 💻 Run Locally (Optional)

### 1. Clone the repo
```bash
git clone https://github.com/Vedant-Nalge/EROH_Hackathon.git
cd EROH_Hackathon
```

### 2. Open the website
```bash
# Windows
start index.html

# macOS / Linux
open index.html
```
> No server needed — pure HTML + JavaScript, opens directly in browser.

### 3. Run the Python simulation
```bash
pip install -r requirements.txt
python simulation_runner.py
```

### 4. Generate charts
```bash
python generate_plots.py
```

### 5. Recompile the PDF (requires MiKTeX or TeX Live)
```bash
cd latex
pdflatex report.tex
pdflatex report.tex
```

---

## 📊 Results Summary

| Metric | Baseline | Target | **VoltGrid AI** | Status |
|---|---|---|---|---|
| Service Reliability | 78.0% | ≥ 89.7% | **97.2% – 98.7%** | ✅ Exceeded |
| System Energy Losses | 10.0% | ≤ 8.00% | **8.00%** | ✅ Achieved |
| EBITDA Margin | 14–18% | ≥ 12.0% | **49.2% – 56.5%** | ✅ Exceeded |
| Emergency Reserves | Unmanaged | 5% locked | **60 MW / 30 MWh** | ✅ Compliant |
| Net Annual Value | Baseline | — | **+INR 1,784 Cr/yr** | ✅ Delivered |

---

## 📁 Project Structure

```
EROH_Hackathon/
│
├── 🌐 index.html                     ← Interactive dashboard (open this!)
├── 📄 README.md                      ← You are here
├── 📦 requirements.txt               ← Python dependencies
│
├── 🐍 config.py                      ← Cluster capacities, tariffs, loss factors
├── 🐍 forecasting_engine.py          ← Weather & demand forecasting
├── 🐍 optimizer.py                   ← MILP dispatch optimizer (PuLP CBC)
├── 🐍 simulation_runner.py           ← Multi-regime stress-test runner
├── 🐍 generate_plots.py              ← Chart generation
│
├── 📊 simulation_summary.csv         ← Results: 4 regimes × 5 clusters
│
├── 📐 latex/
│   ├── report.pdf                    ← ★ 17-PAGE TECHNICAL REPORT (READ THIS)
│   ├── report.tex                    ← LaTeX source
│   └── fig_*.png                     ← Charts embedded in report
│
└── 🌐 web/
    ├── index.html                    ← Dashboard source
    └── simulation_hourly_data.json  ← 24h simulation data
```

---

## 👤 Author

**Vedant Nalge** · [github.com/Vedant-Nalge](https://github.com/Vedant-Nalge)

---
<div align="center">
<sub>VoltGrid AI · Energy Systems, Quantitative Modeling & Power Operations · November 2026</sub>
</div>
