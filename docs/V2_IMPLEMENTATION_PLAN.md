# PROMPTGREEN v2.0 — TECHNICAL EXECUTION PLAN & ARCHITECTURAL BLUEPRINT

**Target Version:** PromptGreen v2.0 (Active Optimization & Carbon Telemetry Platform)  
**Baseline Version:** PromptGreen v1.0 (Zero-Budget Pre-Deploy Carbon Gate)  
**Reference Documents:**
1. *PromptGreen Capstone Project Thesis: Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable Large Language Model Inference* (Dayananda Sagar University, 2026)
2. *PromptGreen: Master System Architecture & Prompt Optimization Roadmap* (Enterprise Upgrade Specification)

---

## EXECUTIVE SUMMARY

This technical execution plan defines the systematic 4-day engineering roadmap to transition the active PromptGreen codebase from its current **v1.0 baseline** (a passive lexical diff reviewer and SQLite carbon calculator) into the **v2.0 enterprise platform** specified in the Capstone Project Thesis.

The core paradigm shift replaces passive prompt auditing with **active four-stage prompt compression**, separates **prefill versus autoregressive decode thermodynamics ($3.8\times$ factor)**, introduces a **semantic cosine-similarity guardrail ($\ge 0.92$)**, scales persistence to an **asynchronous dual-mode telemetry ledger**, and provides an **interactive Next.js 15 Green Prompt Studio**—all engineered to operate **CPU-first on an Intel Core i7-10610U developer machine with 32 GB RAM and zero mandatory GPU or Docker prerequisites**.

---

## 1. EXISTING COMPONENT REUSE MATRIX

To ensure rapid delivery within four days and preserve proven functionality, existing components will be reused, refactored, or extended without gratuitous rewrites.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPONENT REUSE TOPOLOGY                                  │
├──────────────────────────┬───────────────────────┬─────────────────────────────────────┤
│ Component / File Path    │ Proposed Action       │ Architectural Role in v2.0          │
├──────────────────────────┼───────────────────────┼─────────────────────────────────────┤
│ promptgreen/             │                       │                                     │
│   analysis/              │ Retain & Refactor     │ Pure input token parsing, regex     │
│   diff_parser.py         │                       │ feature extraction, and AST code    │
│                          │                       │ mask coordination.                  │
│                          │                       │                                     │
│   predictor/             │ Retain & Upgrade      │ Predicts output token inflation via │
│   hybrid_predictor.py    │                       │ ML regression + Green Model Tier    │
│                          │                       │ Router.                             │
│                          │                       │                                     │
│   engine/                │ Upgrade & Expand      │ Thermodynamic prefill/decode energy │
│   carbon_engine.py       │                       │ model, hardware TDP, PUE (1.15),    │
│                          │                       │ water footprint, net savings.       │
│                          │                       │                                     │
│   gate/                  │ Retain & Upgrade      │ Budget validation + auto-fix PR     │
│   prompt_gate.py         │                       │ Markdown comment generation.        │
│                          │                       │                                     │
│   ledger/                │ Retain & Abstract     │ Dual-mode ledger: SQLite (local) &  │
│   database.py            │                       │ PostgreSQL/TimescaleDB (enterprise).│
│                          │                       │                                     │
│   validation/            │ Retain & Expand       │ Runs 240-prompt multi-domain        │
│   benchmark.py           │                       │ benchmark suite evaluation.         │
│                          │                       │                                     │
│   api/                   │ Upgrade to Async      │ FastAPI async service exposing      │
│   server.py              │                       │ /api/v1/optimize, /telemetry, SSE.  │
│                          │                       │                                     │
│   cli.py                 │ Retain & Extend       │ CLI entrypoint: add `optimize`      │
│                          │                       │ subcommand with in-place flag.      │
│                          │                       │                                     │
│ dashboard/app.py         │ Retain as Secondary   │ Standalone Streamlit explorer for   │
│                          │                       │ local data science & offline demos. │
│                          │                       │                                     │
│ Website/index.html &     │ Retain for Fallback   │ Lightweight client-side zero-install│
│ gui_simulator.html       │                       │ fallback demonstration interfaces.  │
└──────────────────────────┴───────────────────────┴─────────────────────────────────────┘
```

### Detailed Component Analysis

#### 1. `promptgreen/analysis/diff_parser.py` (Retain & Refactor)
- **Current State:** Contains `PromptDiffAnalyzer`, 30+ regex patterns for verb complexity, few-shot counting, Chain-of-Thought (CoT) detection, format complexity, and `generate_green_alternative()`.
- **v2.0 Strategy:** Keep all regex patterns and `PromptDeltaFeatures` vectorization. Extract the heuristic string transformation logic into the new `promptgreen/optimizer/` package. Extend `diff_parser.py` with an AST-based code-block masker (`__CODE_BLOCK_i__`) to protect Python/JavaScript syntax, file paths, JSON schemas, and backtick identifiers prior to neural compression.

#### 2. `promptgreen/predictor/hybrid_predictor.py` (Retain & Upgrade)
- **Current State:** Blends rule-based output token estimation with a scikit-learn `RandomForestRegressor` trained on `data/benchmark_suite.json`.
- **v2.0 Strategy:** Retain the dual-layer architecture. Expand the feature vector to include compression ratio ($R_{\text{comp}}$) and code density. Add a **Green Model Router** module that evaluates prompt complexity after compression to recommend downgrading from frontier models (e.g., GPT-4o) to compact green models (e.g., GPT-4o-mini / Gemini Flash).

#### 3. `promptgreen/engine/carbon_engine.py` (Upgrade & Expand)
- **Current State:** Uses static per-token energy multipliers ($E_{\text{in}}, E_{\text{out}}$) without hardware differentiation or prefill/decode asymmetry.
- **v2.0 Strategy:** Upgrade the mathematical formulation to model separate prefill and decode thermodynamics:
  $$E_{\text{inf}} = \text{PUE} \times \left( T_{\text{in}} \cdot \alpha_{\text{prefill}, m} + T_{\text{out}} \cdot \alpha_{\text{decode}, m} \right)$$
  where $\alpha_{\text{decode}} \approx 3.8 \times \alpha_{\text{prefill}}$. Add Data Center PUE ($1.15$), local compressor overhead subtraction ($E_{\text{local\_opt}}$), and datacenter cooling water consumption ($\text{mL}$).

#### 4. `promptgreen/gate/prompt_gate.py` (Retain & Upgrade)
- **Current State:** Evaluates carbon delta against budget thresholds, returning `PASS`, `WARN`, or `FAIL`, and compiles Markdown reports.
- **v2.0 Strategy:** Retain budget gate logic. Upgrade `markdown_report` generation to include a GitHub-native ````suggestion``` block with the compressed prompt so developers can commit the optimization in one click on Pull Requests.

