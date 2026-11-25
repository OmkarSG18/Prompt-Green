"""
PromptGreen V2 Database Persistence Layer (Dual-Engine: PostgreSQL/TimescaleDB & SQLite).
Provides enterprise time-series telemetry persistence, hypertable continuous aggregation,
and transparent fallback to local SQLite for zero-budget CPU development.
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("promptgreen.ledger")


@dataclass
class LedgerRecord:
    """Legacy V1/V2 Ledger record for backward compatibility."""
    id: Optional[int]
    commit_hash: str
    author: str
    team: str
    model_name: str
    region: str
    old_prompt: str
    new_prompt: str
    input_token_delta: int
    predicted_output_token_delta: float
    carbon_delta_gco2_1k: float
    monthly_carbon_delta_gco2: float
    status: str
    timestamp: Optional[str] = None
    opt_mode: Optional[str] = "BALANCED"
    semantic_score: Optional[float] = 1.0
    net_energy_wh: Optional[float] = 0.0
    net_carbon_g: Optional[float] = 0.0
    water_saved_ml: Optional[float] = 0.0
    routing_outcome: Optional[str] = "KEEP_CURRENT_MODEL"
    recommended_tier: Optional[str] = "mid_tier"
    latency_ms: Optional[float] = 0.0


@dataclass
class OptimizationEvent:
    """Enterprise time-series optimization event model for TimescaleDB and V2 telemetry."""
    event_id: str = field(default_factory=lambda: f"opt_{uuid.uuid4().hex[:12]}_{int(time.time())}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    prompt_category: str = "general"
    author: str = "local-user"
    team: str = "Engineering"
    model_name: str = "mid_tier"
    region: str = "ILLUSTRATIVE_385"
    original_text: str = ""
    optimized_text: str = ""
    original_tokens: int = 0
    optimized_tokens: int = 0
    tokens_saved: int = 0
    compression_ratio: float = 1.0
    semantic_similarity: float = 1.0
    optimization_latency_ms: float = 0.0
    pipeline_stages_applied: str = "stage1,stage2,stage3,stage4"
    routing_decision: str = "KEEP_CURRENT_MODEL"
    recommended_tier: str = "mid_tier"
    modeled_prefill_energy_j: Optional[float] = None
    modeled_decode_energy_j: Optional[float] = None
    modeled_total_energy_j: float = 0.0
    modeled_carbon_gco2e: float = 0.0
    water_saved_ml: float = 0.0
    grid_carbon_intensity: float = 385.0
    status: str = "PASS"
    stage_breakdown: Dict[str, Any] = field(default_factory=dict)
    token_breakdown: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    fallback_type: str = "none"
    actual_retention_rate: Optional[float] = None  # Backward-compatible alias for final_token_retention_ratio
    rollback_stage: str = "none"
    compressor_retention_rate: Optional[float] = None  # Backward-compatible alias for accepted_compressor_retention_rate
    final_token_retention_ratio: Optional[float] = None  # Final prompt tokens / original tokens
    accepted_compressor_retention_rate: Optional[float] = None  # Rate of accepted compressor candidate (None if fallback/rollback/bypassed)
    last_compressor_attempt_retention_rate: Optional[float] = None  # Target rate of last compressor attempt (e.g. 0.40, 0.60, 0.80)
    net_energy_wh: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(d["timestamp"], datetime):
            d["timestamp"] = d["timestamp"].isoformat()
        return d


class PromptLedger:
    """
    PromptGreen Persistent Telemetry Ledger.
    Supports dual-mode execution:
    1. PostgreSQL + TimescaleDB (when DATABASE_URL or POSTGRES_URL is configured and reachable).
    2. Local SQLite (zero-budget CPU fallback, preserving prompt_ledger.db history).
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        connection_url: Optional[str] = None
    ):
        self.db_path = db_path or os.environ.get("PROMPTGREEN_DB_PATH") or "prompt_ledger.db"
        self.requested_url = connection_url or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
        self.engine_type = "sqlite"
        self._pg_engine = None
        self.has_timescaledb = False

        self._init_backend()

    def _init_backend(self):
        """Initializes PostgreSQL/TimescaleDB if available; otherwise falls back to SQLite."""
        if self.requested_url and (
            self.requested_url.startswith("postgresql://") or
            self.requested_url.startswith("postgresql+psycopg2://")
        ):
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(
                    self.requested_url,
                    pool_size=5,
                    max_overflow=10,
                    connect_args={"connect_timeout": 3}
                )
                with engine.connect() as conn:
                    # Test connection
                    conn.execute(text("SELECT 1"))
                    # Check TimescaleDB extension
                    res = conn.execute(text(
                        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
                    )).scalar()
                    self.has_timescaledb = bool(res and res > 0)

                self._pg_engine = engine
                self.engine_type = "timescaledb" if self.has_timescaledb else "postgresql"
                self._init_pg_schema()
                logger.info(
                    "PromptLedger initialized with %s backend: %s",
                    self.engine_type, self._redact_url(self.requested_url)
                )
                return
            except Exception as exc:
                logger.warning(
                    "PromptLedger failed to connect to PostgreSQL (%s). Falling back to SQLite: %s",
                    exc, self.db_path
                )
                self.engine_type = "sqlite"
                self._pg_engine = None

        # Fallback / Default: SQLite
        self.engine_type = "sqlite"
        self._init_sqlite_schema()

    @staticmethod
    def _redact_url(url: str) -> str:
        """Masks database password in connection string for safe logging."""
        try:
            from urllib.parse import urlparse, urlunparse
            p = urlparse(url)
            if p.password:
                netloc = f"{p.username}:***@{p.hostname}:{p.port or ''}"
                return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
            return url
        except Exception:
            return "postgresql://***"

    # --------------------------------------------------------------------------
    # SQLite Implementation
    # --------------------------------------------------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite_schema(self):
        """Initializes tables for SQLite backend (both prompt_records and optimization_events)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Legacy prompt_records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompt_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash TEXT,
                    author TEXT,
                    team TEXT,
                    model_name TEXT,
                    region TEXT,
                    old_prompt TEXT,
                    new_prompt TEXT,
                    input_token_delta INTEGER,
                    predicted_output_token_delta REAL,
                    carbon_delta_gco2_1k REAL,
                    monthly_carbon_delta_gco2 REAL,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    opt_mode TEXT DEFAULT 'BALANCED',
                    semantic_score REAL DEFAULT 1.0,
                    net_energy_wh REAL DEFAULT 0.0,
                    net_carbon_g REAL DEFAULT 0.0,
                    water_saved_ml REAL DEFAULT 0.0,
                    routing_outcome TEXT DEFAULT 'KEEP_CURRENT_MODEL',
                    recommended_tier TEXT DEFAULT 'mid_tier',
                    latency_ms REAL DEFAULT 0.0,
                    retry_count INTEGER DEFAULT 0,
                    fallback_type TEXT DEFAULT 'none',
                    actual_retention_rate REAL DEFAULT NULL,
                    rollback_stage TEXT DEFAULT 'none',
                    compressor_retention_rate REAL DEFAULT NULL,
                    final_token_retention_ratio REAL DEFAULT NULL,
                    accepted_compressor_retention_rate REAL DEFAULT NULL,
                    last_compressor_attempt_retention_rate REAL DEFAULT NULL
                )
            """)

            # Ensure all V2 columns exist in existing SQLite databases
            cursor.execute("PRAGMA table_info(prompt_records)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            v2_cols = [
                ("opt_mode", "TEXT DEFAULT 'BALANCED'"),
                ("semantic_score", "REAL DEFAULT 1.0"),
                ("net_energy_wh", "REAL DEFAULT 0.0"),
                ("net_carbon_g", "REAL DEFAULT 0.0"),
                ("water_saved_ml", "REAL DEFAULT 0.0"),
                ("routing_outcome", "TEXT DEFAULT 'KEEP_CURRENT_MODEL'"),
                ("recommended_tier", "TEXT DEFAULT 'mid_tier'"),
                ("latency_ms", "REAL DEFAULT 0.0"),
                ("retry_count", "INTEGER DEFAULT 0"),
                ("fallback_type", "TEXT DEFAULT 'none'"),
                ("actual_retention_rate", "REAL DEFAULT NULL"),
                ("rollback_stage", "TEXT DEFAULT 'none'"),
                ("compressor_retention_rate", "REAL DEFAULT NULL"),
                ("final_token_retention_ratio", "REAL DEFAULT NULL"),
                ("accepted_compressor_retention_rate", "REAL DEFAULT NULL"),
                ("last_compressor_attempt_retention_rate", "REAL DEFAULT NULL"),
            ]
            for col_name, col_def in v2_cols:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE prompt_records ADD COLUMN {col_name} {col_def}")

            # 2. Modern optimization_events entity
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS optimization_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    prompt_category TEXT DEFAULT 'general',
                    author TEXT DEFAULT 'local-user',
                    team TEXT DEFAULT 'Engineering',
                    model_name TEXT DEFAULT 'mid_tier',
                    region TEXT DEFAULT 'ILLUSTRATIVE_385',
                    original_text TEXT,
                    optimized_text TEXT,
                    original_tokens INTEGER DEFAULT 0,
                    optimized_tokens INTEGER DEFAULT 0,
                    tokens_saved INTEGER DEFAULT 0,
                    compression_ratio REAL DEFAULT 1.0,
                    semantic_similarity REAL DEFAULT 1.0,
                    optimization_latency_ms REAL DEFAULT 0.0,
                    pipeline_stages_applied TEXT DEFAULT 'stage1,stage2,stage3,stage4',
                    routing_decision TEXT DEFAULT 'KEEP_CURRENT_MODEL',
                    recommended_tier TEXT DEFAULT 'mid_tier',
                    modeled_prefill_energy_j REAL DEFAULT NULL,
                    modeled_decode_energy_j REAL DEFAULT NULL,
                    modeled_total_energy_j REAL DEFAULT 0.0,
                    modeled_carbon_gco2e REAL DEFAULT 0.0,
                    water_saved_ml REAL DEFAULT 0.0,
                    grid_carbon_intensity REAL DEFAULT 385.0,
                    status TEXT DEFAULT 'PASS',
                    stage_breakdown TEXT DEFAULT '{}',
                    token_breakdown TEXT DEFAULT '{}',
                    retry_count INTEGER DEFAULT 0,
                    fallback_type TEXT DEFAULT 'none',
                    actual_retention_rate REAL DEFAULT NULL,
                    rollback_stage TEXT DEFAULT 'none',
                    compressor_retention_rate REAL DEFAULT NULL,
                    final_token_retention_ratio REAL DEFAULT NULL,
                    accepted_compressor_retention_rate REAL DEFAULT NULL,
                    last_compressor_attempt_retention_rate REAL DEFAULT NULL
                )
            """)

            # Ensure all V2 columns exist in existing optimization_events tables
            cursor.execute("PRAGMA table_info(optimization_events)")
            existing_event_cols = {row[1] for row in cursor.fetchall()}
            event_v2_cols = [
                ("prompt_category", "TEXT DEFAULT 'general'"),
                ("author", "TEXT DEFAULT 'local-user'"),
                ("team", "TEXT DEFAULT 'Engineering'"),
                ("model_name", "TEXT DEFAULT 'mid_tier'"),
                ("region", "TEXT DEFAULT 'ILLUSTRATIVE_385'"),
                ("original_text", "TEXT"),
                ("optimized_text", "TEXT"),
                ("original_tokens", "INTEGER DEFAULT 0"),
                ("optimized_tokens", "INTEGER DEFAULT 0"),
                ("tokens_saved", "INTEGER DEFAULT 0"),
                ("compression_ratio", "REAL DEFAULT 1.0"),
                ("semantic_similarity", "REAL DEFAULT 1.0"),
                ("optimization_latency_ms", "REAL DEFAULT 0.0"),
                ("pipeline_stages_applied", "TEXT DEFAULT 'stage1,stage2,stage3,stage4'"),
                ("routing_decision", "TEXT DEFAULT 'KEEP_CURRENT_MODEL'"),
                ("recommended_tier", "TEXT DEFAULT 'mid_tier'"),
                ("modeled_prefill_energy_j", "REAL DEFAULT NULL"),
                ("modeled_decode_energy_j", "REAL DEFAULT NULL"),
                ("modeled_total_energy_j", "REAL DEFAULT 0.0"),
                ("modeled_carbon_gco2e", "REAL DEFAULT 0.0"),
                ("water_saved_ml", "REAL DEFAULT 0.0"),
                ("grid_carbon_intensity", "REAL DEFAULT 385.0"),
                ("status", "TEXT DEFAULT 'PASS'"),
                ("stage_breakdown", "TEXT DEFAULT '{}'"),
                ("token_breakdown", "TEXT DEFAULT '{}'"),
                ("retry_count", "INTEGER DEFAULT 0"),
                ("fallback_type", "TEXT DEFAULT 'none'"),
                ("actual_retention_rate", "REAL DEFAULT NULL"),
                ("rollback_stage", "TEXT DEFAULT 'none'"),
                ("compressor_retention_rate", "REAL DEFAULT NULL"),
                ("final_token_retention_ratio", "REAL DEFAULT NULL"),
                ("accepted_compressor_retention_rate", "REAL DEFAULT NULL"),
                ("last_compressor_attempt_retention_rate", "REAL DEFAULT NULL"),
            ]
            for col_name, col_def in event_v2_cols:
                if col_name not in existing_event_cols:
                    cursor.execute(f"ALTER TABLE optimization_events ADD COLUMN {col_name} {col_def}")

            # Genuine historical backfill:
            # If original_tokens and optimized_tokens exist, backfill final_token_retention_ratio and actual_retention_rate
            # strictly when genuine non-zero original token counts exist. Rows with 0, missing or NULL tokens stay NULL.
            cursor.execute("""
                UPDATE optimization_events
                SET final_token_retention_ratio = ROUND(CAST(optimized_tokens AS REAL) / CAST(original_tokens AS REAL), 4),
                    actual_retention_rate = ROUND(CAST(optimized_tokens AS REAL) / CAST(original_tokens AS REAL), 4)
                WHERE final_token_retention_ratio IS NULL
                  AND original_tokens IS NOT NULL
                  AND original_tokens > 0
                  AND optimized_tokens IS NOT NULL
            """)
            if "original_token_count" in existing_cols and "optimized_token_count" in existing_cols:
                cursor.execute("""
                    UPDATE prompt_records
                    SET final_token_retention_ratio = ROUND(CAST(optimized_token_count AS REAL) / CAST(original_token_count AS REAL), 4),
                        actual_retention_rate = ROUND(CAST(optimized_token_count AS REAL) / CAST(original_token_count AS REAL), 4)
                    WHERE final_token_retention_ratio IS NULL
                      AND original_token_count IS NOT NULL
                      AND original_token_count > 0
                      AND optimized_token_count IS NOT NULL
                """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_events_timestamp ON optimization_events (timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_events_category ON optimization_events (prompt_category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_events_routing ON optimization_events (routing_decision)")
            conn.commit()

    def init_db(self):
        """Public alias for backward compatibility."""
        if self.engine_type == "sqlite":
            self._init_sqlite_schema()
        else:
            self._init_pg_schema()

    # --------------------------------------------------------------------------
    # PostgreSQL / TimescaleDB Implementation
    # --------------------------------------------------------------------------

    def _init_pg_schema(self):
        """Initializes tables and hypertable in PostgreSQL / TimescaleDB."""
        if not self._pg_engine:
            return
        from sqlalchemy import text
        with self._pg_engine.begin() as conn:
            conn.execute(text("""
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
                    retry_count INTEGER DEFAULT 0,
                    fallback_type TEXT DEFAULT 'none',
                    actual_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    rollback_stage TEXT DEFAULT 'none',
                    compressor_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    final_token_retention_ratio DOUBLE PRECISION DEFAULT NULL,
                    accepted_compressor_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    last_compressor_attempt_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    PRIMARY KEY (id, timestamp)
                );
            """))

            conn.execute(text("""
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
                    modeled_prefill_energy_j DOUBLE PRECISION DEFAULT NULL,
                    modeled_decode_energy_j DOUBLE PRECISION DEFAULT NULL,
                    modeled_total_energy_j DOUBLE PRECISION DEFAULT 0.0,
                    modeled_carbon_gco2e DOUBLE PRECISION DEFAULT 0.0,
                    water_saved_ml DOUBLE PRECISION DEFAULT 0.0,
                    grid_carbon_intensity DOUBLE PRECISION DEFAULT 385.0,
                    status VARCHAR(16) DEFAULT 'PASS',
                    stage_breakdown JSONB DEFAULT '{}'::jsonb,
                    token_breakdown JSONB DEFAULT '{}'::jsonb,
                    retry_count INTEGER DEFAULT 0,
                    fallback_type VARCHAR(32) DEFAULT 'none',
                    actual_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    rollback_stage VARCHAR(32) DEFAULT 'none',
                    compressor_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    final_token_retention_ratio DOUBLE PRECISION DEFAULT NULL,
                    accepted_compressor_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    last_compressor_attempt_retention_rate DOUBLE PRECISION DEFAULT NULL,
                    PRIMARY KEY (event_id, timestamp)
                );
            """))

            # Additive schema evolution for existing PostgreSQL / TimescaleDB databases
            conn.execute(text("""
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS fallback_type TEXT DEFAULT 'none';
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS actual_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS rollback_stage TEXT DEFAULT 'none';
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS compressor_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS final_token_retention_ratio DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS accepted_compressor_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE prompt_records ADD COLUMN IF NOT EXISTS last_compressor_attempt_retention_rate DOUBLE PRECISION DEFAULT NULL;

                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS fallback_type VARCHAR(32) DEFAULT 'none';
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS actual_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS rollback_stage VARCHAR(32) DEFAULT 'none';
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS compressor_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS final_token_retention_ratio DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS accepted_compressor_retention_rate DOUBLE PRECISION DEFAULT NULL;
                ALTER TABLE optimization_events ADD COLUMN IF NOT EXISTS last_compressor_attempt_retention_rate DOUBLE PRECISION DEFAULT NULL;

                UPDATE optimization_events
                SET final_token_retention_ratio = ROUND(CAST(optimized_tokens AS NUMERIC) / CAST(original_tokens AS NUMERIC), 4),
                    actual_retention_rate = ROUND(CAST(optimized_tokens AS NUMERIC) / CAST(original_tokens AS NUMERIC), 4)
                WHERE final_token_retention_ratio IS NULL
                  AND original_tokens IS NOT NULL
                  AND original_tokens > 0
                  AND optimized_tokens IS NOT NULL;
            """))

            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_opt_events_category ON optimization_events (prompt_category, timestamp DESC);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_opt_events_routing ON optimization_events (routing_decision, timestamp DESC);"))

            if self.has_timescaledb:
                try:
                    conn.execute(text(
                        "SELECT create_hypertable('optimization_events', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');"
                    ))
                except Exception as exc:
                    logger.warning("Could not create TimescaleDB hypertable: %s", exc)

    # --------------------------------------------------------------------------
    # Recording API (V1, V2, and Enterprise OptimizationEvent)
    # --------------------------------------------------------------------------

    def record_prompt_review(
        self,
        commit_hash: str,
        author: str,
        team: str,
        model_name: str,
        region: str,
        old_prompt: str,
        new_prompt: str,
        input_token_delta: int,
        predicted_output_token_delta: float,
        carbon_delta_gco2_1k: float,
        monthly_carbon_delta_gco2: float,
        status: str
    ) -> int:
        """Inserts a new prompt review record into the ledger (V1 compatible)."""
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.begin() as conn:
                res = conn.execute(text("""
                    INSERT INTO prompt_records (
                        commit_hash, author, team, model_name, region,
                        old_prompt, new_prompt, input_token_delta,
                        predicted_output_token_delta, carbon_delta_gco2_1k,
                        monthly_carbon_delta_gco2, status
                    ) VALUES (
                        :commit_hash, :author, :team, :model_name, :region,
                        :old_prompt, :new_prompt, :input_token_delta,
                        :predicted_output_token_delta, :carbon_delta_gco2_1k,
                        :monthly_carbon_delta_gco2, :status
                    ) RETURNING id
                """), {
                    "commit_hash": commit_hash, "author": author, "team": team,
                    "model_name": model_name, "region": region, "old_prompt": old_prompt,
                    "new_prompt": new_prompt, "input_token_delta": input_token_delta,
                    "predicted_output_token_delta": predicted_output_token_delta,
                    "carbon_delta_gco2_1k": carbon_delta_gco2_1k,
                    "monthly_carbon_delta_gco2": monthly_carbon_delta_gco2,
                    "status": status
                })
                row = res.fetchone()
                return row[0] if row else 1

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prompt_records (
                    commit_hash, author, team, model_name, region,
                    old_prompt, new_prompt, input_token_delta,
                    predicted_output_token_delta, carbon_delta_gco2_1k,
                    monthly_carbon_delta_gco2, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                commit_hash, author, team, model_name, region,
                old_prompt, new_prompt, input_token_delta,
                predicted_output_token_delta, carbon_delta_gco2_1k,
                monthly_carbon_delta_gco2, status
            ))
            conn.commit()
            return cursor.lastrowid

    def record_v2_run(
        self,
        commit_hash: str = "v2-run",
        author: str = "local-user",
        team: str = "Engineering",
        model_name: str = "mid_tier",
        region: str = "ILLUSTRATIVE_385",
        old_prompt: str = "",
        new_prompt: str = "",
        input_token_delta: int = 0,
        predicted_output_token_delta: float = 0.0,
        carbon_delta_gco2_1k: float = 0.0,
        monthly_carbon_delta_gco2: float = 0.0,
        status: str = "PASS",
        opt_mode: str = "BALANCED",
        semantic_score: float = 1.0,
        net_energy_wh: float = 0.0,
        net_carbon_g: float = 0.0,
        water_saved_ml: float = 0.0,
        routing_outcome: str = "KEEP_CURRENT_MODEL",
        recommended_tier: str = "mid_tier",
        latency_ms: float = 0.0,
        retry_count: int = 0,
        fallback_type: str = "none",
        actual_retention_rate: Optional[float] = None,
        rollback_stage: str = "none",
        compressor_retention_rate: Optional[float] = None,
        final_token_retention_ratio: Optional[float] = None,
        accepted_compressor_retention_rate: Optional[float] = None,
        last_compressor_attempt_retention_rate: Optional[float] = None
    ) -> int:
        """Inserts a full V2 prompt optimization and telemetry record into the ledger."""
        effective_final_retention = final_token_retention_ratio if final_token_retention_ratio is not None else actual_retention_rate
        effective_accepted_comp = accepted_compressor_retention_rate if accepted_compressor_retention_rate is not None else compressor_retention_rate
        effective_last_comp = last_compressor_attempt_retention_rate

        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.begin() as conn:
                res = conn.execute(text("""
                    INSERT INTO prompt_records (
                        commit_hash, author, team, model_name, region,
                        old_prompt, new_prompt, input_token_delta,
                        predicted_output_token_delta, carbon_delta_gco2_1k,
                        monthly_carbon_delta_gco2, status,
                        opt_mode, semantic_score, net_energy_wh,
                        net_carbon_g, water_saved_ml, routing_outcome,
                        recommended_tier, latency_ms,
                        retry_count, fallback_type, actual_retention_rate, rollback_stage,
                        compressor_retention_rate, final_token_retention_ratio,
                        accepted_compressor_retention_rate, last_compressor_attempt_retention_rate
                    ) VALUES (
                        :commit_hash, :author, :team, :model_name, :region,
                        :old_prompt, :new_prompt, :input_token_delta,
                        :predicted_output_token_delta, :carbon_delta_gco2_1k,
                        :monthly_carbon_delta_gco2, :status,
                        :opt_mode, :semantic_score, :net_energy_wh,
                        :net_carbon_g, :water_saved_ml, :routing_outcome,
                        :recommended_tier, :latency_ms,
                        :retry_count, :fallback_type, :actual_retention_rate, :rollback_stage,
                        :compressor_retention_rate, :final_token_retention_ratio,
                        :accepted_compressor_retention_rate, :last_compressor_attempt_retention_rate
                    ) RETURNING id
                """), {
                    "commit_hash": commit_hash, "author": author, "team": team,
                    "model_name": model_name, "region": region, "old_prompt": old_prompt,
                    "new_prompt": new_prompt, "input_token_delta": input_token_delta,
                    "predicted_output_token_delta": predicted_output_token_delta,
                    "carbon_delta_gco2_1k": carbon_delta_gco2_1k,
                    "monthly_carbon_delta_gco2": monthly_carbon_delta_gco2,
                    "status": status, "opt_mode": opt_mode, "semantic_score": semantic_score,
                    "net_energy_wh": net_energy_wh, "net_carbon_g": net_carbon_g,
                    "water_saved_ml": water_saved_ml, "routing_outcome": routing_outcome,
                    "recommended_tier": recommended_tier, "latency_ms": latency_ms,
                    "retry_count": retry_count, "fallback_type": fallback_type,
                    "actual_retention_rate": effective_final_retention, "rollback_stage": rollback_stage,
                    "compressor_retention_rate": effective_accepted_comp,
                    "final_token_retention_ratio": effective_final_retention,
                    "accepted_compressor_retention_rate": effective_accepted_comp,
                    "last_compressor_attempt_retention_rate": effective_last_comp
                })
                row = res.fetchone()
                return row[0] if row else 1

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prompt_records (
                    commit_hash, author, team, model_name, region,
                    old_prompt, new_prompt, input_token_delta,
                    predicted_output_token_delta, carbon_delta_gco2_1k,
                    monthly_carbon_delta_gco2, status,
                    opt_mode, semantic_score, net_energy_wh,
                    net_carbon_g, water_saved_ml, routing_outcome,
                    recommended_tier, latency_ms,
                    retry_count, fallback_type, actual_retention_rate, rollback_stage,
                    compressor_retention_rate, final_token_retention_ratio,
                    accepted_compressor_retention_rate, last_compressor_attempt_retention_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                commit_hash, author, team, model_name, region,
                old_prompt, new_prompt, input_token_delta,
                predicted_output_token_delta, carbon_delta_gco2_1k,
                monthly_carbon_delta_gco2, status,
                opt_mode, semantic_score, net_energy_wh,
                net_carbon_g, water_saved_ml, routing_outcome,
                recommended_tier, latency_ms,
                retry_count, fallback_type, effective_final_retention, rollback_stage,
                effective_accepted_comp, effective_final_retention,
                effective_accepted_comp, effective_last_comp
            ))
            conn.commit()
            return cursor.lastrowid
            conn.commit()
            return cursor.lastrowid

    def record_optimization_event(
        self,
        event: Union[OptimizationEvent, Dict[str, Any]],
        mirror_to_prompt_records: bool = True
    ) -> str:
        """
        Persists a complete enterprise OptimizationEvent into optimization_events table.
        Optionally mirrors the event to prompt_records for backward compatibility if not
        already recorded by the caller.
        """
        if isinstance(event, dict):
            # Parse dict into OptimizationEvent with default fallback values
            evt_kwargs = {k: v for k, v in event.items() if hasattr(OptimizationEvent, k)}
            evt = OptimizationEvent(**evt_kwargs)
        else:
            evt = event

        ts = evt.timestamp if isinstance(evt.timestamp, datetime) else datetime.now(timezone.utc)
        stage_json = json.dumps(evt.stage_breakdown or {})
        token_json = json.dumps(evt.token_breakdown or {})

        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO optimization_events (
                        event_id, timestamp, prompt_category, author, team,
                        model_name, region, original_text, optimized_text,
                        original_tokens, optimized_tokens, tokens_saved,
                        compression_ratio, semantic_similarity, optimization_latency_ms,
                        pipeline_stages_applied, routing_decision, recommended_tier,
                        modeled_prefill_energy_j, modeled_decode_energy_j,
                        modeled_total_energy_j, modeled_carbon_gco2e, water_saved_ml,
                        grid_carbon_intensity, status, stage_breakdown, token_breakdown,
                        retry_count, fallback_type, actual_retention_rate, rollback_stage,
                        compressor_retention_rate, final_token_retention_ratio,
                        accepted_compressor_retention_rate, last_compressor_attempt_retention_rate
                    ) VALUES (
                        :event_id, :timestamp, :prompt_category, :author, :team,
                        :model_name, :region, :original_text, :optimized_text,
                        :original_tokens, :optimized_tokens, :tokens_saved,
                        :compression_ratio, :semantic_similarity, :optimization_latency_ms,
                        :pipeline_stages_applied, :routing_decision, :recommended_tier,
                        :modeled_prefill_energy_j, :modeled_decode_energy_j,
                        :modeled_total_energy_j, :modeled_carbon_gco2e, :water_saved_ml,
                        :grid_carbon_intensity, :status, CAST(:stage_breakdown AS jsonb), CAST(:token_breakdown AS jsonb),
                        :retry_count, :fallback_type, :actual_retention_rate, :rollback_stage,
                        :compressor_retention_rate, :final_token_retention_ratio,
                        :accepted_compressor_retention_rate, :last_compressor_attempt_retention_rate
                    )
                """), {
                    "event_id": evt.event_id, "timestamp": ts, "prompt_category": evt.prompt_category,
                    "author": evt.author, "team": evt.team, "model_name": evt.model_name,
                    "region": evt.region, "original_text": evt.original_text, "optimized_text": evt.optimized_text,
                    "original_tokens": evt.original_tokens, "optimized_tokens": evt.optimized_tokens,
                    "tokens_saved": evt.tokens_saved, "compression_ratio": evt.compression_ratio,
                    "semantic_similarity": evt.semantic_similarity, "optimization_latency_ms": evt.optimization_latency_ms,
                    "pipeline_stages_applied": evt.pipeline_stages_applied, "routing_decision": evt.routing_decision,
                    "recommended_tier": evt.recommended_tier, "modeled_prefill_energy_j": evt.modeled_prefill_energy_j,
                    "modeled_decode_energy_j": evt.modeled_decode_energy_j, "modeled_total_energy_j": evt.modeled_total_energy_j,
                    "modeled_carbon_gco2e": evt.modeled_carbon_gco2e, "water_saved_ml": evt.water_saved_ml,
                    "grid_carbon_intensity": evt.grid_carbon_intensity, "status": evt.status,
                    "stage_breakdown": stage_json, "token_breakdown": token_json,
                    "retry_count": evt.retry_count, "fallback_type": evt.fallback_type,
                    "actual_retention_rate": evt.actual_retention_rate, "rollback_stage": evt.rollback_stage,
                    "compressor_retention_rate": evt.compressor_retention_rate,
                    "final_token_retention_ratio": evt.final_token_retention_ratio,
                    "accepted_compressor_retention_rate": evt.accepted_compressor_retention_rate,
                    "last_compressor_attempt_retention_rate": evt.last_compressor_attempt_retention_rate
                })
        else:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO optimization_events (
                        event_id, timestamp, prompt_category, author, team,
                        model_name, region, original_text, optimized_text,
                        original_tokens, optimized_tokens, tokens_saved,
                        compression_ratio, semantic_similarity, optimization_latency_ms,
                        pipeline_stages_applied, routing_decision, recommended_tier,
                        modeled_prefill_energy_j, modeled_decode_energy_j,
                        modeled_total_energy_j, modeled_carbon_gco2e, water_saved_ml,
                        grid_carbon_intensity, status, stage_breakdown, token_breakdown,
                        retry_count, fallback_type, actual_retention_rate, rollback_stage,
                        compressor_retention_rate, final_token_retention_ratio,
                        accepted_compressor_retention_rate, last_compressor_attempt_retention_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    evt.event_id, ts.strftime("%Y-%m-%d %H:%M:%S"), evt.prompt_category, evt.author, evt.team,
                    evt.model_name, evt.region, evt.original_text, evt.optimized_text,
                    evt.original_tokens, evt.optimized_tokens, evt.tokens_saved,
                    evt.compression_ratio, evt.semantic_similarity, evt.optimization_latency_ms,
                    evt.pipeline_stages_applied, evt.routing_decision, evt.recommended_tier,
                    evt.modeled_prefill_energy_j, evt.modeled_decode_energy_j,
                    evt.modeled_total_energy_j, evt.modeled_carbon_gco2e, evt.water_saved_ml,
                    evt.grid_carbon_intensity, evt.status, stage_json, token_json,
                    evt.retry_count, evt.fallback_type, evt.actual_retention_rate, evt.rollback_stage,
                    evt.compressor_retention_rate, evt.final_token_retention_ratio,
                    evt.accepted_compressor_retention_rate, evt.last_compressor_attempt_retention_rate
                ))
                conn.commit()

        # Mirror to prompt_records for backward compatibility if requested
        if mirror_to_prompt_records:
            try:
                # Use genuine net_energy_wh if provided; otherwise derive from modeled carbon abatement,
                # never substituting gross optimized prompt consumption.
                if evt.net_energy_wh is not None:
                    net_energy_wh = evt.net_energy_wh
                elif evt.modeled_carbon_gco2e != 0.0 and evt.grid_carbon_intensity > 0:
                    net_energy_wh = (evt.modeled_carbon_gco2e * 1000.0) / evt.grid_carbon_intensity
                else:
                    net_energy_wh = 0.0

                self.record_v2_run(
                    commit_hash=evt.event_id[:8],
                    author=evt.author,
                    team=evt.team,
                    model_name=evt.model_name,
                    region=evt.region,
                    old_prompt=evt.original_text,
                    new_prompt=evt.optimized_text,
                    input_token_delta=-evt.tokens_saved,
                    predicted_output_token_delta=0.0,
                    carbon_delta_gco2_1k=-evt.modeled_carbon_gco2e * 1000.0,
                    monthly_carbon_delta_gco2=-evt.modeled_carbon_gco2e * 30000.0,
                    status=evt.status,
                    opt_mode=evt.pipeline_stages_applied,
                    semantic_score=evt.semantic_similarity,
                    net_energy_wh=net_energy_wh,
                    net_carbon_g=evt.modeled_carbon_gco2e,
                    water_saved_ml=evt.water_saved_ml,
                    routing_outcome=evt.routing_decision,
                    recommended_tier=evt.recommended_tier,
                    latency_ms=evt.optimization_latency_ms,
                    retry_count=evt.retry_count,
                    fallback_type=evt.fallback_type,
                    actual_retention_rate=evt.actual_retention_rate,
                    rollback_stage=evt.rollback_stage,
                    compressor_retention_rate=evt.compressor_retention_rate,
                    final_token_retention_ratio=evt.final_token_retention_ratio,
                    accepted_compressor_retention_rate=evt.accepted_compressor_retention_rate,
                    last_compressor_attempt_retention_rate=evt.last_compressor_attempt_retention_rate
                )
            except Exception as mirror_exc:
                logger.debug("Mirroring to prompt_records skipped: %s", mirror_exc)

        return evt.event_id

    # --------------------------------------------------------------------------
    # Query API (Compatible with Existing Views & Dashboards)
    # --------------------------------------------------------------------------

    def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves recent ledger records, enriched with modeled Joules from optimization_events
        when available, without mutating database schema.
        """
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                try:
                    res = conn.execute(text("""
                        SELECT pr.*,
                               oe.modeled_prefill_energy_j,
                               oe.modeled_decode_energy_j,
                               oe.modeled_total_energy_j
                        FROM prompt_records pr
                        LEFT JOIN (
                            SELECT DISTINCT ON (event_id)
                                   event_id,
                                   optimization_latency_ms,
                                   tokens_saved,
                                   modeled_prefill_energy_j,
                                   modeled_decode_energy_j,
                                   modeled_total_energy_j
                            FROM optimization_events
                        ) oe ON (
                            pr.commit_hash = oe.event_id
                            OR (pr.commit_hash LIKE 'opt_%' AND oe.event_id LIKE pr.commit_hash || '%')
                            OR (pr.commit_hash = 'v2-api' AND pr.latency_ms = oe.optimization_latency_ms AND pr.input_token_delta = -oe.tokens_saved)
                        )
                        ORDER BY pr.id DESC
                        LIMIT :limit
                    """), {"limit": limit})
                    return [dict(row._mapping) for row in res]
                except Exception:
                    res = conn.execute(text("""
                        SELECT * FROM prompt_records
                        ORDER BY id DESC
                        LIMIT :limit
                    """), {"limit": limit})
                    return [dict(row._mapping) for row in res]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT pr.*,
                           oe.modeled_prefill_energy_j,
                           oe.modeled_decode_energy_j,
                           oe.modeled_total_energy_j
                    FROM prompt_records pr
                    LEFT JOIN optimization_events oe
                      ON (
                          pr.commit_hash = oe.event_id
                          OR (pr.commit_hash LIKE 'opt_%' AND oe.event_id LIKE pr.commit_hash || '%')
                          OR (pr.commit_hash = 'v2-api' AND pr.latency_ms = oe.optimization_latency_ms AND pr.input_token_delta = -oe.tokens_saved)
                      )
                    GROUP BY pr.id
                    ORDER BY pr.id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            except Exception:
                cursor.execute("""
                    SELECT * FROM prompt_records
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

    def get_team_leaderboard(self) -> List[Dict[str, Any]]:
        """Calculates carbon savings / additions per team."""
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT team,
                           COUNT(*) as total_reviews,
                           SUM(carbon_delta_gco2_1k) as net_carbon_delta_1k,
                           SUM(monthly_carbon_delta_gco2) as net_monthly_carbon
                    FROM prompt_records
                    GROUP BY team
                    ORDER BY net_carbon_delta_1k ASC
                """))
                return [dict(row._mapping) for row in res]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT team,
                       COUNT(*) as total_reviews,
                       SUM(carbon_delta_gco2_1k) as net_carbon_delta_1k,
                       SUM(monthly_carbon_delta_gco2) as net_monthly_carbon
                FROM prompt_records
                GROUP BY team
                ORDER BY net_carbon_delta_1k ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_model_comparison(self) -> List[Dict[str, Any]]:
        """Calculates total carbon impact breakdown per model."""
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT model_name,
                           COUNT(*) as review_count,
                           AVG(carbon_delta_gco2_1k) as avg_delta_1k,
                           SUM(monthly_carbon_delta_gco2) as total_monthly_carbon
                    FROM prompt_records
                    GROUP BY model_name
                """))
                return [dict(row._mapping) for row in res]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT model_name,
                       COUNT(*) as review_count,
                       AVG(carbon_delta_gco2_1k) as avg_delta_1k,
                       SUM(monthly_carbon_delta_gco2) as total_monthly_carbon
                FROM prompt_records
                GROUP BY model_name
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_cumulative_carbon_debt(self) -> Dict[str, Any]:
        """Retrieves total cumulative carbon metrics across all prompt reviews."""
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT COUNT(*) as total_reviews,
                           SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed_reviews,
                           SUM(CASE WHEN status = 'WARN' THEN 1 ELSE 0 END) as warned_reviews,
                           SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed_reviews,
                           COALESCE(SUM(carbon_delta_gco2_1k), 0.0) as total_carbon_delta_1k,
                           COALESCE(SUM(monthly_carbon_delta_gco2), 0.0) as total_monthly_carbon
                    FROM prompt_records
                """))
                row = res.fetchone()
                return dict(row._mapping) if row else {}

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total_reviews,
                       SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed_reviews,
                       SUM(CASE WHEN status = 'WARN' THEN 1 ELSE 0 END) as warned_reviews,
                       SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed_reviews,
                       COALESCE(SUM(carbon_delta_gco2_1k), 0.0) as total_carbon_delta_1k,
                       COALESCE(SUM(monthly_carbon_delta_gco2), 0.0) as total_monthly_carbon
                FROM prompt_records
            """)
            row = cursor.fetchone()
            return dict(row) if row else {}

    def get_v2_summary(self) -> Dict[str, Any]:
        """Retrieves aggregated V2 telemetry metrics across all prompt records."""
        if self._pg_engine:
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT COUNT(*) as total_runs,
                           SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed_runs,
                           SUM(CASE WHEN status = 'WARN' THEN 1 ELSE 0 END) as warned_runs,
                           SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed_runs,
                           COALESCE(SUM(net_energy_wh), 0.0) as total_net_energy_wh_saved,
                           COALESCE(SUM(net_carbon_g), 0.0) as total_net_carbon_g_saved,
                           COALESCE(SUM(water_saved_ml), 0.0) as total_water_saved_ml,
                           COALESCE(AVG(semantic_score), 1.0) as avg_semantic_score,
                           COALESCE(AVG(latency_ms), 0.0) as avg_latency_ms
                    FROM prompt_records
                """))
                row = res.fetchone()
                return dict(row._mapping) if row else {}

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total_runs,
                       SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed_runs,
                       SUM(CASE WHEN status = 'WARN' THEN 1 ELSE 0 END) as warned_runs,
                       SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed_runs,
                       COALESCE(SUM(net_energy_wh), 0.0) as total_net_energy_wh_saved,
                       COALESCE(SUM(net_carbon_g), 0.0) as total_net_carbon_g_saved,
                       COALESCE(SUM(water_saved_ml), 0.0) as total_water_saved_ml,
                       COALESCE(AVG(semantic_score), 1.0) as avg_semantic_score,
                       COALESCE(AVG(latency_ms), 0.0) as avg_latency_ms
                FROM prompt_records
            """)
            row = cursor.fetchone()
            return dict(row) if row else {}

    # --------------------------------------------------------------------------
    # Modern Time-Series & Telemetry Event Queries
    # --------------------------------------------------------------------------

    def query_events(
        self,
        category: Optional[str] = None,
        routing: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Queries optimization_events table with optional filtering."""
        where_clauses = []
        params = {}

        if category:
            where_clauses.append("prompt_category = :category" if self._pg_engine else "prompt_category = ?")
            params["category"] = category
        if routing:
            where_clauses.append("routing_decision = :routing" if self._pg_engine else "routing_decision = ?")
            params["routing"] = routing
        if status:
            where_clauses.append("status = :status" if self._pg_engine else "status = ?")
            params["status"] = status

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        if self._pg_engine:
            from sqlalchemy import text
            sql = f"""
                SELECT * FROM optimization_events
                {where_sql}
                ORDER BY timestamp DESC
                LIMIT :limit OFFSET :offset
            """
            params["limit"] = limit
            params["offset"] = offset
            with self._pg_engine.connect() as conn:
                res = conn.execute(text(sql), params)
                return [dict(row._mapping) for row in res]

        sql = f"""
            SELECT * FROM optimization_events
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        sql_params = list(params.values()) + [limit, offset]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, sql_params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                if isinstance(d.get("stage_breakdown"), str):
                    try:
                        d["stage_breakdown"] = json.loads(d["stage_breakdown"])
                    except Exception:
                        pass
                if isinstance(d.get("token_breakdown"), str):
                    try:
                        d["token_breakdown"] = json.loads(d["token_breakdown"])
                    except Exception:
                        pass
                results.append(d)
            return results

    def get_time_series_aggregates(
        self,
        interval: str = "hour",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Returns aggregated time-series telemetry metrics.
        Utilizes TimescaleDB time_bucket if available; date_trunc in PostgreSQL; or strftime in SQLite.
        """
        if self._pg_engine:
            from sqlalchemy import text
            if self.has_timescaledb:
                bucket_expr = "time_bucket('1 hour', timestamp)" if interval == "hour" else "time_bucket('1 day', timestamp)"
            else:
                bucket_expr = f"date_trunc('{interval}', timestamp)"

            sql = f"""
                SELECT {bucket_expr} AS bucket,
                       COUNT(*) AS total_optimizations,
                       COALESCE(SUM(tokens_saved), 0) AS total_tokens_saved,
                       COALESCE(SUM(modeled_total_energy_j), 0.0) AS total_energy_saved_j,
                       COALESCE(SUM(modeled_carbon_gco2e), 0.0) AS total_carbon_saved_gco2e,
                       COALESCE(AVG(compression_ratio), 1.0) AS avg_compression_ratio,
                       COALESCE(AVG(semantic_similarity), 1.0) AS avg_semantic_similarity,
                       COALESCE(AVG(optimization_latency_ms), 0.0) AS avg_latency_ms
                FROM optimization_events
                GROUP BY bucket
                ORDER BY bucket DESC
                LIMIT :limit
            """
            with self._pg_engine.connect() as conn:
                res = conn.execute(text(sql), {"limit": limit})
                rows = [dict(row._mapping) for row in res]
                for r in rows:
                    if isinstance(r.get("bucket"), datetime):
                        r["bucket"] = r["bucket"].isoformat()
                return rows

        # SQLite strftime implementation
        strftime_fmt = "%Y-%m-%d %H:00:00" if interval == "hour" else "%Y-%m-%d"
        sql = f"""
            SELECT strftime('{strftime_fmt}', timestamp) AS bucket,
                   COUNT(*) AS total_optimizations,
                   COALESCE(SUM(tokens_saved), 0) AS total_tokens_saved,
                   COALESCE(SUM(modeled_total_energy_j), 0.0) AS total_energy_saved_j,
                   COALESCE(SUM(modeled_carbon_gco2e), 0.0) AS total_carbon_saved_gco2e,
                   COALESCE(AVG(compression_ratio), 1.0) AS avg_compression_ratio,
                   COALESCE(AVG(semantic_similarity), 1.0) AS avg_semantic_similarity,
                   COALESCE(AVG(optimization_latency_ms), 0.0) AS avg_latency_ms
            FROM optimization_events
            WHERE timestamp IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_engine_status(self) -> Dict[str, Any]:
        """Returns diagnostic status regarding active persistence backend, hypertable, and record counts."""
        record_count = 0
        event_count = 0

        if self._pg_engine:
            from sqlalchemy import text
            try:
                with self._pg_engine.connect() as conn:
                    record_count = conn.execute(text("SELECT COUNT(*) FROM prompt_records")).scalar() or 0
                    event_count = conn.execute(text("SELECT COUNT(*) FROM optimization_events")).scalar() or 0
            except Exception as e:
                logger.debug("Failed counting PG rows: %s", e)
        else:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM prompt_records")
                    record_count = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM optimization_events")
                    event_count = cursor.fetchone()[0]
            except Exception as e:
                logger.debug("Failed counting SQLite rows: %s", e)

        return {
            "backend": self.engine_type,
            "has_timescaledb": self.has_timescaledb,
            "db_path": self.db_path if self.engine_type == "sqlite" else None,
            "connection_url": self._redact_url(self.requested_url) if self.requested_url else None,
            "prompt_records_count": record_count,
            "optimization_events_count": event_count,
        }

    def seed_demo_data_if_empty(self):
        """Seeds demo data into ledger if empty for dashboard visualization."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM prompt_records")
            cnt = cursor.fetchone()[0]
            if cnt > 0:
                return

        demo_entries = [
            ("a1b2c3d", "alice", "AI Platform", "Llama-3 8B", "US", "Explain in detail...", "Summarize in 3 bullet...", -6, -240.0, -0.048, -480.0, "PASS"),
            ("e5f6g7h", "bob", "Product Search", "Mistral 7B", "EU", "Provide comprehensive...", "List top 3...", -10, -320.0, -0.038, -380.0, "PASS"),
            ("i9j0k1l", "carol", "Customer Care", "Llama-3 8B", "US", "Classify sentiment...", "Classify sentiment + 5 examples...", 50, 180.0, 0.065, 650.0, "WARN"),
            ("m2n3o4p", "dave", "Analytics", "Phi-3 3.8B", "IN", "Think step by step...", "Return JSON with 3 fields...", -20, -180.0, -0.095, -950.0, "PASS"),
            ("q5r6s7t", "eve", "Legal Bot", "Llama-3 70B", "US", "Context: 10 pages...", "Context: 10 pages + 5 examples...", 120, 450.0, 1.250, 12500.0, "FAIL")
        ]

        for e in demo_entries:
            self.record_prompt_review(
                commit_hash=e[0], author=e[1], team=e[2], model_name=e[3], region=e[4],
                old_prompt=e[5], new_prompt=e[6], input_token_delta=e[7],
                predicted_output_token_delta=e[8], carbon_delta_gco2_1k=e[9],
                monthly_carbon_delta_gco2=e[10], status=e[11]
            )
