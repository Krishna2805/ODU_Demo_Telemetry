"""
generate_data.py — Telemetry Dataset Generator
==============================================
Procedurally simulates LEO spacecraft telemetry and operator note logs.
Grounded in physical limits and templates defined in config.py.
"""

import os
import random
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

from backend.config import (
    GS_LIST,
    SUNLIGHT_NOMINAL_NOTES,
    ECLIPSE_NOMINAL_NOTES,
    TRANSITION_NOMINAL_NOTES,
    VOLTAGE_DRIFT_NOTES,
    THERMAL_ANOMALY_NOTES,
    COMMS_DEGRADATION_NOTES,
    ADCS_FRICTION_NOTES,
    MULTI_ANOMALY_NOTES,
)

np.random.seed(42)


def init_sat_state():
    """Create initial continuity state for a satellite."""
    wheel_sign = 1 if np.random.rand() > 0.5 else -1
    return {
        "wheel_speed": int(np.random.uniform(1100, 1400)) * wheel_sign,
        "angular_velocity": round(float(np.random.uniform(0.08, 0.15)), 3),
        "attitude_error": round(float(np.random.uniform(0.20, 0.40)), 3),
        "cpu_usage": round(float(np.random.uniform(30.0, 40.0)), 1),
        "memory_usage": round(float(np.random.uniform(45.0, 52.0)), 1),
        "rssi": round(float(np.random.normal(-72.0, 2.0)), 1),
    }


def evolve_background(state):
    """Evolve background variables with bounded random walk + mean reversion."""
    state["wheel_speed"] += int(np.random.uniform(-80, 80))
    state["attitude_error"] = max(
        0.05, round(state["attitude_error"] + float(np.random.normal(0, 0.03)), 3)
    )
    state["attitude_error"] = round(state["attitude_error"] * 0.95 + 0.30 * 0.05, 3)
    state["angular_velocity"] = max(
        0.01, round(state["angular_velocity"] + float(np.random.normal(0, 0.01)), 3)
    )
    state["angular_velocity"] = round(state["angular_velocity"] * 0.9 + 0.12 * 0.1, 3)
    state["cpu_usage"] = round(
        float(np.clip(state["cpu_usage"] + np.random.normal(0, 1.5), 20.0, 60.0)), 1
    )
    state["memory_usage"] = round(
        float(np.clip(state["memory_usage"] + np.random.normal(0, 1.0), 35.0, 65.0)), 1
    )
    state["rssi"] = round(
        (state["rssi"] + float(np.random.normal(0, 1.0))) * 0.85 + (-72.0) * 0.15, 1
    )
    return state


def generate_eps(orbital_mode):
    """Generate EPS telemetry based on orbital mode."""
    if orbital_mode == "sunlight":
        return {
            "solar_current": round(float(np.random.normal(4.5, 0.2)), 2),
            "battery_voltage": round(float(np.random.normal(28.2, 0.15)), 2),
            "battery_soc": round(float(np.random.normal(95.0, 1.0)), 2),
        }
    elif orbital_mode == "transition":
        return {
            "solar_current": round(float(np.random.normal(1.8, 0.15)), 2),
            "battery_voltage": round(float(np.random.normal(26.8, 0.2)), 2),
            "battery_soc": round(float(np.random.normal(88.0, 1.5)), 2),
        }
    else:  # eclipse
        sc = round(float(np.random.normal(0.02, 0.005)), 3)
        return {
            "solar_current": max(0.0, sc),
            "battery_voltage": round(float(np.random.normal(25.5, 0.2)), 2),
            "battery_soc": round(float(np.random.normal(78.0, 2.0)), 2),
        }


def generate_thermal(orbital_mode):
    """Generate thermal telemetry based on orbital mode."""
    battery_temp = round(float(np.random.normal(22.0, 1.5)), 1)
    obc_temp = round(float(np.random.normal(28.0, 2.0)), 1)
    if orbital_mode == "sunlight":
        sp_temp = round(float(np.random.normal(68.0, 3.0)), 1)
    elif orbital_mode == "transition":
        sp_temp = round(float(np.random.normal(10.0, 5.0)), 1)
    else:
        sp_temp = round(float(np.random.normal(-55.0, 4.0)), 1)
    return battery_temp, obc_temp, sp_temp


