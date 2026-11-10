import sqlite3
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class LedgerRecord:
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


class PromptLedger:
    """
    Deliverable D5: Prompt Carbon Ledger Database Manager.
    Manages local SQLite database for per-version tracking, team leaderboards,
    model energy comparisons, and cumulative carbon debt metrics.
    """

    def __init__(self, db_path: str = "prompt_ledger.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the SQLite schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
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
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

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
        """Inserts a new prompt review record into the ledger."""
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

    def get_recent_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent ledger records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM prompt_records
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_team_leaderboard(self) -> List[Dict[str, Any]]:
        """Calculates carbon savings / additions per team."""
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
