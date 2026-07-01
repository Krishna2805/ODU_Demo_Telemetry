"""
CSS styling and HTML generation helper utilities for the frontend.
"""

import streamlit as st
from backend.config import RECOMMENDED_ACTION, SEVERITY_COLOURS, SEVERITY_BG
from backend.risk_scorer import AssessmentResult


def inject_custom_css():
    """Injects CSS overrides into the page."""
    st.markdown("""
<style>
  /* Google Font */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* Overall background */
  .stApp { background: #0d1117; color: #e6edf3; }

  /* Sidebar styling */
  section[data-testid="stSidebar"] {
    background: #161b22;
    border-right: 1px solid #30363d;
  }

  /* Section headers */
  .section-header {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #8b949e;
    margin: 1.6rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #21262d;
  }

  /* Severity badge */
  .severity-badge {
    display: inline-block;
    padding: 0.35rem 1.1rem;
    border-radius: 6px;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin-bottom: 0.25rem;
  }
  .severity-source {
    font-size: 0.78rem;
    color: #8b949e;
    margin-top: 0.1rem;
    margin-bottom: 0.8rem;
  }

  /* Generic card */
  .info-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 1.0rem;
    margin-bottom: 0.8rem;
  }

  /* Telemetry Table styling */
  table.telemetry-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
  }
  table.telemetry-table th {
    text-align: left;
    color: #8b949e;
    font-size: 0.75rem;
    text-transform: uppercase;
    font-weight: 600;
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid #30363d;
  }
  table.telemetry-table td {
    padding: 0.6rem;
    border-bottom: 1px solid #21262d;
    font-size: 0.85rem;
  }
  table.telemetry-table tr:hover {
    background-color: #161b2250;
  }

  /* Limit-flag chips */
  .chip-yellow {
    background-color: #d2992225;
    color: #d29922;
    border: 1px solid #d2992240;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
  }
  .chip-red {
    background-color: #f8514925;
    color: #f85149;
    border: 1px solid #f8514940;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  /* Telemetry text colors */
  .tel-nominal { color: #58a6ff; font-weight: 500; }
  .tel-caution { color: #d29922; font-weight: 600; }
  .tel-critical { color: #f85149; font-weight: 600; }

  /* Relationship label classes */
  .rel-supports {
    color: #3fb950;
    background-color: #3fb95015;
    padding: 0.25rem 0.6rem;
    border-radius: 4px;
    font-weight: 500;
  }
  .rel-adds_context {
    color: #58a6ff;
    background-color: #58a6ff15;
    padding: 0.25rem 0.6rem;
    border-radius: 4px;
    font-weight: 500;
  }
  .rel-potential_conflict {
    color: #f85149;
    background-color: #f8514915;
    padding: 0.25rem 0.6rem;
    border-radius: 4px;
    font-weight: 600;
  }
  .rel-cannot_determine {
    color: #8b949e;
    background-color: #21262d;
    padding: 0.25rem 0.6rem;
    border-radius: 4px;
  }

  /* Custom override log entry card */
  .override-log-card {
    background: #0d1117;
    border-left: 3px solid #ab7df8;
    padding: 0.75rem 1.0rem;
    margin-bottom: 0.6rem;
    border-radius: 0 4px 4px 0;
    font-size: 0.82rem;
  }
</style>
""", unsafe_allow_html=True)


def get_severity_badge_html(result: AssessmentResult) -> str:
    """Creates HTML snippet for the severity badge and its source indicator."""
    sev = result.calculated_severity
    col = SEVERITY_COLOURS.get(sev, '#8b949e')
    bg  = SEVERITY_BG.get(sev, '#161b22')
    src_label = (
        'Severity determined by: Rule Engine Hard Limit'
        if result.severity_source == 'rule_engine_floor'
        else 'Severity determined by: Risk Score'
    )
    return f"""
        <div class="severity-badge" style="background:{bg}; color:{col}; border: 1px solid {col}40;">
            {sev}
        </div>
        <div class="severity-source">{src_label}</div>
    """


def get_relationship_html(rel: str) -> str:
    """Wraps note relationship label in HTML styling classes."""
    label = {
        'supports':          '🟢 Supports telemetry',
        'adds_context':      '🔵 Adds context',
        'potential_conflict':'🔴 Potential conflict',
        'cannot_determine':  '⚪ Cannot determine',
    }.get(rel, '⚪ Cannot determine')

    css_class = {
        'supports':          'rel-supports',
        'adds_context':      'rel-adds_context',
        'potential_conflict':'rel-potential_conflict',
        'cannot_determine':  'rel-cannot_determine',
    }.get(rel, 'rel-cannot_determine')

    return f'<span class="{css_class}">{label}</span>'


def get_tone_icon(tone: str) -> str:
    """Maps tone to a status emoji."""
    return {'alarmed': '🔴', 'cautious': '🟡', 'routine': '🟢', 'uncertain': '⚪'}.get(tone, '⚪')


def get_confidence_bar_colour(conf: float) -> str:
    """Returns hex color corresponding to confidence levels."""
    if conf >= 75:
        return '#3fb950'
    if conf >= 45:
        return '#d29922'
    return '#f85149'


def format_value(param: str, v) -> str:
    """Formats engineering values for parameters."""
    if v is None:
        return '—'
    if param == 'ber':
        return f"{float(v):.2e}"
    if param in ('uptime_sec',):
        h = int(float(v)) // 3600
        return f"{h}h"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def get_value_colour_class(value: float, param: str, rule_result) -> str:
    """Finds the CSS class matching the rules check results."""
    if not rule_result:
        return 'tel-nominal'
    
    # 1. Check if parameter triggered a hard limit
    hard_params = rule_result.hard_limit_parameters()
    if param in hard_params:
        return 'tel-critical'
        
    # 2. Check if parameter triggered a yellow limit
    yellow_params = rule_result.yellow_limit_parameters()
    if param in yellow_params:
        return 'tel-caution'
        
    return 'tel-nominal'
