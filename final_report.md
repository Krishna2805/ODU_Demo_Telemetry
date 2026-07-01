# Spacecraft Telemetry Health Assessment System
## Tier 3 Decision-Support Framework for Ground Segment Operations
**Author:** Flight Operations Engineering Team  
**Date:** July 1, 2026

---

### 1. Problem Framing

During spacecraft operations, the ground segment is the ultimate safety net. While onboard Fault Detection, Isolation, and Recovery (FDIR) systems (Tiers 1 and 2) operate in milliseconds to minutes to protect the satellite from immediate hazards, they are constrained by limited onboard computing power and lack historical context. Tier 3 operations—human-in-the-loop ground segment monitoring—focus on diagnosing complex anomalies, detecting long-term parameter drifts, and planning recovery procedures.

Flight controllers are responsible for analyzing telemetry data received during brief ground station contacts (passes) and combining it with handwritten logs or pass notes. This environment presents two critical challenges:
1. **Alert Fatigue:** A single orbit transition or eclipse period can trigger dozens of minor limit warnings across multiple subsystems. If an alarm system is too sensitive or lacks context, operators experience alarm desensitization (the "cry-wolf" effect), leading to ignored critical alerts or unauthorized overrides.
2. **Cognitive Overload under Pressure:** When an anomaly occurs, operators must quickly correlate numeric telemetry with historical baselines and natural-language logs. A missed correlation can delay safety actions, while a false alarm can cause unnecessary safe-mode entries, interrupting mission science and wasting attitude control propellants.

The system described in this report is designed as a ground-based decision-support tool. It does not automate recovery commands (which could introduce unintended states if the automation is misconfigured), but instead acts as a unified diagnostic advisor. It consumes numeric pass telemetry and operator notes, and outputs a calculated severity level, a transparent confidence score, and a plain-English explanation of its reasoning.

---

### 2. Data Strategy and Research Grounding

#### Real-World Benchmarks and Synthesis Rationale
Before designing the telemetry profiles, we investigated three prominent spacecraft anomaly benchmarks:
1. **OPS-SAT Anomaly Detection (OPSSAT-AD):** A flight dataset from the European Space Agency’s (ESA) OPS-SAT CubeSat, featuring expert-labeled anomalies across nine channels. It demonstrates how real anomalies present as short transients, gradual drifts, or sustained steps.
2. **ESA Anomaly Detection Benchmark (ESA-ADB):** A multi-mission dataset that highlights the correlation of anomalies across multiple subsystems (e.g., thermal fluctuations driven by transmitter power draws).
3. **NASA SMAP/MSL Telemetry Anomaly Dataset:** A common machine learning benchmark containing normalized spacecraft data. While historically significant, its anonymized channel IDs and normalized values make it unsuitable for operator-facing decision support where physical units are required.

Real anomaly benchmarks are designed for training unsupervised time-series algorithms. They lack operator notes, severity classifications, and the operational context needed for a decision-support system. Therefore, we chose to construct a procedurally simulated dataset of 500 ground station passes across 50 Low-Earth Orbit (LEO) satellites. This dataset is explicitly grounded in the physical patterns observed in the ESA benchmarks (such as gradual battery degradation and ADCS pointing drifts) and includes synthetic operator notes that model realistic communication noise, uncertainty, and potential discrepancies.

#### Operating Limits and Engineering Grounding
The telemetry parameter bounds are anchored in the **CubeSat Design Specification (CDS)** and standard lithium-ion cell chemistry sheets:
* **Electrical Power System (EPS):** The nominal battery pack voltage is set to $24.0\text{--}30.0\text{V}$ (modeled on a standard 7S Li-ion configuration). A red limit is established at $<22.0\text{V}$ (representing cell depletion), which demands immediate critical attention. The state of charge (SoC) mirrors this with a critical red limit at $<20\%$ and a yellow caution limit between $20\text{--}35\%$.
* **Thermal Subsystem:** Lithium batteries are highly sensitive to temperature. The nominal battery temperature is set to $5\text{--}40\text{°C}$, with red limits at $<0\text{°C}$ (risk of electrolyte freezing during charge) and $>45\text{°C}$ (thermal runaway risk).
* **Attitude Determination and Control System (ADCS):** Pointing accuracy is critical for communication link margins and solar panel orientation. The pointing error threshold is nominally $\le 1.0\text{°}$, with a caution limit at $3.0\text{--}5.0\text{°}$ and a red limit at $>5.0\text{°}$ (representing attitude control loss).
* **Communications:** Bit error rate (BER) limits follow standard digital link constraints, where a BER $>10^{-4}$ represents critical link degradation and $10^{-6}\text{--}10^{-4}$ represents a yellow warning range.

---

### 3. System Architecture and Mathematical Formulation

