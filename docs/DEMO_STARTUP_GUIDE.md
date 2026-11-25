# PromptGreen V2 — Demonstration & Startup Guide
**Academic Capstone Project Demonstration Runbook**
**Target Audience:** Academic Evaluators, Faculty Teachers, and External Viva Interviewers  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  
**Branch:** `version-2`  
**Local Port:** `http://localhost:8000`

---

## 1. Executive Summary

PromptGreen is an active prompt optimization and carbon-aware telemetry engine for sustainable Large Language Model (LLM) inference. The system couples a **deterministic 4-stage optimization pipeline** (Rule Pruner, Lexical Compressor, Output Directive Shaper, and Semantic Fidelity Guard) with a **rigorous thermodynamic energy engine** and a **conservative Green Model Router**.

All measurements strictly adhere to first-principles physical thermodynamics in canonical **Watt-hours (Wh)**, avoid unsupported empirical claims, preserve strict semantic invariants (medical safety, code blocks, JSON schemas), and maintain an immutable **SQLite audit ledger**.

---

## 2. Prerequisites & Offline Capability

- **Operating System:** Windows 10/11 (or macOS / Linux via equivalent Python commands).
- **Python Runtime:** Python 3.10+ (using either a local virtual environment `.venv` / `venv` or system Python).
- **Network Independence:** PromptGreen V2 is completely self-contained. The frontend user interface in `Website/index.html` embeds offline CSS fallbacks, local SVG icons, and connects directly to the local backend on `http://localhost:8000`. No active internet connection or external CDN is required during viva evaluation.
- **Ollama Integration (Optional):** If a local Ollama daemon is active, Stage 3 executes local neural directive compression. If Ollama is unavailable or times out, the pipeline safely completes as a deterministic no-op fallback without failure or latency blocks.

---

## 3. Quick-Start Launch Procedure

### Option A: 1-Click Launch (Recommended for Windows)

Double-click `start_promptgreen.bat` in the repository root directory.

The launcher automatically:
1. Detects your Python virtual environment (`.venv` or `venv`) or system Python.
2. Sets `PYTHONPATH` to the repository root.
3. Starts the Uvicorn HTTP server hosting both the Green Prompt Studio and the FastAPI REST API on port `8000`.
4. Automatically opens your default web browser to:
   ```
   http://localhost:8000
   ```

### Option B: Terminal Command Launch

Open PowerShell or Command Prompt in the repository root and run:

```powershell
# Activate your virtual environment if applicable
.\.venv\Scripts\Activate.ps1

# Set python path and start unified server
$env:PYTHONPATH = "."
python Website/server.py
```

