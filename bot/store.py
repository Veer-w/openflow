from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ExecutionRecord, Workflow


class SQLiteStore:
    def __init__(self, db_path: str = "data/workflows.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
                )
                """
            )

    def create_workflow(self, workflow: Workflow) -> Workflow:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO workflows (id, name, definition, created_at) VALUES (?, ?, ?, ?)",
                (
                    workflow.id,
                    workflow.name,
                    workflow.model_dump_json(),
                    workflow.created_at.isoformat(),
                ),
            )
        return workflow

    def update_workflow(self, workflow_id: str, workflow: Workflow) -> Workflow | None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if not existing:
                return None
            conn.execute(
                "UPDATE workflows SET name = ?, definition = ? WHERE id = ?",
                (
                    workflow.name,
                    workflow.model_dump_json(),
                    workflow_id,
                ),
            )
        return workflow

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT definition FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()

        if not row:
            return None
        return Workflow.model_validate_json(row["definition"])

    def list_workflows(self) -> list[Workflow]:
        with self._connect() as conn:
            rows = conn.execute("SELECT definition FROM workflows ORDER BY created_at DESC").fetchall()

        return [Workflow.model_validate_json(row["definition"]) for row in rows]

    def create_execution(self, workflow_id: str) -> ExecutionRecord:
        execution = ExecutionRecord(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO executions (id, workflow_id, status, started_at, finished_at, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution.id,
                    execution.workflow_id,
                    execution.status,
                    execution.started_at.isoformat(),
                    None,
                    None,
                    None,
                ),
            )
        return execution

    def finish_execution(
        self,
        execution_id: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        result_blob = json.dumps(result) if result is not None else None

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE executions
                SET status = ?, finished_at = ?, result = ?, error = ?
                WHERE id = ?
                """,
                (status, finished_at, result_blob, error, execution_id),
            )

    def get_execution(self, execution_id: str) -> ExecutionRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM executions WHERE id = ?",
                (execution_id,),
            ).fetchone()

        if not row:
            return None

        return ExecutionRecord(
            id=row["id"],
            workflow_id=row["workflow_id"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )
