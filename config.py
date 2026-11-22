"""
Configuration and Parameters for the National EV Charging and Battery Swapping Energy Network.
Clusters: Delhi NCR, Mumbai MMR, Bengaluru, Hyderabad, Chennai.
Total Capacity: 1,200 MW | Total Storage: 600 MWh
"""

import numpy as np

# Metro Clusters Configuration
CLUSTERS = {
    "DEL": {
        "name": "Delhi NCR",
        "total_mw": 320.0,
        "dcfc_mw": 192.0,      # 60%
        "swap_mw": 128.0,      # 40%
        "total_storage_mwh": 160.0,
        "bess_mwh": 64.0,       # Stationary BESS
        "swap_storage_mwh": 96.0, # Swap pack inventory
        "base_fleet_share": 0.65, # High commercial 2W/3W/cab fleet share
        "summer_temp_peak": 44.0, # Ambient extreme (Celsius)
        "monsoon_solar_factor": 0.40,
        "grid_connection_limit_mw": 300.0,
    },
    "BOM": {
        "name": "Mumbai MMR",
        "total_mw": 280.0,
        "dcfc_mw": 168.0,
        "swap_mw": 112.0,
        "total_storage_mwh": 140.0,
        "bess_mwh": 56.0,
        "swap_storage_mwh": 84.0,
        "base_fleet_share": 0.58,
        "summer_temp_peak": 36.0,
        "monsoon_solar_factor": 0.25, # Heavy monsoon cloud cover
        "grid_connection_limit_mw": 260.0,
    },
    "BLR": {
        "name": "Bengaluru",
        "total_mw": 240.0,
        "dcfc_mw": 144.0,
        "swap_mw": 96.0,
        "total_storage_mwh": 120.0,
        "bess_mwh": 48.0,
        "swap_storage_mwh": 72.0,
        "base_fleet_share": 0.50,
        "summer_temp_peak": 36.0,
        "monsoon_solar_factor": 0.45,
        "grid_connection_limit_mw": 230.0,
    },
    "HYD": {
        "name": "Hyderabad",
        "total_mw": 200.0,
        "dcfc_mw": 120.0,
        "swap_mw": 80.0,
        "total_storage_mwh": 100.0,
        "bess_mwh": 40.0,
        "swap_storage_mwh": 60.0,
        "base_fleet_share": 0.55,
        "summer_temp_peak": 42.0,
        "monsoon_solar_factor": 0.40,
        "grid_connection_limit_mw": 190.0,
    },
    "MAA": {
        "name": "Chennai",
        "total_mw": 160.0,
        "dcfc_mw": 96.0,
        "swap_mw": 64.0,
        "total_storage_mwh": 80.0,
        "bess_mwh": 32.0,
        "swap_storage_mwh": 48.0,
        "base_fleet_share": 0.52,
        "summer_temp_peak": 41.0,
        "monsoon_solar_factor": 0.50,
        "grid_connection_limit_mw": 150.0,
    }
}

# Aggregate Network Constants
TOTAL_NETWORK_CAPACITY_MW = 1200.0
TOTAL_DCFC_MW = 720.0
TOTAL_SWAP_MW = 480.0
TOTAL_STORAGE_MWH = 600.0
TOTAL_BESS_MWH = 240.0
TOTAL_SWAP_STORAGE_MWH = 360.0

# Regulatory & Reserve Mandate
RESERVE_CAPACITY_FRACTION = 0.05       # 5% uncommitted capacity for emergency/priority fleet
RESERVE_SWAP_PACK_FRACTION = 0.05     # 5% uncommitted swap inventory

# Energy Sourcing Mix & Pricing (INR / kWh)
OPEN_ACCESS_SHARE = 0.35              # 35% contracted renewable energy (Solar 22%, Wind 13%)
OA_SOLAR_TARIFF = 3.10                # Long term PPA tariff
OA_WIND_TARIFF = 3.65                 # Long term Wind PPA tariff
OA_BLENDED_TARIFF = 0.63 * OA_SOLAR_TARIFF + 0.37 * OA_WIND_TARIFF # ~ 3.30 INR/kWh
OA_WHEELING_LOSS_PCT = 0.035          # 3.5% ISTS/InSTS wheeling loss

# DISCOM Time-of-Day (ToD) Tariff Structure (INR / kWh)
DISCOM_TARIFF = {
    "off_peak": 4.90,   # 22:00 - 06:00
    "normal": 6.80,     # 09:00 - 18:00
    "peak": 9.20        # 06:00 - 09:00, 18:00 - 22:00
}

# Retail Pricing & Elasticity Parameters
BASE_DCFC_RETAIL_PRICE = 16.50        # INR / kWh
BASE_SWAP_EQUIV_PRICE = 18.50         # INR / kWh equivalent (e.g. ₹74 per 4 kWh pack)
PRICE_BOUND_PCT = 0.20                # ±20% limit relative to previous day average
PRICE_ELASTICITY = {
    "retail": -0.65,                  # Sensitive to surge pricing
    "ridehail": -0.40,                # Moderate flexibility (can shift hubs or delay by 30-45m)
    "logistics": -0.18                # Inelastic schedule constraints, high SLA priority
}

# Loss Characteristics & Baseline vs Target
LOSS_FACTORS = {
    "baseline": {
        "charger_efficiency": 0.92,       # 8% power electronic conversion loss
        "bess_roundtrip_eff": 0.86,       # 14% round-trip BESS loss
        "swap_roundtrip_eff": 0.84,       # 16% round-trip pack loss (frequent cycling)
        "idle_self_discharge_daily": 0.025,# 2.5% per day including standby parasitic HVAC
        "distribution_loss": 0.025,       # 2.5% local transformer and cable loss
        "blended_total_loss_target": 0.100# Baseline 10.0% loss
    },
    "optimized": {
        "charger_efficiency": 0.955,      # 4.5% loss with modular stage-switching
        "bess_roundtrip_eff": 0.915,      # 8.5% loss with thermal pre-conditioning
        "swap_roundtrip_eff": 0.900,      # 10% loss with smart C-rate (C/3 default, 1C peak)
        "idle_self_discharge_daily": 0.008,# 0.8% daily with deep idle hibernation
        "distribution_loss": 0.016,       # 1.6% loss with power-factor active correction
        "blended_total_loss_target": 0.080# Target 8.0% loss (20% reduction)
    }
}

# Battery Degradation Parameters (LFP / NMC commercial cells)
BATTERY_CAPITAL_COST_INR_PER_KWH = 8200.0  # ₹8,200 / kWh (~ $98/kWh)
LFP_BASE_CYCLE_LIFE = 3500                 # At 80% DoD, 25°C, 0.5C
DEGRADATION_COEFF_ALPHA = 1.8e-4           # Per-cycle baseline fade rate
TEMP_ACCELERATION_COEFF = 0.038            # 3.8% increase in fade rate per °C above 30°C
CRATE_STRESS_EXPONENT = 1.35               # Non-linear stress exponent for C-rate > 0.7C

# SLA and Reliability Targets
BASELINE_RELIABILITY = 0.78                # 78% currently delivered
TARGET_RELIABILITY = 0.897                 # 89.7% target (~90%, 15% relative improvement)
UNMET_DEMAND_PENALTY_INR_PER_KWH = 24.0    # Opportunity loss + customer churn penalty
MIN_EBITDA_MARGIN_TARGET = 0.12            # 12% across each metro cluster
