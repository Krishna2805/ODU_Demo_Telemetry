"""
test_llm_analysis.py — LLM Analysis Verification Suite
======================================================
Contains all unit tests for the Gemini LLM analysis module.
"""

import sys
import os
from unittest.mock import MagicMock

# Adjust paths to make backend module visible
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import llm_analysis
from backend.config import VALID_TONES, VALID_RELATIONSHIPS
from backend.rule_engine import run_rule_engine
from backend.trend_detector import TrendDetectorResult


def run_tests():
    print("=" * 60)
    print("RUNNING LLM ANALYSIS UNIT TESTS")
    print("=" * 60)

    # ---- Test 1: Fallback path (always runs, no API needed) ----
    print("\n--- Test 1: Fallback path (simulate missing API key) ---")
    saved_configured = llm_analysis._LLM_CONFIGURED
    llm_analysis._LLM_CONFIGURED = False

    fallback = llm_analysis.analyse_note(
        telemetry={"battery_voltage": 28.2, "orbital_mode": "sunlight"},
        operator_note="All nominal.",
    )
    assert fallback.llm_available == False
    assert fallback.tone == "uncertain"
    assert fallback.note_telemetry_relationship == "cannot_determine"
    print("  Result:", fallback)
    print("  ✓ PASS: Fallback returns safe defaults with llm_available=False")
    llm_analysis._LLM_CONFIGURED = saved_configured

    # Check if live API is available
    if not llm_analysis._LLM_CONFIGURED:
        print("\n[SKIP] Live API tests skipped -- GEMINI_API_KEY not set.")
        sys.exit(0)

    # Shared nominal telemetry for live tests
    telemetry_nominal = {
        "orbital_mode": "sunlight",
        "battery_voltage": 28.2,
        "battery_soc": 95.0,
        "battery_temp": 22.0,
        "attitude_error": 0.3,
        "wheel_speed": 1200,
        "rssi": -72.0,
        "ber": 1e-8,
        "link_margin": 10.5,
        "cpu_usage": 35.0,
        "memory_usage": 48.0,
    }

    # ---- Test 2: Scenario A — routine nominal note ----
    print("\n--- Test 2 (live): Scenario A -- routine nominal note ---")
    r2 = llm_analysis.analyse_note(telemetry_nominal, "All nominal, clean pass.")
    print("  Tone:", r2.tone, "| Relationship:", r2.note_telemetry_relationship)
    print("  Concerns:", r2.concerns)
    if not r2.llm_available:
        print("  [SKIP] API unavailable (quota/network)")
    else:
        assert r2.tone in VALID_TONES
        assert r2.note_telemetry_relationship in VALID_RELATIONSHIPS
        assert isinstance(r2.concerns, list)
        print("  ✓ PASS: Valid structured JSON returned for routine pass")

    # ---- Test 3: Scenario E — potential conflict ----
    print("\n--- Test 3 (live): Scenario E -- potential conflict ---")
    telemetry_e = {**telemetry_nominal, "attitude_error": 0.37, "wheel_speed": -1208}
    r3 = llm_analysis.analyse_note(telemetry_e, "attitude looks wrong to me, wheel speed feels high")
    print("  Tone:", r3.tone, "| Relationship:", r3.note_telemetry_relationship)
    print("  Concerns:", r3.concerns)
    if not r3.llm_available:
        print("  [SKIP] API unavailable (quota/network)")
    else:
        assert r3.note_telemetry_relationship == "potential_conflict"
        print("  ✓ PASS: Scenario E correctly classified as potential_conflict")

    # ---- Test 4: Scenario C — alarmed hard limit breach note ----
    print("\n--- Test 4 (live): Scenario C -- alarmed / critical breach ---")
    telemetry_c = {
        **telemetry_nominal,
        "orbital_mode": "eclipse",
        "battery_voltage": 21.5,
        "battery_soc": 14.0,
    }
    r4 = llm_analysis.analyse_note(
        telemetry_c, "Voltage below 22V on entry, flagged for review immediately"
    )
    print("  Tone:", r4.tone, "| Relationship:", r4.note_telemetry_relationship)
    if not r4.llm_available:
        print("  [SKIP] API unavailable (quota/network)")
    else:
        assert r4.tone in ("alarmed", "cautious")
        print("  ✓ PASS: Scenario C classified with alarmed/cautious tone")

    # ---- Test 5: Scenario D — uncertain multi-yellow ----
    print("\n--- Test 5 (live): Scenario D -- uncertain, multi-yellow ---")
    telemetry_d = {
        **telemetry_nominal,
        "orbital_mode": "eclipse",
        "battery_voltage": 24.15,
        "battery_temp": 41.2,
        "attitude_error": 2.85,
        "ber": 8.5e-6,
        "cpu_usage": 81.5,
        "memory_usage": 80.8,
    }
    r5 = llm_analysis.analyse_note(telemetry_d, "something seems off but can't tell what")
    print("  Tone:", r5.tone, "| Relationship:", r5.note_telemetry_relationship)
    if not r5.llm_available:
        print("  [SKIP] API unavailable (quota/network)")
    else:
        assert r5.tone in ("uncertain", "cautious")
        print("  ✓ PASS: Scenario D classified with uncertain/cautious tone")

    # ---- Test 6: JSON parse failure simulation ----
    print("\n--- Test 6: Simulate JSON parse failure ---")
    class _BadResponse:
        text = "This is not JSON at all, sorry."

    saved_client = llm_analysis._client
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _BadResponse()
    llm_analysis._client = mock_client

    r6 = llm_analysis.analyse_note(telemetry_nominal, "All nominal.")
    assert r6.llm_available == False
    assert r6.tone == "uncertain"
    print("  ✓ PASS: JSON parse failure returns fallback with llm_available=False")
    llm_analysis._client = saved_client

    # ---- Test 7: Job 2 narrative (live) ----
    print("\n--- Test 7 (live): Job 2 -- reasoning narrative for Scenario C ---")
    re_result = run_rule_engine(
        {
            "battery_voltage": 21.5,
            "battery_soc": 14.0,
            "battery_temp": 22.0,
            "obc_temp": 28.0,
            "attitude_error": 0.3,
            "wheel_speed": 1200,
            "solar_current": 0.01,
            "solar_panel_temp": -55.0,
            "angular_velocity": 0.1,
            "power_bus_voltage": 5.02,
            "link_margin": 10.5,
            "rssi": -72.0,
            "ber": 1e-8,
            "cpu_usage": 35.0,
            "memory_usage": 48.0,
            "error_count": 0,
            "orbital_mode": "eclipse",
        }
    )
    td_result = TrendDetectorResult()
    note_ctx = (
        r4
        if (r4 and r4.llm_available)
        else llm_analysis.NoteAnalysisResult(
            tone="alarmed",
            note_telemetry_relationship="supports",
            concerns=["voltage critically low"],
            subsystems_mentioned=["EPS"],
        )
    )

    narrative = llm_analysis.generate_narrative(
        sat_id="SAT-1003",
        pass_num=10,
        severity="CRITICAL",
        confidence=75.0,
        rule_result=re_result,
        trend_result=td_result,
        note_analysis=note_ctx,
        operator_note="Voltage below 22V on entry, flagged for review immediately",
    )
    print("  Narrative:", narrative.narrative)
    if not narrative.llm_available:
        print("  [SKIP] API unavailable (quota/network)")
    else:
        assert len(narrative.narrative) > 20
        print("  ✓ PASS: Reasoning narrative generated successfully")

    print("\n" + "=" * 60)
    print("ALL LLM ANALYSIS TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
