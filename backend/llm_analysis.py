"""
llm_analysis.py — Gemini LLM Analysis Module
=============================================
Communicates with the Gemini API to extract operator note structured data (Job 1)
and generate narrative prose explaining overall pass health (Job 2).
"""

import concurrent.futures
import json
import os
import textwrap
import time
from dataclasses import dataclass, field
from google import genai
from google.genai import types as genai_types
from backend.config import (
    VALID_TONES,
    VALID_RELATIONSHIPS,
    LLM_TIMEOUT_SECONDS,
    _LLM_RETRY_ATTEMPTS,
    _LLM_RETRY_DELAY,
)

# Load .env file manually if it exists to populate os.environ
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    except Exception:
        pass

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# API key setup — fail gracefully if missing
_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_LLM_CONFIGURED = False
_client = None

if _API_KEY:
    try:
        _client = genai.Client(api_key=_API_KEY)
        _LLM_CONFIGURED = True
    except Exception:
        _LLM_CONFIGURED = False


@dataclass
class NoteAnalysisResult:
    """Output of Job 1 (note analysis)."""
    concerns: list = field(default_factory=list)
    tone: str = "uncertain"
    subsystems_mentioned: list = field(default_factory=list)
    note_telemetry_relationship: str = "cannot_determine"
    time_observations: list = field(default_factory=list)
    llm_available: bool = True  # False -> risk scorer applies -15% fallback penalty


@dataclass
class ReasoningResult:
    """Output of Job 2 (reasoning narrative)."""
    narrative: str = ""
    llm_available: bool = True


def _fallback_note_analysis(reason: str = "") -> NoteAnalysisResult:
    """Return a safe fallback NoteAnalysisResult for any error condition."""
    return NoteAnalysisResult(
        concerns=[],
        tone="uncertain",
        subsystems_mentioned=[],
        note_telemetry_relationship="cannot_determine",
        time_observations=[],
        llm_available=False,
    )


def _fallback_reasoning(reason: str = "") -> ReasoningResult:
    """Return a safe fallback ReasoningResult for any error condition."""
    return ReasoningResult(
        narrative="LLM analysis unavailable. The rule engine and trend detector results above are deterministic and reliable.",
        llm_available=False,
    )


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if the model includes them despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()
    return text


def _run_with_timeout(fn, timeout: float = LLM_TIMEOUT_SECONDS):
    """
    Run fn() in a background thread with a hard wall-clock timeout.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"[LLM] ⏱ TIMEOUT: API call did not respond within {timeout}s — falling back to deterministic mode")
        return None
    finally:
        executor.shutdown(wait=False)


def _run_with_retry(
    fn,
    timeout: float = LLM_TIMEOUT_SECONDS,
    attempts: int = _LLM_RETRY_ATTEMPTS,
    delay: float = _LLM_RETRY_DELAY,
):
    """
    Wrapper around _run_with_timeout that retries on transient server errors.
    """
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            result = _run_with_timeout(fn, timeout=timeout)
            if result is not None:
                return result
            # Timeout — don't retry, just surface the fallback quickly
            return None
        except Exception as exc:
            exc_str = str(exc)
            # Retry only on transient server-side errors
            if "503" in exc_str or "UNAVAILABLE" in exc_str or "429" in exc_str:
                last_exc = exc
                print(f"[LLM] ⚠ Transient error (attempt {attempt}/{attempts}): {exc_str[:120]}")
                if attempt < attempts:
                    time.sleep(delay)
                continue
            print(f"[LLM] ❌ Non-retryable API error: {exc_str[:200]}")
            raise
    # All retry attempts exhausted
    print(f"[LLM] ❌ All {attempts} retry attempts exhausted. Last error: {str(last_exc)[:200]}")
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("All retry attempts exhausted with no exception recorded.")


# =====================================================================
# JOB 1: NOTE ANALYSIS
# =====================================================================

_JOB1_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a spacecraft telemetry analyst assistant.
    You will be given an operator note written during a ground station pass, along with key telemetry readings from that pass.
    Your task is to analyse the note in the context of the telemetry and return a structured JSON object.

    IMPORTANT RULES:
    - Return ONLY valid JSON. No markdown code fences, no preamble, no explanation.
    - Your response must be parseable by Python's json.loads() directly.
    - Use exactly the field names specified.
    - tone must be exactly one of: alarmed, cautious, routine, uncertain
    - note_telemetry_relationship must be exactly one of: supports, adds_context, potential_conflict, cannot_determine

    FIELD DEFINITIONS:
    - concerns: list of specific issues or anomalies mentioned or implied by the note (empty list if none)
    - tone: the overall sentiment of the operator note
        alarmed   = operator is urgently flagging a problem
        cautious  = operator is monitoring something that could develop
        routine   = note is unremarkable, nominal operations described
        uncertain = operator explicitly does not know what is happening
    - subsystems_mentioned: list of subsystem names mentioned or implied (e.g. EPS, ADCS, Comms, OBC, Thermal)
    - note_telemetry_relationship: how the note relates to the numeric telemetry
        supports          = note is consistent with and reinforces the telemetry readings
        adds_context      = note provides additional information beyond what the numbers show
        potential_conflict = note suggests something the numbers do not, or vice versa
        cannot_determine  = not enough information to judge the relationship
    - time_observations: any references to time, trends, history, or sequences (e.g. "across the last few passes") -- empty list if none

    RETURN THIS EXACT SCHEMA (no other text):
    {
      "concerns": [],
      "tone": "routine",
      "subsystems_mentioned": [],
      "note_telemetry_relationship": "supports",
      "time_observations": []
    }
""")


