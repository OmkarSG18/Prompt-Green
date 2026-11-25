# PROMPTGREEN V2 — DATABASE MODERNIZATION REPORT
## Dual-Engine Telemetry Persistence: PostgreSQL / TimescaleDB & SQLite Fallback

**Project:** PromptGreen V2 — Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment  
**Document Version:** 1.0.0  
**Date:** November 24, 2026  
**Status:** COMPLETE, AUDITED & VERIFIED  
**Repository Branch:** `version-2`  
**Execution Environment:** Intel Core i7-10610U CPU (4 cores / 8 threads @ 1.80GHz–4.90GHz), 32 GB RAM, Windows 11, Python 3.11.9, SQLAlchemy 2.1.6, psycopg2 2.9.13 (CPU-first, zero-budget)  
**Deliverable ID:** R4 / Phase 4 of Master Implementation Roadmap  

---

## 1. Executive Summary

Phase 4 of PromptGreen V2 establishes an enterprise-grade **dual-engine telemetry persistence layer** (`promptgreen/ledger/database.py`), transitioning PromptGreen from a standalone single-file SQLite database to a horizontally scalable, time-series-optimized PostgreSQL and TimescaleDB architecture, while maintaining **100% backward compatibility** and zero-budget offline resilience.

Key architectural achievements in Phase 4:
1. **Preservation Invariant Met:** All 448 historical prompt records in `prompt_ledger.db` remain completely intact with zero data loss or schema corruption.
2. **Dual-Engine Architecture:** The persistence manager dynamically detects `DATABASE_URL` / `POSTGRES_URL`. If a PostgreSQL/TimescaleDB cluster is reachable, it automatically configures connection pooling, creates production tables, and provisions TimescaleDB hypertables. If PostgreSQL is offline, unconfigured, or unreachable, it degrades gracefully to local SQLite without throwing fatal exceptions.
3. **TimescaleDB Continuous Aggregates:** Defined hypertable chunking (7-day intervals on `timestamp`), specialized composite indexes, automated chunk compression policies (14-day threshold), and a real-time continuous aggregate materialized view (`hourly_savings_summary`).
4. **Unified Telemetry Entity (`OptimizationEvent`):** Implemented an extended time-series entity capturing prefill/decode energy ($J$), abated carbon ($gCO_2e$), water savings ($ml$), stage latencies, routing decisions, and deep JSON stage/token breakdowns.
5. **Migration Tooling:** Delivered declarative SQL DDL (`scripts/init_timescaledb.sql`) and an automated migration utility (`scripts/migrate_sqlite_to_timescale.py`) supporting dry-run validation and live batch migration.
6. **REST API Telemetry Extensions:** Added dedicated endpoints `/api/v2/telemetry/events`, `/api/v2/telemetry/time-series`, `/api/v2/telemetry/stats`, and `/api/v2/telemetry/status` to the FastAPI backend.
7. **Automated Verification:** Authored unit and regression tests in `tests/test_database_modernization.py` covering schema creation, record writing, time-series aggregation, and offline fallback mechanics (100% pass rate).

---

## 2. Schema Architecture & Data Models

### 2.1 Legacy & Compatibility Table: `prompt_records`
To guarantee that existing V1 and V2 command-center interfaces, CLI tools, and historical evaluation scripts continue functioning seamlessly, `prompt_records` is retained across both SQLite and PostgreSQL backends:

```sql
CREATE TABLE IF NOT EXISTS prompt_records (
    id SERIAL,
    commit_hash TEXT,
    author TEXT,
    team TEXT,
    model_name TEXT,
    region TEXT,
    old_prompt TEXT,
    new_prompt TEXT,
    input_token_delta INTEGER,
    predicted_output_token_delta DOUBLE PRECISION,
    carbon_delta_gco2_1k DOUBLE PRECISION,
    monthly_carbon_delta_gco2 DOUBLE PRECISION,
    status TEXT,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    opt_mode TEXT DEFAULT 'BALANCED',
    semantic_score DOUBLE PRECISION DEFAULT 1.0,
    net_energy_wh DOUBLE PRECISION DEFAULT 0.0,
    net_carbon_g DOUBLE PRECISION DEFAULT 0.0,
    water_saved_ml DOUBLE PRECISION DEFAULT 0.0,
    routing_outcome TEXT DEFAULT 'KEEP_CURRENT_MODEL',
    recommended_tier TEXT DEFAULT 'mid_tier',
    latency_ms DOUBLE PRECISION DEFAULT 0.0,
    PRIMARY KEY (id, timestamp)
);
```

