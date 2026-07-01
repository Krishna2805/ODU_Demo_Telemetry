"""
app.py — Streamlit Operator Dashboard
======================================
Consumes an AssessmentResult and renders the telemetry health dashboard.
"""

import os
import sys
import datetime
import html
import pandas as pd
import streamlit as st

# --- Root path patching so backend is importable regardless of launch method ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.config import RECOMMENDED_ACTION, DEMO_SCENARIOS, SEVERITY_COLOURS
from backend.risk_scorer import assess_pass, AssessmentResult
from frontend.ui_styles import (
    inject_custom_css,
    get_severity_badge_html,
    get_relationship_html,
    get_tone_icon,
    get_confidence_bar_colour,
    format_value,
    get_value_colour_class,
)

# Page config
st.set_page_config(
    page_title="Telemetry Health Assessment",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject premium CSS styling
inject_custom_css()


# =====================================================================
# DATA LOADING (cached — runs once per session)
# =====================================================================
@st.cache_data(show_spinner="Loading telemetry dataset…")
def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['pass_num'] = df['pass_num'].astype(int)
    return df


CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'telemetry_dataset.csv')

if not os.path.exists(CSV_PATH):
    st.error(f"❌ `telemetry_dataset.csv` not found at {CSV_PATH}. Run `backend/generate_data.py` first.")
    st.stop()

df_all = load_dataset(CSV_PATH)


# =====================================================================
# SESSION STATE INIT & OVERRIDES JSON
# =====================================================================
import json

OVERRIDES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'operator_overrides.json')