#### 5. `promptgreen/ledger/database.py` (Retain & Abstract)
- **Current State:** Synchronous SQLite database manager (`prompt_ledger.db`).
- **v2.0 Strategy:** Preserve the SQLite implementation so local development requires zero external database installation. Introduce an abstract repository interface (`LedgerRepository`) supporting both SQLite (default) and PostgreSQL/TimescaleDB (when `DATABASE_URL` is set).

#### 6. `promptgreen/validation/benchmark.py` (Retain & Expand)
- **Current State:** Evaluates 50 benchmark pairs offline.
- **v2.0 Strategy:** Retain the runner architecture. Expand dataset loading to support the full 240-prompt multi-domain enterprise benchmark (`data/benchmark_suite_240.json`), evaluating token reduction, semantic similarity retention, and net carbon abatement.

#### 7. `promptgreen/api/server.py` (Upgrade to Async)
- **Current State:** Synchronous FastAPI routes (`/api/v1/review`, `/api/v1/generate-green`, `/api/v1/ledger/*`).
- **v2.0 Strategy:** Convert all routes to `async def`. Add `POST /api/v1/optimize`, `POST /api/v1/analyze-diff`, and `GET /api/v1/telemetry`. Maintain legacy endpoints for backward compatibility.

#### 8. `promptgreen/cli.py` (Retain & Extend)
- **Current State:** Click CLI with `analyze`, `git-diff`, `benchmark`, and `ledger`.
- **v2.0 Strategy:** Retain all existing commands. Add `promptgreen optimize [PROMPT/FILE] [--mode balanced] [--in-place]` with interactive Rich terminal diff tables.

---

## 2. THESIS REQUIREMENTS BREAKDOWN

| Requirement Category | Specific Thesis Requirement | Baseline v1.0 Status | v2.0 Implementation Plan | Verification Method |
| :--- | :--- | :--- | :--- | :--- |
| **Active Optimization** | 4-Stage Prompt Optimization Pipeline achieving $\ge 40\%$ token reduction | Partially Complete (lexical regex only) | Build `promptgreen/optimizer/` combining AST Rule Pruner, LLMLingua-2, SLM Shaper, and Semantic Guard. | Unit tests across 240 benchmark prompts; token count assertion. |
| **Code Preservation** | Zero corruption of fenced code, JSON keys, AST tokens | Missing (regex strips arbitrarily) | AST and regex masking (`__CODE_BLOCK_i__`) with verbatim restoration in `rule_pruner.py`. | Python `ast.parse()` validation on all code-containing prompts. |
| **Extractive Compression** | Distilled BERT token classifier (LLMLingua-2) in $< 100\text{ ms}$ | Missing | Integrate `llmlingua` with CPU ONNX/PyTorch fallback in `compressor.py`. | Execution latency profiling ($< 80\text{ ms}$ CPU). |
| **Output Shaping** | Bound open-ended directives to reduce decode tokens by $\ge 35\%$ | Heuristic string appends | Local SLM via Ollama (`qwen2.5:1.5b`) with deterministic rule-template fallback in `output_shaper.py`. | Predicted output token reduction delta verification. |
| **Semantic Guardrail** | Cosine similarity $\ge 0.92$ with adaptive fallback relaxation | Missing | Embeddings via `sentence-transformers/all-MiniLM-L6-v2` in `semantic_guard.py`. | Cosine similarity assertion ($\ge 0.920$ on benchmark). |
| **Thermodynamic Modeling** | Prefill vs. Decode ($3.8\times$), PUE ($1.15$), net carbon subtraction | Missing (static token multiplier) | Refactor `carbon_engine.py` with physical power draw, cooling water ($\text{mL}$), and $E_{\text{local\_opt}}$ deduction. | Mathematical unit tests against published GPU energy benchmarks. |
| **Model Down-Routing** | Recommend green model tier when prompt is simplified | Missing | Add complexity evaluation & tier router in `hybrid_predictor.py`. | Tier recommendation assertions on simplified prompts. |
| **Telemetry Ledger** | Track per-prompt optimization events, compression ratios, and $\text{gCO}_2\text{e}$ | Local SQLite table `prompt_records` | Abstract `LedgerRepository` supporting SQLite and PostgreSQL/TimescaleDB. | Query verification for cumulative savings and event history. |
| **REST API** | Async endpoints: `/api/v1/optimize`, `/telemetry` | Synchronous legacy endpoints | Upgrade `server.py` to async FastAPI with Pydantic v2 schemas. | Automated FastAPI TestClient test suite. |
| **Unified UI** | Next.js 15 Green Prompt Studio with Monaco Editor and live diffs | Split (Streamlit + static HTML) | Build Next.js 15 App in `frontend/` with Monaco editor, token heatmap, and Recharts. | End-to-end browser walkthrough and API response rendering. |
| **Benchmark Suite** | 240 prompts across 4 domains (Code, RAG, Analytical, CI/CD) | 50 prompts (legacy format) | Create `data/benchmark_suite_240.json` with 60 prompts per domain. | Benchmark runner metrics: $\ge 40\%$ reduction, $\ge 0.92$ similarity. |

