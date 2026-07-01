"""
config.py — Telemetry Health Assessment System Configuration
===========================================================
Single source of truth for limit thresholds, weights, constants,
and note templates across the system.
"""

# =====================================================================
# SEVERITY LEVELS & MAPPINGS
# =====================================================================
SEVERITY_LEVELS = {
    'NOMINAL': 0,
    'MONITOR': 1,
    'WARNING': 2,
    'CRITICAL': 3,
}

# Risk score thresholds mapping
SCORE_THRESHOLDS = [
    (76, 'CRITICAL'),
    (51, 'WARNING'),
    (26, 'MONITOR'),
    (0,  'NOMINAL'),
]

# Recommended actions displayed in Section 5 (Assessment)
RECOMMENDED_ACTION = {
    'NOMINAL':  'No action required. Continue routine operations and log baseline values.',
    'MONITOR':  'Increase telemetry polling frequency. Monitor trend parameters during next ground pass.',
    'WARNING':  'Notify shift manager and subsystem specialists. Prepare draft contingency execution commands.',
    'CRITICAL': 'IMMEDIATE ACTION REQUIRED. Initiate anomaly resolution team. Prepare subsystem isolation commands.',
}

# UI Severity badge colors
SEVERITY_COLOURS = {
    'NOMINAL':  '#3fb950',   # green
    'MONITOR':  '#d29922',   # yellow/amber
    'WARNING':  '#f0883e',   # orange
    'CRITICAL': '#f85149',   # red
}

SEVERITY_BG = {
    'NOMINAL':  '#1f6feb20',  # faint blue-tinted dark
    'MONITOR':  '#d2992215',  # faint amber
    'WARNING':  '#f0883e15',  # faint orange
    'CRITICAL': '#f8514915',  # faint red
}

# =====================================================================
# RULE ENGINE LIMIT DEFINITIONS
# =====================================================================

# Hard limits: (parameter, description, threshold, comparison, severity_floor, unit)
HARD_LIMITS = [
    {
        'parameter': 'battery_voltage',
        'description': 'Battery voltage below red limit',
        'threshold': 22.0,
        'comparison': 'lt',
        'severity_floor': 'CRITICAL',
        'unit': 'V',
    },
    {
        'parameter': 'battery_temp',
        'description': 'Battery temperature above red limit',
        'threshold': 45.0,
        'comparison': 'gt',
        'severity_floor': 'CRITICAL',
        'unit': '°C',
    },
    {
        'parameter': 'battery_temp',
        'description': 'Battery temperature below red limit',
        'threshold': 0.0,
        'comparison': 'lt',
        'severity_floor': 'CRITICAL',
        'unit': '°C',
    },
    {
        'parameter': 'battery_soc',
        'description': 'Battery state of charge below red limit',
        'threshold': 20.0,
        'comparison': 'lt',
        'severity_floor': 'CRITICAL',
        'unit': '%',
    },
    {
        'parameter': 'attitude_error',
        'description': 'Attitude error above red limit',
        'threshold': 5.0,
        'comparison': 'gt',
        'severity_floor': 'CRITICAL',
        'unit': '°',
    },
    {
        'parameter': 'memory_usage',
        'description': 'OBC memory usage above red limit',
        'threshold': 90.0,
        'comparison': 'gt',
        'severity_floor': 'WARNING',
        'unit': '%',
    },
    {
        'parameter': 'ber',
        'description': 'Bit error rate above red limit',
        'threshold': 1e-4,
        'comparison': 'gt',
        'severity_floor': 'WARNING',
        'unit': '',
    },
    {
        'parameter': 'cpu_usage',
        'description': 'CPU usage above red limit',
        'threshold': 90.0,
        'comparison': 'gt',
        'severity_floor': 'WARNING',
        'unit': '%',
    },
]

