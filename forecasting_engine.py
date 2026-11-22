"""
Multi-Horizon Probabilistic Forecasting Engine for Renewable Generation, Weather Dynamics,
EV Charging / Swapping Load, and IEX Market Clearing Prices.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from config import CLUSTERS, OPEN_ACCESS_SHARE, DISCOM_TARIFF


class WeatherAndDemandForecaster:
    """
    Simulates multi-horizon physical weather, renewable generation,
    cluster-level EV load variance (HVAC-driven + fleet shifts), and wholesale IEX prices.
    """

    def __init__(self, seed: int = 42):
        np.random.seed(seed)

    def generate_weather_profile(self, cluster_id: str, season: str = "summer", hours: int = 24) -> pd.DataFrame:
        """
        Generates realistic 24-hour weather data (Ambient Temp, Solar GHI, Wind Speed, Cloud Cover).
        """
        cluster = CLUSTERS[cluster_id]
        t = np.arange(hours)

        # Baseline temperatures
        if season == "summer":
            t_max = cluster["summer_temp_peak"]
            t_min = t_max - 12.0
            cloud_cover_mean = 0.15
            wind_base = 5.5
        elif season == "monsoon":
            t_max = 32.0
            t_min = 25.0
            cloud_cover_mean = 1.0 - cluster["monsoon_solar_factor"]
            wind_base = 8.5 # High wind generation during monsoon in South/West India
        elif season == "winter":
            t_max = 24.0 if cluster_id == "DEL" else 30.0
            t_min = 7.0 if cluster_id == "DEL" else 20.0
            cloud_cover_mean = 0.25 # Winter smog/fog in Delhi
            wind_base = 3.5
        else: # Normal / Autumn
            t_max = 33.0
            t_min = 22.0
            cloud_cover_mean = 0.20
            wind_base = 4.8

        # Diurnal temperature cycle: peak around 14:00 - 15:00
        temp = t_min + (t_max - t_min) * 0.5 * (1 + np.sin(2 * np.pi * (t - 9) / 24))
        temp += np.random.normal(0, 0.5, hours)

        # Solar Irradiance (GHI in W/m2)
        # Solar window ~ 06:00 to 18:00, peak at 12:30
        solar_zenith = np.maximum(0, np.sin(np.pi * (t - 6) / 12))
        clear_sky_ghi = 980.0 * (solar_zenith ** 1.15)
        
        # Correlated cloud cover (AR(1) process)
        cloud_shocks = np.random.beta(2, 5, hours) * (cloud_cover_mean * 2.0)
        cloud_cover = np.clip(cloud_shocks, 0.0, 0.95)
        actual_ghi = clear_sky_ghi * (1.0 - 0.75 * cloud_cover)

        # Wind speed (Weibull distributed proxy)
        wind_speed = wind_base + np.random.rayleigh(scale=2.0, size=hours)

        return pd.DataFrame({
            "hour": t,
            "temp_ambient": np.round(temp, 2),
            "ghi": np.round(actual_ghi, 1),
            "cloud_cover": np.round(cloud_cover, 2),
            "wind_speed": np.round(wind_speed, 2)
        })

    def generate_renewable_generation(self, cluster_id: str, weather_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates contracted Open-Access Solar & Wind generation (MW) accounting for
        PV thermal de-rating (0.4%/°C above 25°C cell temp) and wind turbine power curves.
        """
        cluster = CLUSTERS[cluster_id]
        total_mw = cluster["total_mw"]
        
        # Contracted capacity under 35% Open Access
        contracted_oa_mw = total_mw * OPEN_ACCESS_SHARE
        solar_capacity_mw = contracted_oa_mw * 0.65  # 65% Solar in OA portfolio
        wind_capacity_mw = contracted_oa_mw * 0.35   # 35% Wind in OA portfolio

        # Solar PV output with thermal de-rating
        # Cell temp ~ Ambient Temp + 0.03 * GHI
        t_cell = weather_df["temp_ambient"] + 0.03 * weather_df["ghi"]
        thermal_derating = np.maximum(0.75, 1.0 - 0.004 * (t_cell - 25.0))
        solar_gen = solar_capacity_mw * (weather_df["ghi"] / 1000.0) * thermal_derating
        solar_gen = np.clip(solar_gen, 0.0, solar_capacity_mw)

        # Wind output with IEC standard power curve (cut-in 3 m/s, rated 12 m/s, cut-out 25 m/s)
        v = weather_df["wind_speed"].values
        wind_cf = np.zeros_like(v)
        mask_mid = (v >= 3.0) & (v < 12.0)
        wind_cf[mask_mid] = ((v[mask_mid] - 3.0) / (12.0 - 3.0)) ** 3
        mask_rated = (v >= 12.0) & (v <= 25.0)
        wind_cf[mask_rated] = 1.0
        wind_gen = wind_capacity_mw * wind_cf

        total_oa_gen = solar_gen + wind_gen

        return pd.DataFrame({
            "hour": weather_df["hour"],
            "oa_solar_mw": np.round(solar_gen, 2),
            "oa_wind_mw": np.round(wind_gen, 2),
            "oa_total_mw": np.round(total_oa_gen, 2)
        })

    def generate_ev_demand_profile(self, cluster_id: str, weather_df: pd.DataFrame) -> pd.DataFrame:
        """
        Models cluster-level DC fast charging and swap demand, factoring in:
        1. Commuter / Retail charging spikes (18:00 - 22:00)
        2. Ridehailing shifts (08:00 - 11:00 and 17:00 - 21:00)
        3. Logistics night depots & afternoon swap windows
        4. Ambient heat HVAC auxiliary load (+25% battery consumption when temp > 38°C)
        """
        cluster = CLUSTERS[cluster_id]
        t = weather_df["hour"].values
        temp = weather_df["temp_ambient"].values

        # HVAC temperature strain factor on EV battery consumption
        # Baseline EV efficiency calibrated at 25°C. At 44°C, AC load raises energy consumption by up to 28%
        hvac_penalty = np.ones_like(temp)
        high_temp_mask = temp > 30.0
        hvac_penalty[high_temp_mask] += 0.018 * (temp[high_temp_mask] - 30.0)

        # Baseline diurnal shapes (normalized)
        # Retail & Ridehailing Fast Charging: Morning Peak (9am) and Evening Peak (8pm)
        dcfc_shape = (
            0.25 +
            0.45 * np.exp(-((t - 9.5) / 2.5) ** 2) +
            0.65 * np.exp(-((t - 19.5) / 3.0) ** 2) +
            0.15 * np.exp(-((t - 14.0) / 2.0) ** 2)
        )
        
        # Battery Swapping (2W/3W Delivery & E-Rickshaws):
        # Heavy morning dispatch (07:30), mid-shift swap (13:30), evening shift change (18:30), night return (22:30)
        swap_shape = (
            0.20 +
            0.55 * np.exp(-((t - 8.0) / 2.0) ** 2) +
            0.60 * np.exp(-((t - 14.0) / 2.2) ** 2) +
            0.70 * np.exp(-((t - 19.0) / 2.5) ** 2) +
            0.40 * np.exp(-((t - 22.5) / 1.8) ** 2)
        )

        # Scale by installed cluster capacity & average utilization factor (~55-65% peak)
        nominal_dcfc_peak = cluster["dcfc_mw"] * 0.70
        nominal_swap_peak = cluster["swap_mw"] * 0.72

        dcfc_demand_p50 = nominal_dcfc_peak * (dcfc_shape / np.max(dcfc_shape)) * hvac_penalty
        swap_demand_p50 = nominal_swap_peak * (swap_shape / np.max(swap_shape)) * hvac_penalty

        # Uncertainty bounds: P10 (-12%) and P90 (+15%)
        dcfc_p10 = dcfc_demand_p50 * 0.88
        dcfc_p90 = dcfc_demand_p50 * 1.15

        swap_p10 = swap_demand_p50 * 0.88
        swap_p90 = swap_demand_p50 * 1.15

        return pd.DataFrame({
            "hour": t,
            "dcfc_demand_mw": np.round(dcfc_demand_p50, 2),
            "dcfc_p10_mw": np.round(dcfc_p10, 2),
            "dcfc_p90_mw": np.round(dcfc_p90, 2),
            "swap_demand_mw": np.round(swap_demand_p50, 2),
            "swap_p10_mw": np.round(swap_p10, 2),
            "swap_p90_mw": np.round(swap_p90, 2),
            "total_demand_mw": np.round(dcfc_demand_p50 + swap_demand_p50, 2),
            "hvac_strain_factor": np.round(hvac_penalty, 3)
        })

    def generate_iex_market_prices(self, hours: int = 24, scenario: str = "normal") -> pd.DataFrame:
        """
        Simulates IEX Day-Ahead Market (DAM) and Real-Time Market (RTM) clearing prices (INR / kWh).
        Reflects duck-curve pricing: afternoon solar suppression, steep evening ramp (18:00-22:00).
        """
        t = np.arange(hours)
        
        # Base Indian Energy Exchange diurnal price shape
        # Night off-peak: ₹3.80 - ₹4.50
        # Solar trough (11am - 2pm): ₹3.20 - ₹4.00
        # Morning peak (7am - 9am): ₹5.80 - ₹6.50
        # Evening peak (6pm - 10pm): ₹7.80 - ₹9.50 (can hit regulatory cap of ₹10.00)
        base_price = (
            4.20 +
            1.80 * np.exp(-((t - 8.0) / 2.0) ** 2) -
            0.90 * np.exp(-((t - 13.0) / 2.5) ** 2) +
            4.20 * np.exp(-((t - 20.0) / 2.2) ** 2)
        )

        if scenario == "price_spike":
            # Grid shortage / thermal plant outage scenario: prices hit ₹10.00 ceiling during evening
            base_price = base_price * 1.35
            base_price[18:23] = np.minimum(10.00, base_price[18:23] * 1.25)

        dam_price = np.clip(base_price + np.random.normal(0, 0.25, hours), 2.50, 10.00)
        
        # RTM price has volatility / forecast error premium (±15% spread around DAM)
        rtm_spread = np.random.normal(0, 0.45, hours)
        rtm_price = np.clip(dam_price + rtm_spread, 2.00, 10.00)

        return pd.DataFrame({
            "hour": t,
            "iex_dam_price": np.round(dam_price, 2),
            "iex_rtm_price": np.round(rtm_price, 2)
        })
