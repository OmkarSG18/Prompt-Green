# PromptGreen

> **Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment**

PromptGreen is a developer-centric Green AI framework that predicts the carbon delta (incremental carbon footprint) of Large Language Model (LLM) prompt modifications **before** deployment. By integrating carbon analysis directly into the developer workflow and CI/CD pipelines, PromptGreen prevents carbon-intensive prompt changes from silently accumulating carbon debt in production.

---

## 🌟 Key Highlights

- **Shift-Left Carbon Review**: Evaluates prompt differences (diffs) during Pull Request review rather than diagnosing emissions after inference.
- **Hybrid Token Inflation Predictor**: Blends semantic NLP heuristics (verb complexity, Chain-of-Thought triggers, few-shot demonstration overhead) with machine learning regression (Ridge / Random Forest).
- **Carbon-Intensity Engine**: Converts token deltas into energy consumption (mJ) and emissions ($gCO_2$) across regional energy grids using published model power profiles.
- **Active Deployment Gates**: Enforces customizable carbon budget thresholds with `warn` or `block` policies in CI/CD.
- **Zero Financial Cost**: Runs locally on CPU without requiring paid external APIs, cloud GPU instances, or specialized hardware.
- **Audit & Analytics**: Features a local SQLite ledger, a Streamlit dashboard, a FastAPI web simulator, and a rich CLI.

---

## 🏗️ Architecture

```
                                  Prompt Change (Diff)
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Analysis Layer (PromptDiffAnalyzer)                                                │
│    • Token count via tiktoken                                                         │
│    • Semantic complexity & verb analysis                                              │
│    • Few-shot example & Chain-of-Thought (CoT) detection                              │
└──────────────────────────────────┬────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Prediction Layer (HybridPredictor)                                                 │
│    • Rule-based semantic estimation (Layer 1)                                         │
│    • ML regression model (Layer 2)                                                    │
│    • Dynamic weighted ensemble output                                                 │
└──────────────────────────────────┬────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ 3. Carbon Calculation (CarbonEngine)                                                  │
│    • Model energy profile lookup (Llama-3, Mistral, Phi-3, etc.)                      │
│    • Regional grid carbon intensity (US, EU, IN, Global)                              │
│    • Per-inference and monthly carbon delta projection                                │
└──────────────────────────────────┬────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Enforcement & Reporting (PromptGate)                                               │
│    • Budget comparison (PASS / WARN / FAIL)                                           │
│    • Actionable optimization tips & green prompt suggestions                          │
│    • GitHub Action PR comments / CLI tables / SQLite ledger record                    │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install the dependencies in a virtual environment:

```bash
# Clone the repository
git clone https://github.com/<your-username>/PromptGreen.git
cd PromptGreen

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install the package and dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Run the CLI

PromptGreen includes a command-line interface for analyzing prompts, inspecting historical logs, and testing benchmarks.

#### Analyze a Prompt Change
```bash
promptgreen analyze \
  --old "Explain in detail with extensive examples how quantum computing works." \
  --new "Summarize how quantum computing works in 3 concise bullet points." \
  --model llama-3-8b \
  --region US \
  --budget 0.5 \
  --mode warn
```

#### Run Git Diff Review
Inspect changes between commits directly:
```bash
promptgreen git-diff --commit HEAD~1 --model llama-3-8b --budget 0.5
```

#### View Carbon Ledger History
```bash
promptgreen ledger --limit 10
```

#### Run Validation Benchmarks
```bash
promptgreen benchmark
```

---

## 🖥️ User Interfaces

PromptGreen provides multiple interfaces to suit different development and demonstration needs:

### 1. Interactive Streamlit Dashboard
Visualize model energy comparisons, regional grid differences, cumulative carbon savings, and review records:
```bash
streamlit run dashboard/app.py
```

### 2. Web Application & API
Start the FastAPI server hosting the REST endpoints and web interface:
```bash
python Website/server.py
```
Open `http://localhost:8000` in your browser.

### 3. Standalone GUI Simulator
Open `gui_simulator.html` directly in any modern browser for client-side parameter tuning and live validation.

---

## 🤖 GitHub Actions CI/CD Integration

PromptGreen can run as an automated quality gate in your GitHub pull requests.

### Using the Workflow

Add `.github/workflows/promptgreen_gate.yml` to your repository:

```yaml
name: PromptGreen Carbon Gate Review

on:
  pull_request:
    branches: [ main, master ]

jobs:
  carbon_gate_review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3
        with:
          fetch-depth: 2

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install . pytest

      - name: Execute Prompt Carbon Review
        run: |
          python -m promptgreen.cli git-diff --commit HEAD~1 --budget 0.5 --mode warn
```

---

## 🧪 Verification & Testing

Run the test suite:
```bash
python -m pytest
```

Run the core engine verification script:
```bash
python verify_engine.py
```

---

## 📁 Repository Structure

```
PromptGreen/
├── .github/
│   └── workflows/
│       └── promptgreen_gate.yml      # Automated GitHub Actions workflow
├── dashboard/
│   └── app.py                        # Streamlit visual dashboard
├── data/
│   └── benchmark_suite.json          # 50-pair benchmark dataset
├── docs/
│   └── FINAL_REPORT.md               # Research report and formal methodology
├── promptgreen/                      # Core Python source package
│   ├── analysis/                     # Semantic NLP & prompt diff parser
│   ├── api/                          # FastAPI service endpoints
│   ├── engine/                       # Energy & carbon modeling engine
│   ├── gate/                         # Policy evaluation & markdown generator
│   ├── ledger/                       # SQLite persistent ledger
│   ├── predictor/                    # Hybrid rule + ML inflation predictor
│   ├── validation/                   # Benchmark validation suite runner
│   └── cli.py                        # Command-line interface entry point
├── tests/
│   └── test_all.py                   # Automated unit and integration tests
├── Website/                          # Web simulator application
│   ├── index.html
│   └── server.py
├── action.yml                        # Composite GitHub Action specification
├── gui_simulator.html                # Standalone simulator tool
├── requirements.txt                  # Project dependencies
├── setup.py                          # Package setup configuration
└── verify_engine.py                  # Core engine prompt greening verification
```

---

## 🎯 Benchmark Results

PromptGreen was evaluated on a curated 50-pair prompt benchmark across multiple domains (Summarization, Code Generation, Reasoning, Classification, Open Generation):

| Metric | Target | Measured Result |
| :--- | :--- | :--- |
| **Directional Accuracy** | $\ge 85.0\%$ | **100.0%** |
| **Mean Absolute Percentage Error (MAPE)** | $\le 20.0\%$ | **14.2%** |
| **Regression $R^2$ Score** | $\ge 0.80$ | **0.885** |

---

## 🌍 Sustainable Development Goals (SDG) Alignment

- **SDG 13: Climate Action**: Directly mitigates the carbon footprint of AI inference workloads.
- **SDG 12: Responsible Consumption & Production**: Encourages token efficiency and waste reduction in prompt design.
- **SDG 9: Industry, Innovation & Infrastructure**: Provides open-source sustainable AI tooling for development workflows.
