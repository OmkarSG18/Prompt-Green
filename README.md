# PromptGreen V2

> **Zero-Budget Carbon-Aware Prompt Optimization, Semantic Fidelity Verification, and Intelligent Model Routing for Sustainable LLM Deployment**

[![CI/CD Pipeline](https://github.com/OmkarSG18/Prompt-Green/actions/workflows/promptgreen_gate.yml/badge.svg?branch=version-2)](https://github.com/OmkarSG18/Prompt-Green/actions/workflows/promptgreen_gate.yml)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](https://github.com/OmkarSG18/Prompt-Green/tree/version-2)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 184 Passing](https://img.shields.io/badge/tests-184%20passed-brightgreen.svg)](tests/)

---

## 🌿 Overview

**PromptGreen V2** is a developer-first Green AI framework that optimizes prompt token efficiency, guarantees semantic fidelity, models hardware-level inference energy, and routes LLM requests to Pareto-optimal model tiers **before** deployment.

Modern Large Language Models incur significant operational energy consumption and carbon emissions during inference. Unchecked prompt inflation—caused by verbose instructions, boilerplate conversational filler, redundant few-shot examples, and unconstrained output generation—multiplies downstream emissions across millions of requests.

PromptGreen V2 solves this by shifting carbon accountability left. Operating completely locally on standard CPU hardware with **zero financial overhead**, PromptGreen provides a four-stage prompt optimization pipeline, automated cosine similarity safeguards, physics-based thermodynamic energy modeling, and a real-time web studio.

---

## 🌟 What's New in PromptGreen V2

| Feature | Version 1.0 (Baseline) | Version 2.0 (Current) |
|---|---|---|
| **Optimization Pipeline** | Static heuristic prompt diffing | **Four-Stage Pipeline**: Rule Pruner → Neural Compressor → Output Shaper → Semantic Guard |
| **Safety & Fidelity** | Manual developer inspection | **Automated Rollback Safeguard**: Thresholded cosine similarity ($\ge 0.85$) with stage rollback |
| **Model Routing** | Single-model static energy lookup | **Pareto-Optimal Dynamic Routing**: Edge/Small (Phi-3, Gemma-2) vs Mid-Tier (Llama-3 8B) vs Frontier (70B/GPT-4o) |
| **Energy Modeling** | Simplified token multiplication | **Thermodynamic Engine**: Separated prefill vs decode phase energy, PUE, GPU profiles (A100, H100, L40S, RTX 4090) |
| **Web Experience** | Basic Streamlit UI + simple HTML | **Full Single Page Application (SPA)**: Studio, Analytics, History, Architecture, and Evaluation tabs |
| **Storage & Scale** | Basic SQLite log | **Enterprise Ledger**: SQLite (`prompt_ledger.db`), TimescaleDB migration, Redis caching, Celery workers |
| **Benchmark Evidence** | 50 prompt pairs | **Comprehensive Suites**: 50 Baseline + 240 Multi-Domain + 1000 IGE Generalization + 1200 Scaled Prompts |
| **Test Suite** | Basic unit tests | **184 Passing Tests**: Unit, integration, regression, and end-to-end browser user journey tests |

---

## 🏗️ System Architecture

PromptGreen V2 operates as an integrated end-to-end green deployment pipeline:

```
                            Incoming Raw Prompt
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │               STAGE 1: STRUCTURAL RULE PRUNER (RulePruner)                    │
 │  • Strips conversational greetings, sign-offs, and filler phrases             │
 │  • Removes redundant polite boilerplate and repetitive syntax                 │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │               STAGE 2: NEURAL TOKEN COMPRESSOR (Compressor)                   │
 │  • LLMLingua-2 / Token-importance information entropy evaluation              │
 │  • Dynamically eliminates low-information tokens while preserving semantics   │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │                  STAGE 3: OUTPUT SHAPER (OutputShaper)                        │
 │  • Injects concise structural constraints into system instructions            │
 │  • Constrains verbose LLM output decoding without degrading answer quality    │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │             STAGE 4: SEMANTIC FIDELITY GUARD (SemanticGuard)                  │
 │  • Computes cosine similarity between original and optimized embeddings       │
 │  • Evaluates against safety threshold (similarity >= 0.85)                    │
 │  • AUTOMATED ROLLBACK: Reverts to previous stage if fidelity degrades         │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │                 PARETO-OPTIMAL MODEL ROUTER (ModelRouter)                     │
 │  • Analyzes prompt task complexity, domain requirements, and carbon budgets   │
 │  • Recommends optimal tier: Edge (SLM) ──► Mid-Tier ──► Frontier               │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │             THERMODYNAMIC ENERGY & CARBON ENGINE (CarbonEngine)               │
 │  • Separated prefill energy (quadratic/linear FLOPs) vs decode energy         │
 │  • GPU specs: A100 (400W), H100 (700W), L40S (350W), RTX 4090 (450W)          │
 │  • Grid carbon intensities: US (380 g/kWh), EU (260 g/kWh), IN (720 g/kWh)    │
 └───────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                                     ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │             ENTERPRISE LEDGER & ANALYTICS (PromptLedger & API)                │
 │  • SQLite ledger (prompt_ledger.db) / Optional PostgreSQL + TimescaleDB       │
 │  • FastAPI REST endpoints (port 8000) & SPA Frontend (port 8080)              │
 └───────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ The Four-Stage Optimization Pipeline

1. **Stage 1 — Structural Rule Pruner (`RulePruner`):**
   Applies deterministic regex transformations to strip conversational preambles (*"Hello, can you please..."*), redundant politeness, and excessive whitespace while preserving technical context and code blocks.
2. **Stage 2 — Neural Token Compressor (`Compressor`):**
   Applies semantic token pruning inspired by LLMLingua-2. Evaluates token importance and selectively prunes low-entropy tokens to reduce prefill sequence length.
3. **Stage 3 — Output Shaper (`OutputShaper`):**
   Appends structured brevity constraints (*"Respond concisely in structured bullet points without preamble"*), curbing generation length during the energy-intensive autoregressive decode phase.
4. **Stage 4 — Semantic Fidelity Guard (`SemanticGuard`):**
   Computes embedding cosine similarity ($S_{cos}$) between the original and transformed prompt. If $S_{cos} < 0.85$, the pipeline initiates an **automated stage rollback**, reverting the prompt to the last valid stage to ensure zero loss of critical user intent.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ installed
- Windows PowerShell, Command Prompt, or Linux/macOS bash

### 2. Installation

Clone the repository and switch to branch `version-2`:

```bash
git clone -b version-2 https://github.com/OmkarSG18/Prompt-Green.git
cd PromptGreen

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# Install dependencies and local editable package
pip install -r requirements.txt
pip install -e .
```

### 3. Launch PromptGreen V2 Services

PromptGreen includes master lifecycle orchestrators for Windows:

```powershell
# Option A: PowerShell Master Launcher (Starts Backend on :8000 and Frontend on :8080)
.\start.ps1

# Option B: Windows Command Prompt Launcher
start_promptgreen.bat
```

Once launched, open your browser to:
- **Frontend SPA Studio:** [http://127.0.0.1:8080](http://127.0.0.1:8080)
- **FastAPI Backend Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Health Check:** [http://127.0.0.1:8000/api/v2/health](http://127.0.0.1:8000/api/v2/health)

To stop all background services cleanly:
```powershell
.\stop.ps1
# or
stop_promptgreen.bat
```

---

## 🖥️ Web Single Page Application (SPA)

The V2 web interface ([Website/index.html](Website/index.html)) provides five specialized modules:

1. **Studio (`#studio`):**
   Interactive prompt editor with real-time token count, four-stage optimization toggle, visual token diff, cosine similarity meter, latency breakdown, and carbon delta savings.
2. **Analytics (`#analytics`):**
   Aggregated emission analytics, cumulative carbon saved ($gCO_2$), energy curves ($mJ$), regional grid comparison charts, and Pareto efficiency frontiers.
3. **History (`#history`):**
   Complete transactional audit trail queried from `prompt_ledger.db`. Search by prompt ID, filter by model, view rollback flags, and inspect before/after prompts.
4. **Architecture (`#architecture`):**
   Interactive architectural diagrams, mathematical energy equations, GPU hardware profiles, and pipeline flow documentation.
5. **Evaluation (`#evaluation`):**
   Interactive browser for empirical benchmark results across the 50, 240, 1000, and 1200 prompt datasets with domain breakdown and accuracy metrics.

---

## 💻 CLI Usage

PromptGreen provides a rich command-line interface for terminal workflows:

```bash
# Optimize a prompt through the 4-stage pipeline
promptgreen optimize "Hello, could you please explain quantum computing with extensive examples?"

# Analyze prompt diff and predict carbon delta
promptgreen analyze \
  --old "Explain in detail with extensive examples how quantum computing works." \
  --new "Summarize quantum computing in 3 concise bullet points." \
  --model llama-3-8b \
  --region US \
  --budget 0.5 \
  --mode warn

# Review carbon impact of recent Git commits
promptgreen git-diff --commit HEAD~1 --model llama-3-8b --budget 0.5

# Inspect historical ledger records
promptgreen ledger --limit 10

# Execute benchmark validation suite
promptgreen benchmark
```

---

## 📊 Benchmark Datasets & Scientific Validation

PromptGreen V2 has been evaluated across four rigorous empirical benchmark suites:

| Benchmark Suite | Size | Focus / Domain | Key Results & Metrics |
|---|---|---|---|
| **Baseline 50** (`data/benchmark_50_prompts.json`) | 50 pairs | Multi-domain prompt diffs | **100% Directional Accuracy**, 14.2% MAPE, $R^2 = 0.885$ |
| **Independent 240** (`data/benchmark_240_independent.json`) | 240 prompts | General, technical, creative | **235 Accepted (97.9%)**, 5 Safe Rollbacks, **167 net tokens saved** |
| **IGE-1000** (`data/benchmark_ige_1000_unseen.json`) | 1,000 prompts | Unseen out-of-domain evaluation | Evaluated across Conservative, Balanced, and Aggressive modes |
| **Scaled 1200** (`data/benchmark_1200_independent.json`) | 1,200 prompts | 10 distinct task domains | Full Pareto frontier validation across Edge, Mid-Tier, and Frontier models |

Authoritative benchmark summaries, category breakdowns, and raw outputs are stored in [results/](results/).

---

## 🧪 Testing & Verification

The repository includes a comprehensive test suite of **184 automated tests**:

```bash
# Run the complete test suite
python -m pytest

# Run tests with execution timings
python -m pytest --durations=10

# Run specific functional suites
python -m pytest tests/test_pipeline.py
python -m pytest tests/test_semantic_guard.py
python -m pytest tests/test_carbon_engine.py
python -m pytest tests/test_model_router.py
python -m pytest tests/test_benchmark_v2.py
```

All 184 tests pass cleanly, verifying pipeline correctness, semantic guard rollbacks, thermodynamic calculations, API endpoints, and database interactions.

---

## 🗄️ Enterprise Data & Lifecycle Architecture

- **Production SQLite Ledger (`prompt_ledger.db`):**
  Embedded zero-configuration database recording 500+ prompt optimization runs, token deltas, carbon savings, semantic similarities, and rollback events.
- **TimescaleDB & PostgreSQL Integration:**
  Includes enterprise migration scripts ([scripts/init_timescaledb.sql](scripts/init_timescaledb.sql) and [scripts/migrate_sqlite_to_timescale.py](scripts/migrate_sqlite_to_timescale.py)) for high-throughput time-series telemetry.
- **Asynchronous Task Queue:**
  Modular Redis caching and Celery task definitions ([promptgreen/cache/redis_cache.py](promptgreen/cache/redis_cache.py) and [promptgreen/tasks/benchmark_tasks.py](promptgreen/tasks/benchmark_tasks.py)).

---

## 📁 Repository Structure

```
PromptGreen/
├── .github/
│   └── workflows/
│       └── promptgreen_gate.yml       # GitHub Actions CI/CD Quality Gate
├── data/                              # Frozen Benchmark Datasets
│   ├── benchmark_50_prompts.json
│   ├── benchmark_240_independent.json
│   ├── benchmark_1000_unseen.json
│   └── benchmark_1200_independent.json
├── docs/                              # Research Reports, Viva Guides & Audits
│   ├── evidence/                      # High-resolution browser validation PNGs
│   ├── DEMO_STARTUP_GUIDE.md
│   ├── FINAL_VIVA_DEMONSTRATION_GUIDE.md
│   └── PROMPTGREEN_V2_FINAL_VALIDATION_REPORT.md
├── promptgreen/                       # Production Core Python Library
│   ├── analysis/                      # Prompt diff and complexity analyzer
│   ├── api/                           # FastAPI endpoints and ASGI app
│   ├── cache/                         # Redis and memory caching
│   ├── engine/                        # Carbon, thermodynamics & model router
│   ├── gate/                          # CI/CD policy enforcement
│   ├── ledger/                        # SQLite and database manager
│   ├── optimizer/                     # 4-stage pipeline (pruner, compressor, shaper, guard)
│   ├── predictor/                     # Hybrid inflation regression models
│   ├── tasks/                         # Celery background workers
│   ├── validation/                    # V2 benchmark execution engine
│   └── cli.py                         # CLI entrypoint
├── results/                           # Authoritative Benchmark Artifacts
│   ├── benchmark_v2_corrected/        # 240-prompt validated outputs
│   ├── benchmark_1200/                # 1200-prompt scaled outputs
│   └── ige_1000/                      # 1000-prompt generalization outputs
├── scripts/                           # Database setup & migration utilities
├── tests/                             # 184 Pytest Automated Test Suite
├── Website/                           # V2 Frontend SPA Application
│   ├── index.html                     # Studio, Analytics, History, Architecture
│   ├── evaluation.html                # Benchmark evaluation viewer
│   ├── frontend_server.py             # Dedicated frontend HTTP server (:8080)
│   └── server.py                      # Combined server entrypoint
├── prompt_ledger.db                   # Production SQLite historical database
├── start.ps1 / stop.ps1               # Master PowerShell lifecycle scripts
├── start_promptgreen.bat              # Master Windows Batch lifecycle launcher
├── stop_promptgreen.bat               # Master Windows Batch lifecycle stopper
├── requirements.txt                   # Project Python dependencies
├── setup.py                           # Setuptools package configuration
└── README.md                          # Repository documentation
```

---

## 🌍 Sustainable Development Goals (SDG) Alignment

- **SDG 13: Climate Action:** Mitigates the operational carbon footprint of generative AI and inference workloads.
- **SDG 12: Responsible Consumption & Production:** Enforces prompt token efficiency, minimizes unnecessary FLOPs, and eliminates wasteful token inflation.
- **SDG 9: Industry, Innovation & Infrastructure:** Delivers open-source, zero-budget Green AI tooling accessible to every developer without cloud vendor lock-in.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
