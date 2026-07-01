"""
risk_scorer.py — Risk Scorer & Pipeline Integrator
===================================================
Orchestrates the rule engine, trend detector, and LLM note analyst,
calculates the integrated risk score and confidence.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

from backend.config import (
    SCORE_THRESHOLDS,
    TREND_RISK_WEIGHTS,
    CONFIDENCE_FLOOR,
    BASE_CONFIDENCE,
    SEVERITY_LEVELS,
)
from backend.rule_engine import run_rule_engine, RuleEngineResult
from backend.trend_detector import detect_trends, TrendDetectorResult
from backend.llm_analysis import (
    analyse_note,
    generate_narrative,
    NoteAnalysisResult,
    ReasoningResult,
)


@dataclass
class ConfidencePenalty:
    """A single named penalty contributing to the confidence deduction."""
    reason: str
    deduction: int     # positive integer representing points deducted


@dataclass
class AssessmentResult:
    """The complete output for a single pass. Streamlit reads this."""
    # Identifiers
    sat_id: str = ''
    pass_num: int = 0
    pass_id: str = ''

    # Deterministic outputs
    calculated_severity: str = 'NOMINAL'   # immutable — set by rules + scorer
    severity_source: str = 'risk_score'    # 'risk_score' or 'rule_engine_floor'
    risk_score: int = 0
    confidence: float = 100.0

    # Component outputs
    rule_result: Optional[RuleEngineResult] = None
    trend_result: Optional[TrendDetectorResult] = None
    note_analysis: Optional[NoteAnalysisResult] = None
    reasoning: Optional[ReasoningResult] = None

    # Confidence breakdown
    confidence_penalties: list = field(default_factory=list)

    # Operator override fields (populated by UI)
    operator_action: str = ''           # 'confirmed', 'downgraded', 'escalated', or ''
    operator_override_note: str = ''
    override_timestamp: str = ''

    # LLM availability
    llm_available: bool = True

    def hard_limit_badge_label(self) -> str:
        """
        Returns a badge label for hard limit breaches that distinguishes
        CRITICAL-floor breaches from WARNING-floor breaches.
        """
        if not self.rule_result or not self.rule_result.any_hard_limit_breached:
            return ''
        if self.rule_result.severity_floor == 'CRITICAL':
            return 'CRITICAL — Hard Limit Breached'
        elif self.rule_result.severity_floor == 'WARNING':
            return 'WARNING — Hard Limit Breached'
        return ''


def _compute_risk_score(
    rule_result: RuleEngineResult,
    trend_result: TrendDetectorResult,
) -> int:
    """
    Compute the raw 0–100 risk score from rule engine and trend flags.
    """
    score = 0
    score += rule_result.yellow_risk_points

    for flag in trend_result.trend_flags:
        score += TREND_RISK_WEIGHTS.get(flag.category, 0)

    if rule_result.any_hard_limit_breached:
        if rule_result.severity_floor == 'CRITICAL':
            score = max(score, 76)
        elif rule_result.severity_floor == 'WARNING':
            score = max(score, 51)

    return min(score, 100)


def _score_to_severity(score: int) -> str:
    """Map a risk score to a severity label."""
    for threshold, label in SCORE_THRESHOLDS:
        if score >= threshold:
            return label
    return 'NOMINAL'


def _apply_severity_floor(computed: str, floor: str) -> str:
    """
    Ensure computed severity is at least as high as the rule engine floor.
    """
    if SEVERITY_LEVELS.get(floor, 0) > SEVERITY_LEVELS.get(computed, 0):
        return floor
    return computed


def _compute_confidence(
    rule_result: RuleEngineResult,
    trend_result: TrendDetectorResult,
    note_analysis: NoteAnalysisResult,
    telemetry: dict,
) -> tuple[float, list]:
    """
    Compute the deterministic confidence score (0–100%).
    """
    penalties = []
    total_deduction = 0

    # --- Penalty: BER above warning threshold ---
    ber = telemetry.get('ber', 0)
    if ber is not None and ber > 1e-6:
        reason = (
            'Telemetry Link Corruption — Bit error rate above critical threshold'
            if ber > 1e-4 else
            'Telemetry Link Quality Degraded — Bit error rate above warning threshold'
        )
        p = ConfidencePenalty(reason=reason, deduction=30)
        penalties.append(p)
        total_deduction += 30

    # --- Penalty: Note-telemetry "potential_conflict" ---
    if note_analysis.note_telemetry_relationship == 'potential_conflict':
        p = ConfidencePenalty(
            reason='Operator note conflicts with telemetry readings — direction of truth unclear',
            deduction=20,
        )
        penalties.append(p)
        total_deduction += 20

    # --- Penalty: LLM fallback (note could not be analysed) ---
    if not note_analysis.llm_available:
        p = ConfidencePenalty(
            reason='LLM analysis unavailable — operator note not assessed',
            deduction=15,
        )
        penalties.append(p)
        total_deduction += 15

    # --- Penalty: Multi-subsystem borderline (2+ yellow categories) ---
    yellow_categories = set(f.weight_category for f in rule_result.yellow_limit_flags)
    if len(yellow_categories) >= 2:
        p = ConfidencePenalty(
            reason=f'Multiple subsystem caution flags ({len(yellow_categories)} categories) — ambiguous overall picture',
            deduction=15,
        )
        penalties.append(p)
        total_deduction += 15

    # --- Penalty: Note tone "uncertain" ---
    if note_analysis.tone == 'uncertain':
        p = ConfidencePenalty(
            reason='Operator note tone is uncertain — operator themselves unsure',
            deduction=10,
        )
        penalties.append(p)
        total_deduction += 10

    # --- Penalty: Note "cannot_determine" relationship ---
    if note_analysis.note_telemetry_relationship == 'cannot_determine':
        p = ConfidencePenalty(
            reason='Note-telemetry relationship cannot be determined — note too vague to contextualise',
            deduction=5,
        )
        penalties.append(p)
        total_deduction += 5

    # --- Penalty: Each individual yellow limit tripped (-5% each) ---
    trend_conf_deduction = trend_result.total_conf_penalty
    n_yellow = len(rule_result.yellow_limit_flags)
    if n_yellow > 0:
        yellow_conf_deduction = n_yellow * 5
        p = ConfidencePenalty(
            reason=f'{n_yellow} caution limit(s) tripped — minor local uncertainty',
            deduction=yellow_conf_deduction,
        )
        penalties.append(p)
        total_deduction += yellow_conf_deduction

    # --- Penalty: Trend flags (from trend detector) ---
    if trend_result.any_trend_detected:
        p = ConfidencePenalty(
            reason=f'Monotonic trend detected ({", ".join(f.label for f in trend_result.trend_flags)}) — parameter direction is worsening',
            deduction=trend_conf_deduction,
        )
        penalties.append(p)
        total_deduction += trend_conf_deduction

    confidence = max(BASE_CONFIDENCE - total_deduction, CONFIDENCE_FLOOR)
    return float(confidence), penalties


def assess_pass(
    telemetry: dict,
    operator_note: str,
    df: Optional[pd.DataFrame] = None,
    min_trend_passes: int = 3,
) -> AssessmentResult:
    """
    Run the full assessment pipeline for a single pass.
    """
    sat_id  = telemetry.get('sat_id', 'UNKNOWN')
    pass_num = telemetry.get('pass_num', 0)
    pass_id = telemetry.get('pass_id', f'{sat_id}-P{pass_num}')

    result = AssessmentResult(
        sat_id=sat_id,
        pass_num=pass_num,
        pass_id=pass_id,
    )

    # STEP 1: Rule Engine
    rule_result = run_rule_engine(telemetry)
    result.rule_result = rule_result

    # STEP 2: Trend Detector
    if df is not None:
        trend_result = detect_trends(telemetry, df, min_passes=min_trend_passes)
    else:
        trend_result = TrendDetectorResult()
    result.trend_result = trend_result

    # STEP 3: LLM Job 1 — Note Analysis
    note_analysis = analyse_note(telemetry, operator_note)
    result.note_analysis = note_analysis
    result.llm_available = note_analysis.llm_available

    # STEP 4: Risk Score + Severity
    risk_score = _compute_risk_score(rule_result, trend_result)
    score_severity = _score_to_severity(risk_score)
    final_severity = _apply_severity_floor(score_severity, rule_result.severity_floor)

    floor_level = SEVERITY_LEVELS.get(rule_result.severity_floor, 0)
    score_level = SEVERITY_LEVELS.get(score_severity, 0)
    severity_source = (
        'rule_engine_floor'
        if rule_result.any_hard_limit_breached and floor_level >= score_level
        else 'risk_score'
    )

    result.risk_score = risk_score
    result.calculated_severity = final_severity
    result.severity_source = severity_source

    # STEP 5: Confidence Score
    confidence, penalties = _compute_confidence(
        rule_result, trend_result, note_analysis, telemetry
    )
    result.confidence = confidence
    result.confidence_penalties = penalties

    # STEP 6: LLM Job 2 — Reasoning Narrative
    reasoning = generate_narrative(
        sat_id=sat_id,
        pass_num=pass_num,
        severity=final_severity,
        confidence=confidence,
        rule_result=rule_result,
        trend_result=trend_result,
        note_analysis=note_analysis,
        operator_note=operator_note,
    )
    result.reasoning = reasoning

    return result