def make_orbital_modes(n_passes):
    """Generate a realistic sequence of orbital modes for n passes."""
    cycle = [
        "sunlight",
        "sunlight",
        "transition",
        "eclipse",
        "eclipse",
        "transition",
        "sunlight",
        "sunlight",
        "transition",
        "eclipse",
    ]
    modes = []
    for i in range(n_passes):
        modes.append(cycle[i % len(cycle)])
    return modes


def generate_handcrafted(records, pass_counter):
    """Generate the 5 original handcrafted satellites with scenarios A–E."""
    satellites = ["SAT-1001", "SAT-1002", "SAT-1003", "SAT-1004", "SAT-1005"]
    passes_per_sat = 10
    t_start = datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc)

    for sat_idx, sat_id in enumerate(satellites):
        uptime = 100000.0 + sat_idx * 50000.0
        error_count = 0
        state = init_sat_state()
        modes = make_orbital_modes(passes_per_sat)

        for pass_num in range(1, passes_per_sat + 1):
            pass_id = f"PASS-{pass_counter}"
            pass_counter += 1

            timestamp = t_start + timedelta(minutes=90 * (pass_num - 1))
            duration = round(float(np.random.uniform(8.5, 11.5)), 2)
            orbital_mode = modes[pass_num - 1]
            ground_station = GS_LIST[(sat_idx + pass_num) % len(GS_LIST)]
            uptime += 5400.0 + duration * 60.0

            # Background telemetry
            eps = generate_eps(orbital_mode)
            solar_current = eps["solar_current"]
            battery_voltage = eps["battery_voltage"]
            battery_soc = eps["battery_soc"]
            power_bus_voltage = round(float(np.random.normal(5.02, 0.03)), 2)
            battery_temp, obc_temp, solar_panel_temp = generate_thermal(orbital_mode)

            state = evolve_background(state)
            wheel_speed = state["wheel_speed"]
            attitude_error = state["attitude_error"]
            angular_velocity = state["angular_velocity"]
            rssi = state["rssi"]
            ber = float(f"{np.random.uniform(1e-8, 5e-7):.2e}")
            link_margin = round(float(np.random.normal(10.5, 0.8)), 1)
            cpu_usage = state["cpu_usage"]
            memory_usage = state["memory_usage"]

            # Default notes
            if orbital_mode == "sunlight":
                operator_note = random.choice(SUNLIGHT_NOMINAL_NOTES)
            elif orbital_mode == "transition":
                operator_note = random.choice(TRANSITION_NOMINAL_NOTES)
            else:
                operator_note = random.choice(ECLIPSE_NOMINAL_NOTES)

            scenario_name = "Nominal Operations"

            # --- SAT-1001: STRICTLY NOMINAL ---
            if sat_id == "SAT-1001":
                if pass_num == 3:
                    scenario_name = "Scenario A — Clean Nominal Pass"
                    operator_note = "All nominal, clean pass."

            # --- SAT-1002: COMMS DEGRADATION & BORDERLINE (SCENARIO D) ---
            elif sat_id == "SAT-1002":
                if pass_num == 5:
                    scenario_name = "Scenario D — Genuine Uncertainty"
                    battery_voltage = 24.15
                    battery_temp = 41.2
                    obc_temp = 52.8
                    attitude_error = 2.85
                    ber = 8.5e-6
                    cpu_usage = 81.5
                    memory_usage = 80.8
                    operator_note = "something seems off but can't tell what"
                elif pass_num in [6, 7, 8]:
                    scenario_name = "Comms Degradation Trend"
                    rssi = round(-90.0 - (pass_num - 5) * 3.5, 1)
                    ber = float(f"{1.2e-6 * (10 ** (pass_num - 5)):.2e}")
                    link_margin = round(4.5 - (pass_num - 5) * 1.0, 1)
                    operator_note = f"Minor RF noise observed during tracking. Link margin at {link_margin} dB."
                elif pass_num in [9, 10]:
                    scenario_name = "Comms Link Failure"
                    rssi = -102.5
                    ber = 3.5e-4
                    link_margin = 1.2
                    operator_note = "Significant data corruption on download, BER above limits. Persistently poor link margin."

            # --- SAT-1003: VOLTAGE DRIFT (CONSISTENT -0.4V/ORBIT) ---
            elif sat_id == "SAT-1003":
                base_voltage = 26.0
                base_soc = 72.0
                v_deltas = [-0.40, -0.40, -0.40, -0.45, -0.45, -0.45, -0.45, -0.50, -0.60]
                s_deltas = [-4.0, -5.0, -5.0, -5.0, -5.0, -6.0, -7.0, -8.0, -9.0]
                vv = base_voltage
                ss = base_soc
                for i in range(pass_num - 1):
                    vv += v_deltas[i]
                    ss += s_deltas[i]
                battery_voltage = round(vv + float(np.random.uniform(-0.05, 0.05)), 2)
                battery_soc = round(max(ss + float(np.random.uniform(-0.5, 0.5)), 5.0), 1)

                if pass_num <= 4:
                    scenario_name = "Subtle Voltage Decline"
                elif pass_num == 5:
                    scenario_name = "Voltage Drift (Unambiguous Trend)"
                    operator_note = "voltage is drifting lower across the last few passes"
                elif pass_num in [6, 7, 8]:
                    scenario_name = "Voltage Drift (Continued Decline)"
                    operator_note = f"Voltage continues to slide, currently at {battery_voltage}V. Discharge rate higher than model."
                elif pass_num == 9:
                    scenario_name = "Voltage Warning (Yellow Limit)"
                    operator_note = f"Voltage at {battery_voltage}V, approaching red limit. SoC at {battery_soc}%."
                elif pass_num == 10:
                    scenario_name = "Scenario C — Hard Limit Breach (Critical)"
                    operator_note = "Voltage below 22V on entry, flagged for review immediately"

            # --- SAT-1004: ECLIPSE STRESS ---
            elif sat_id == "SAT-1004":
                if pass_num <= 4:
                    orbital_mode = "sunlight"
                    solar_current = round(float(np.random.normal(4.6, 0.1)), 2)
                    battery_voltage = round(float(np.random.normal(28.4, 0.1)), 2)
                    battery_soc = round(float(np.random.normal(96.0, 0.5)), 2)
                elif pass_num == 5:
                    orbital_mode = "transition"
                    solar_current = 1.6
                    battery_voltage = 26.4
                    battery_soc = 86.0
                else:
                    orbital_mode = "eclipse"
                    solar_current = 0.01
                    voltages = [25.2, 24.5, 23.6, 22.8, 22.1]
                    socs = [74.0, 60.0, 45.0, 31.0, 22.0]
                    battery_voltage = voltages[pass_num - 6]
                    battery_soc = socs[pass_num - 6]
                    if pass_num == 9:
                        scenario_name = "Scenario B — Eclipse Battery Stress"
                        battery_voltage = 22.8
                        battery_soc = 31.0
                        operator_note = "battery dipping during eclipse, watching it"
                    elif pass_num == 10:
                        scenario_name = "Post-Eclipse Stress Recovery"
                        operator_note = "Battery voltage recovered slowly, eclipse duration remains high."
                    else:
                        scenario_name = "Eclipse Operations"

            # --- SAT-1005: ADCS FRICTION & SCENARIO E ---
            elif sat_id == "SAT-1005":
                if pass_num == 3:
                    scenario_name = "Scenario E — Potential Conflict"
                    attitude_error = round(state["attitude_error"] + float(np.random.normal(0, 0.02)), 3)
                    attitude_error = max(0.15, min(attitude_error, 0.50))
                    angular_velocity = round(state["angular_velocity"] + float(np.random.normal(0, 0.005)), 3)
                    angular_velocity = max(0.05, min(angular_velocity, 0.20))
                    operator_note = "attitude looks wrong to me, wheel speed feels high"
                elif pass_num == 6:
                    scenario_name = "ADCS Reaction Wheel Friction Trend"
                    wheel_speed = 3200
                    attitude_error = 0.75
                    operator_note = "Wheel speed trending higher, possible reaction wheel friction"
                elif pass_num in [7, 8, 9]:
                    scenario_name = "ADCS Friction Creep"
                    ws = [3900, 4400, 4800]
                    ae = [1.35, 2.45, 3.75]
                    wheel_speed = ws[pass_num - 7]
                    attitude_error = ae[pass_num - 7]
                    operator_note = f"ADCS attitude error creep observed. Reaction wheel speed at {wheel_speed} RPM."
                elif pass_num == 10:
                    scenario_name = "ADCS Control Loss"
                    wheel_speed = 5250
                    attitude_error = 5.32
                    angular_velocity = 1.85
                    error_count = 1
                    operator_note = "Reaction wheel speed saturated, attitude error exceeded critical limit of 5 deg."

            state["wheel_speed"] = wheel_speed
            state["attitude_error"] = attitude_error
            state["angular_velocity"] = angular_velocity
            state["cpu_usage"] = cpu_usage
            state["memory_usage"] = memory_usage
            state["rssi"] = rssi

            records.append(
                {
                    "pass_id": pass_id,
                    "sat_id": sat_id,
                    "pass_num": pass_num,
                    "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                    "duration_min": duration,
                    "orbital_mode": orbital_mode,
                    "ground_station": ground_station,
                    "battery_voltage": battery_voltage,
                    "solar_current": solar_current,
                    "power_bus_voltage": power_bus_voltage,
                    "battery_soc": battery_soc,
                    "battery_temp": battery_temp,
                    "obc_temp": obc_temp,
                    "solar_panel_temp": solar_panel_temp,
                    "attitude_error": attitude_error,
                    "angular_velocity": angular_velocity,
                    "wheel_speed": wheel_speed,
                    "rssi": rssi,
                    "ber": ber,
                    "link_margin": link_margin,
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "uptime_sec": round(uptime, 1),
                    "error_count": error_count,
                    "operator_note": operator_note,
                    "scenario_name": scenario_name,
                }
            )

    return pass_counter