def _build_job1_user_prompt(telemetry: dict, operator_note: str) -> str:
    """Build the user-facing portion of the Job 1 prompt."""
    ber = telemetry.get("ber", "N/A")
    ber_str = f"{ber:.2e}" if isinstance(ber, float) else str(ber)

    return textwrap.dedent(f"""\
        OPERATOR NOTE:
        "{operator_note}"

        KEY TELEMETRY VALUES (this pass):
        Orbital mode       : {telemetry.get("orbital_mode", "N/A")}
        Battery voltage    : {telemetry.get("battery_voltage", "N/A")} V  (nominal 24-30V, yellow <24V, red <22V)
        Battery SoC        : {telemetry.get("battery_soc", "N/A")} %  (nominal >35%, yellow 20-35%, red <20%)
        Battery temp       : {telemetry.get("battery_temp", "N/A")} deg C  (nominal 5-40C, yellow >40C, red >45C)
        Attitude error     : {telemetry.get("attitude_error", "N/A")} deg  (nominal <1 deg, yellow 3-5 deg, red >5 deg)
        Wheel speed        : {telemetry.get("wheel_speed", "N/A")} RPM  (yellow if |RPM| > 3000)
        RSSI               : {telemetry.get("rssi", "N/A")} dBm  (yellow if < -90 dBm)
        BER                : {ber_str}  (yellow 1e-6 to 1e-4, red >1e-4)
        Link margin        : {telemetry.get("link_margin", "N/A")} dB  (yellow if < 3 dB)
        CPU usage          : {telemetry.get("cpu_usage", "N/A")} %  (yellow >80%, red >90%)
        Memory usage       : {telemetry.get("memory_usage", "N/A")} %  (yellow >80%, red >90%)

        Analyse the operator note in the context of these telemetry values and return the JSON object.
    """)


def analyse_note(telemetry: dict, operator_note: str) -> NoteAnalysisResult:
    """
    Job 1: Call Gemini to analyse the operator note relative to telemetry.
    """
    if not _LLM_CONFIGURED:
        return _fallback_note_analysis(
            "LLM not configured -- GEMINI_API_KEY missing or invalid"
        )

    full_prompt = (
        _JOB1_SYSTEM_PROMPT + "\n\n" + _build_job1_user_prompt(telemetry, operator_note)
    )

    try:
        def _call_job1():
            return _client.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=512,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = _run_with_retry(_call_job1)
        if response is None:
            print("[LLM] Job 1 (Note Analysis): timed out — using fallback")
            return _fallback_note_analysis("LLM timed out or failed to respond")

        raw_text = _strip_fences(response.text)
        parsed = json.loads(raw_text)

        # Validate and normalise each field
        concerns = parsed.get("concerns", [])
        concerns = concerns if isinstance(concerns, list) else []

        tone = parsed.get("tone", "uncertain")
        tone = tone if tone in VALID_TONES else "uncertain"

        subsystems = parsed.get("subsystems_mentioned", [])
        subsystems = subsystems if isinstance(subsystems, list) else []

        relationship = parsed.get("note_telemetry_relationship", "cannot_determine")
        relationship = (
            relationship if relationship in VALID_RELATIONSHIPS else "cannot_determine"
        )

        time_obs = parsed.get("time_observations", [])
        time_obs = time_obs if isinstance(time_obs, list) else []

        print(f"[LLM] Job 1 (Note Analysis): OK — tone={tone}, relationship={relationship}")
        return NoteAnalysisResult(
            concerns=concerns,
            tone=tone,
            subsystems_mentioned=subsystems,
            note_telemetry_relationship=relationship,
            time_observations=time_obs,
            llm_available=True,
        )

    except json.JSONDecodeError as e:
        print(f"[LLM] Job 1 (Note Analysis): ❌ JSON parse error — {e}")
        return _fallback_note_analysis("JSON parse error in LLM response")

    except Exception as e:
        print(f"[LLM] Job 1 (Note Analysis): ❌ API call failed — {e}")
        return _fallback_note_analysis("LLM API call failed")