### Scope Boundary: Mandatory Thesis vs. Enterprise Roadmap

```
┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│     MANDATORY THESIS SCOPE (4-DAY SPRINT)    │     OPTIONAL ENTERPRISE ROADMAP (POST-THESIS)│
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ • 4-Stage Optimizer (`promptgreen/optimizer`)│ • Cloud multi-tenant VPS Kubernetes hosting  │
│ • AST code block & schema protection         │ • Dedicated external TimescaleDB cluster     │
│ • LLMLingua-2 CPU inference + ONNX fallback  │ • Celery Beat live grid webhook scheduler    │
│ • Output directive shaper + template fallback│ • VS Code Marketplace extension distribution │
│ • MiniLM-L6-v2 cosine guardrail (>= 0.92)    │ • Drop-in `GreenOpenAI` production SDK      │
│ • Prefill vs Decode thermodynamics (3.8x)    │ • Live multi-provider LiteLLM API billing    │
│ • Net carbon savings & water footprint math  │ • Multi-tenant organization RBAC auth        │
│ • Green Model Tier Recommender               │                                              │
│ • Async FastAPI service + SQLite/Postgres    │                                              │
│ • Next.js 15 Green Prompt Studio             │                                              │
│ • 240-prompt benchmark dataset validation    │                                              │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

---

## 3. FOUR-STAGE OPTIMIZATION ARCHITECTURE

The core innovation of PromptGreen v2.0 is the dedicated active optimization package housed in `promptgreen/optimizer/`.

```
                                      Raw User Prompt
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Structural & Rule-Based Pruner (`rule_pruner.py`)                                 │
│ • Unicode NFC normalization & whitespace collapsing                                        │
│ • Strip conversational pleasantries ("Could you please kindly...")                         │
│ • AST parsing: detect Python/JS code fences (```...```), JSON schemas, inline backticks    │
│ • Replace protected segments with immutable placeholders (`__CODE_BLOCK_0__`)              │
└────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                             │ Masked Natural-Language Text
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Extractive Token Compression (`compressor.py`)                                    │
│ • Microsoft LLMLingua-2 BERT token classifier                                              │
│ • Mode-specific retention rates: Conservative (0.75), Balanced (0.55), Aggressive (0.40)   │
│ • `force_tokens` locks `__CODE_BLOCK_i__` tokens from deletion                             │
│ • Fallback: Information-density lexical pruner if PyTorch/BERT is unavailable              │
└────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                             │ Compressed Text
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Abstractive Output Shaping (`output_shaper.py`)                                   │
│ • Detect unbounded generation directives ("explain in detail", "write an essay")          │
│ • Primary: Local quantized SLM via Ollama (`qwen2.5:1.5b` or `llama3.2:1b`)                │
│ • Fallback: Deterministic bound templates ("Max 100 words; bullet points only")            │
│ • Slashing high-energy autoregressive decode tokens by 35%–60%                             │
└────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                             │ Candidate Prompt (Unmasked)
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Semantic Fidelity Guardrail (`semantic_guard.py`)                                 │
│ • Generate dense vector embeddings via `all-MiniLM-L6-v2` (384-dimensional)               │
│ • Compute Cosine Similarity $S_{\text{cos}}(P_{\text{orig}}, P_{\text{cand}})$             │
│ • Threshold Gate: Is $S_{\text{cos}} \ge \theta_{\text{min}}$ (default 0.92)?              │
│   ├── YES ──> Accept optimized prompt, record telemetry, and return.                       │
│   └── NO  ──> ADAPTIVE FALLBACK LOOP:                                                      │
│               Relax retention rate ($\tau: 0.40 \rightarrow 0.60 \rightarrow 0.80$).       │
│               If still breached, revert cleanly to Stage 1 output ($S_{\text{cos}} = 0.988)│
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Module Specifications

#### 1. `promptgreen/optimizer/rule_pruner.py`
- **Class:** `RuleAndASTPruner`
- **Public Methods:**
  ```python
  def prune_and_mask(self, raw_prompt: str) -> Tuple[str, Dict[str, str]]:
      """Strips polite boilerplate, extracts code/JSON blocks into placeholders,

      returns (masked_text, placeholder_map)."""
  def restore_masks(self, text: str, placeholder_map: Dict[str, str]) -> str:
      """Restores protected code/JSON blocks verbatim from placeholder map."""
  ```