### 2.2 Modern Time-Series Entity: `optimization_events`
The primary telemetry entity captures granular scientific measurements per prompt optimization request:

| Field | Type | Description |
|---|---|---|
| `event_id` | `VARCHAR(64)` | Unique optimization request identifier (UUIDv4 + timestamp) |
| `timestamp` | `TIMESTAMPTZ` | Partitioning key for TimescaleDB hypertable |
| `prompt_category` | `VARCHAR(64)` | Task classification (e.g., coding, extraction, reasoning) |
| `author` / `team` | `VARCHAR(64)` | Multi-tenant attribution metadata |
| `model_name` | `VARCHAR(64)` | Target model tier identifier |
| `region` | `VARCHAR(64)` | Power grid scenario (e.g., ILLUSTRATIVE_385, US_CLEAN_100) |
| `original_text` | `TEXT` | Uncompressed input prompt |
| `optimized_text` | `TEXT` | Prompt output after multi-stage optimization |
| `original_tokens` | `INTEGER` | Token count before optimization |
| `optimized_tokens` | `INTEGER` | Effective token count after optimization |
| `tokens_saved` | `INTEGER` | Net token reduction ($\Delta = T_{\text{orig}} - T_{\text{opt}}$) |
| `compression_ratio` | `REAL / DOUBLE` | Extractive compression ratio ($T_{\text{opt}} / T_{\text{orig}}$) |
| `semantic_similarity` | `REAL / DOUBLE` | Embedding cosine similarity verified by MiniLM |
| `optimization_latency_ms` | `REAL / DOUBLE` | End-to-end pipeline execution time |
| `pipeline_stages_applied`| `VARCHAR(128)`| Active stages executed (e.g., `stage1,stage2,stage3,stage4`) |
| `routing_decision` | `VARCHAR(64)` | Green Model Router recommendation |
| `recommended_tier` | `VARCHAR(64)` | Recommended model tier |
| `modeled_prefill_energy_j` | `REAL / DOUBLE` | Modeled GPU prefill energy consumption ($J$) |
| `modeled_decode_energy_j` | `REAL / DOUBLE` | Modeled GPU decode energy consumption ($J$) |
| `modeled_total_energy_j` | `REAL / DOUBLE` | Sum of prefill and decode energy ($J$) |
| `modeled_carbon_gco2e` | `REAL / DOUBLE` | Net abated greenhouse gas emissions ($gCO_2e$) |
| `water_saved_ml` | `REAL / DOUBLE` | Modeled datacenter cooling water reduction ($ml$) |
| `grid_carbon_intensity` | `REAL / DOUBLE` | Carbon intensity factor ($gCO_2 / kWh$) |
| `status` | `VARCHAR(16)` | Gate review status (`PASS`, `WARN`, `FAIL`) |
| `stage_breakdown` | `JSONB / TEXT` | JSON object containing per-stage latencies and actions |
| `token_breakdown` | `JSONB / TEXT` | JSON object containing token delta diagnostics |

---

## 3. TimescaleDB Features & Optimizations

In `scripts/init_timescaledb.sql`, TimescaleDB extensions are configured for high-throughput carbon telemetry:

1. **Hypertable Chunking:**
   ```sql
   SELECT create_hypertable('optimization_events', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
   ```
   Partitioning into 7-day chunks ensures that memory-resident B-Trees remain small and fit into RAM during high-frequency telemetry writes.

2. **Continuous Aggregation Materialized View:**
   ```sql
   CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_savings_summary
   WITH (timescaledb.continuous) AS
   SELECT time_bucket('1 hour', timestamp) AS bucket,
          prompt_category,
          COUNT(*) AS total_optimizations,
          SUM(tokens_saved) AS total_tokens_saved,
          SUM(modeled_total_energy_j) AS total_energy_saved_j,
          SUM(modeled_carbon_gco2e) AS total_carbon_saved_gco2e,
          AVG(compression_ratio) AS avg_compression_ratio,
          AVG(semantic_similarity) AS avg_semantic_similarity,
          AVG(optimization_latency_ms) AS avg_latency_ms
   FROM optimization_events
   GROUP BY bucket, prompt_category
   WITH NO DATA;
   ```
   Pre-computes hourly summaries continuously in the background, transforming costly analytics scans into instantaneous lookups for the Green Prompt Studio.