# Yellow limits: (parameter, description, threshold, comparison, weight_category, unit)
YELLOW_LIMITS = [
    {
        'parameter': 'battery_voltage',
        'description': 'Battery voltage in yellow (caution) range',
        'threshold_lo': 22.0,
        'threshold_hi': 24.0,
        'comparison': 'range',
        'weight_category': 'eps_thermal',
        'unit': 'V',
    },
    {
        'parameter': 'battery_soc',
        'description': 'Battery SoC in yellow (caution) range',
        'threshold_lo': 20.0,
        'threshold_hi': 35.0,
        'comparison': 'range',
        'weight_category': 'eps_thermal',
        'unit': '%',
    },
    {
        'parameter': 'battery_temp',
        'description': 'Battery temperature above yellow caution threshold',
        'threshold': 40.0,
        'comparison': 'gt',
        'weight_category': 'eps_thermal',
        'unit': '°C',
    },
    {
        'parameter': 'battery_temp',
        'description': 'Battery temperature below yellow caution threshold',
        'threshold': 5.0,
        'comparison': 'lt',
        'weight_category': 'eps_thermal',
        'unit': '°C',
    },
    {
        'parameter': 'attitude_error',
        'description': 'Attitude error in yellow (caution) range',
        'threshold_lo': 3.0,
        'threshold_hi': 5.0,
        'comparison': 'range',
        'weight_category': 'adcs',
        'unit': '°',
    },
    {
        'parameter': 'wheel_speed',
        'description': 'Reaction wheel speed above caution limit',
        'threshold': 3000,
        'comparison': 'abs_gt',
        'weight_category': 'adcs',
        'unit': 'RPM',
    },
    {
        'parameter': 'link_margin',
        'description': 'Link margin below caution threshold',
        'threshold': 3.0,
        'comparison': 'lt',
        'weight_category': 'comms',
        'unit': 'dB',
    },
    {
        'parameter': 'rssi',
        'description': 'RSSI below caution threshold',
        'threshold': -90.0,
        'comparison': 'lt',
        'weight_category': 'comms',
        'unit': 'dBm',
    },
    {
        'parameter': 'ber',
        'description': 'Bit error rate in yellow (caution) range',
        'threshold_lo': 1e-6,
        'threshold_hi': 1e-4,
        'comparison': 'range',
        'weight_category': 'comms',
        'unit': '',
    },
    {
        'parameter': 'cpu_usage',
        'description': 'CPU usage in yellow (caution) range',
        'threshold_lo': 80.0,
        'threshold_hi': 90.0,
        'comparison': 'range',
        'weight_category': 'obc',
        'unit': '%',
    },
    {
        'parameter': 'memory_usage',
        'description': 'Memory usage in yellow (caution) range',
        'threshold_lo': 80.0,
        'threshold_hi': 90.0,
        'comparison': 'range',
        'weight_category': 'obc',
        'unit': '%',
    },
    {
        'parameter': 'error_count',
        'description': 'OBC error count non-zero',
        'threshold': 0,
        'comparison': 'gt',
        'weight_category': 'obc',
        'unit': '',
    },
    {
        'parameter': 'obc_temp',
        'description': 'OBC temperature above caution limit',
        'threshold': 55.0,
        'comparison': 'gt',
        'weight_category': 'obc',
        'unit': '°C',
    },
]

# Yellow weight category → risk points (capped at 40 total)
YELLOW_WEIGHTS = {
    'eps_thermal': 15,
    'adcs': 10,
    'comms': 7,
    'obc': 4,
}
YELLOW_TOTAL_CAP = 40

# =====================================================================
# TREND DETECTOR CONFIGURATION
# =====================================================================
MIN_TREND_PASSES = 3

TREND_PARAMETERS = {
    'battery_voltage':  {'category': 'critical',  'risk_pts': 10, 'conf_penalty': 10, 'label': 'Battery Voltage',           'unit': 'V',    'bad_direction': 'declining'},
    'battery_soc':      {'category': 'critical',  'risk_pts': 10, 'conf_penalty': 10, 'label': 'Battery State of Charge',    'unit': '%',    'bad_direction': 'declining'},
    'battery_temp':     {'category': 'critical',  'risk_pts': 10, 'conf_penalty': 10, 'label': 'Battery Temperature',        'unit': '°C',   'bad_direction': 'either'},
    'attitude_error':   {'category': 'critical',  'risk_pts': 10, 'conf_penalty': 10, 'label': 'Attitude Error',             'unit': '°',    'bad_direction': 'rising'},
    'wheel_speed':      {'category': 'critical',  'risk_pts': 10, 'conf_penalty': 10, 'label': 'Reaction Wheel Speed',       'unit': ' RPM',  'bad_direction': 'abs_rising'},
    'obc_temp':         {'category': 'secondary', 'risk_pts': 5,  'conf_penalty': 5,  'label': 'OBC Temperature',            'unit': '°C',   'bad_direction': 'rising'},
    'cpu_usage':        {'category': 'secondary', 'risk_pts': 5,  'conf_penalty': 5,  'label': 'CPU Usage',                  'unit': '%',    'bad_direction': 'rising'},
}

# =====================================================================
# RISK & CONFIDENCE CONSTANTS
# =====================================================================
TREND_RISK_WEIGHTS = {
    'critical': 10,
    'secondary': 5,
}

CONFIDENCE_FLOOR = 10
BASE_CONFIDENCE  = 100

# =====================================================================
# LLM SERVICE CONFIGURATION
# =====================================================================
VALID_TONES = {"alarmed", "cautious", "routine", "uncertain"}
VALID_RELATIONSHIPS = {"supports", "adds_context", "potential_conflict", "cannot_determine"}

LLM_TIMEOUT_SECONDS = 15
_LLM_RETRY_ATTEMPTS = 3
_LLM_RETRY_DELAY = 2.0

# =====================================================================
# SYNTHETIC DATASET GENERATION CONFIGS & TEMPLATES
# =====================================================================
GS_LIST = [
    "GS-GSOC",
    "GS-SVALBARD",
    "GS-KIRUNA",
    "GS-ADELAIDE",
    "GS-PERTH",
    "GS-MASPALOMAS",
]