- **Syntax Protection Mechanism:** Uses regex matching for fenced blocks (```` ```...``` ````), JSON structures (`{...}` with key-value pairs), and inline backticks. When code is identified as Python, passes the snippet to `ast.parse()` to guarantee syntax validity before masking.

#### 2. `promptgreen/optimizer/compressor.py`
- **Class:** `PromptCompressor`
- **Public Methods:**
  ```python
  def compress(self, masked_text: str, target_rate: float = 0.55, force_tokens: Optional[List[str]] = None) -> str:
      """Compresses natural-language prose using LLMLingua-2 while preserving forced tokens."""
  ```
- **CPU Fallback:** If `llmlingua` cannot load or model weights are missing, activates a vectorized TF-IDF / stop-word heuristic classifier that prunes low-entropy natural-language tokens without altering placeholder keys.

#### 3. `promptgreen/optimizer/output_shaper.py`
- **Class:** `OutputDirectiveShaper`
- **Public Methods:**
  ```python
  def shape_directives(self, prompt: str, task_hint: Optional[str] = None) -> str:
      """Detects unconstrained generation phrases and appends structural length bounds."""
  ```
- **Dual Engine:**
  - *Primary:* Calls Ollama REST API (`http://localhost:11434/api/generate`) with `qwen2.5:1.5b` if reachable.
  - *Fallback:* Deterministic directive injection mapping open-ended request patterns to concise boundaries (e.g., `"explain how"` $\rightarrow$ `"summarize key points, max 150 words"`).

#### 4. `promptgreen/optimizer/semantic_guard.py`
- **Class:** `SemanticFidelityGuard`
- **Public Methods:**
  ```python
  def compute_similarity(self, text_a: str, text_b: str) -> float:
      """Computes L2-normalized cosine similarity between two prompt texts."""
  def verify_guardrail(self, original: str, candidate: str, threshold: float = 0.92) -> Tuple[bool, float]:
      """Returns (passed_guard, similarity_score)."""
  ```
- **Dual Engine:**
  - *Primary:* `sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2")`.
  - *Fallback:* Scikit-learn character n-gram / TF-IDF cosine similarity with adjusted threshold calibration.

#### 5. `promptgreen/optimizer/pipeline.py`
- **Class:** `PromptGreenOptimizer`
- **Public Interface:**
  ```python
  @dataclass
  class OptimizationResult:
      original_prompt: str
      optimized_prompt: str
      input_tokens_original: int
      input_tokens_optimized: int
      input_token_reduction_pct: float
      estimated_output_tokens_original: float
      estimated_output_tokens_optimized: float
      output_token_reduction_pct: float
      semantic_similarity: float
      guardrail_passed: bool
      stage_used: str  # "stage_2_llmlingua", "stage_4_fallback", "stage_1_rules"
      latency_ms: float

  def optimize(self, raw_prompt: str, mode: str = "balanced") -> OptimizationResult:
      """Orchestrates 4-stage optimization with adaptive fallback relaxation."""
  ```

---

## 4. CARBON ENGINE AND GREEN MODEL ROUTING

### Thermodynamic Prefill vs. Decode Physics

In transformer architectures, input prompt processing (prefill) is compute-bound and executed in parallel across matrix cores, whereas token generation (decode) is memory-bandwidth bound and executed sequentially. Consequently, **each generated output token consumes $3.5\times$ to $4.5\times$ more electrical energy than an ingested input token**.

PromptGreen v2.0 formalizes this asymmetry using empirical benchmark profiles from Samsi et al. (2023) and Patterson et al. (2021):

$$\alpha_{\text{decode}, m} = 3.8 \times \alpha_{\text{prefill}, m}$$

### Mathematical Equations

#### 1. Single Inference Energy ($E_{\text{inf}}$ in Watt-hours)
$$E_{\text{inf}}(T_{\text{in}}, T_{\text{out}}, m) = \text{PUE} \times \left( \frac{T_{\text{in}} \cdot \alpha_{\text{prefill}, m} + T_{\text{out}} \cdot \alpha_{\text{decode}, m}}{1000} \right)$$
where $\text{PUE} = 1.15$ (standard modern hyperscale data center efficiency) and $\alpha$ is in $\text{mWh/token}$.

#### 2. Net Environmental Carbon Abatement ($\Delta C_{\text{net}}$ in $\text{gCO}_2\text{e}$)
$$\Delta C_{\text{net}} = \left[ \frac{(E_{\text{inf, orig}} - E_{\text{inf, opt}} - E_{\text{local\_opt}})}{1000} \right] \times I_{\text{grid}}$$
where:
- $E_{\text{local\_opt}}$ represents the measured energy consumed by running the PromptGreen optimizer locally ($\approx 0.0018\text{ Wh}$ on CPU).
- $I_{\text{grid}}$ is the regional electrical grid carbon intensity in $\text{gCO}_2\text{e/kWh}$.

#### 3. Datacenter Water Consumption Savings ($W_{\text{saved}}$ in milliliters)
$$W_{\text{saved}} = \Delta E_{\text{net}} \times \text{WUE}$$
where $\text{WUE} = 1.8\text{ L/kWh} = 1.8\text{ mL/Wh}$ (Water Usage Effectiveness).

### Hardware Profiles (`promptgreen/engine/hardware_profiles.json`)

