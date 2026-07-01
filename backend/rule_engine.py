"""
Checks single-pass telemetry limits against thresholds.
"""

from dataclasses import dataclass, field
from backend.config import HARD_LIMITS, YELLOW_LIMITS, YELLOW_WEIGHTS, YELLOW_TOTAL_CAP, SEVERITY_LEVELS


@dataclass
class LimitFlag:
    """Single triggered limit flag."""
    parameter: str
    description: str
    value: float
    threshold: float
    limit_type: str          # 'hard' or 'yellow'
    severity_floor: str      # 'CRITICAL', 'WARNING', or '' for yellows
    weight_category: str     # 'eps_thermal', 'adcs', 'comms', 'obc', or '' for hards
    unit: str = ''

    def display_value(self) -> str:
        """Format value for display."""
        if self.parameter == 'ber':
            return f"{self.value:.2e}"
        return f"{self.value:.2f}{self.unit}"

    def display_threshold(self) -> str:
        """Format threshold for display."""
        if self.parameter == 'ber':
            return f"{self.threshold:.1e}"
        return f"{self.threshold:.2f}{self.unit}"


@dataclass
class RuleEngineResult:
    """Rule engine check outputs."""
    # Hard limit findings
    hard_limit_flags: list = field(default_factory=list)
    any_hard_limit_breached: bool = False
    severity_floor: str = 'NOMINAL'        # Minimum severity, set by hardest breach

    # Yellow limit findings
    yellow_limit_flags: list = field(default_factory=list)
    yellow_risk_points: int = 0            # Total risk from yellows (capped at 40)
    yellow_risk_uncapped: int = 0          # Uncapped total (for transparency display)

    # Solar current special flag
    solar_current_warning: bool = False    # True if near-zero current in sunlight

    def hard_limit_parameters(self) -> list:
        """Return list of parameter names with hard limit breaches."""
        return [f.parameter for f in self.hard_limit_flags]

    def yellow_limit_parameters(self) -> list:
        """Return list of parameter names with yellow limit flags."""
        return [f.parameter for f in self.yellow_limit_flags]


def check_comparison(value: float, limit_def: dict) -> bool:
    """
    Returns True if value crosses the threshold.
    """
    comp = limit_def['comparison']
    if comp == 'lt':
        return value < limit_def['threshold']
    elif comp == 'gt':
        return value > limit_def['threshold']
    elif comp == 'range':
        return limit_def['threshold_lo'] < value < limit_def['threshold_hi']
    elif comp == 'abs_gt':
        return abs(value) > limit_def['threshold']
    return False


def run_rule_engine(telemetry: dict) -> RuleEngineResult:
    """
    Runs checks for all hard and yellow limits.
    """
    result = RuleEngineResult()

    # 1. Check hard limits
    worst_severity = 'NOMINAL'

    for limit_def in HARD_LIMITS:
        param = limit_def['parameter']
        value = telemetry.get(param)
        if value is None:
            continue

        if check_comparison(value, limit_def):
            threshold_display = limit_def['threshold']

            flag = LimitFlag(
                parameter=param,
                description=limit_def['description'],
                value=float(value),
                threshold=float(threshold_display),
                limit_type='hard',
                severity_floor=limit_def['severity_floor'],
                weight_category='',
                unit=limit_def['unit'],
            )
            result.hard_limit_flags.append(flag)
            result.any_hard_limit_breached = True

            # Track worst severity floor
            f_level = SEVERITY_LEVELS.get(limit_def['severity_floor'], 0)
            w_level = SEVERITY_LEVELS.get(worst_severity, 0)
            if f_level > w_level:
                worst_severity = limit_def['severity_floor']

    # 2. Check solar current under sunlight anomaly
    orbital_mode = telemetry.get('orbital_mode')
    solar_current = telemetry.get('solar_current')
    if orbital_mode == 'sunlight' and solar_current is not None and solar_current < 0.2:
        result.solar_current_warning = True
        w_level = SEVERITY_LEVELS.get(worst_severity, 0)
        f_level = SEVERITY_LEVELS.get('WARNING', 0)
        if f_level > w_level:
            worst_severity = 'WARNING'

    result.severity_floor = worst_severity

    # 3. Check yellow limits
    yellow_uncapped = 0
    for limit_def in YELLOW_LIMITS:
        param = limit_def['parameter']
        value = telemetry.get(param)
        if value is None:
            continue

        if check_comparison(value, limit_def):
            # Form display threshold
            if limit_def['comparison'] == 'range':
                threshold_val = limit_def['threshold_lo']  # default fallback
            else:
                threshold_val = limit_def['threshold']

            flag = LimitFlag(
                parameter=param,
                description=limit_def['description'],
                value=float(value),
                threshold=float(threshold_val),
                limit_type='yellow',
                severity_floor='',
                weight_category=limit_def['weight_category'],
                unit=limit_def['unit'],
            )
            result.yellow_limit_flags.append(flag)
            yellow_uncapped += YELLOW_WEIGHTS.get(limit_def['weight_category'], 0)

    result.yellow_risk_uncapped = yellow_uncapped
    result.yellow_risk_points = min(yellow_uncapped, YELLOW_TOTAL_CAP)

    return result


def summarise_result(result: RuleEngineResult) -> str:
    """Builds a summary string of the checked limits."""
    lines = []
    lines.append(f"Severity Floor  : {result.severity_floor}")
    lines.append(f"Hard Limit Breach: {result.any_hard_limit_breached}")
    lines.append(f"Yellow Risk Pts : {result.yellow_risk_points} (uncapped: {result.yellow_risk_uncapped})")

    if result.hard_limit_flags:
        lines.append("\n[HARD LIMITS]")
        for f in result.hard_limit_flags:
            lines.append(f"  🔴 {f.description}: measured {f.display_value()} (limit: {f.display_threshold()}) -> floor {f.severity_floor}")

    if result.solar_current_warning:
        lines.append("  🔴 WARNING: Solar current near zero in sunlight mode")

    if result.yellow_limit_flags:
        lines.append("\n[YELLOW LIMITS]")
        for f in result.yellow_limit_flags:
            lines.append(f"  🟡 {f.description}: measured {f.display_value()} -> weight category {f.weight_category}")

    return "\n".join(lines)