# =====================================================================
# JOB 2: REASONING NARRATIVE
# =====================================================================

_JOB2_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a spacecraft operations expert writing a brief assessment for a mission controller.
    You will be given the results of a deterministic rule engine check, a trend analysis, an operator note analysis, and the computed severity and confidence scores for a single ground station pass.
    Write 3 to 5 sentences of plain English that explain the overall health picture for this pass.
    Be concise and specific. Do not use bullet points, headers, or formatting. Just flowing prose.
    Focus on: what the biggest concern is (if any), what the trend means operationally, and whether the operator note supports or contradicts the telemetry picture.
    If everything is nominal, say so clearly and briefly.
""")


def _build_job2_user_prompt(
    sat_id: str,
    pass_num: int,
    severity: str,
    confidence: float,
    hard_flags: list,
    yellow_flags: list,
    trend_flags: list,
    note_analysis: NoteAnalysisResult,
    operator_note: str,
) -> str:
    """Build the Job 2 prompt. Kept compact to control cost and latency."""
    hard_summary = (
        "; ".join(
            f"{f.description} (measured {f.display_value()}, limit {f.display_threshold()})"
            for f in hard_flags
        )
        if hard_flags
        else "None"
    )

    yellow_items = yellow_flags[:4]
    yellow_summary = (
        "; ".join(f"{f.description} ({f.display_value()})" for f in yellow_items)
        + (f"; +{len(yellow_flags) - 4} more" if len(yellow_flags) > 4 else "")
        if yellow_flags
        else "None"
    )

    trend_summary = (
        "; ".join(f.display_summary() for f in trend_flags)
        if trend_flags
        else "No trends detected"
    )

    concerns_str = (
        ", ".join(note_analysis.concerns)
        if note_analysis.concerns
        else "none identified"
    )
    subs_str = (
        ", ".join(note_analysis.subsystems_mentioned)
        if note_analysis.subsystems_mentioned
        else "none specified"
    )
    time_obs_str = (
        "; ".join(note_analysis.time_observations)
        if note_analysis.time_observations
        else "none"
    )

    return textwrap.dedent(f"""\
        SATELLITE : {sat_id}, Pass {pass_num}
        SEVERITY  : {severity}
        CONFIDENCE: {confidence:.0f}%

        RULE ENGINE:
          Hard limit breaches : {hard_summary}
          Yellow limit flags  : {yellow_summary}

        TREND ANALYSIS:
          {trend_summary}

        OPERATOR NOTE:
          "{operator_note}"
        Note tone            : {note_analysis.tone}
        Note-telemetry link  : {note_analysis.note_telemetry_relationship}
        Concerns from note   : {concerns_str}
        Subsystems mentioned : {subs_str}
        Time observations    : {time_obs_str}

        Write your 3-5 sentence assessment now.
    """)


def generate_narrative(
    sat_id: str,
    pass_num: int,
    severity: str,
    confidence: float,
    rule_result,
    trend_result,
    note_analysis: NoteAnalysisResult,
    operator_note: str,
) -> ReasoningResult:
    """
    Job 2: Call Gemini to generate a plain-English reasoning narrative.
    """
    if not _LLM_CONFIGURED:
        return _fallback_reasoning("LLM not configured")

    user_prompt = _build_job2_user_prompt(
        sat_id=sat_id,
        pass_num=pass_num,
        severity=severity,
        confidence=confidence,
        hard_flags=rule_result.hard_limit_flags,
        yellow_flags=rule_result.yellow_limit_flags,
        trend_flags=trend_result.trend_flags,
        note_analysis=note_analysis,
        operator_note=operator_note,
    )

    try:
        def _call_job2():
            return _client.models.generate_content(
                model=MODEL_NAME,
                contents=_JOB2_SYSTEM_PROMPT + "\n\n" + user_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=300,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )

        response = _run_with_retry(_call_job2)
        if response is None:
            print("[LLM] Job 2 (Reasoning): timed out — using fallback")
            return _fallback_reasoning("LLM timed out or failed to respond")

        narrative = response.text.strip()
        if not narrative:
            print("[LLM] Job 2 (Reasoning): ⚠ Empty response from API")
            return _fallback_reasoning("Empty response from LLM")

        print(f"[LLM] Job 2 (Reasoning): OK — {len(narrative)} chars")
        return ReasoningResult(narrative=narrative, llm_available=True)

    except Exception as e:
        print(f"[LLM] Job 2 (Reasoning): ❌ API call failed — {e}")
        return _fallback_reasoning("LLM API call failed")