```json
{
  "hardware_configurations": {
    "h100_pcie": { "name": "NVIDIA H100 PCIe", "tdp_watts": 700, "memory_gb": 80, "cooling_type": "air/liquid" },
    "a100_sxm4": { "name": "NVIDIA A100 SXM4", "tdp_watts": 400, "memory_gb": 80, "cooling_type": "liquid" },
    "l4_pcie":   { "name": "NVIDIA L4 PCIe",   "tdp_watts": 72,  "memory_gb": 24, "cooling_type": "air" }
  },
  "model_energy_coefficients": {
    "frontier_dense": {
      "display_name": "GPT-4o / Claude 3.5 Sonnet Class",
      "hardware": "h100_pcie",
      "alpha_prefill_mwh": 0.42,
      "alpha_decode_mwh": 1.60
    },
    "large_reasoning": {
      "display_name": "Llama-3 70B / Qwen-2.5 72B Class",
      "hardware": "a100_sxm4",
      "alpha_prefill_mwh": 0.35,
      "alpha_decode_mwh": 1.35
    },
    "mid_tier": {
      "display_name": "Mixtral 8x7B / Command-R Class",
      "hardware": "a100_sxm4",
      "alpha_prefill_mwh": 0.24,
      "alpha_decode_mwh": 0.92
    },
    "compact_green": {
      "display_name": "Llama-3.2 3B / Phi-3.5 3.8B / Mini Class",
      "hardware": "l4_pcie",
      "alpha_prefill_mwh": 0.04,
      "alpha_decode_mwh": 0.15
    }
  }
}
```

### Green Model Down-Routing Engine

When a verbose prompt is compressed, its structural complexity drops significantly. The **Green Model Router** in `promptgreen/predictor/hybrid_predictor.py` assesses three post-compression features:
1. **Token Length:** Does $T_{\text{in, opt}} \le 250$ tokens?
2. **Code Density:** Is code token fraction $< 0.15$?
3. **Reasoning Requirement:** Is Chain-of-Thought absent ($CoT = \text{False}$)?

If all conditions hold, the router outputs a formal recommendation:
> *"Prompt complexity is low. Down-routing from Frontier Dense (GPT-4o) to Compact Green (GPT-4o-mini / Gemini Flash) is recommended, yielding an additional $12.4\times$ carbon reduction."*

---

## 5. BACKEND AND DATABASE ARCHITECTURE

### Minimum Architecture vs. Enterprise Scaling

To satisfy the thesis without introducing unexecutable dependencies on a local machine lacking Docker, PromptGreen v2.0 implements a **dual-engine persistence and task management architecture**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               BACKEND PERSISTENCE STRATEGY                             │
├──────────────────────────┬──────────────────────────────┬──────────────────────────────┤
│ Operational Mode         │ Local Development / Thesis   │ Enterprise Production        │
├──────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ Database Technology      │ SQLite (WAL mode, async)     │ PostgreSQL 16 + TimescaleDB  │
│ Configuration Trigger    │ Default (`DATABASE_URL=""`)  │ `DATABASE_URL="postgresql.."`│
│ Concurrency Handling     │ WAL mode + connection pool   │ TimescaleDB connection pool  │
│ Time-Series Hypertable   │ Filtered SQLite timestamp index│ TimescaleDB hypertable      │
│ Async Task Execution     │ Python `asyncio.create_task` │ Celery 5 + Redis 7 broker    │
│ External Daemon Required │ **None (Zero install)**      │ Docker Compose daemon        │
└──────────────────────────┴──────────────────────────────┴──────────────────────────────┘
```

### Abstract Repository Interface (`promptgreen/ledger/database.py`)

```python
class LedgerRepository(ABC):
    @abstractmethod
    async def record_optimization(self, record: OptimizationRecord) -> int: ...
    @abstractmethod
    async def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]: ...
    @abstractmethod
    async def get_telemetry_summary(self) -> Dict[str, Any]: ...
    @abstractmethod
    async def get_model_savings_breakdown(self) -> List[Dict[str, Any]]: ...
