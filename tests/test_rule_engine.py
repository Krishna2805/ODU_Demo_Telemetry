"""
test_rule_engine.py — Rule Engine Verification Suite
=====================================================
Contains all unit tests for the deterministic rule engine.
"""

import sys
import os

# Adjust paths to make backend module visible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.rule_engine import run_rule_engine, summarise_result


def run_tests():
    print("=" * 60)
    print("RUNNING RULE ENGINE UNIT TESTS")
    print("=" * 60)

    # Test 1: Scenario C — red limit breach (CRITICAL)
    print("\n--- Test 1: Scenario C (Red Limit Breach) ---")
    t1 = {
        'battery_voltage': 21.0,    # red limit: < 22.0
        'battery_soc': 77.9,
        'battery_temp': 22.0,
        'obc_temp': 28.0,
        'attitude_error': 0.3,
        'wheel_speed': 1200,
        'solar_current': 0.01,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 1e-8,
        'cpu_usage': 35.0,
        'memory_usage': 48.0,
        'error_count': 0,
        'orbital_mode': 'eclipse',
    }
    r1 = run_rule_engine(t1)
    print(summarise_result(r1))
    assert r1.severity_floor == 'CRITICAL', f"Expected CRITICAL, got {r1.severity_floor}"
    assert r1.any_hard_limit_breached
    print("  ✓ PASS: severity floor is CRITICAL")

    # Test 2: Scenario A — clean nominal (no flags)
    print("\n--- Test 2: Scenario A (Clean Nominal) ---")
    t2 = {
        'battery_voltage': 28.2,
        'battery_soc': 95.0,
        'battery_temp': 22.0,
        'obc_temp': 28.0,
        'attitude_error': 0.3,
        'wheel_speed': 1200,
        'solar_current': 4.5,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 1e-8,
        'cpu_usage': 35.0,
        'memory_usage': 48.0,
        'error_count': 0,
        'orbital_mode': 'sunlight',
    }
    r2 = run_rule_engine(t2)
    print(summarise_result(r2))
    assert r2.severity_floor == 'NOMINAL'
    assert not r2.any_hard_limit_breached
    assert len(r2.yellow_limit_flags) == 0
    print("  ✓ PASS: severity floor is NOMINAL, no flags")

    # Test 3: Scenario D — multi-yellow, no hard limit
    print("\n--- Test 3: Scenario D (Genuine Uncertainty — multi-yellow) ---")
    t3 = {
        'battery_voltage': 24.15,
        'battery_soc': 77.9,
        'battery_temp': 41.2,       # yellow: > 40°C
        'obc_temp': 52.8,
        'attitude_error': 2.85,
        'wheel_speed': 1200,
        'solar_current': 0.01,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 8.5e-6,              # yellow: in range 1e-6 to 1e-4
        'cpu_usage': 81.5,          # yellow: in range 80-90%
        'memory_usage': 80.8,       # yellow: in range 80-90%
        'error_count': 0,
        'orbital_mode': 'eclipse',
    }
    r3 = run_rule_engine(t3)
    print(summarise_result(r3))
    assert r3.severity_floor == 'NOMINAL', f"Expected NOMINAL (no hard breach), got {r3.severity_floor}"
    assert not r3.any_hard_limit_breached
    assert len(r3.yellow_limit_flags) > 0
    print(f"  ✓ PASS: No hard breach, {len(r3.yellow_limit_flags)} yellow flag(s), {r3.yellow_risk_points} risk pts")

    # Test 4: Yellow cap — three EPS/thermal yellows should cap at 40
    print("\n--- Test 4: Yellow Cap (3x EPS/Thermal = 45 uncapped → 40 capped) ---")
    t4 = {
        'battery_voltage': 23.5,    # yellow: in 22-24 range
        'battery_soc': 28.0,        # yellow: in 20-35 range
        'battery_temp': 42.0,       # yellow: > 40°C
        'obc_temp': 28.0,
        'attitude_error': 0.3,
        'wheel_speed': 1200,
        'solar_current': 0.01,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 1e-8,
        'cpu_usage': 35.0,
        'memory_usage': 48.0,
        'error_count': 0,
        'orbital_mode': 'eclipse',
    }
    r4 = run_rule_engine(t4)
    print(summarise_result(r4))
    assert r4.yellow_risk_uncapped == 45, f"Expected 45 uncapped, got {r4.yellow_risk_uncapped}"
    assert r4.yellow_risk_points == 40, f"Expected 40 capped, got {r4.yellow_risk_points}"
    assert r4.severity_floor == 'NOMINAL'
    print("  ✓ PASS: Yellow total capped at 40 (uncapped was 45)")

    # Test 5: LLM alarmed note with all-green telemetry should NOT produce CRITICAL
    print("\n--- Test 5: Green Telemetry Must Stay NOMINAL ---")
    t5 = {
        'battery_voltage': 28.5,
        'battery_soc': 95.0,
        'battery_temp': 22.0,
        'obc_temp': 28.0,
        'attitude_error': 0.25,
        'wheel_speed': 1200,
        'solar_current': 4.5,
        'link_margin': 11.0,
        'rssi': -70.0,
        'ber': 1e-8,
        'cpu_usage': 30.0,
        'memory_usage': 45.0,
        'error_count': 0,
        'orbital_mode': 'sunlight',
    }
    r5 = run_rule_engine(t5)
    print(summarise_result(r5))
    assert r5.severity_floor == 'NOMINAL'
    assert not r5.any_hard_limit_breached
    print("  ✓ PASS: All-green telemetry → NOMINAL regardless of external context")

    # Test 6: Attitude error critical breach
    print("\n--- Test 6: ADCS Critical Breach (attitude_error > 5°) ---")
    t6 = {
        'battery_voltage': 28.0,
        'battery_soc': 92.0,
        'battery_temp': 22.0,
        'obc_temp': 28.0,
        'attitude_error': 5.32,
        'wheel_speed': 5250,
        'solar_current': 0.01,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 1e-8,
        'cpu_usage': 35.0,
        'memory_usage': 48.0,
        'error_count': 0,
        'orbital_mode': 'eclipse',
    }
    r6 = run_rule_engine(t6)
    print(summarise_result(r6))
    assert r6.severity_floor == 'CRITICAL'
    print("  ✓ PASS: Attitude error breach → CRITICAL floor")

    # Test 7: BER hard limit → WARNING floor
    print("\n--- Test 7: BER Hard Limit → WARNING floor ---")
    t7 = {
        'battery_voltage': 28.0,
        'battery_soc': 92.0,
        'battery_temp': 22.0,
        'obc_temp': 28.0,
        'attitude_error': 0.3,
        'wheel_speed': 1200,
        'solar_current': 4.5,
        'link_margin': 10.5,
        'rssi': -72.0,
        'ber': 3.5e-4,
        'cpu_usage': 35.0,
        'memory_usage': 48.0,
        'error_count': 0,
        'orbital_mode': 'sunlight',
    }
    r7 = run_rule_engine(t7)
    print(summarise_result(r7))
    assert r7.severity_floor == 'WARNING'
    print("  ✓ PASS: BER breach → WARNING floor")

    print("\n" + "=" * 60)
    print("ALL RULE ENGINE TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
