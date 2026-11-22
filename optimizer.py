"""
Mixed-Integer Linear Programming (MILP) Optimization Engine for Regional Energy Allocation,
Storage Scheduling, Dynamic Bidding (IEX DAM/RTM, Open Access, DISCOM), and Demand Steering.
"""

import pulp
import numpy as np
import pandas as pd
from typing import Dict, Any
from config import (
    CLUSTERS, RESERVE_CAPACITY_FRACTION, RESERVE_SWAP_PACK_FRACTION,
    OA_SOLAR_TARIFF, OA_WIND_TARIFF, OA_WHEELING_LOSS_PCT,
    DISCOM_TARIFF, BASE_DCFC_RETAIL_PRICE, BASE_SWAP_EQUIV_PRICE,
    PRICE_ELASTICITY, LOSS_FACTORS, BATTERY_CAPITAL_COST_INR_PER_KWH,
    LFP_BASE_CYCLE_LIFE, TARGET_RELIABILITY, BASELINE_RELIABILITY,
    UNMET_DEMAND_PENALTY_INR_PER_KWH
)


class ClusterEnergyOptimizer:
    """
    Optimizes hourly multi-source energy procurement, stationary BESS & swap pack storage,
    dynamic retail/swap pricing, loss minimization, and reserve guarantees for an Indian metro cluster.
    """

    def __init__(self, cluster_id: str, mode: str = "optimized"):
        self.cluster_id = cluster_id
        self.cluster = CLUSTERS[cluster_id]
        self.mode = mode
        self.loss_cfg = LOSS_FACTORS[mode]

    def solve_dispatch(
        self,
        weather_df: pd.DataFrame,
        renewable_df: pd.DataFrame,
        demand_df: pd.DataFrame,
        market_df: pd.DataFrame,
        reliability_target: float = TARGET_RELIABILITY,
        max_loss_target: float = 0.080
    ) -> Dict[str, Any]:
        """
        Solves dispatch under:
        1. 'optimized': Full multi-horizon AI MILP with dynamic pricing, predictive pre-charging,
           loss minimization, reserve protection.
        2. 'baseline': Uncoordinated heuristic matching current operator status (inflexible flat pricing,
           unmanaged charging causing peak queues and pack stockouts, 78% reliability, 10% losses).
        """
        T = len(weather_df)
        hours = list(range(T))
        c = self.cluster
        grid_cap = c["grid_connection_limit_mw"]

        bess_capacity = c["bess_mwh"]
        swap_capacity = c["swap_storage_mwh"]

        # Reserve requirements: 5% uncommitted capacity & swap packs
        reserve_mw = c["total_mw"] * RESERVE_CAPACITY_FRACTION
        reserve_swap_mwh = swap_capacity * RESERVE_SWAP_PACK_FRACTION
        grid_effective_limit = max(10.0, grid_cap - reserve_mw)

        if self.mode == "baseline":
            # -------------------------------------------------------------
            # Uncoordinated Baseline Heuristic (Current Operating Regime)
            # -------------------------------------------------------------
            # In baseline: Flat pricing (no dynamic steering), naive immediate charging,
            # severe peak bottleneck (18:00 - 22:00) where grid cap & depleted swap packs
            # cause queue turn-aways and stockouts, resulting in ~78% reliability.
            results = []
            curr_bess_soc = 0.50 * bess_capacity
            curr_swap_soc = 0.65 * swap_capacity

            eta_conv = self.loss_cfg["charger_efficiency"] # 0.92
            eta_bess_rte = self.loss_cfg["bess_roundtrip_eff"] # 0.86
            eta_swap_rte = self.loss_cfg["swap_roundtrip_eff"] # 0.84
            idle_loss_hourly = self.loss_cfg["idle_self_discharge_daily"] / 24.0 # 2.5% daily
            eta_dist = 1.0 - self.loss_cfg["distribution_loss"] # 0.025

            degradation_cost_per_mwh = (BATTERY_CAPITAL_COST_INR_PER_KWH * 1000.0) / (LFP_BASE_CYCLE_LIFE * 2 * 0.8)

            for t in hours:
                dcfc_req = float(demand_df.loc[t, "dcfc_demand_mw"])
                swap_req = float(demand_df.loc[t, "swap_demand_mw"])
                solar_avail = float(renewable_df.loc[t, "oa_solar_mw"])
                wind_avail = float(renewable_df.loc[t, "oa_wind_mw"])
                dam_p = float(market_df.loc[t, "iex_dam_price"])
                rtm_p = float(market_df.loc[t, "iex_rtm_price"])

                # In baseline, during peak hours (17:00-22:00), demand exceeds local grid throughput
                # and swap inventory is depleted due to unmanaged charging, causing 22% stockouts/dropoffs.
                # Calibrated to operator's reported 78.0% service reliability.
                is_peak_strain = (17 <= t <= 21) or (8 <= t <= 10)
                if is_peak_strain:
                    serve_ratio = 0.68  # Peak congestion & stockout
                else:
                    serve_ratio = 0.86  # Non-peak mismatch due to regional wind lull / solar forecast error

                dcfc_s = dcfc_req * serve_ratio
                swap_s = min(swap_req * serve_ratio, max(0.0, curr_swap_soc - reserve_swap_mwh))

                # Unmanaged charging: swap packs charged immediately at high C-rate
                swap_ch = min(c["swap_mw"] * 0.8, (swap_capacity - curr_swap_soc) / eta_swap_rte)
                
                # Baseline BESS is uncoordinated: idle or charged at wrong times
                bess_ch = 0.0
                bess_dis = 0.0
                if is_peak_strain and curr_bess_soc > 0.20 * bess_capacity:
                    bess_dis = min(0.3 * bess_capacity, curr_bess_soc - 0.10 * bess_capacity)
                elif not is_peak_strain and solar_avail > 10.0 and curr_bess_soc < 0.80 * bess_capacity:
                    bess_ch = min(0.3 * bess_capacity, 0.90 * bess_capacity - curr_bess_soc)

                # Storage updates
                curr_bess_soc = np.clip(curr_bess_soc + bess_ch * np.sqrt(eta_bess_rte) - bess_dis / np.sqrt(eta_bess_rte), 0.10 * bess_capacity, 0.95 * bess_capacity)
                curr_swap_soc = np.clip(curr_swap_soc + swap_ch * eta_swap_rte - swap_s - curr_swap_soc * idle_loss_hourly, reserve_swap_mwh, swap_capacity)

                # Power procurement
                hub_power = (dcfc_s / eta_conv) + bess_ch + swap_ch
                net_grid_needed = max(0.0, hub_power - bess_dis) / eta_dist

                solar_used = min(solar_avail * (1.0 - OA_WHEELING_LOSS_PCT), net_grid_needed)
                rem = net_grid_needed - solar_used
                wind_used = min(wind_avail * (1.0 - OA_WHEELING_LOSS_PCT), rem)
                rem -= wind_used

                # Naive DISCOM and DAM split
                dam_procure = min(rem * 0.60, grid_effective_limit)
                discom_procure = min(rem - dam_procure, grid_effective_limit)
                rtm_buy = max(0.0, rem - (dam_procure + discom_procure))

                # Losses
                loss_t = (
                    (1.0 - eta_conv) * (dcfc_s + swap_ch) +
                    (1.0 - eta_bess_rte) * bess_dis +
                    idle_loss_hourly * curr_swap_soc +
                    (1.0 - eta_dist) * net_grid_needed
                )

                rev_inr = (dcfc_s * BASE_DCFC_RETAIL_PRICE + swap_s * BASE_SWAP_EQUIV_PRICE) * 1000.0

                if (6 <= t < 9) or (18 <= t < 22):
                    discom_p = DISCOM_TARIFF["peak"]
                elif (22 <= t <= 23) or (0 <= t < 6):
                    discom_p = DISCOM_TARIFF["off_peak"]
                else:
                    discom_p = DISCOM_TARIFF["normal"]

                procure_cost = (
                    solar_used * OA_SOLAR_TARIFF +
                    wind_used * OA_WIND_TARIFF +
                    dam_procure * dam_p +
                    rtm_buy * rtm_p +
                    discom_procure * discom_p
                ) * 1000.0

                deg_cost = (bess_dis + swap_ch) * degradation_cost_per_mwh

                results.append({
                    "hour": t,
                    "dcfc_served_mw": dcfc_s,
                    "swap_served_mw": swap_s,
                    "total_served_mw": dcfc_s + swap_s,
                    "unmet_demand_mw": (dcfc_req + swap_req) - (dcfc_s + swap_s),
                    "dcfc_price_inr": BASE_DCFC_RETAIL_PRICE,
                    "swap_price_inr": BASE_SWAP_EQUIV_PRICE,
                    "solar_used_mw": solar_used,
                    "wind_used_mw": wind_used,
                    "dam_mw": dam_procure,
                    "rtm_buy_mw": rtm_buy,
                    "rtm_sell_mw": 0.0,
                    "discom_mw": discom_procure,
                    "bess_soc_mwh": curr_bess_soc,
                    "swap_soc_mwh": curr_swap_soc,
                    "bess_ch_mw": bess_ch,
                    "bess_dis_mw": bess_dis,
                    "swap_ch_mw": swap_ch,
                    "system_loss_mw": loss_t,
                    "revenue_inr": rev_inr,
                    "procurement_cost_inr": procure_cost,
                    "degradation_cost_inr": deg_cost
                })

            res_df = pd.DataFrame(results)
            total_served = res_df["total_served_mw"].sum()
            total_forecast = demand_df["total_demand_mw"].sum()
            actual_reliability = total_served / total_forecast if total_forecast > 0 else 0.78

            total_loss = res_df["system_loss_mw"].sum()
            total_throughput = total_served + total_loss
            loss_pct = (total_loss / total_throughput) if total_throughput > 0 else 0.10

            total_rev = res_df["revenue_inr"].sum()
            total_procure = res_df["procurement_cost_inr"].sum()
            total_deg = res_df["degradation_cost_inr"].sum()
            hub_opex = 0.14 * total_rev
            ebitda = total_rev - total_procure - hub_opex - total_deg
            ebitda_margin = (ebitda / total_rev) if total_rev > 0 else 0.0

            return {
                "status": "Heuristic_Baseline",
                "success": True,
                "cluster_id": self.cluster_id,
                "mode": self.mode,
                "reliability": actual_reliability,
                "loss_pct": loss_pct,
                "total_revenue_inr": total_rev,
                "total_procurement_cost_inr": total_procure,
                "degradation_cost_inr": total_deg,
                "ebitda_inr": ebitda,
                "ebitda_margin": ebitda_margin,
                "hourly_df": res_df
            }

        # ---------------------------------------------------------
        # AI-Optimized MILP Framework
        # ---------------------------------------------------------
        prob = pulp.LpProblem(f"Energy_Optimization_{self.cluster_id}_{self.mode}", pulp.LpMaximize)

        p_solar = pulp.LpVariable.dicts("P_Solar", hours, lowBound=0, upBound=grid_cap)
        p_wind = pulp.LpVariable.dicts("P_Wind", hours, lowBound=0, upBound=grid_cap)
        p_dam = pulp.LpVariable.dicts("P_DAM", hours, lowBound=0, upBound=grid_cap)
        p_rtm_buy = pulp.LpVariable.dicts("P_RTM_Buy", hours, lowBound=0, upBound=grid_cap)
        
        max_export_mw = 0.25 * grid_cap
        p_rtm_sell = pulp.LpVariable.dicts("P_RTM_Sell", hours, lowBound=0, upBound=max_export_mw)
        p_discom = pulp.LpVariable.dicts("P_DISCOM", hours, lowBound=0, upBound=grid_cap)

        e_bess = pulp.LpVariable.dicts("E_BESS", hours, lowBound=0, upBound=bess_capacity)
        p_bess_ch = pulp.LpVariable.dicts("P_BESS_Ch", hours, lowBound=0, upBound=0.5 * bess_capacity)
        p_bess_dis = pulp.LpVariable.dicts("P_BESS_Dis", hours, lowBound=0, upBound=0.5 * bess_capacity)

        e_swap = pulp.LpVariable.dicts("E_Swap_Inv", hours, lowBound=0, upBound=swap_capacity)
        p_swap_ch = pulp.LpVariable.dicts("P_Swap_Ch", hours, lowBound=0, upBound=c["swap_mw"])

        price_mults = [0.80, 0.90, 1.00, 1.10, 1.20]
        K = len(price_mults)

        z_dcfc = pulp.LpVariable.dicts("Z_DCFC", (hours, range(K)), cat=pulp.LpBinary)
        z_swap = pulp.LpVariable.dicts("Z_Swap", (hours, range(K)), cat=pulp.LpBinary)

        dcfc_served_k = pulp.LpVariable.dicts("DCFC_Served_K", (hours, range(K)), lowBound=0)
        swap_served_k = pulp.LpVariable.dicts("Swap_Served_K", (hours, range(K)), lowBound=0)

        dcfc_served = pulp.LpVariable.dicts("DCFC_Served", hours, lowBound=0, upBound=c["dcfc_mw"])
        swap_served = pulp.LpVariable.dicts("Swap_Served", hours, lowBound=0, upBound=c["swap_mw"])
        unmet_demand = pulp.LpVariable.dicts("Unmet_Demand", hours, lowBound=0)
        system_loss = pulp.LpVariable.dicts("System_Loss", hours, lowBound=0)

        fleet_share = c["base_fleet_share"]
        eff_elasticity_dcfc = fleet_share * PRICE_ELASTICITY["ridehail"] + (1 - fleet_share) * PRICE_ELASTICITY["retail"]
        eff_elasticity_swap = fleet_share * PRICE_ELASTICITY["logistics"] + (1 - fleet_share) * PRICE_ELASTICITY["retail"]

        bracket_dcfc_price = [BASE_DCFC_RETAIL_PRICE * m for m in price_mults]
        bracket_swap_price = [BASE_SWAP_EQUIV_PRICE * m for m in price_mults]

        initial_bess_soc = 0.50 * bess_capacity
        initial_swap_soc = 0.65 * swap_capacity
        min_bess_soc = 0.10 * bess_capacity
        max_bess_soc = 0.95 * bess_capacity

        eta_ch = np.sqrt(self.loss_cfg["bess_roundtrip_eff"])
        eta_dis = np.sqrt(self.loss_cfg["bess_roundtrip_eff"])
        eta_conv = self.loss_cfg["charger_efficiency"]
        eta_dist = 1.0 - self.loss_cfg["distribution_loss"]
        idle_loss_hourly = self.loss_cfg["idle_self_discharge_daily"] / 24.0

        for t in hours:
            prob += p_solar[t] <= float(renewable_df.loc[t, "oa_solar_mw"])
            prob += p_wind[t] <= float(renewable_df.loc[t, "oa_wind_mw"])

            prob += pulp.lpSum([z_dcfc[t][k] for k in range(K)]) == 1
            prob += pulp.lpSum([z_swap[t][k] for k in range(K)]) == 1

            base_dcfc_t = float(demand_df.loc[t, "dcfc_demand_mw"])
            base_swap_t = float(demand_df.loc[t, "swap_demand_mw"])

            for k in range(K):
                cap_dcfc_k = base_dcfc_t * max(0.1, (1.0 + eff_elasticity_dcfc * (price_mults[k] - 1.0)))
                prob += dcfc_served_k[t][k] <= z_dcfc[t][k] * cap_dcfc_k

                cap_swap_k = base_swap_t * max(0.1, (1.0 + eff_elasticity_swap * (price_mults[k] - 1.0)))
                prob += swap_served_k[t][k] <= z_swap[t][k] * cap_swap_k

            prob += dcfc_served[t] == pulp.lpSum([dcfc_served_k[t][k] for k in range(K)])
            prob += swap_served[t] == pulp.lpSum([swap_served_k[t][k] for k in range(K)])

            prob += unmet_demand[t] >= (base_dcfc_t + base_swap_t) - (dcfc_served[t] + swap_served[t])

            grid_import = (p_solar[t] + p_wind[t]) * (1.0 - OA_WHEELING_LOSS_PCT) + p_dam[t] + p_rtm_buy[t] + p_discom[t]
            prob += grid_import <= grid_effective_limit
            prob += p_rtm_sell[t] <= p_bess_dis[t] + 0.5 * (p_solar[t] + p_wind[t])

            if t == 0:
                prob += e_bess[t] == initial_bess_soc + (p_bess_ch[t] * eta_ch - p_bess_dis[t] / eta_dis)
            else:
                prob += e_bess[t] == e_bess[t-1] + (p_bess_ch[t] * eta_ch - p_bess_dis[t] / eta_dis)

            prob += e_bess[t] >= min_bess_soc
            prob += e_bess[t] <= max_bess_soc

            swap_recharge_eff = self.loss_cfg["swap_roundtrip_eff"]
            if t == 0:
                prob += e_swap[t] == initial_swap_soc + p_swap_ch[t] * swap_recharge_eff - swap_served[t] - initial_swap_soc * idle_loss_hourly
            else:
                prob += e_swap[t] == e_swap[t-1] + p_swap_ch[t] * swap_recharge_eff - swap_served[t] - e_swap[t-1] * idle_loss_hourly

            # Hard 5% reserve obligation
            prob += e_swap[t] >= reserve_swap_mwh
            prob += e_swap[t] <= swap_capacity

            total_hub_power = (dcfc_served[t] / eta_conv) + p_bess_ch[t] + p_swap_ch[t]
            prob += grid_import * eta_dist + p_bess_dis[t] >= total_hub_power + p_rtm_sell[t]

            prob += system_loss[t] >= (
                (1.0 - eta_conv) * (dcfc_served[t] + p_swap_ch[t]) +
                (1.0 - self.loss_cfg["bess_roundtrip_eff"]) * p_bess_dis[t] +
                idle_loss_hourly * e_swap[t] +
                (1.0 - eta_dist) * grid_import
            )

        total_forecast_demand = float(demand_df["total_demand_mw"].sum())
        total_served_demand = pulp.lpSum([dcfc_served[t] + swap_served[t] for t in hours])
        total_system_losses = pulp.lpSum([system_loss[t] for t in hours])

        # Enforce Reliability Target (>= 89.7%)
        prob += total_served_demand >= reliability_target * total_forecast_demand

        # Enforce Loss Target (<= 8.0%)
        max_loss_ratio = max_loss_target / (1.0 - max_loss_target)
        prob += total_system_losses <= max_loss_ratio * total_served_demand

        rev_components = []
        cost_components = []
        degradation_cost_per_mwh = (BATTERY_CAPITAL_COST_INR_PER_KWH * 1000.0) / (LFP_BASE_CYCLE_LIFE * 2 * 0.8)

        for t in hours:
            rev_dcfc_t = pulp.lpSum([dcfc_served_k[t][k] * bracket_dcfc_price[k] * 1000.0 for k in range(K)])
            rev_swap_t = pulp.lpSum([swap_served_k[t][k] * bracket_swap_price[k] * 1000.0 for k in range(K)])
            rev_components.append(rev_dcfc_t + rev_swap_t)

            dam_p = float(market_df.loc[t, "iex_dam_price"]) * 1000.0
            rtm_p = float(market_df.loc[t, "iex_rtm_price"]) * 1000.0
            
            if (6 <= t < 9) or (18 <= t < 22):
                discom_p = DISCOM_TARIFF["peak"] * 1000.0
            elif (22 <= t <= 23) or (0 <= t < 6):
                discom_p = DISCOM_TARIFF["off_peak"] * 1000.0
            else:
                discom_p = DISCOM_TARIFF["normal"] * 1000.0

            cost_t = (
                p_solar[t] * OA_SOLAR_TARIFF * 1000.0 +
                p_wind[t] * OA_WIND_TARIFF * 1000.0 +
                p_dam[t] * dam_p +
                p_rtm_buy[t] * rtm_p -
                p_rtm_sell[t] * (rtm_p * 0.90) +
                p_discom[t] * discom_p +
                (p_bess_dis[t] + p_swap_ch[t]) * degradation_cost_per_mwh +
                unmet_demand[t] * UNMET_DEMAND_PENALTY_INR_PER_KWH * 1000.0
            )
            cost_components.append(cost_t)

        prob += pulp.lpSum(rev_components) - pulp.lpSum(cost_components)

        prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=60))

        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            print(f"Warning: {self.cluster_id} solver returned {status}.")
            return {"status": status, "success": False}

        results = []
        for t in hours:
            dcfc_bracket_idx = max(range(K), key=lambda k: pulp.value(z_dcfc[t][k]) or 0)
            swap_bracket_idx = max(range(K), key=lambda k: pulp.value(z_swap[t][k]) or 0)

            dcfc_p_val = bracket_dcfc_price[dcfc_bracket_idx]
            swap_p_val = bracket_swap_price[swap_bracket_idx]

            dcfc_s = float(pulp.value(dcfc_served[t]))
            swap_s = float(pulp.value(swap_served[t]))
            unmet_s = float(pulp.value(unmet_demand[t]))
            loss_s = float(pulp.value(system_loss[t]))

            dam_s = float(pulp.value(p_dam[t]))
            rtm_buy_s = float(pulp.value(p_rtm_buy[t]))
            rtm_sell_s = float(pulp.value(p_rtm_sell[t]))
            discom_s = float(pulp.value(p_discom[t]))
            solar_s = float(pulp.value(p_solar[t]))
            wind_s = float(pulp.value(p_wind[t]))

            bess_soc_s = float(pulp.value(e_bess[t]))
            swap_soc_s = float(pulp.value(e_swap[t]))
            bess_ch_s = float(pulp.value(p_bess_ch[t]))
            bess_dis_s = float(pulp.value(p_bess_dis[t]))
            swap_ch_s = float(pulp.value(p_swap_ch[t]))

            rev_inr = (dcfc_s * dcfc_p_val + swap_s * swap_p_val) * 1000.0
            dam_p = float(market_df.loc[t, "iex_dam_price"])
            rtm_p = float(market_df.loc[t, "iex_rtm_price"])

            if (6 <= t < 9) or (18 <= t < 22):
                discom_p = DISCOM_TARIFF["peak"]
            elif (22 <= t <= 23) or (0 <= t < 6):
                discom_p = DISCOM_TARIFF["off_peak"]
            else:
                discom_p = DISCOM_TARIFF["normal"]

            procure_cost_inr = (
                solar_s * OA_SOLAR_TARIFF +
                wind_s * OA_WIND_TARIFF +
                dam_s * dam_p +
                rtm_buy_s * rtm_p -
                rtm_sell_s * (rtm_p * 0.90) +
                discom_s * discom_p
            ) * 1000.0

            deg_cost_inr = (bess_dis_s + swap_ch_s) * degradation_cost_per_mwh

            results.append({
                "hour": t,
                "dcfc_served_mw": dcfc_s,
                "swap_served_mw": swap_s,
                "total_served_mw": dcfc_s + swap_s,
                "unmet_demand_mw": unmet_s,
                "dcfc_price_inr": dcfc_p_val,
                "swap_price_inr": swap_p_val,
                "solar_used_mw": solar_s,
                "wind_used_mw": wind_s,
                "dam_mw": dam_s,
                "rtm_buy_mw": rtm_buy_s,
                "rtm_sell_mw": rtm_sell_s,
                "discom_mw": discom_s,
                "bess_soc_mwh": bess_soc_s,
                "swap_soc_mwh": swap_soc_s,
                "bess_ch_mw": bess_ch_s,
                "bess_dis_mw": bess_dis_s,
                "swap_ch_mw": swap_ch_s,
                "system_loss_mw": loss_s,
                "revenue_inr": rev_inr,
                "procurement_cost_inr": procure_cost_inr,
                "degradation_cost_inr": deg_cost_inr
            })

        res_df = pd.DataFrame(results)

        total_served = res_df["total_served_mw"].sum()
        total_forecast = demand_df["total_demand_mw"].sum()
        actual_reliability = total_served / total_forecast if total_forecast > 0 else 1.0

        total_loss = res_df["system_loss_mw"].sum()
        total_throughput = total_served + total_loss
        loss_pct = (total_loss / total_throughput) if total_throughput > 0 else 0.0

        total_rev = res_df["revenue_inr"].sum()
        total_procure = res_df["procurement_cost_inr"].sum()
        total_deg = res_df["degradation_cost_inr"].sum()
        hub_opex = 0.14 * total_rev
        ebitda = total_rev - total_procure - hub_opex - total_deg
        ebitda_margin = (ebitda / total_rev) if total_rev > 0 else 0.0

        return {
            "status": "Optimal",
            "success": True,
            "cluster_id": self.cluster_id,
            "mode": self.mode,
            "reliability": actual_reliability,
            "loss_pct": loss_pct,
            "total_revenue_inr": total_rev,
            "total_procurement_cost_inr": total_procure,
            "degradation_cost_inr": total_deg,
            "ebitda_inr": ebitda,
            "ebitda_margin": ebitda_margin,
            "hourly_df": res_df
        }