```

### Core API Endpoints (`promptgreen/api/server.py`)

1. **`POST /api/v1/optimize`**
   - *Input:* `{ "prompt": str, "model": str, "mode": "conservative"|"balanced"|"aggressive", "target_similarity": float }`
   - *Output:* `{ "original_prompt": str, "optimized_prompt": str, "token_reduction_pct": float, "semantic_similarity": float, "net_carbon_saved_gco2": float, "water_saved_ml": float, "model_routing_recommendation": str }`
   - *Latency:* $< 100\text{ ms}$ on CPU.
2. **`POST /api/v1/analyze-diff`**
   - *Input:* `{ "old_prompt": str, "new_prompt": str, "model": str, "region": str }`
   - *Output:* Full carbon delta breakdown, prefill/decode split, and gate verdict (`PASS`/`WARN`/`FAIL`).
3. **`GET /api/v1/telemetry/summary`**
   - *Output:* Cumulative prompt reviews, total tokens pruned, net $\text{gCO}_2\text{e}$ prevented, smartphone charges equivalent.
4. **`GET /api/v1/ledger/records`**
   - *Output:* Paginated list of optimization events with before/after token metrics and similarity scores.

---

## 6. FRONTEND: NEXT.JS 15 "GREEN PROMPT STUDIO"

The v2.0 frontend consolidates the fragmented Streamlit, HTML, and simulator views into a single, high-performance web platform built with **Next.js 15, TypeScript, Tailwind CSS, Monaco Editor, and Recharts**.

```
frontend/
├── app/
│   ├── layout.tsx                     # Root layout with dark mode & navigation
│   ├── page.tsx                       # Interactive Green Prompt Studio
│   └── analytics/
│       └── page.tsx                   # Enterprise Carbon Telemetry Dashboard
├── components/
│   ├── studio/
│   │   ├── PromptEditor.tsx           # Monaco Editor with live token-energy heatmap
│   │   ├── DiffViewer.tsx             # Side-by-side synchronized prompt diff
│   │   ├── CompressionDial.tsx        # Conservative / Balanced / Aggressive mode selector
│   │   ├── FidelityGauge.tsx          # Real-time circular SVG semantic fidelity score
│   │   └── ImpactCards.tsx            # Tokens, Energy, Carbon, Water savings cards
│   ├── analytics/
│   │   ├── SavingsTrendChart.tsx      # Recharts cumulative carbon reduction over time
│   │   ├── ModelMatrixTable.tsx       # Comparative energy savings across model tiers
│   │   └── Leaderboard.tsx            # Team-by-team sustainability rankings
│   └── ui/                            # Reusable Radix / Tailwind primitives (Buttons, Badges)
├── lib/
│   ├── api.ts                         # Typed API client for FastAPI endpoints
│   └── types.ts                       # Shared TypeScript interfaces
├── package.json
└── tailwind.config.js
```

### Key UI Features

1. **Interactive Prompt Studio (`app/page.tsx`):**
   - Split-screen workspace. In the left Monaco editor pane, developers paste raw prompts. As they type, a real-time token badge updates instantly.
   - Top control bar allows instant toggling between **Conservative ($\tau=0.75$)**, **Balanced ($\tau=0.55$)**, and **Aggressive ($\tau=0.40$)** presets.
   - Clicking **"Optimize Prompt"** executes `POST /api/v1/optimize`.
   - In the right pane, the optimized prompt renders with highlighted deletions/insertions alongside a one-click **"Copy Optimized Prompt"** button.
2. **Real-Time Visual Indicators:**
   - **Fidelity Gauge:** Color-coded circular score ($0.0 - 1.0$) with green ($\ge 0.92$), amber ($0.88 - 0.91$), and red ($< 0.88$).
   - **Live Impact Cards:** Displays Input Tokens Saved ($\Delta T_{\text{in}}$), Output Tokens Shaped ($\Delta T_{\text{out}}$), Net Watt-Hours Conserved ($\text{mWh}$), and Net $\text{gCO}_2\text{e}$ Prevented.
   - **Green Model Router Badge:** Displays recommended tier downgrade with instant potential savings calculation.

---

## 7. CPU-FIRST EXECUTION & HARDWARE OPTIMIZATION

### Target Machine Constraints
- **Processor:** Intel Core i7-10610U (4 Cores, 8 Threads, 1.8 GHz base, up to 4.9 GHz boost).
- **RAM:** 32 GB DDR4.
- **GPU:** Intel UHD Graphics (integrated, non-CUDA).
- **Storage:** NVMe SSD.

### Memory & Latency Profiling on CPU

```
┌───────────────────────────┬──────────────┬───────────────┬─────────────────────────────┐
│ Component / Model         │ Memory (RAM) │ CPU Latency   │ Optimization Mechanism      │
├───────────────────────────┼──────────────┼───────────────┼─────────────────────────────┤
│ Stage 1: Rule & AST Pruner│ < 10 MB      │ 2 – 4 ms      │ Python compiled regex & ast │
│ Stage 2: LLMLingua-2 BERT │ ~450 MB      │ 55 – 80 ms    │ PyTorch CPU (4 threads)     │
│ Stage 3: Ollama SLM (Qwen)│ ~1.2 GB      │ 200 – 400 ms  │ 4-bit quantization (Q4_K_M) │
│ Stage 3 Fallback: Template│ < 5 MB       │ 1 – 2 ms      │ Deterministic rule bounds   │
│ Stage 4: all-MiniLM-L6-v2 │ ~85 MB       │ 8 – 15 ms     │ ONNX Runtime / PyTorch CPU  │
├───────────────────────────┼──────────────┼───────────────┼─────────────────────────────┤
│ Total Pipeline Execution  │ ~1.75 GB     │ 70 – 110 ms*  │ *With template SLM fallback │
└───────────────────────────┴──────────────┴───────────────┴─────────────────────────────┘
```

### Deterministic CPU Fallback Safeguards
To ensure PromptGreen **never crashes or hangs indefinitely** on a machine without a dedicated GPU or running Ollama daemon:
1. **PyTorch Thread Tuning:** Initialize `torch.set_num_threads(4)` at startup to prevent core oversubscription and CPU thrashing.
2. **Ollama Service Healthcheck:** `output_shaper.py` sends a fast HTTP GET to `http://localhost:11434/api/tags` with a 200ms timeout. If Ollama is not active, it transparently applies deterministic output-bounding directive templates without throwing exceptions.
3. **Sentence-Transformers Fallback:** If `sentence-transformers` is unavailable or model download fails due to network isolation, `semantic_guard.py` automatically falls back to an internal scikit-learn TF-IDF / character n-gram cosine similarity model calibrated to match dense vector scores.

---

