"""
Simulation Runner and Scenario Analysis Engine.
Executes multi-scenario stress-tests across Delhi NCR, Mumbai MMR, Bengaluru, Hyderabad, and Chennai.
Compares Baseline (Uncoordinated Heuristic) vs. AI-Optimized Framework.
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from config import CLUSTERS, TARGET_RELIABILITY, BASELINE_RELIABILITY
from forecasting_engine import WeatherAndDemandForecaster
from optimizer import ClusterEnergyOptimizer


def run_cluster_simulation(cluster_id: str, season: str = "normal", market_scenario: str = "normal") -> Dict[str, Any]:
    """
    Runs both Baseline and AI-Optimized simulations for a single cluster and scenario.
    """
    forecaster = WeatherAndDemandForecaster(seed=hash(cluster_id) % 10000 + 42)
    
    weather_df = forecaster.generate_weather_profile(cluster_id, season=season)
    renewable_df = forecaster.generate_renewable_generation(cluster_id, weather_df)
    demand_df = forecaster.generate_ev_demand_profile(cluster_id, weather_df)
    market_df = forecaster.generate_iex_market_prices(scenario=market_scenario)

    # 1. Baseline Model (Heuristic dispatch: 78% reliability target, 10% loss baseline)
    baseline_opt = ClusterEnergyOptimizer(cluster_id, mode="baseline")
    baseline_res = baseline_opt.solve_dispatch(
        weather_df, renewable_df, demand_df, market_df,
        reliability_target=BASELINE_RELIABILITY,
        max_loss_target=0.100
    )

    # 2. AI-Optimized Model (89.7%+ reliability target, <=8.0% loss target)
    opt_optimizer = ClusterEnergyOptimizer(cluster_id, mode="optimized")
    optimized_res = opt_optimizer.solve_dispatch(
        weather_df, renewable_df, demand_df, market_df,
        reliability_target=TARGET_RELIABILITY,
        max_loss_target=0.080
    )

    return {
        "cluster_id": cluster_id,
        "season": season,
        "market_scenario": market_scenario,
        "baseline": baseline_res,
        "optimized": optimized_res
    }


def run_full_suite() -> Dict[str, Any]:
    """
    Executes full multi-cluster stress suite across 4 representative operating regimes:
    1. Base / Autumn Normal
    2. Peak Summer Heatwave
    3. Severe Monsoon Cloud Cover
    4. Extreme IEX Wholesale Price Spike
    """
    scenarios = [
        {"name": "Base Normal", "season": "normal", "market": "normal"},
        {"name": "Peak Summer Heatwave", "season": "summer", "market": "normal"},
        {"name": "Monsoon Solar Slump", "season": "monsoon", "market": "normal"},
        {"name": "Wholesale Price Spike", "season": "summer", "market": "price_spike"}
    ]

    all_results = {}
    summary_records = []

    print("=" * 80)
    print("STARTING NATIONAL EV CHARGING & BATTERY SWAP OPTIMIZATION SIMULATION SUITE")
    print(f"Network: 1,200 MW Installed Capacity | 600 MWh Storage | 5 Metro Clusters")
    print("=" * 80)

    for sc in scenarios:
        sc_name = sc["name"]
        print(f"\n---> Simulating Scenario: {sc_name} (Season: {sc['season']}, Market: {sc['market']})")
        sc_cluster_res = {}

        for cluster_id, cluster_data in CLUSTERS.items():
            res = run_cluster_simulation(cluster_id, season=sc["season"], market_scenario=sc["market"])
            sc_cluster_res[cluster_id] = res

            b = res["baseline"]
            o = res["optimized"]

            summary_records.append({
                "Scenario": sc_name,
                "Cluster": cluster_data["name"],
                "Cluster_ID": cluster_id,
                "Installed_MW": cluster_data["total_mw"],
                "Storage_MWh": cluster_data["total_storage_mwh"],
                "Baseline_Reliability_%": round(b["reliability"] * 100, 2),
                "Optimized_Reliability_%": round(o["reliability"] * 100, 2),
                "Reliability_Improvement_%": round((o["reliability"] - b["reliability"]) * 100, 2),
                "Baseline_Loss_%": round(b["loss_pct"] * 100, 2),
                "Optimized_Loss_%": round(o["loss_pct"] * 100, 2),
                "Loss_Reduction_%": round((b["loss_pct"] - o["loss_pct"]) * 100, 2),
                "Baseline_EBITDA_Margin_%": round(b["ebitda_margin"] * 100, 2),
                "Optimized_EBITDA_Margin_%": round(o["ebitda_margin"] * 100, 2),
                "Daily_Revenue_INR_Lakh": round(o["total_revenue_inr"] / 1e5, 2),
                "Daily_EBITDA_INR_Lakh": round(o["ebitda_inr"] / 1e5, 2)
            })

            print(f"  [{cluster_id}] {cluster_data['name']:<12} | "
                  f"Reliability: {b['reliability']*100:.1f}% -> {o['reliability']*100:.1f}% | "
                  f"Losses: {b['loss_pct']*100:.2f}% -> {o['loss_pct']*100:.2f}% | "
                  f"EBITDA Margin: {o['ebitda_margin']*100:.1f}%")

        all_results[sc_name] = sc_cluster_res

    summary_df = pd.DataFrame(summary_records)
    
    # Save results to CSV & JSON
    out_dir = r"C:\Users\vedan\.gemini\antigravity\scratch\ev_energy_framework"
    csv_path = os.path.join(out_dir, "simulation_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    print("\n" + "=" * 80)
    print(f"Simulation Complete! Results saved to {csv_path}")
    print("=" * 80)

    # Print high-level scenario rollups
    print("\nOVERALL SCENARIO PERFORMANCE ROLLUP (NETWORK WEIGHTED):")
    rollup = summary_df.groupby("Scenario").agg({
        "Baseline_Reliability_%": "mean",
        "Optimized_Reliability_%": "mean",
        "Baseline_Loss_%": "mean",
        "Optimized_Loss_%": "mean",
        "Optimized_EBITDA_Margin_%": "mean",
        "Daily_Revenue_INR_Lakh": "sum",
        "Daily_EBITDA_INR_Lakh": "sum"
    }).round(2)
    print(rollup.to_string())

    return {
        "summary_df": summary_df,
        "rollup_df": rollup,
        "all_results": all_results
    }


if __name__ == "__main__":
    results = run_full_suite()