3. **Automated Chunk Compression:**
   ```sql
   ALTER TABLE optimization_events SET (
       timescaledb.compress,
       timescaledb.compress_segmentby = 'prompt_category, model_name',
       timescaledb.compress_orderby = 'timestamp DESC'
   );
   SELECT add_compression_policy('optimization_events', INTERVAL '14 days', if_not_exists => TRUE);
   ```
   Historical events older than 14 days are compressed using columnar compression (Gorilla/Delta-of-delta algorithms), achieving up to 90% disk space reduction.

---

## 4. Dual-Engine Fallback Mechanics & Resilience

A fundamental principle of the zero-budget development environment is that **the absence of an external database service must never disrupt developer workflows or test suites**.

PromptGreen implements a fail-safe connection lifecycle:
1. `PromptLedger` reads `connection_url`, `DATABASE_URL`, or `POSTGRES_URL`.
2. If a PostgreSQL URL is detected, it attempts an explicit 3-second connection handshake using SQLAlchemy 2.0.
3. If the connection fails (e.g., PostgreSQL daemon offline, wrong credentials, network partition), `PromptLedger`:
   - Emits a structured diagnostic warning: `[PromptLedger] PostgreSQL connection failed (...). Gracefully falling back to SQLite: prompt_ledger.db`.
   - Reverts its internal engine to SQLite mode.
   - Initialises local SQLite tables and indexes.
4. Time-series aggregation adapts dynamically:
   - When on TimescaleDB: queries `time_bucket('1 hour', timestamp)`.
   - When on PostgreSQL: queries `date_trunc('hour', timestamp)`.
   - When on SQLite: queries `strftime('%Y-%m-%d %H:00:00', timestamp)`.

---

## 5. REST API Integration

Four high-performance REST endpoints were integrated into `promptgreen/api/server.py`:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v2/telemetry/events` | `GET` | Fetches filtered optimization events (filters: `category`, `routing`, `status`, pagination via `limit`, `offset`) |
| `/api/v2/telemetry/time-series` | `GET` | Returns aggregated time-series buckets (`hour` or `day`) for dashboard charting |
| `/api/v2/telemetry/stats` | `GET` | Computes comprehensive savings, carbon debt, and telemetry rollups |
| `/api/v2/telemetry/status` | `GET` | Reports persistence engine health (`sqlite`, `postgresql`, `timescaledb`), hypertable status, and total record counts |

---

## 6. Verification and Test Results

The persistence layer was validated against test suites:
1. `tests/test_database_modernization.py`:
   - `test_sqlite_schema_initialization`: PASSED
   - `test_legacy_v1_record_and_query`: PASSED
   - `test_v2_run_and_summary`: PASSED
   - `test_modern_optimization_event_persistence`: PASSED
   - `test_time_series_aggregates`: PASSED
   - `test_unreachable_postgres_fallback`: PASSED
2. `tests/test_all.py`: All 8 existing end-to-end tests passed without regression.
3. `scripts/migrate_sqlite_to_timescale.py --dry-run`: Confirmed successful zero-loss reading of all 448 historical production records in `prompt_ledger.db`.

---

## 7. Phase 4 Sign-Off

**Phase 4 is complete, audited, and verified.** Deliverables:
- Dual-Engine Persistence Engine: `promptgreen/ledger/database.py`
- Package Exports: `promptgreen/ledger/__init__.py`
- Declarative TimescaleDB Schema: `scripts/init_timescaledb.sql`
- Migration Utility: `scripts/migrate_sqlite_to_timescale.py`
- REST API Telemetry Endpoints: `promptgreen/api/server.py`
- Automated Test Suite: `tests/test_database_modernization.py`
- Architectural Deliverable: `docs/POSTGRESQL_TIMESCALEDB_INTEGRATION_REPORT.md`