Open your browser to:
- **Green Prompt Studio UI:** [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 4. Curated 5-Scenario Demonstration Script

To present the full breadth of PromptGreen V2 during an academic viva or interview, follow these five structured scenarios:

### Scenario 1: Verbose Corporate Prompt (Energy & Token Abatement)
* **Goal:** Demonstrate active structural fluff removal, 4-stage pipeline execution, and positive thermodynamic Wh abatement.
* **Input Prompt:**
  ```text
  Hello dear assistant! Could you please be so kind as to give me an extremely comprehensive, detailed, extensive, full explanation of quantum superposition with many examples? Thank you very much in advance for your kind help!
  ```
* **Configuration:**
  - Optimization Mode: **Balanced**
  - Target Model: **Frontier Dense (GPT-4 / Claude-3.5 Sonnet class)**
  - Grid Scenario: **ILLUSTRATIVE_385 (385 gCO2e/kWh)**
* **Key Observations in UI:**
  - **Pipeline Strip:** Stage 1 (Rule Pruner) trims redundant greetings and honorifics.
  - **Token Metrics:** Input tokens reduced by ~25% (43 → 32 tokens).
  - **Thermodynamic Card:** Gross energy savings exceed CPU overhead, yielding a positive net energy reduction (~0.0025 Wh) and measurable carbon abatement in gCO2e.

---

### Scenario 2: Simple Query (Green Model Routing Recommendation)
* **Goal:** Demonstrate conservative model-routing recommendations from a high-power frontier tier to a green compact model.
* **Input Prompt:**
  ```text
  Classify the sentiment of the following customer comment as POSITIVE, NEGATIVE, or NEUTRAL: 'The packaging arrived slightly damaged, but the headphones inside were pristine and work great!'
  ```
* **Configuration:**
  - Optimization Mode: **Balanced**
  - Target Model: **Frontier Dense**
* **Key Observations in UI:**
  - **Routing Recommendation Card:** Displays **RECOMMEND_DOWNGRADE** to `compact_green`.
  - **Suitability:** High confidence that simple classification does not require a 400W+ frontier cluster.
  - **Physical Energy Comparison:** Compares inference energy on `frontier_dense` (0.091 Wh) vs `compact_green` (0.007 Wh), displaying potential savings.
  - **Advisory Banner:** Notes that routing is strictly advisory and user-controlled; models are never switched silently.

---

### Scenario 3: Safety-Critical Clinical Dosage (Semantic Guardrail)
* **Goal:** Prove that medical, dosage, and safety-critical constraints are inviolable and cannot be stripped by aggressive optimization or downgraded.
* **Input Prompt:**
  ```text
  Administer Epinephrine 0.3mg IM for anaphylaxis immediately. Monitor blood pressure every 2 minutes. Do NOT administer IV bolus under any circumstances.
  ```
* **Configuration:**
  - Optimization Mode: **Aggressive**
  - Target Model: **Frontier Dense**
* **Key Observations in UI:**
  - **Semantic Guard Strip:** Cosine similarity remains 1.0000; strict negation `Do NOT administer IV bolus` and dosage `0.3mg` are preserved intact.
  - **Routing Recommendation:** Enforces **NO_SAFE_DOWNGRADE**. Medical advice is classified as safety-critical and restricted from being moved to lower-capability tiers.

---

### Scenario 4: Technical Code Block (AST & Fenced Markdown Invariant)
* **Goal:** Demonstrate that technical code blocks, cryptographic implementations, and syntax formatting are protected byte-for-byte.
* **Input Prompt:**
  ```text
  Review the following Python hashing function and verify whether it correctly implements constant-time comparison:
  ```python
  import hmac
  def verify_signature(secret: bytes, message: bytes, signature: bytes) -> bool:
      mac = hmac.new(secret, message, 'sha256')
      return hmac.compare_digest(mac.digest(), signature)
  ```
  Check for any timing side-channel vulnerabilities.
  ```
* **Configuration:**
  - Optimization Mode: **Balanced**
* **Key Observations in UI:**
  - **Preservation:** The triple-backtick fenced code block, variable names, and function body are identical character-by-character.
  - **Guard Status:** Guardrail passed with high fidelity.

---

### Scenario 5: Micro-Prompt (Honest Thermodynamic Accounting & Carbon Debt)
* **Goal:** Demonstrate that PromptGreen does not make false green claims: if prompt savings are trivial, the engine honestly displays negative savings and flags carbon debt.
* **Input Prompt:**
  ```text
  Hi!
  ```
* **Configuration:**
  - Optimization Mode: **Balanced**
  - Target Model: **Compact Green**
* **Key Observations in UI:**
  - **Token Metrics:** 0 tokens saved (prompt is already minimal).
  - **Thermodynamic Card:** Gross savings = 0.0 Wh, while optimizer CPU overhead $E_{\text{overhead}} > 0$.
  - **Honest Alert:** An amber warning badge appears: `Net Carbon Debt: Local optimizer energy exceeded gross inference savings`. Net energy is negative ($\sim -0.0006$ Wh).
  - **Evaluation Defense:** Highlights academic integrity—PromptGreen rejects greenwashing.

---

## 5. Live Telemetry & Audit Ledger

At the bottom of the Green Prompt Studio:
- **Optimization History Table:** Every single optimization executed through the UI or API is automatically written to `prompt_ledger.db`.
- **Fields Logged:** Record ID, Timestamp, Target Model Tier, Input/Output Token Deltas, Net Energy Saved (Wh), Net Carbon Abated (gCO2e), Routing Outcome, and Guardrail Status.
- **Cumulative KPI Counters:** Displays real-time aggregate counts of total optimizations, successful semantic passes, cumulative Wh abated, and cumulative grams of CO2e avoided.
- **Direct Database Query:** Evaluators can verify data directly via Python:
  ```powershell
  python -c "from promptgreen.ledger.database import PromptLedger; db = PromptLedger(); print(db.get_v2_summary())"
  ```

---

## 6. Shutdown Procedure

To cleanly stop the local application:
1. In the console window running `start_promptgreen.bat` or `python Website/server.py`, press **`Ctrl + C`**.
2. Alternatively, double-click **`stop_promptgreen.bat`** in the repository root to automatically find and terminate any process listening on port 8000.