SUNLIGHT_NOMINAL_NOTES = [
    "Sunlight tracking nominal, EPS fully charged.",
    "All solar panels generating power. Charging battery.",
    "Nominal sunlight pass. Battery SOC recovering.",
    "Solar array output stable. Bus voltage nominal.",
    "Sunlight pass, battery charge rate within predicted models.",
    "Acquisition of signal successful, subsystems in nominal sunlight state.",
    "All systems healthy in sunlit portion of the orbit.",
    "Solar panel current normal, battery charging.",
    "Sunlight operations stable, EPS performing well.",
    "Battery fully charged. Solar array output nominal.",
]

ECLIPSE_NOMINAL_NOTES = [
    "Eclipse entry, solar current zeroed as expected.",
    "Battery draw within predicted eclipse profile.",
    "Eclipse pass, SoC trending down as modelled.",
    "Orbital shadow, EPS on battery draw only.",
    "Standard eclipse operations, thermal nominal.",
    "Solar current is zero in shadow. Discharging battery.",
    "No solar array output. Battery voltage stable.",
    "Eclipse pass, thermal subsystem maintaining temperature.",
    "Satellite in eclipse. Power subsystem performing within specs.",
    "Battery discharging during shadow phase, values nominal.",
]

TRANSITION_NOMINAL_NOTES = [
    "Entering eclipse transition, solar current decreasing.",
    "Transitioning to sunlight, solar array output rising.",
    "Orbit transition phase. Subsystem parameters adjusting.",
    "Penumbra entry, solar current declining.",
    "Leaving shadow. Solar array beginning to generate power.",
    "Transition mode, power bus voltage stable.",
    "Orbit penumbra exit. Normal tracking lock.",
    "Transition pass, checking battery charge switch-over.",
]

VOLTAGE_DRIFT_NOTES = [
    "voltage is drifting lower across the last few passes",
    "Battery voltage continues to decline. Discharge rate elevated.",
    "Linear decline in battery voltage observed. EPS team notified.",
    "Slow voltage drop detected across orbits. Subsystem under review.",
    "EPS battery voltage shows downward trend over consecutive passes.",
    "Voltage slide persistent. Non-critical discharge path suspected.",
    "Monitoring linear discharge trend on battery bus.",
    "Voltage lower than baseline. Subsystem health checks running.",
]

THERMAL_ANOMALY_NOTES = [
    "Battery temperature elevated. Thermal trend concerning.",
    "OBC temperature creeping higher. Checking thermal control loops.",
    "Thermal subsystem showing minor heating trend. Parameters monitored.",
    "Slight thermal elevation observed. Subsystems remain operational.",
    "Battery temp approaching yellow limit. Heat dissipation active.",
    "OBC board temperature higher than normal baseline.",
    "Monitoring rising thermal trend on battery modules.",
    "OBC thermal parameters elevated. Fan/heater state confirmed off.",
]

COMMS_DEGRADATION_NOTES = [
    "Minor RF noise observed during tracking. Link margin narrow.",
    "Link quality declining, RSSI low, BER elevated.",
    "Comms link marginal. Signal dropouts observed near horizon.",
    "Packet drops detected. BER showing minor upward trend.",
    "RSSI low. RF environment degraded during pass.",
    "Comms subsystem experiencing elevated noise floor.",
    "Link margin close to threshold. Comm system performance checked.",
    "Tracking lock unstable, high BER reported.",
]

ADCS_FRICTION_NOTES = [
    "ADCS attitude error creep observed.",
    "Wheel speed trending higher, possible reaction wheel friction.",
    "Reaction wheel speed elevated. Torque limits normal.",
    "Attitude error creeping. ADCS sub-system checked.",
    "Reaction wheel drag detected. High RPM required to maintain pointing.",
    "ADCS pointing error slightly elevated. Gyro drift suspected.",
    "ADCS reacting to high momentum buildup. Desaturation scheduled.",
    "Reaction wheel speed higher than historical baseline.",
]

MULTI_ANOMALY_NOTES = [
    "Multiple subsystems showing stress: EPS and thermal parameters elevated.",
    "Simultaneous deviations on EPS and ADCS. Telemetry under review.",
    "Multi-system cautions: battery voltage low and CPU usage high.",
    "ADCS attitude error and comms BER both elevated.",
    "OBC temp and CPU load concurrently above nominal baselines.",
    "Coincident warnings on power bus and thermal subsystems.",
]

DEMO_SCENARIOS = {
    "A — Clean Nominal":            ('SAT-1001', 3),
    "B — Eclipse Stress":           ('SAT-1004', 9),
    "C — Hard Limit Breach":        ('SAT-1003', 10),
    "D — Genuine Uncertainty":      ('SAT-1002', 5),
    "E — Note/Telemetry Conflict":  ('SAT-1005', 3),
}