## 8. DEPENDENCY AND INTEGRATION MAP

### Component Integration Contracts

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM INTEGRATION GRAPH                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   [Next.js Studio / CLI / CI Gate]                                                     │
│                  │                                                                     │
│                  ▼  POST {prompt, model, mode}                                         │
│        [FastAPI Gateway (server.py)]                                                   │
│                  │                                                                     │
│                  ├───────────────► [PromptGreenOptimizer (pipeline.py)]                │
│                  │                            │                                        │
│                  │                            ├──► [RuleAndASTPruner]                  │
│                  │                            ├──► [PromptCompressor]                  │
│                  │                            ├──► [OutputDirectiveShaper]             │
│                  │                            └──► [SemanticFidelityGuard]             │
│                  │                                                                     │
│                  ├───────────────► [CarbonEngine (carbon_engine.py)]                   │
│                  │                            │                                        │
│                  │                            ├──► Reads hardware_profiles.json        │
│                  │                            └──► Calculates Net Carbon & Water Saved │
│                  │                                                                     │
│                  ├───────────────► [GreenModelRouter (hybrid_predictor.py)]            │
│                  │                            │                                        │
│                  │                            └──► Evaluates tier downgrade potential  │
│                  │                                                                     │
│                  └───────────────► [LedgerRepository (database.py)]                    │
│                                               │                                        │
│                                               └──► Asynchronously writes telemetry     │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Transfer Objects (DTO)

```python
@dataclass
class OptimizationRequestDTO:
    prompt: str
    model: str = "llama-3-8b"
    mode: str = "balanced"  # "conservative", "balanced", "aggressive"
    target_similarity: float = 0.92
    region: str = "US"
    monthly_volume: int = 10000

@dataclass
class OptimizationResponseDTO:
    original_prompt: str
    optimized_prompt: str
    input_tokens_orig: int
    input_tokens_opt: int
    input_token_reduction_pct: float
    output_tokens_orig: float
    output_tokens_opt: float
    output_token_reduction_pct: float
    semantic_similarity: float
    guardrail_passed: bool
    net_carbon_saved_gco2_1k: float
    net_monthly_carbon_saved_kg: float
    net_water_saved_ml_1k: float
    energy_delta_mwh: float
    recommended_model_tier: Optional[str]
    optimization_latency_ms: float
```

---

