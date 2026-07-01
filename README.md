# Spacecraft Telemetry Health Assessment System (Tier 3 Ground Support)

A modern, high-reliability decision support dashboard for low-Earth orbit (LEO) satellite ground control stations. This application implements a multi-path telemetry diagnostic pipeline combining instantaneous deterministic rule checks, historical trend evaluation, and natural language log processing via the Google Gemini API.

It acts at **Tier 3 (Ground Segment)** of the satellite's Fault Detection, Isolation, and Recovery (FDIR) hierarchy, designed to prevent automation bias by integrating human-in-the-loop operator actions with a transparent, explainable confidence scoring framework.

---

## 🚀 Key Features

* **Deterministic Rule Engine (Single-Pass):** Evaluates instantaneous parameter limit crossings. Safety-critical breaches automatically enforce severity "floors" that cannot be overridden by downstream models.
* **Monotonic Trend Detector (Multi-Pass):** Scans historical ground station passes (orbits) to identify slow-acting parameter degradation (e.g. battery discharge or attitude error rise) while suppressing normal eclipse-to-sunlight thermal cycling.
* **Natural Language Note Analysis:** Utilizes `gemini-2.5-flash-lite` to extract operator concerns, evaluate tone, and cross-examine written log entries against numeric telemetry.
* **Explainable Confidence Scorer:** Dynamically penalizes confidence based on signal quality, note-telemetry conflicts, and system availability. Floor-clamped at a minimum of 10%.
* **Human-in-the-Loop Overrides:** Allows operators to confirm, downgrade, or escalate automated assessments with notes. These override decisions are stored permanently in a local audit log on disk.
* **🎲 Random Pass Advisor:** A sidebar exploration tool that draws random orbital configurations from the 500-pass dataset to test procedural anomaly permutations.

---

## 📂 Project Architecture

```
ODU Demo/
├── backend/
│   ├── config.py          # Single source of truth (thresholds, weights, prompt templates)
│   ├── rule_engine.py     # Stateless single-pass limit checks
│   ├── trend_detector.py  # Historical monotonic lookback logic
│   ├── llm_analysis.py    # Sequential Job 1 (Note parsing) & Job 2 (Narrative) wrappers
│   ├── risk_scorer.py     # Central integration pipeline & confidence scorer
│   └── generate_data.py   # Bounded random walk dataset generator (500 passes)
│
├── frontend/
│   ├── app.py             # Streamlit layout entrypoint
│   └── ui_styles.py       # Custom premium dark CSS overrides & HTML elements
│
├── tests/
│   ├── test_rule_engine.py     # Offline unit tests
│   ├── test_trend_detector.py  # Offline trend checks
│   ├── test_llm_analysis.py    # Live/mock LLM tests
│   └── test_risk_scorer.py     # Pipeline integration suite
│
├── .env.example           # Environment template
├── .gitignore             # Configured to only track codebase & final report
├── final_report.md        # Official Systems Engineering Phase Report
└── README.md              # Project documentation
```

---

## 🛠️ Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Krishna2805/ODU_Demo_Telemetry.git
   cd ODU_Demo_Telemetry
   ```

2. **Install Dependencies:**
   Ensure you have Python 3.10+ installed. Install the required Python packages:
   ```bash
   pip install streamlit pandas numpy google-genai python-dotenv
   ```

3. **Configure API Credentials:**
   Copy the environment template and insert your Google Gemini API key:
   ```bash
   copy .env.example .env
   # Open .env and set GEMINI_API_KEY=your_actual_api_key
   ```
   *Note: If no API key is provided, the system degrades gracefully into deterministic offline mode, applying a -15% confidence penalty.*

4. **Generate the Telemetry Dataset:**
   Generate the 500-pass simulated telemetry database:
   ```bash
   python backend/generate_data.py
   ```

---

## 🖥️ Running the Application

Start the Streamlit dashboard:
```bash
streamlit run frontend/app.py
```
Open your browser to the local URL (usually `http://localhost:8501`).

---

## 🧪 Running Unit & Integration Tests

The test suite is modularized to support offline validation of deterministic components:

* **Verify Rule Engine & Trend Detector (Offline — does not require API key):**
  ```bash
  python tests/test_rule_engine.py
  python tests/test_trend_detector.py
  ```
* **Verify LLM Wrappers & Risk Integrator (Requires configured `.env` key):**
  ```bash
  python tests/test_llm_analysis.py
  python tests/test_risk_scorer.py
  ```

---

## 📖 Curated Demo Case Studies

Use the **Quick-select Demo Scenarios** in the sidebar to load target verification cases:
* **Scenario A (Clean Nominal):** 100% confidence baseline, zero flags.
* **Scenario B (Eclipse Stress):** Monotonic temperature & SoC degradation.
* **Scenario C (Hard Limit Breach):** Hard voltage breach (< 22V) enforcing a CRITICAL status.
* **Scenario D (Genuine Uncertainty):** Multi-system yellow warnings + uncertain operator note dropping confidence to the 10% floor.
* **Scenario E (Note/Telemetry Conflict):** Discrepancy between green numbers and concerning text notes, triggering a warning and a -20% confidence penalty.