def generate_procedural_satellite(sat_id, records, pass_counter, n_passes=10):
    """Generate a single procedural satellite with chronological timeline."""
    t_start = datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc)
    modes = make_orbital_modes(n_passes)
    state = init_sat_state()
    uptime = 120000.0 + random.uniform(0, 100000)

    # 1. Assign a timeline profile type
    profile = random.choice([
        "nominal", "eclipse_stress", "voltage_drift",
        "thermal_anomaly", "comms_degradation", "adcs_friction", "multi_anomaly"
    ])

    for pass_num in range(1, n_passes + 1):
        pass_id = f"PASS-{pass_counter}"
        pass_counter += 1

        timestamp = t_start + timedelta(minutes=90 * (pass_num - 1))
        duration = round(float(np.random.uniform(8.5, 11.5)), 2)
        orbital_mode = modes[pass_num - 1]
        ground_station = random.choice(GS_LIST)
        uptime += 5400.0 + duration * 60.0

        # Background telemetry
        eps = generate_eps(orbital_mode)
        solar_current = eps["solar_current"]
        battery_voltage = eps["battery_voltage"]
        battery_soc = eps["battery_soc"]
        power_bus_voltage = round(float(np.random.normal(5.02, 0.02)), 2)
        battery_temp, obc_temp, solar_panel_temp = generate_thermal(orbital_mode)

        state = evolve_background(state)
        wheel_speed = state["wheel_speed"]
        attitude_error = state["attitude_error"]
        angular_velocity = state["angular_velocity"]
        rssi = state["rssi"]
        ber = float(f"{np.random.uniform(1e-8, 5e-7):.2e}")
        link_margin = round(float(np.random.normal(10.5, 0.8)), 1)
        cpu_usage = state["cpu_usage"]
        memory_usage = state["memory_usage"]
        error_count = 0

        # Default operator note templates
        if orbital_mode == "sunlight":
            operator_note = random.choice(SUNLIGHT_NOMINAL_NOTES)
        elif orbital_mode == "transition":
            operator_note = random.choice(TRANSITION_NOMINAL_NOTES)
        else:
            operator_note = random.choice(ECLIPSE_NOMINAL_NOTES)

        scenario_name = f"Procedural Profile: {profile.capitalize()}"

        # 2. Inject anomalous progressions based on satellite profile
        if profile == "eclipse_stress":
            if orbital_mode == "eclipse":
                battery_voltage = round(float(np.random.normal(23.4, 0.4)), 2)
                battery_soc = round(float(np.random.normal(29.0, 4.0)), 2)
                operator_note = "Severe battery load observed during eclipse pass."

        elif profile == "voltage_drift":
            # Progressive drop of ~0.35V per pass
            volt_leak = 0.38 * (pass_num - 1)
            battery_voltage = round(battery_voltage - volt_leak, 2)
            battery_soc = max(5.0, round(battery_soc - 7.5 * (pass_num - 1), 1))
            if pass_num >= 5:
                operator_note = random.choice(VOLTAGE_DRIFT_NOTES)
                if battery_voltage < 22.0:
                    operator_note = "Battery pack terminal voltage dangerously low, charging disabled."

        elif profile == "thermal_anomaly":
            # Creep temperature upwards
            temp_rise = 2.2 * (pass_num - 1)
            battery_temp = round(battery_temp + temp_rise, 1)
            obc_temp = round(obc_temp + temp_rise * 0.8, 1)
            if pass_num >= 6:
                operator_note = random.choice(THERMAL_ANOMALY_NOTES)

        elif profile == "comms_degradation":
            # Progressively drop RSSI and raise BER
            if pass_num >= 5:
                rssi = round(rssi - 4.0 * (pass_num - 4), 1)
                ber = float(f"{1.5e-6 * (12 ** (pass_num - 5)):.2e}")
                link_margin = max(0.5, round(link_margin - 1.5 * (pass_num - 4), 1))
                operator_note = random.choice(COMMS_DEGRADATION_NOTES)

        elif profile == "adcs_friction":
            # Rise attitude error and wheel speed
            if pass_num >= 4:
                wheel_speed = int(wheel_speed + 450 * (pass_num - 3) * (1 if wheel_speed >= 0 else -1))
                attitude_error = round(attitude_error + 0.65 * (pass_num - 3), 2)
                operator_note = random.choice(ADCS_FRICTION_NOTES)

        elif profile == "multi_anomaly":
            if pass_num >= 7:
                battery_voltage = round(battery_voltage - 2.5, 2)
                cpu_usage = round(float(np.random.uniform(85.0, 94.0)), 1)
                operator_note = random.choice(MULTI_ANOMALY_NOTES)

        # Ensure bounds mapping fits telemetry size limits
        state["wheel_speed"] = wheel_speed
        state["attitude_error"] = attitude_error
        state["angular_velocity"] = angular_velocity
        state["cpu_usage"] = cpu_usage
        state["memory_usage"] = memory_usage
        state["rssi"] = rssi

        records.append(
            {
                "pass_id": pass_id,
                "sat_id": sat_id,
                "pass_num": pass_num,
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                "duration_min": duration,
                "orbital_mode": orbital_mode,
                "ground_station": ground_station,
                "battery_voltage": battery_voltage,
                "solar_current": solar_current,
                "power_bus_voltage": power_bus_voltage,
                "battery_soc": battery_soc,
                "battery_temp": battery_temp,
                "obc_temp": obc_temp,
                "solar_panel_temp": solar_panel_temp,
                "attitude_error": attitude_error,
                "angular_velocity": angular_velocity,
                "wheel_speed": wheel_speed,
                "rssi": rssi,
                "ber": ber,
                "link_margin": link_margin,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "uptime_sec": round(uptime, 1),
                "error_count": error_count,
                "operator_note": operator_note,
                "scenario_name": scenario_name,
            }
        )

    return pass_counter


def generate_telemetry_dataset():
    records = []
    pass_counter = 1001

    pass_counter = generate_handcrafted(records, pass_counter)

    for i in range(45):
        sat_id = f"SAT-{2001 + i}"
        pass_counter = generate_procedural_satellite(
            sat_id, records, pass_counter, n_passes=10
        )

    df = pd.DataFrame(records)
    # Output to parent directory relative to backend
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_path = os.path.join(parent_dir, "telemetry_dataset.csv")
    df.to_csv(target_path, index=False)

    print("=" * 60)
    print("DATASET GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total passes generated:  {len(df)}")
    print(f"Number of satellites:    {df['sat_id'].nunique()}")
    print("Saved to " + target_path)


if __name__ == "__main__":
    generate_telemetry_dataset()