def load_overrides():
    if os.path.exists(OVERRIDES_JSON_PATH):
        try:
            with open(OVERRIDES_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[UI] Error loading overrides JSON: {e}")
    return []

def save_overrides(log_list):
    try:
        with open(OVERRIDES_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(log_list, f, indent=2)
    except Exception as e:
        print(f"[UI] Error saving overrides JSON: {e}")

if 'result' not in st.session_state:
    st.session_state.result = None
if 'override_log' not in st.session_state:
    st.session_state.override_log = load_overrides()
if 'sel_sat' not in st.session_state:
    st.session_state.sel_sat = 'SAT-1001'
if 'sel_pass' not in st.session_state:
    st.session_state.sel_pass = 3
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False


# =====================================================================
# SIDEBAR — Selector Panel
# =====================================================================

def _quick_select(sid: str, pnum: int):
    """Set selection state and flag auto-run. Called via on_click."""
    st.session_state.sel_sat = sid
    st.session_state.sel_pass = pnum
    st.session_state.auto_run = True
    st.session_state.result = None  # clear old result


with st.sidebar:
    st.markdown("## 🛰️ Telemetry Assessment")
    st.markdown("---")

    st.markdown("#### Quick-select Demo Scenarios")
    for label, (sid, pnum) in DEMO_SCENARIOS.items():
        st.button(
            label,
            use_container_width=True,
            on_click=_quick_select,
            args=(sid, pnum),
        )

    # --- Select a random pass from the entire 500-pass dataset ---
    def _select_random_pass():
        random_row = df_all.sample(n=1).iloc[0]
        st.session_state.sel_sat = str(random_row['sat_id'])
        st.session_state.sel_pass = int(random_row['pass_num'])
        st.session_state.auto_run = True
        st.session_state.result = None

    st.button(
        "🎲 Random Pass Advisor",
        use_container_width=True,
        on_click=_select_random_pass,
    )

    st.markdown("---")
    st.markdown("### Select Pass")
    sat_ids = sorted(df_all['sat_id'].unique())

    def _on_sat_change():
        new_sat = st.session_state._wid_sat
        if new_sat != st.session_state.sel_sat:
            st.session_state.sel_sat = new_sat
            sat_passes_tmp = df_all[df_all['sat_id'] == new_sat].sort_values('pass_num')
            st.session_state.sel_pass = int(sat_passes_tmp['pass_num'].iloc[0])
            st.session_state.result = None

    try:
        sat_idx = sat_ids.index(st.session_state.sel_sat)
    except ValueError:
        sat_idx = 0

    st.selectbox(
        "Satellite ID", sat_ids, index=sat_idx,
        key="_wid_sat", on_change=_on_sat_change,
    )

    def _on_pass_change():
        new_pass = st.session_state._wid_pass
        if new_pass != st.session_state.sel_pass:
            st.session_state.sel_pass = new_pass
            st.session_state.result = None

    sat_passes = df_all[df_all['sat_id'] == st.session_state.sel_sat].sort_values('pass_num')
    pass_nums  = sat_passes['pass_num'].tolist()

    try:
        pass_idx = pass_nums.index(st.session_state.sel_pass)
    except ValueError:
        pass_idx = 0

    st.selectbox(
        "Pass Number", pass_nums, index=pass_idx,
        format_func=lambda n: f"Pass {n}",
        key="_wid_pass", on_change=_on_pass_change,
    )

    selected_row = sat_passes[sat_passes['pass_num'] == st.session_state.sel_pass].iloc[0]

    # Initialize / update note in session state
    pass_id_str = str(selected_row['pass_id'])
    if 'last_selected_pass_id' not in st.session_state or st.session_state.last_selected_pass_id != pass_id_str:
        st.session_state.current_note = str(selected_row.get('operator_note', ''))
        st.session_state.last_selected_pass_id = pass_id_str

    st.markdown("---")
    st.markdown("### Operator Note")
    st.caption("Pre-filled from dataset. Edit freely.")

    operator_note = st.text_area(
        "Note",
        value=st.session_state.current_note,
        height=110,
        label_visibility='collapsed',
    )
    if operator_note != st.session_state.current_note:
        st.session_state.current_note = operator_note

    st.markdown("---")
    run_assessment = st.button("▶  Run Assessment", use_container_width=True, type='primary')

    st.markdown("---")
    st.caption(f"Dataset: {len(df_all)} passes · {df_all['sat_id'].nunique()} satellites")


# =====================================================================
# RUN PIPELINE INTEGRATION
# =====================================================================
if st.session_state.auto_run:
    st.session_state.auto_run = False
    run_assessment = True

if run_assessment:
    telemetry = selected_row.to_dict()
    current_note_txt = st.session_state.current_note
    with st.spinner("Running assessment pipeline…"):
        result = assess_pass(
            telemetry=telemetry,
            operator_note=current_note_txt,
            df=df_all,
        )
    st.session_state.result = result
    
    # Look up existing override from persistent log
    existing = next((x for x in st.session_state.override_log 
                     if x['sat_id'] == result.sat_id and x['pass_num'] == result.pass_num), None)
    if existing:
        result.operator_action = existing['operator_action']
        result.operator_override_note = existing['override_note']
        result.override_timestamp = existing['timestamp']
    else:
        result.operator_action = ''
        result.operator_override_note = ''
        result.override_timestamp = ''


result: AssessmentResult = st.session_state.result

# =====================================================================
# UI RENDERING — LANDING OR DASHBOARD
# =====================================================================

if result is None:
    # --- Landing State ---
    st.title("🛰️ Spacecraft Telemetry Health Assessment System")
    st.write("")
    
    st.markdown(f"""
    <div class="info-card" style="border-left: 4px solid #58a6ff;">
        <h4>Welcome to the Tier 3 Decision-Support Panel</h4>
        <p>This system integrates three concurrent paths of analysis to evaluate spacecraft pass health:</p>
        <ol>
            <li><strong>Deterministic Rule Engine:</strong> Instantaneous Red/Yellow limit crossings.</li>
            <li><strong>Monotonic Trend Detector:</strong> Historic lookback to capture parameters slowly degrading.</li>
            <li><strong>Gemini Natural Language Engine:</strong> Correlates operator notes with telemetry.</li>
        </ol>
        <p><strong>To begin:</strong> Select a satellite and pass from the sidebar and click <strong>Run Assessment</strong>, 
        or click one of the <strong>Quick-select Demo Scenarios</strong> to load a handcrafted case study.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- Main Dashboard Header ---
sat_id = result.sat_id
pass_num = result.pass_num

st.markdown(f'<div class="section-header">Section 1: Pass Header Metadata</div>', unsafe_allow_html=True)

# 2-column header: metadata on left, severity badge on right
col_hdr_left, col_hdr_right = st.columns([3, 1])

with col_hdr_left:
    st.title(f"Telemetry Assessment: {sat_id}")
    st.subheader(f"Ground Station Pass {pass_num} — {selected_row.get('timestamp', 'N/A')}")
    st.markdown(f"""
    **Ground Station:** `{selected_row.get('ground_station', 'N/A')}` &nbsp;·&nbsp; 
    **Pass Duration:** `{selected_row.get('duration_min', 'N/A')} min` &nbsp;·&nbsp; 
    **Uptime:** `{format_value('uptime_sec', selected_row.get('uptime_sec'))}` &nbsp;·&nbsp; 
    **Pass ID:** `{result.pass_id}`
    """)

with col_hdr_right:
    st.markdown(get_severity_badge_html(result), unsafe_allow_html=True)


# =====================================================================
# SECTION 2: TELEMETRY SUMMARY
# =====================================================================
st.markdown('<div class="section-header">Section 2: Telemetry Parameters Summary</div>', unsafe_allow_html=True)

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("##### 🔌 Power & Thermal Subsystems")
    
    v_class = get_value_colour_class(selected_row['battery_voltage'], 'battery_voltage', result.rule_result)
    soc_class = get_value_colour_class(selected_row['battery_soc'], 'battery_soc', result.rule_result)
    bt_class = get_value_colour_class(selected_row['battery_temp'], 'battery_temp', result.rule_result)
    ot_class = get_value_colour_class(selected_row['obc_temp'], 'obc_temp', result.rule_result)
    
    st.markdown(f"""
    <table class="telemetry-table">
      <thead>
        <tr><th>Parameter</th><th>Value</th><th>Nominal Bound</th></tr>
      </thead>
      <tbody>
        <tr><td>Battery Voltage</td><td class="{v_class}">{format_value('battery_voltage', selected_row['battery_voltage'])} V</td><td>24.0 – 30.0 V (Red: &lt;22.0)</td></tr>
        <tr><td>Solar Array Current</td><td>{format_value('solar_current', selected_row['solar_current'])} A</td><td>Sunlight: 1.0 – 6.0 A (Red: &lt;0.2)</td></tr>
        <tr><td>Power Bus Voltage</td><td>{format_value('power_bus_voltage', selected_row['power_bus_voltage'])} V</td><td>5.0 V ± 0.15 V</td></tr>
        <tr><td>Battery State of Charge</td><td class="{soc_class}">{format_value('battery_soc', selected_row['battery_soc'])} %</td><td>&gt; 35.0 % (Red: &lt;20.0)</td></tr>
        <tr><td>Battery Temperature</td><td class="{bt_class}">{format_value('battery_temp', selected_row['battery_temp'])} °C</td><td>5.0 – 40.0 °C (Red: &lt;0 / &gt;45)</td></tr>
        <tr><td>OBC Temperature</td><td class="{ot_class}">{format_value('obc_temp', selected_row['obc_temp'])} °C</td><td>-10.0 – 55.0 °C</td></tr>
        <tr><td>Solar Panel Temp</td><td>{format_value('solar_panel_temp', selected_row['solar_panel_temp'])} °C</td><td>-65.0 – 80.0 °C</td></tr>
      </tbody>
    </table>
    """, unsafe_allow_html=True)

with col_t2:
    st.markdown("##### 🧭 ADCS, Comms & OBC Subsystems")
    
    ae_class = get_value_colour_class(selected_row['attitude_error'], 'attitude_error', result.rule_result)
    ws_class = get_value_colour_class(selected_row['wheel_speed'], 'wheel_speed', result.rule_result)
    ber_class = get_value_colour_class(selected_row['ber'], 'ber', result.rule_result)
    cpu_class = get_value_colour_class(selected_row['cpu_usage'], 'cpu_usage', result.rule_result)
    mem_class = get_value_colour_class(selected_row['memory_usage'], 'memory_usage', result.rule_result)
    ec_class = get_value_colour_class(selected_row['error_count'], 'error_count', result.rule_result)
    
    st.markdown(f"""
    <table class="telemetry-table">
      <thead>
        <tr><th>Parameter</th><th>Value</th><th>Nominal Bound</th></tr>
      </thead>
      <tbody>
        <tr><td>Attitude Error</td><td class="{ae_class}">{format_value('attitude_error', selected_row['attitude_error'])} °</td><td>&lt; 1.0 ° (Red: &gt;5.0)</td></tr>
        <tr><td>Angular Velocity</td><td>{format_value('angular_velocity', selected_row['angular_velocity'])} °/s</td><td>&lt; 0.5 °/s</td></tr>
        <tr><td>Reaction Wheel Speed</td><td class="{ws_class}">{format_value('wheel_speed', selected_row['wheel_speed'])} RPM</td><td>-3000 – 3000 RPM</td></tr>
        <tr><td>RSSI</td><td>{format_value('rssi', selected_row['rssi'])} dBm</td><td>&gt; -90.0 dBm</td></tr>
        <tr><td>Bit Error Rate (BER)</td><td class="{ber_class}">{format_value('ber', selected_row['ber'])}</td><td>&lt; 1e-6 (Red: &gt;1e-4)</td></tr>
        <tr><td>Link Margin</td><td>{format_value('link_margin', selected_row['link_margin'])} dB</td><td>&gt; 3.0 dB</td></tr>
        <tr><td>CPU / Memory Usage</td><td class="{cpu_class}">{format_value('cpu_usage', selected_row['cpu_usage'])}%</td><td>&lt; 80.0 % (Red: &gt;90.0)</td></tr>
        <tr><td>OBC Error Count</td><td class="{ec_class}">{format_value('error_count', selected_row['error_count'])}</td><td>0 (Non-zero adds caution)</td></tr>
      </tbody>
    </table>
    """, unsafe_allow_html=True)

st.markdown(
    '<div style="text-align: right; font-size: 0.72rem; color: #8b949e; margin-top: -0.2rem;">'
    '<span class="tel-caution">■</span> Caution (yellow limit) &nbsp;'
    '<span class="tel-critical">■</span> Breach (red limit)</div>',
    unsafe_allow_html=True
)


# =====================================================================
# SECTION 3: RULE ENGINE FLAGS
# =====================================================================
st.markdown('<div class="section-header">Section 3: Rule Engine Flags</div>', unsafe_allow_html=True)

rr = result.rule_result
if not rr:
    st.info("Rule engine output unavailable.")
else:
    if not rr.any_hard_limit_breached and not rr.yellow_limit_flags and not rr.solar_current_warning:
        st.markdown(
            '<div class="info-card" style="color:#3fb950;">✅ No limit violations detected. All parameters within acceptable bounds.</div>',
            unsafe_allow_html=True
        )
    else:
        col_r1, col_r2 = st.columns(2)
        
        with col_r1:
            if rr.hard_limit_flags:
                st.markdown("**🔴 Hard Limit Breaches** — sets severity floor, cannot be bypassed")
                for flag in rr.hard_limit_flags:
                    st.markdown(
                        f'<div class="info-card" style="border-left: 3px solid #f85149; padding: 0.5rem 0.8rem; font-size: 0.82rem;">'
                        f'<strong>{flag.parameter}</strong>: {flag.description}<br/>'
                        f'<span style="color:#8b949e;">Value: {flag.display_value()} (limit: {flag.display_threshold()}) &nbsp;·&nbsp; Floor: {flag.severity_floor}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            if rr.solar_current_warning:
                st.markdown("**🔴 Solar Current Sunlight Anomaly**")
                st.markdown(
                    f'<div class="info-card" style="border-left: 3px solid #f85149; padding: 0.5rem 0.8rem; font-size: 0.82rem;">'
                    f'<strong>solar_current</strong>: Current is {selected_row["solar_current"]}A while in sunlight mode (expected &gt;1.0A).<br/>'
                    f'<span style="color:#8b949e;">Severity Floor forced to: WARNING</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            if not rr.hard_limit_flags and not rr.solar_current_warning:
                st.markdown("🟢 No hard limit breaches detected.")

        with col_r2:
            if rr.yellow_limit_flags:
                st.markdown(f"**🟡 Caution Limits** — additive risk points (capped at {rr.yellow_risk_points} pts)")
                for flag in rr.yellow_limit_flags:
                    st.markdown(
                        f'<div class="info-card" style="border-left: 3px solid #d29922; padding: 0.5rem 0.8rem; font-size: 0.82rem;">'
                        f'<strong>{flag.parameter}</strong>: {flag.description}<br/>'
                        f'<span style="color:#8b949e;">Value: {flag.display_value()} (limit: {flag.display_threshold()}) &nbsp;·&nbsp; Category: {flag.weight_category}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown("🟢 No caution (yellow) limit flags detected.")


# =====================================================================
# SECTION 4: LLM NOTE ANALYSIS (JOB 1)
# =====================================================================
st.markdown('<div class="section-header">Section 4: Natural Language Note Analysis</div>', unsafe_allow_html=True)

na = result.note_analysis
if not na:
    st.info("LLM note analysis output unavailable.")
else:
    # Availability banner
    if not na.llm_available:
        st.warning("⚠️ LLM analysis is unavailable. A -15% confidence penalty has been applied. Displaying deterministic fallbacks.")
    
    col_l1, col_l2 = st.columns([1, 1])
    
    with col_l1:
        st.markdown("**Operator Note (Raw Input):**")
        st.markdown(f'<div class="info-card" style="font-style: italic;">"{st.session_state.current_note}"</div>', unsafe_allow_html=True)
        
        st.markdown("**Subsystem References:**")
        if na.subsystems_mentioned:
            chips = " ".join([f'<span class="chip-yellow" style="font-size:0.75rem; margin-right:0.3rem;">{s}</span>' for s in na.subsystems_mentioned])
            st.markdown(f'<div style="margin-bottom:0.8rem;">{chips}</div>', unsafe_allow_html=True)
        else:
            st.markdown("None detected.")

    with col_l2:
        st.markdown("**Extracted NLP Parameters:**")
        tone_str = na.tone.capitalize() if na.tone else 'Uncertain'
        tone_emoji = get_tone_icon(na.tone)
        
        rel_html = get_relationship_html(na.note_telemetry_relationship)
        
        st.markdown(f"""
        <table class="telemetry-table" style="margin-top:0;">
          <tr><td><strong>Operator Tone</strong></td><td>{tone_emoji} {tone_str}</td></tr>
          <tr><td><strong>Note-Telemetry Link</strong></td><td>{rel_html}</td></tr>
          <tr><td><strong>Temporal Reference</strong></td><td>{', '.join(na.time_observations) if na.time_observations else 'None'}</td></tr>
        </table>
        """, unsafe_allow_html=True)

    st.markdown("**Extracted Operator Concerns:**")
    if na.concerns:
        for c in na.concerns:
            st.markdown(f"- ⚠️ {html.escape(c)}")
    else:
        st.markdown("- *No operational concerns extracted from note.*")


# =====================================================================
# SECTION 5: ASSESSMENT
# =====================================================================
st.markdown('<div class="section-header">Section 5: Integrated Health Assessment</div>', unsafe_allow_html=True)

col_a1, col_a2 = st.columns([2, 3])

with col_a1:
    st.markdown("##### Numerical Assessment Metrics")
    
    # Severity indicator
    sev = result.calculated_severity
    col = SEVERITY_COLOURS.get(sev, '#8b949e')
    st.markdown(f"""
    <div style="font-size: 0.85rem; color:#8b949e; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:-0.2rem;">Health Status</div>
    <div style="font-size: 2.2rem; font-weight:800; color:{col}; margin-bottom:0.8rem;">{sev}</div>
    """, unsafe_allow_html=True)
    
    # Risk score meter
    score = result.risk_score
    st.markdown(f"**Additive Risk Score:** `{score} / 100`")
    st.progress(score / 100.0)
    
    # Confidence meter
    conf = result.confidence
    st.markdown(f"**Assessment Confidence:** `{conf:.0f}%` &nbsp; (Floor: 10%)")
    st.progress(conf / 100.0)

with col_a2:
    st.markdown("##### Operator Diagnostic Narrative")
    narrative_txt = result.reasoning.narrative if (result.reasoning and result.reasoning.narrative) else "LLM Narrative explanation unavailable."
    st.markdown(f'<div class="info-card" style="border-left: 4px solid {get_confidence_bar_colour(conf)};">{narrative_txt}</div>', unsafe_allow_html=True)
    
    action = RECOMMENDED_ACTION.get(sev, RECOMMENDED_ACTION['NOMINAL'])
    st.markdown(f"**Recommended Action Plan:**")
    st.markdown(f"*{action}*")


# =====================================================================
# SECTION 6: CONFIDENCE BREAKDOWN
# =====================================================================
st.markdown('<div class="section-header">Section 6: Confidence Score Penalty Breakdown</div>', unsafe_allow_html=True)

if not result.confidence_penalties:
    st.markdown(
        '<div class="info-card" style="color:#3fb950; font-size:0.85rem;">✅ Base Confidence remains at 100%. No deductions applied.</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown("The following deterministic penalties were applied to calculate the final confidence score:")
    
    # 2-column layout to balance the UI
    col_p1, col_p2 = st.columns(2)
    
    half = (len(result.confidence_penalties) + 1) // 2
    p_cols = [result.confidence_penalties[:half], result.confidence_penalties[half:]]
    
    for i, col_penalties in enumerate([col_p1, col_p2]):
        with col_penalties:
            for p in p_cols[i]:
                st.markdown(
                    f'<div class="info-card" style="border-left: 3px solid #ff7b72; padding: 0.5rem 0.8rem; font-size: 0.82rem; margin-bottom: 0.5rem;">'
                    f'<strong>-{p.deduction}%</strong> &nbsp; · &nbsp; {p.reason}'
                    f'</div>',
                    unsafe_allow_html=True
                )


# =====================================================================
# SECTION 7: OPERATOR OVERRIDE
# =====================================================================
st.markdown('<div class="section-header">Section 7: Human-in-the-Loop Operator Override</div>', unsafe_allow_html=True)

st.write("Operator actions sit alongside the calculated severity. Overrides are logged historically but never overwrite the calculated severity.")

col_ov1, col_ov2 = st.columns([2, 3])

with col_ov1:
    st.markdown("##### Record Assessment")
    
    action_options = ["Confirm Assessment", "Downgrade Severity", "Escalate Severity"]
    
    # Pre-select based on existing log value
    rev_mapping = {"confirmed": 0, "downgraded": 1, "escalated": 2}
    default_idx = rev_mapping.get(result.operator_action, 0)
    
    selected_action = st.radio("Action type:", action_options, index=default_idx)
    
    override_note_txt = st.text_area(
        "Operator Override Notes / Rationale",
        value=result.operator_override_note,
        placeholder="Enter justification for escalation, downgrade, or confirmation...",
        height=95,
    )
    
    if st.button("✅ Log and Submit Assessment", type="primary", use_container_width=True):
        act_mapping = {
            "Confirm Assessment": "confirmed",
            "Downgrade Severity": "downgraded",
            "Escalate Severity": "escalated",
        }
        
        result.operator_action = act_mapping[selected_action]
        result.operator_override_note = override_note_txt.strip()
        result.override_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Save to session history log
        log_entry = {
            "timestamp": result.override_timestamp,
            "sat_id": result.sat_id,
            "pass_num": result.pass_num,
            "calculated_severity": result.calculated_severity,
            "operator_action": result.operator_action,
            "override_note": result.operator_override_note,
        }
        
        # Update in-place if an entry for this sat + pass already exists to avoid duplicates
        existing_idx = next((i for i, x in enumerate(st.session_state.override_log) 
                             if x['sat_id'] == result.sat_id and x['pass_num'] == result.pass_num), None)
        if existing_idx is not None:
            st.session_state.override_log[existing_idx] = log_entry
        else:
            st.session_state.override_log.append(log_entry)
            
        save_overrides(st.session_state.override_log)
        st.success(f"Assessment successfully logged for satellite {result.sat_id} pass {result.pass_num}!")

with col_ov2:
    st.markdown("##### Historic Operator Override Log (This Session)")
    
    if not st.session_state.override_log:
        st.caption("No overrides or confirmations logged in this session yet.")
    else:
        # Display logs in reverse order
        for log in reversed(st.session_state.override_log):
            action_badge = log['operator_action'].upper()
            action_col = "#ab7df8" if action_badge == 'CONFIRMED' else ("#ff7b72" if action_badge == 'ESCALATED' else "#58a6ff")
            
            st.markdown(f"""
            <div class="override-log-card">
              <span style="color:#8b949e;">{log['timestamp']}</span> &nbsp;·&nbsp; 
              <strong>{log['sat_id']} Pass {log['pass_num']}</strong> &nbsp;·&nbsp; 
              Calculated: <span style="color:{SEVERITY_COLOURS.get(log['calculated_severity'], '#8b949e')}; font-weight:600;">{log['calculated_severity']}</span> &nbsp;·&nbsp; 
              Action: <span style="color:{action_col}; font-weight:700;">{action_badge}</span><br/>
              <span style="color:#e6edf3; font-style:italic;">"{html.escape(log['override_note']) if log['override_note'] else 'No operator comments.'}"</span>
            </div>
            """, unsafe_allow_html=True)