## 9. FOUR-DAY EXECUTION SCHEDULE

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              4-DAY SPRINT ROADMAP                                      │
├─────────┬───────────────────────────────────┬──────────────────────────────────────────┤
│ Day     │ Focus Area                        │ Primary Deliverables                     │
├─────────┼───────────────────────────────────┼──────────────────────────────────────────┤
│ Day 1   │ 4-Stage Active Optimization Core  │ `promptgreen/optimizer/` package & unit  │
│         │ & Semantic Guardrail              │ tests (Pruner, LLMLingua-2, Guard).      │
├─────────┼───────────────────────────────────┼──────────────────────────────────────────┤
│ Day 2   │ Thermodynamic Carbon Physics,     │ Refactored `carbon_engine.py`, hardware  │
│         │ Hardware Profiles & Model Routing │ profiles, Green Model Router.            │
├─────────┼───────────────────────────────────┼──────────────────────────────────────────┤
│ Day 3   │ Async Backend, Dual-Mode Ledger   │ Async FastAPI routes, SQLite WAL ledger, │
│         │ & 240-Prompt Benchmark Suite      │ `benchmark_suite_240.json` validation.   │
├─────────┼───────────────────────────────────┼──────────────────────────────────────────┤
│ Day 4   │ Next.js 15 Green Prompt Studio    │ Full Next.js web application with Monaco │
│         │ & End-to-End System Verification  │ Editor, diffs, charts, and test report.  │
└─────────┴───────────────────────────────────┴──────────────────────────────────────────┘
```

### Day 1: 4-Stage Active Prompt Optimization Core

- **Goals:** Build the complete active optimization pipeline in `promptgreen/optimizer/` with code protection, extractive pruning, output shaping, and semantic fidelity verification.
- **Files to Create:**
  - `promptgreen/optimizer/__init__.py`
  - `promptgreen/optimizer/rule_pruner.py`
  - `promptgreen/optimizer/compressor.py`
  - `promptgreen/optimizer/output_shaper.py`
  - `promptgreen/optimizer/semantic_guard.py`
  - `promptgreen/optimizer/pipeline.py`
  - `tests/test_optimizer.py`
- **Files to Modify:**
  - `promptgreen/analysis/diff_parser.py` (integrate AST code masking helper)
- **Key Deliverables:** Working `PromptGreenOptimizer.optimize()` function achieving $\ge 40\%$ token reduction and $\ge 0.92$ cosine similarity on sample prompts.
- **Verification Tests:**
  - `test_ast_code_preservation`: Verifies fenced Python/JS blocks and JSON keys are not corrupted.
  - `test_semantic_guard_fallback`: Simulates aggressive over-pruning and verifies automatic relaxation fallback to $\ge 0.92$.
  - `test_cpu_latency`: Verifies total optimization latency $< 100\text{ ms}$ on CPU.

### Day 2: Thermodynamic Carbon Physics, Hardware Profiles & Model Routing

- **Goals:** Upgrade `carbon_engine.py` to calculate prefill vs. decode energy separation ($3.8\times$), PUE ($1.15$), hardware TDP ratings, cooling water, and green model down-routing.
- **Files to Create:**
  - `promptgreen/engine/hardware_profiles.json`
  - `tests/test_carbon_physics.py`
- **Files to Modify:**
  - `promptgreen/engine/carbon_engine.py` (implement prefill/decode formula, net carbon subtraction, and water savings)
  - `promptgreen/predictor/hybrid_predictor.py` (implement `GreenModelRouter`)
- **Key Deliverables:** Physic-backed carbon engine outputting net carbon abatement ($\Delta C_{\text{net}}$), datacenter water conserved ($\text{mL}$), and model down-routing recommendations.
- **Verification Tests:**
  - `test_prefill_vs_decode_ratio`: Verifies decode token energy is $3.8\times$ prefill token energy.
  - `test_net_carbon_savings`: Verifies compressor overhead ($E_{\text{local\_opt}}$) is subtracted from gross savings.
  - `test_green_model_router`: Verifies low-complexity prompts trigger recommendations to compact model tiers.

### Day 3: Asynchronous Backend, Dual-Mode Ledger & 240-Prompt Benchmark

- **Goals:** Upgrade FastAPI to asynchronous endpoints, implement abstract dual-mode ledger (SQLite default + PostgreSQL optional), upgrade CLI, and create the 240-prompt benchmark dataset.
- **Files to Create:**
  - `data/benchmark_suite_240.json` (240 enterprise prompts across Code, RAG, Analytical, CI/CD)
  - `tests/test_api_v2.py`
  - `tests/test_benchmark_240.py`
- **Files to Modify:**
  - `promptgreen/api/server.py` (convert to `async def`, add `/api/v1/optimize`, `/telemetry`)
  - `promptgreen/ledger/database.py` (add `OptimizationRecord` schema and async WAL-mode connection)
  - `promptgreen/cli.py` (add `promptgreen optimize` command with terminal diff table)
  - `promptgreen/validation/benchmark.py` (support 240-prompt suite)
- **Key Deliverables:** Fully functional async REST API, enhanced CLI, and verified benchmark runner reporting $\ge 40\%$ token reduction and $\ge 0.92$ similarity across all 240 prompts.
- **Verification Tests:**
  - `test_api_optimize_endpoint`: FastAPI test client verifies valid JSON response with all telemetry fields.
  - `test_benchmark_240_suite`: Runs runner against 240 pairs and asserts target metrics.

### Day 4: Next.js 15 Green Prompt Studio & End-to-End System Verification

- **Goals:** Scaffold and implement the Next.js 15 Green Prompt Studio in `frontend/`, connect to FastAPI backend, run end-to-end integration tests, and produce the final verification report.
- **Files to Create:**
  - `frontend/package.json`
  - `frontend/tsconfig.json`
  - `frontend/tailwind.config.js`
  - `frontend/app/layout.tsx`
  - `frontend/app/page.tsx` (Studio interface with Monaco editor)
  - `frontend/components/studio/PromptEditor.tsx`
  - `frontend/components/studio/DiffViewer.tsx`
  - `frontend/components/studio/FidelityGauge.tsx`
  - `frontend/components/studio/ImpactCards.tsx`
  - `frontend/lib/api.ts`
- **Files to Modify:**
  - `action.yml` & `.github/workflows/promptgreen_gate.yml` (update documentation and CLI invocations)
- **Key Deliverables:** Running Next.js application communicating seamlessly with the FastAPI backend, verified by end-to-end testing.
- **Verification Tests:**
  - Full project test suite execution: `python -m pytest -p no:langsmith -v`
  - Full engine verification run: `python verify_engine.py`
  - Frontend production build verification: `npm run build` inside `frontend/`

---

## 10. COMPLETION CRITERIA & SUCCESS METRICS

The v2.0 upgrade will be declared complete when all of the following empirical criteria are satisfied:

1. **Active Optimization Performance:**
   - Mean Input Token Reduction across 240 benchmark prompts: $\ge 40.0\%$ (Target: $\sim 48.6\%$).
   - Output Directive Token Reduction: $\ge 35.0\%$ (Target: $\sim 41.2\%$).
   - Mean Semantic Cosine Similarity: $\ge 0.920$ (Target: $\sim 0.946$).
   - Code Syntax Validity: $100\%$ preservation of executable code in fenced blocks.
2. **Computational Latency on CPU:**
   - Total 4-stage optimization latency on Intel Core i7-10610U: $\le 100\text{ ms}$ (median).
3. **Thermodynamic Fidelity:**
   - Decode-to-prefill energy ratio calibrated to $3.8\times$.
   - Net carbon savings strictly subtracts local compressor energy ($E_{\text{local\_opt}}$).
4. **Backend & Test Suite Integrity:**
   - All legacy unit tests in `tests/test_all.py` continue to pass ($8/8$).
   - All new test suites (`test_optimizer.py`, `test_carbon_physics.py`, `test_api_v2.py`, `test_benchmark_240.py`) pass $100\%$.
   - FastAPI `/api/v1/optimize` endpoint returns HTTP 200 with valid telemetry payload in $< 100\text{ ms}$.
5. **Next.js Studio Functionality:**
   - Studio loads in browser without console errors.
   - User prompt input produces live diffs, fidelity gauge animation, and impact metric card updates upon clicking "Optimize".

---

*This document serves as the formal technical blueprint for PromptGreen v2.0 development. Implementation will proceed strictly according to this schedule upon approval.*