The system uses a decoupled, sequential pipeline that processes data through five distinct stages:

```
[Raw Telemetry + Operator Note] 
       │
       ├─────────────────────────┐
       ▼                         ▼
[Rule Engine]            [Trend Detector]
(Instantaneous Limits)   (Monotonic Drifts)
       │                         │
       ▼                         ▼
[Note Parser (Job 1)] ───────────► [Risk & Confidence Scorer]
(JSON Metadata)          (Additive scoring & penalty deductions)
                                 │
                                 ▼
                         [Narrative Gen (Job 2)]
                         (Prose explanation)
                                 │
                                 ▼
                         [Operator Dashboard]
```

#### Deterministic Rule Engine
The rule engine is the first component to evaluate the telemetry. It checks only the current pass's instantaneous values. If any red limit is crossed, the engine triggers an immutable **severity floor** (`CRITICAL` or `WARNING`). This floor acts as an absolute safety gate; subsequent components can increase the severity but can never lower it.

#### Trend Detection Module
Operating in parallel with the rule engine, the trend detector performs a multi-pass historical lookback. It analyzes a minimum of three consecutive passes for the selected satellite. To prevent false positives from normal orbital variations (such as temperature cycles between sunlight and eclipse), it requires strict monotonicity. A trend flag is raised only if a parameter consistently degrades (e.g., battery voltage falling or attitude error rising) across all analyzed passes.

#### Risk Scorer and Severity Classification
The risk score ($R \in [0, 100]$) is computed using an additive system. Yellow limits contribute to the score based on the consequence of their subsystem category:
$$\text{Capped Yellow Points} = \min\left(40, \;\sum \text{Yellow Weights}\right)$$
Where the weights are defined by subsystem criticality: $\text{EPS/Thermal} = 15$, $\text{ADCS} = 10$, $\text{Communications} = 7$, and $\text{OBC} = 4$.

Trend flags contribute to the score based on their operational impact: critical parameters (voltage, SoC, pointing error, wheel speed) add $+10$ points, while secondary parameters (CPU, temperature) add $+5$ points.

The final risk score is mapped to one of four severity levels:
* $[0, 25] \implies \text{NOMINAL}$
* $[26, 50] \implies \text{MONITOR}$
* $[51, 75] \implies \text{WARNING}$
* $[76, 100] \implies \text{CRITICAL}$

If the rule engine detects a red limit breach, the risk score is automatically adjusted to meet the corresponding floor ($R \ge 76$ for `CRITICAL` or $R \ge 51$ for `WARNING`).

#### Deterministic Confidence Score
Uncertainty is treated as a separate operational dimension rather than a severity level. The confidence score ($C \in [10\%, 100\%]$) starts at $100\%$ and is reduced by deterministic penalties:
* **Bit Error Rate Warning/Breach:** $-30\%$ (poor telemetry link quality degrades data reliability).
* **Note-Telemetry Conflict:** $-20\%$ (disagreement between operator observations and telemetry).
* **LLM Analysis Offline:** $-15\%$ (loss of natural language note processing).
* **Multi-Subsystem Caution:** $-15\%$ (simultaneous yellow flags across different subsystems).
* **Uncertain Note Tone:** $-10\%$ (operator note indicates uncertainty).
* **Vague Note Relationship:** $-5\%$ (note cannot be confidently correlated with telemetry).
* **Caution Limits / Trend Flags:** $-5\%$ per tripped yellow limit, $-10\% / -5\%$ per trend flag.

---

### 4. Technical Trade-offs and Design Rationale

1. **Deterministic Scorer vs. Machine Learning Classifier:** We rejected training a machine learning model to classify pass health. In satellite operations, safety-critical decisions require auditability. An operator must know exactly why a pass is classified as `CRITICAL` (e.g., battery voltage fell below $22\text{V}$), rather than relying on a black-box probability density.
2. **Procedural Simulator vs. Generative Adversarial Network (GAN):** Procedural generation was chosen over a GAN for the synthetic dataset. Procedural rules guarantee physical consistency (e.g., zero solar current during eclipse), which is critical for system validation and operator training.
3. **Decoupled LLM Processing:** The Large Language Model is restricted to two specific, structured tasks: note parsing (Job 1) and narrative generation (Job 2). The LLM is never permitted to classify severity or compute confidence. This separation prevents model hallucinations from affecting safety-critical metrics while utilizing the LLM's strength in summarizing unstructured text.
4. **Fast Timeout Fallbacks:** We implemented a 15-second API timeout and automatic retry logic. If the LLM service becomes unresponsive, the system falls back to a deterministic mode, applying a $-15\%$ confidence penalty. This ensures that ground operations are never halted by a network timeout.

---

### 5. Scenario Validation and Operational Results

We validated the system using five representative operational scenarios:

