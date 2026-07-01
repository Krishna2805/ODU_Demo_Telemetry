"""
Trend detection over consecutive passes to flag parameter drift.
"""

from dataclasses import dataclass, field
import pandas as pd
from backend.config import TREND_PARAMETERS, MIN_TREND_PASSES


@dataclass
class TrendFlag:
    """Monotonic parameter trend flag."""
    parameter: str
    label: str
    direction: str           # 'declining' or 'rising'
    n_passes: int            # How many consecutive passes showed this trend (including current)
    values: list             # The actual values from oldest to newest
    risk_pts: int
    conf_penalty: int
    category: str            # 'critical' or 'secondary'
    unit: str = ''

    def display_summary(self) -> str:
        """One-line summary for layout rendering."""
        direction_word = "declining" if self.direction == 'declining' else "rising"
        vals_str = " → ".join([f"{v:.2f}{self.unit}" for v in self.values])
        return (f"Trend Detected: {self.label} {direction_word} for "
                f"{self.n_passes} consecutive passes ({vals_str})")


@dataclass
class TrendDetectorResult:
    """Trend detector outputs."""
    trend_flags: list = field(default_factory=list)
    total_risk_pts: int = 0
    total_conf_penalty: int = 0
    passes_available: int = 0    # How many historical passes were available to look back into

    @property
    def any_trend_detected(self) -> bool:
        return len(self.trend_flags) > 0


def detect_trends(
    current_pass: dict,
    df: pd.DataFrame,
    min_passes: int = MIN_TREND_PASSES,
) -> TrendDetectorResult:
    """
    Scans history to detect consecutive increases or decreases.
    """
    result = TrendDetectorResult()

    sat_id = current_pass.get('sat_id')
    pass_num = current_pass.get('pass_num')

    if sat_id is None or pass_num is None:
        return result  # Cannot do lookback without identifiers

    # We need the last (min_passes - 1) passes BEFORE the current one,
    # plus the current pass itself — total min_passes values.
    lookback_n = min_passes - 1

    history = df[
        (df['sat_id'] == sat_id) & (df['pass_num'] < pass_num)
    ].sort_values('pass_num').tail(lookback_n)

    result.passes_available = len(history)

    if len(history) < lookback_n:
        return result  # Not enough history to declare a trend

    # Run checks on each monitored parameter
    for param, config in TREND_PARAMETERS.items():
        val_current = current_pass.get(param)
        if val_current is None:
            continue

        # Extract values in chronological order
        hist_vals = history[param].tolist()
        all_vals = [float(v) for v in hist_vals] + [float(val_current)]

        # Determine bad direction
        bad_dir = config['bad_direction']

        # Check monotonic behavior
        is_monotonic = True
        declared_direction = None

        if bad_dir == 'declining':
            # Check if strictly decreasing: v0 > v1 > v2 ...
            for i in range(len(all_vals) - 1):
                if all_vals[i] <= all_vals[i+1]:
                    is_monotonic = False
                    break
            declared_direction = 'declining'

        elif bad_dir == 'rising':
            # Check if strictly increasing: v0 < v1 < v2 ...
            for i in range(len(all_vals) - 1):
                if all_vals[i] >= all_vals[i+1]:
                    is_monotonic = False
                    break
            declared_direction = 'rising'

        elif bad_dir == 'abs_rising':
            # Reaction wheel speed: absolute value rising: |v0| < |v1| < |v2| ...
            abs_vals = [abs(v) for v in all_vals]
            for i in range(len(abs_vals) - 1):
                if abs_vals[i] >= abs_vals[i+1]:
                    is_monotonic = False
                    break
            declared_direction = 'rising'

        elif bad_dir == 'either':
            # Battery temp: either steadily increasing or steadily decreasing
            # Check rising
            rising = True
            for i in range(len(all_vals) - 1):
                if all_vals[i] >= all_vals[i+1]:
                    rising = False
                    break
            # Check declining
            declining = True
            for i in range(len(all_vals) - 1):
                if all_vals[i] <= all_vals[i+1]:
                    declining = False
                    break

            if rising:
                declared_direction = 'rising'
            elif declining:
                declared_direction = 'declining'
            else:
                is_monotonic = False

        if is_monotonic and declared_direction:
            flag = TrendFlag(
                parameter=param,
                label=config['label'],
                direction=declared_direction,
                n_passes=len(all_vals),
                values=all_vals,
                risk_pts=config['risk_pts'],
                conf_penalty=config['conf_penalty'],
                category=config['category'],
                unit=config['unit'],
            )
            result.trend_flags.append(flag)
            result.total_risk_pts += config['risk_pts']
            result.total_conf_penalty += config['conf_penalty']

    return result


def summarise_trends(result: TrendDetectorResult) -> str:
    """Formats trends into a text summary."""
    lines = []
    lines.append("=== Trend Detector Result ===")
    lines.append(f"Passes available for lookback : {result.passes_available}")
    lines.append(f"Trend flags detected          : {len(result.trend_flags)}")
    lines.append(f"Total risk pts from trends    : +{result.total_risk_pts}")
    lines.append(f"Total confidence penalty      : -{result.total_conf_penalty}%")

    if result.trend_flags:
        lines.append("\n[TREND FLAGS]")
        for tf in result.trend_flags:
            arrow = "⬇" if tf.direction == 'declining' else "⬆"
            vals_str = " → ".join([f"{v:.2f}{tf.unit}" for v in tf.values])
            lines.append(f"  {arrow}  Trend Detected: {tf.label} {tf.direction} for {tf.n_passes} consecutive passes ({vals_str})")
            lines.append(f"     Risk: +{tf.risk_pts} pts  |  Confidence: -{tf.conf_penalty}%  |  Category: {tf.category}")

    return "\n".join(lines)
