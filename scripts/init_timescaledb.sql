-- ============================================================================
-- PROMPTGREEN V2 — TIMESCALEDB & POSTGRESQL INITIALIZATION SCHEMA
-- Multi-Tenant Carbon Telemetry, Hypertables, and Continuous Aggregation
-- ============================================================================

-- 1. Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 2. Legacy / V1-V2 Prompt Records Table
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

-- 3. Modern Optimization Events Entity (Hypertable)
CREATE TABLE IF NOT EXISTS optimization_events (
    event_id VARCHAR(64),
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    prompt_category VARCHAR(64) DEFAULT 'general',
    author VARCHAR(64) DEFAULT 'local-user',
    team VARCHAR(64) DEFAULT 'Engineering',
    model_name VARCHAR(64) DEFAULT 'mid_tier',
    region VARCHAR(64) DEFAULT 'ILLUSTRATIVE_385',
    original_text TEXT,
    optimized_text TEXT,
    original_tokens INTEGER DEFAULT 0,
    optimized_tokens INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    compression_ratio DOUBLE PRECISION DEFAULT 1.0,
    semantic_similarity DOUBLE PRECISION DEFAULT 1.0,
    optimization_latency_ms DOUBLE PRECISION DEFAULT 0.0,
    pipeline_stages_applied VARCHAR(128) DEFAULT 'stage1,stage2,stage3,stage4',
    routing_decision VARCHAR(64) DEFAULT 'KEEP_CURRENT_MODEL',
    recommended_tier VARCHAR(64) DEFAULT 'mid_tier',
    modeled_prefill_energy_j DOUBLE PRECISION DEFAULT 0.0,
    modeled_decode_energy_j DOUBLE PRECISION DEFAULT 0.0,
    modeled_total_energy_j DOUBLE PRECISION DEFAULT 0.0,
    modeled_carbon_gco2e DOUBLE PRECISION DEFAULT 0.0,
    water_saved_ml DOUBLE PRECISION DEFAULT 0.0,
    grid_carbon_intensity DOUBLE PRECISION DEFAULT 385.0,
    status VARCHAR(16) DEFAULT 'PASS',
    stage_breakdown JSONB DEFAULT '{}'::jsonb,
    token_breakdown JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (event_id, timestamp)
);

-- 4. Convert optimization_events to TimescaleDB Hypertable partitioned by timestamp (7-day chunks)
SELECT create_hypertable('optimization_events', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');

-- 5. Create specialized query indexes
CREATE INDEX IF NOT EXISTS idx_opt_events_category ON optimization_events (prompt_category, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_opt_events_routing ON optimization_events (routing_decision, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_opt_events_team ON optimization_events (team, timestamp DESC);

-- 6. Continuous Aggregate View: Hourly Savings Summary
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

-- 7. Automated Continuous Aggregate Refresh Policy
SELECT add_continuous_aggregate_policy('hourly_savings_summary',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- 8. Compression Policy (compress chunks older than 14 days)
ALTER TABLE optimization_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'prompt_category, model_name',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('optimization_events', INTERVAL '14 days', if_not_exists => TRUE);

-- 9. Data Retention Policy (drop uncompressed historical chunks older than 90 days if enabled)
-- SELECT add_retention_policy('optimization_events', INTERVAL '90 days', if_not_exists => TRUE);