#### Scenario A: Nominal Operations (Clean Pass)
* **Telemetry:** All parameters within nominal bounds.
* **Operator Note:** "All nominal, clean pass."
* **System Output:** `NOMINAL` severity (driven by a risk score of $0$), $100\%$ confidence, and a brief summary confirming nominal operations.
* **Operational Value:** Confirms the baseline state. Operators are not distracted by false alerts.

#### Scenario B: Eclipse Battery Stress
* **Telemetry:** Solar current at zero, battery voltage at $22.8\text{V}$ (yellow limit), battery SoC at $31\%$ (yellow limit). Monotonic declining trends are detected in both voltage and SoC over the prior three passes.
* **Operator Note:** "Battery dipping during eclipse, watching it."
* **System Output:** `MONITOR` or `WARNING` severity (driven by a risk score of $50+$), $70\%$ confidence (reflecting yellow limits and battery trend penalties). The narrative explains the expected eclipse discharge curve.
* **Operational Value:** Flags a developing power constraint before a critical threshold is breached.

#### Scenario C: Voltage Collapse (Hard Limit Breach)
* **Telemetry:** Battery voltage at $21.5\text{V}$ (breaches red limit of $<22.0\text{V}$).
* **Operator Note:** "Voltage below 22V on entry, flagged for review immediately."
* **System Output:** `CRITICAL` severity (driven by the rule engine safety floor), with a risk score adjusted to $76$. The narrative highlights the voltage breach and recommends immediate battery isolation.
* **Operational Value:** Demonstrates that safety rules always override other inputs, enforcing an immediate critical response.

#### Scenario D: Multi-System Uncertainty
* **Telemetry:** Multiple parameters (battery temperature, pointing error, bit error rate, CPU usage) are in their yellow caution ranges.
* **Operator Note:** "Something seems off but can't tell what."
* **System Output:** `MONITOR` or `WARNING` severity. The confidence score drops to $10\%$, reflecting penalties for multiple subsystem yellows, an uncertain note tone, and vague note context.
* **Operational Value:** Highlights high-uncertainty states, alert controllers to double-check telemetry calibration.

#### Scenario E: Note-Telemetry Conflict
* **Telemetry:** All numeric telemetry is nominal.
* **Operator Note:** "Attitude looks wrong to me, wheel speed feels high."
* **System Output:** `NOMINAL` or `MONITOR` severity. The confidence score is reduced by a $-20\%$ conflict penalty. The narrative warns of a potential pointing discrepancy.
* **Operational Value:** Prevents operator complacency when telemetry appears normal but the controller reports a manual observation of concern.

---

### 6. System Weaknesses and Future Work

1. **Static Rules vs. Dynamic Baselines:** The current system uses static limit thresholds. As a spacecraft ages, its solar panels degrade and battery capacity shrinks, causing parameters to drift from their original launch baselines. Future updates should implement dynamic, age-adjusted limits.
2. **Simplified Trend Window:** The trend detector is limited to a fixed three-pass window. An improvement would be to analyze varying window lengths to capture both fast-acting thermal transients and slow-acting, long-term battery degradation.
3. **No Inter-Subsystem Correlation:** The system treats limits independently. For example, high CPU usage and high temperature are flagged as separate anomalies, rather than identifying the thermal load driven by the processor. Future versions should model these physical couplings.

---

### 7. References

1. California Polytechnic State University, *CubeSat Design Specification (CDS)*. Used to define nominal ranges for CubeSat batteries, solar panels, and ADCS subsystems.
2. European Space Agency, *ECSS-E-ST-70-31C: Spacecraft Telemetry and Telecommand Standard*. Grounded the vocabulary and the yellow/red limit check design.
3. European Space Agency, *ECSS-E-70-31A: Ground Systems and Operations*. Provided the multi-level WATCH/WARNING/DISTRESS/CRITICAL classification structure.
4. Sheridan, T. B., & Wickens, C. D. (2000). *Model of Human-Robot Interaction and Trust*. Informed the human factors design, focusing on mitigating alert fatigue through progress disclosure.
5. NASA, *Open MCT (Mission Control Technologies)*. Provided the design rationale for ground station dashboards, emphasizing clear data tracing.
6. Hundman, K., et al. (2018). *Detecting Spacecraft Anomalies Using LSTMs on SMAP/MSL Data*. Consulted for standard anomaly detection approaches, informing our decision to use a rule-based explainable scorer instead.
7. ESA, *OPS-SAT Anomaly Detection Benchmark (OPSSAT-AD)*. Used to study real CubeSat anomalies and validate our procedural drift shapes.
8. ESA, *European Space Agency Anomaly Benchmark (ESA-ADB)*. Analyzed to understand correlation patterns between power, thermal, and RF subsystems.
