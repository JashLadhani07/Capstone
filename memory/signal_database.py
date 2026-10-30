
##############################################################################
# memory/signal_database.py
#
# PURPOSE:
#   Local SQLite storage for signals and HITL reviews.
#
# DATABASE:
#   data/mosaic_signals.db
#
# TABLES:
#   1. signals
#   2. hitl_reviews
##############################################################################

import sqlite3
import json
from pathlib import Path
from typing import Any
from contextlib import contextmanager


class SignalDatabase:

    def __init__(self):
        self.db_path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "mosaic_signals.db"
        )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def initialize(self):

        with self._connect() as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    nct_id TEXT NOT NULL DEFAULT '',
                    agent TEXT NOT NULL DEFAULT '',
                    signal_type TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    evidence TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    )
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS hitl_reviews (
                    review_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    decision TEXT NOT NULL DEFAULT 'pending',
                    reviewer TEXT,
                    rejection_reason TEXT DEFAULT '',
                    edit_summary TEXT DEFAULT '',
                    reviewed_at TEXT,
                    FOREIGN KEY (signal_id)
                        REFERENCES signals(signal_id)
                        ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_created
                ON signals(created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_agent
                ON signals(agent)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_decision
                ON hitl_reviews(decision)
            """)

    # ------------------------------------------------------------------
    # SIGNAL OPERATIONS
    # ------------------------------------------------------------------

    def save_signal(self, signal_id: str, signal: dict, status: str):

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO signals (
                    signal_id, nct_id, agent, signal_type,
                    summary, evidence, confidence, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    signal.get("nct_id", ""),
                    signal.get("agent", ""),
                    signal.get("signal_type", ""),
                    signal.get("summary", ""),
                    json.dumps(
                        signal.get("evidence", []),
                        ensure_ascii=False,
                        default=str,
                    ),
                    float(signal.get("confidence", 0.0)),
                    status,
                ),
            )

    def get_signals(
        self,
        filters: dict | None = None,
        limit: int = 50,
        agent: str | None = None,
        signal_type: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Retrieve signals using optional filters."""

        filters = filters or {}

        agent = filters.get("agent", agent)
        signal_type = filters.get("signal_type", signal_type)
        status = filters.get("status", status)

        conditions = []
        params = []

        if agent:
            conditions.append("agent = ?")
            params.append(agent)

        if signal_type:
            conditions.append("signal_type = ?")
            params.append(signal_type)

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = (
            f"WHERE {' AND '.join(conditions)}"
            if conditions else ""
        )

        limit = max(1, min(int(limit), 200))
        params.append(limit)

        query = f"""
            SELECT *
            FROM signals
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._format_signal(row) for row in rows]

    def get_signal(self, signal_id: str) -> dict | None:

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()

        return self._format_signal(row) if row else None

    # ------------------------------------------------------------------
    # REVIEW QUEUE OPERATIONS
    # ------------------------------------------------------------------

    def create_review(
        self,
        queue_id: str,
        signal_id: str,
        signal: dict,
    ):

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO signals (
                    signal_id, nct_id, agent, signal_type,
                    summary, evidence, confidence, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    signal.get("nct_id", ""),
                    signal.get("agent", ""),
                    signal.get("signal_type", ""),
                    signal.get("summary", ""),
                    json.dumps(
                        signal.get("evidence", []),
                        ensure_ascii=False,
                        default=str,
                    ),
                    float(signal.get("confidence", 0.0)),
                    "pending",
                ),
            )

            conn.execute(
                """
                INSERT INTO hitl_reviews (
                    review_id, signal_id, decision
                )
                VALUES (?, ?, 'pending')
                """,
                (queue_id, signal_id),
            )

    def get_review_queue(self) -> list[dict]:

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    hr.review_id,
                    hr.signal_id,
                    s.agent,
                    s.signal_type,
                    s.summary,
                    s.confidence,
                    s.nct_id,
                    hr.decision,
                    hr.reviewed_at
                FROM hitl_reviews hr
                JOIN signals s
                    ON hr.signal_id = s.signal_id
                WHERE hr.decision = 'pending'
                ORDER BY s.confidence ASC
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def get_review_stats(self) -> dict:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN decision = 'pending'
                        THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN decision IN ('approve', 'edit')
                        THEN 1 ELSE 0 END) AS approved,
                    SUM(CASE WHEN decision = 'reject'
                        THEN 1 ELSE 0 END) AS rejected
                FROM hitl_reviews
                """
            ).fetchone()

        return {
            "pending": row["pending"] or 0,
            "approved": row["approved"] or 0,
            "rejected": row["rejected"] or 0,
        }

    def process_decision(
        self,
        queue_id: str,
        decision: str,
        reviewer: str,
        rejection_reason: str = "",
        edit_summary: str = "",
    ) -> dict | None:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT s.signal_id, s.agent
                FROM hitl_reviews hr
                JOIN signals s ON hr.signal_id = s.signal_id
                WHERE hr.review_id = ?
                  AND hr.decision = 'pending'
                """,
                (queue_id,),
            ).fetchone()

            if not row:
                return None

            signal_id = row["signal_id"]
            agent = row["agent"]

            new_status = (
                "rejected" if decision == "reject" else "approved"
            )

            conn.execute(
                """
                UPDATE signals
                SET status = ?,
                    summary = CASE
                        WHEN ? = 'edit' AND ? != ''
                        THEN ?
                        ELSE summary
                    END
                WHERE signal_id = ?
                """,
                (
                    new_status,
                    decision,
                    edit_summary,
                    edit_summary,
                    signal_id,
                ),
            )

            conn.execute(
                """
                UPDATE hitl_reviews
                SET decision = ?,
                    reviewer = ?,
                    rejection_reason = ?,
                    edit_summary = ?,
                    reviewed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ', 'now'
                    )
                WHERE review_id = ?
                """,
                (
                    decision,
                    reviewer,
                    rejection_reason,
                    edit_summary,
                    queue_id,
                ),
            )

        return {
            "signal_id": signal_id,
            "agent": agent,
        }

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _format_signal(row: sqlite3.Row) -> dict[str, Any]:

        result = dict(row)

        try:
            result["evidence"] = json.loads(result["evidence"])
        except (json.JSONDecodeError, TypeError):
            result["evidence"] = []

        return result

    def close(self):
        """Connections are closed automatically after each operation."""
        pass
