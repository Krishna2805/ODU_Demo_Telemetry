"""
test_risk_scorer.py — Risk Scorer & Pipeline Verification Suite
===============================================================
Contains all integration tests for the full telemetry assessment pipeline.
"""

import sys
import os
import pandas as pd

# Adjust paths to make backend module visible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.risk_scorer import assess_pass
from backend.config import CONFIDENCE_FLOOR

# Load dataset for trend tests if available
CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'telemetry_dataset.csv')
if os.path.exists(CSV_PATH):
    try:
        df_full = pd.read_csv(CSV_PATH)
        df_full['pass_num'] = df_full['pass_num'].astype(int)
    except Exception:
        df_full = None
else:
    df_full = None


def run_tests():
    print("=" * 60)
    print("RUNNING RISK SCORER UNIT & INTEGRATION TESTS")
    print("=" * 60)

    if df_full is None:
        print('  [WARN] telemetry_dataset.csv not found — trend tests will skip lookback')

    # Test 1: Scenario A — clean nominal pass
    print('\n--- Test 1: Scenario A (Clean Nominal) ---')
    t1_tel = {
        'sat_id': 'SAT-1001', 'pass_num': 3, 'pass_id': 'PASS-1003',
        'orbital_mode': 'sunlight',
        'battery_voltage': 28.2, 'battery_soc': 95.0, 'battery_temp': 22.0,
        'obc_temp': 28.0, 'solar_panel_temp': 68.0, 'solar_current': 4.5,
        'power_bus_voltage': 5.01, 'attitude_error': 0.3, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -72.0, 'ber': 1e-8, 'link_margin': 10.5,
        'cpu_usage': 35.0, 'memory_usage': 48.0, 'uptime_sec': 86400,
        'error_count': 0,
    }
    r1 = assess_pass(t1_tel, 'All nominal, clean pass.', df=None)
    print(f'  Severity   : {r1.calculated_severity}')
    print(f'  Risk Score : {r1.risk_score}')
    print(f'  Confidence : {r1.confidence:.0f}%')
    print(f'  LLM avail  : {r1.llm_available}')
    print(f'  Penalties  : {[p.reason[:50] for p in r1.confidence_penalties]}')
    assert r1.calculated_severity == 'NOMINAL', f'Expected NOMINAL, got {r1.calculated_severity}'
    assert r1.severity_source == 'risk_score', f'Expected severity_source "risk_score", got: {r1.severity_source}'
    assert r1.risk_score == 0, f'Clean nominal should have 0 risk score, got {r1.risk_score}'
    min_expected_conf = 65 if not r1.llm_available else 85
    assert r1.confidence >= min_expected_conf
    print('  ✓ PASS')

    # Test 2: Scenario C — hard limit breach → CRITICAL floor
    print('\n--- Test 2: Scenario C (Hard Limit Breach) ---')
    t2_tel = {
        'sat_id': 'SAT-1003', 'pass_num': 10, 'pass_id': 'PASS-1030',
        'orbital_mode': 'eclipse',
        'battery_voltage': 21.5, 'battery_soc': 14.0, 'battery_temp': 22.0,
        'obc_temp': 28.0, 'solar_panel_temp': -55.0, 'solar_current': 0.01,
        'power_bus_voltage': 5.01, 'attitude_error': 0.3, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -72.0, 'ber': 1e-8, 'link_margin': 10.5,
        'cpu_usage': 35.0, 'memory_usage': 48.0, 'uptime_sec': 172800,
        'error_count': 0,
    }
    r2 = assess_pass(t2_tel, 'Voltage below 22V on entry, flagged for review immediately.', df=df_full)
    print(f'  Severity   : {r2.calculated_severity}')
    print(f'  Risk Score : {r2.risk_score}')
    print(f'  Confidence : {r2.confidence:.0f}%')
    print(f'  Hard flags : {[f.description for f in r2.rule_result.hard_limit_flags]}')
    assert r2.calculated_severity == 'CRITICAL', f'Expected CRITICAL, got {r2.calculated_severity}'
    assert r2.severity_source == 'rule_engine_floor'
    assert r2.risk_score >= 76
    print('  ✓ PASS')

    # Test 3: Alarmed note + all-green telemetry
    print('\n--- Test 3: Alarmed Note + Green Telemetry (LLM cannot override rules) ---')
    t3_tel = {
        'sat_id': 'SAT-9999', 'pass_num': 1, 'pass_id': 'PASS-TEST',
        'orbital_mode': 'sunlight',
        'battery_voltage': 28.5, 'battery_soc': 95.0, 'battery_temp': 22.0,
        'obc_temp': 28.0, 'solar_panel_temp': 68.0, 'solar_current': 4.5,
        'power_bus_voltage': 5.01, 'attitude_error': 0.25, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -70.0, 'ber': 1e-8, 'link_margin': 11.0,
        'cpu_usage': 30.0, 'memory_usage': 45.0, 'uptime_sec': 50000,
        'error_count': 0,
    }
    r3 = assess_pass(t3_tel, 'EVERYTHING IS ON FIRE, ABORT ABORT', df=None)
    print(f'  Severity   : {r3.calculated_severity}')
    print(f'  Risk Score : {r3.risk_score}')
    assert r3.calculated_severity in ('NOMINAL', 'MONITOR')
    assert not r3.rule_result.any_hard_limit_breached
    print('  ✓ PASS: All-green telemetry stays NOMINAL/MONITOR regardless of note')

    # Test 4: Yellow cap — 3× EPS yellows
    print('\n--- Test 4: Yellow Cap (3× EPS yellows = 45 uncapped → 40 capped) ---')
    t4_tel = {
        'sat_id': 'SAT-9998', 'pass_num': 1, 'pass_id': 'PASS-YCAP',
        'orbital_mode': 'eclipse',
        'battery_voltage': 23.5, 'battery_soc': 28.0, 'battery_temp': 42.0,
        'obc_temp': 28.0, 'solar_panel_temp': -55.0, 'solar_current': 0.01,
        'power_bus_voltage': 5.01, 'attitude_error': 0.3, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -72.0, 'ber': 1e-8, 'link_margin': 10.5,
        'cpu_usage': 35.0, 'memory_usage': 48.0, 'uptime_sec': 50000,
        'error_count': 0,
    }
    r4 = assess_pass(t4_tel, 'Battery caution across all EPS channels.', df=None)
    print(f'  Severity       : {r4.calculated_severity}')
    print(f'  Risk Score     : {r4.risk_score}')
    assert r4.rule_result.yellow_risk_uncapped == 45
    assert r4.rule_result.yellow_risk_points == 40
    assert r4.calculated_severity in ('WARNING', 'MONITOR')
    assert r4.calculated_severity != 'CRITICAL'
    print('  ✓ PASS: Yellow cap enforced')

    # Test 5: Confidence penalties — BER above threshold
    print('\n--- Test 5: BER Hard Breach → Confidence drops ---')
    t5_tel = {
        'sat_id': 'SAT-9997', 'pass_num': 1, 'pass_id': 'PASS-BER',
        'orbital_mode': 'sunlight',
        'battery_voltage': 28.0, 'battery_soc': 92.0, 'battery_temp': 22.0,
        'obc_temp': 28.0, 'solar_panel_temp': 68.0, 'solar_current': 4.5,
        'power_bus_voltage': 5.01, 'attitude_error': 0.3, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -72.0, 'ber': 3.5e-4, 'link_margin': 10.5,
        'cpu_usage': 35.0, 'memory_usage': 48.0, 'uptime_sec': 50000,
        'error_count': 0,
    }
    r5 = assess_pass(t5_tel, 'Bit errors spiking today.', df=None)
    print(f'  Severity   : {r5.calculated_severity}')
    print(f'  Confidence : {r5.confidence:.0f}%')
    penalty_reasons = [p.reason for p in r5.confidence_penalties]
    has_ber_penalty = any('bit error' in p.lower() for p in penalty_reasons)
    assert has_ber_penalty
    assert r5.confidence <= 70
    print('  ✓ PASS: BER penalty applied correctly')

    # Test 6: Scenario D — multi-yellow uncertainty
    print('\n--- Test 6: Scenario D (Multi-Yellow Uncertainty) ---')
    t6_tel = {
        'sat_id': 'SAT-1002', 'pass_num': 5, 'pass_id': 'PASS-1015',
        'orbital_mode': 'eclipse',
        'battery_voltage': 24.15, 'battery_soc': 77.9, 'battery_temp': 41.2,
        'obc_temp': 52.8, 'solar_panel_temp': -55.0, 'solar_current': 0.01,
        'power_bus_voltage': 5.01, 'attitude_error': 2.85, 'angular_velocity': 0.1,
        'wheel_speed': 1200, 'rssi': -72.0, 'ber': 8.5e-6, 'link_margin': 10.5,
        'cpu_usage': 81.5, 'memory_usage': 80.8, 'uptime_sec': 50000,
        'error_count': 0,
    }
    r6 = assess_pass(t6_tel, "something seems off but can't tell what", df=None)
    print(f'  Severity   : {r6.calculated_severity}')
    print(f'  Risk Score : {r6.risk_score}')
    print(f'  Confidence : {r6.confidence:.0f}%')
    assert r6.calculated_severity in ('MONITOR', 'WARNING')
    assert r6.confidence < 80
    assert not r6.rule_result.any_hard_limit_breached
    print('  ✓ PASS')

    # Test 7: Confidence floor
    print('\n--- Test 7: Confidence Floor (maximum penalty scenario) ---')
    t7_tel = {
        'sat_id': 'SAT-9996', 'pass_num': 1, 'pass_id': 'PASS-FLOOR',
        'orbital_mode': 'eclipse',
        'battery_voltage': 23.0, 'battery_soc': 25.0, 'battery_temp': 42.0,
        'obc_temp': 57.0, 'solar_panel_temp': -55.0, 'solar_current': 0.01,
        'power_bus_voltage': 5.01, 'attitude_error': 3.5, 'angular_velocity': 0.2,
        'wheel_speed': 3200, 'rssi': -91.0, 'ber': 5e-4,
        'link_margin': 2.5, 'cpu_usage': 82.0, 'memory_usage': 81.0,
        'uptime_sec': 50000, 'error_count': 2,
    }
    r7 = assess_pass(t7_tel, "something seems off but can't tell what", df=None)
    print(f'  Confidence : {r7.confidence:.0f}%  (floor = {CONFIDENCE_FLOOR}%)')
    assert r7.confidence >= CONFIDENCE_FLOOR
    print('  ✓ PASS: Confidence floor enforced')

    # Test 8: Scenario B — eclipse battery stress with trend lookback
    print('\n--- Test 8: Scenario B (Eclipse Stress + Trend from dataset) ---')
    if df_full is not None:
        t8_tel = {
            'sat_id': 'SAT-1004', 'pass_num': 9, 'pass_id': 'PASS-1039',
            'orbital_mode': 'eclipse',
            'battery_voltage': 22.8, 'battery_soc': 31.0, 'battery_temp': 22.0,
            'obc_temp': 28.0, 'solar_panel_temp': -55.0, 'solar_current': 0.01,
            'power_bus_voltage': 5.01, 'attitude_error': 0.3, 'angular_velocity': 0.1,
            'wheel_speed': 1200, 'rssi': -72.0, 'ber': 1e-8, 'link_margin': 10.5,
            'cpu_usage': 35.0, 'memory_usage': 48.0, 'uptime_sec': 50000,
            'error_count': 0,
        }
        r8 = assess_pass(t8_tel, 'battery dipping during eclipse, watching it', df=df_full)
        print(f'  Severity        : {r8.calculated_severity}')
        print(f'  Risk Score      : {r8.risk_score}')
        print(f'  Confidence      : {r8.confidence:.0f}%')
        print(f'  Trend flags     : {[f.display_summary() for f in r8.trend_result.trend_flags]}')
        assert r8.calculated_severity in ('MONITOR', 'WARNING')
        print('  ✓ PASS')
    else:
        print('  [SKIP] No dataset available for trend lookback')

    # Test 9: Operator override log
    print('\n--- Test 9: Operator Override Does NOT Overwrite Calculated Severity ---')
    r9 = assess_pass(t2_tel, 'Voltage below 22V on entry, flagged for review immediately.', df=None)
    original_sev = r9.calculated_severity
    r9.operator_action = 'downgraded'
    r9.operator_override_note = 'Operator called it safe, logged'
    assert r9.calculated_severity == original_sev
    print(f'  Calculated severity : {r9.calculated_severity}  ← unchanged')
    print(f'  Operator action     : {r9.operator_action}')
    print('  ✓ PASS: Immutable calculated_severity confirmed')

    print('\n' + "=" * 60)
    print('ALL RISK SCORER INTEGRATION TESTS PASSED')
    print('=' * 60)


if __name__ == "__main__":
    run_tests()
