"""
test_trend_detector.py — Trend Detector Verification Suite
===========================================================
Contains all unit tests for the trend detection module.
"""

import sys
import os
import pandas as pd

# Adjust paths to make backend module visible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.trend_detector import detect_trends, summarise_trends


def run_tests():
    print("=" * 60)
    print("RUNNING TREND DETECTOR UNIT TESTS")
    print("=" * 60)

    # Build a mini dataset simulating SAT-1003's voltage decline
    voltages = [26.05, 25.62, 25.20, 24.76, 24.36, 23.94, 23.48, 22.98, 22.47, 22.02]
    socs =     [72.2,  68.0,  62.6,  57.8,  53.4,  48.1,  42.5,  35.0,  27.2,  18.0]

    rows = []
    for i, (v, s) in enumerate(zip(voltages, socs)):
        rows.append({
            'sat_id': 'SAT-1003', 'pass_num': i + 1,
            'battery_voltage': v, 'battery_soc': s,
            'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
        })
    df_test = pd.DataFrame(rows)

    # Test 1: current pass = pass 10
    current = {
        'sat_id': 'SAT-1003', 'pass_num': 10,
        'battery_voltage': 22.02, 'battery_soc': 18.0,
        'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
    }

    print("\n--- Test 1: SAT-1003 pass 10 (voltage and SoC declining for 10 passes) ---")
    r1 = detect_trends(current, df_test, min_passes=3)
    print(summarise_trends(r1))
    assert r1.any_trend_detected
    detected_params = [f.parameter for f in r1.trend_flags]
    assert 'battery_voltage' in detected_params, "Expected battery_voltage trend"
    assert 'battery_soc' in detected_params, "Expected battery_soc trend"
    print("  ✓ PASS: Voltage and SoC trends detected")

    # Test 2: pass 5 (middle of the trend)
    current_p5 = {
        'sat_id': 'SAT-1003', 'pass_num': 5,
        'battery_voltage': 24.36, 'battery_soc': 53.4,
        'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
    }
    print("\n--- Test 2: SAT-1003 pass 5 (trend visible by pass 5) ---")
    r2 = detect_trends(current_p5, df_test, min_passes=3)
    print(summarise_trends(r2))
    assert r2.any_trend_detected
    print("  ✓ PASS: Trend detected at pass 5")

    # Test 3: pass 2 (not enough history)
    current_p2 = {
        'sat_id': 'SAT-1003', 'pass_num': 2,
        'battery_voltage': 25.62, 'battery_soc': 68.0,
        'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
    }
    print("\n--- Test 3: SAT-1003 pass 2 (insufficient history) ---")
    r3 = detect_trends(current_p2, df_test, min_passes=3)
    print(summarise_trends(r3))
    assert not r3.any_trend_detected
    print("  ✓ PASS: No trend declared (insufficient history)")

    # Test 4: non-monotonic sequence should NOT trigger
    non_mono_rows = [
        {'sat_id': 'SAT-TEST', 'pass_num': 1, 'battery_voltage': 28.0, 'battery_soc': 90.0, 'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0},
        {'sat_id': 'SAT-TEST', 'pass_num': 2, 'battery_voltage': 27.5, 'battery_soc': 88.0, 'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0},
        {'sat_id': 'SAT-TEST', 'pass_num': 3, 'battery_voltage': 28.2, 'battery_soc': 91.0, 'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0},
    ]
    df_non = pd.DataFrame(non_mono_rows)
    current_nm = {
        'sat_id': 'SAT-TEST', 'pass_num': 4,
        'battery_voltage': 27.8, 'battery_soc': 87.0,
        'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
    }
    print("\n--- Test 4: Non-monotonic sequence should NOT trigger trend ---")
    r4 = detect_trends(current_nm, df_non, min_passes=3)
    print(summarise_trends(r4))
    assert not r4.any_trend_detected
    print("  ✓ PASS: Non-monotonic sequence correctly suppressed")

    # Test 5: SAT-1005 ADCS friction — rising attitude_error across passes 6-8
    print("\n--- Test 5: SAT-1005 ADCS pass 8 (rising attitude_error trend) ---")
    adcs_rows = [
        {'sat_id': 'SAT-1005', 'pass_num': 1,  'battery_voltage': 28.2, 'battery_soc': 95.0,
         'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
         'attitude_error': 0.37, 'wheel_speed': -1207},
        {'sat_id': 'SAT-1005', 'pass_num': 2,  'battery_voltage': 28.1, 'battery_soc': 94.5,
         'battery_temp': 22.1, 'obc_temp': 28.1, 'cpu_usage': 35.2,
         'attitude_error': 0.36, 'wheel_speed': -1243},
        {'sat_id': 'SAT-1005', 'pass_num': 3,  'battery_voltage': 28.0, 'battery_soc': 94.0,
         'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.1,
         'attitude_error': 0.37, 'wheel_speed': -1208},
        {'sat_id': 'SAT-1005', 'pass_num': 4,  'battery_voltage': 28.1, 'battery_soc': 94.2,
         'battery_temp': 21.9, 'obc_temp': 27.9, 'cpu_usage': 35.0,
         'attitude_error': 0.40, 'wheel_speed': -1282},
        {'sat_id': 'SAT-1005', 'pass_num': 5,  'battery_voltage': 28.0, 'battery_soc': 93.8,
         'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 34.9,
         'attitude_error': 0.36, 'wheel_speed': -1251},
        {'sat_id': 'SAT-1005', 'pass_num': 6,  'battery_voltage': 27.9, 'battery_soc': 93.5,
         'battery_temp': 22.1, 'obc_temp': 28.2, 'cpu_usage': 35.3,
         'attitude_error': 0.75, 'wheel_speed': 3200},
        {'sat_id': 'SAT-1005', 'pass_num': 7,  'battery_voltage': 27.8, 'battery_soc': 93.0,
         'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
         'attitude_error': 1.35, 'wheel_speed': 3900},
    ]
    df_adcs = pd.DataFrame(adcs_rows)
    current_adcs = {
        'sat_id': 'SAT-1005', 'pass_num': 8,
        'battery_voltage': 27.7, 'battery_soc': 92.5,
        'battery_temp': 22.0, 'obc_temp': 28.0, 'cpu_usage': 35.0,
        'attitude_error': 2.45, 'wheel_speed': 4400,
    }
    r5 = detect_trends(current_adcs, df_adcs, min_passes=3)
    print(summarise_trends(r5))
    assert r5.any_trend_detected, "Expected ADCS trend to be detected"
    detected_params_5 = [f.parameter for f in r5.trend_flags]
    assert 'attitude_error' in detected_params_5, f"Expected attitude_error trend, got: {detected_params_5}"
    assert 'wheel_speed' in detected_params_5,    f"Expected wheel_speed trend, got: {detected_params_5}"
    for flag in r5.trend_flags:
        if flag.parameter in ('attitude_error', 'wheel_speed'):
            assert flag.direction == 'rising'
            assert flag.risk_pts == 10
            assert flag.conf_penalty == 10
            assert flag.category == 'critical'
    print("  ✓ PASS: attitude_error and wheel_speed rising trends detected at pass 8")

    print("\n" + "=" * 60)
    print("ALL TREND DETECTOR TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
