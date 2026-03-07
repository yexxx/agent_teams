from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agent_teams.state.db import open_sqlite


class WorkflowGraphRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    root_task_id: str = Field(min_length=1)
    graph: dict[str, object]
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class WorkflowGraphRepository:
    def __init__(self, db_path: Path) -> None:
        self._conn = open_sqlite(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_graphs (
                workflow_id  TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                session_id   TEXT NOT NULL,
                root_task_id TEXT NOT NULL,
                graph_json   TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_graphs_run ON workflow_graphs(run_id, created_at ASC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_graphs_session ON workflow_graphs(session_id, created_at ASC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_graphs_root_task ON workflow_graphs(root_task_id)"
        )
        self._conn.commit()

    def upsert(
        self,
        *,
        workflow_id: str,
        run_id: str,
        session_id: str,
        root_task_id: str,
        graph: dict[str, object],
    ) -> WorkflowGraphRecord:
        now = datetime.now(tz=timezone.utc).isoformat()
        existing = self.get(workflow_id)
        created_at = existing.created_at.isoformat() if existing is not None else now
        self._conn.execute(
            """
            INSERT INTO workflow_graphs(workflow_id, run_id, session_id, root_task_id, graph_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id)
            DO UPDATE SET
                run_id=excluded.run_id,
                session_id=excluded.session_id,
                root_task_id=excluded.root_task_id,
                graph_json=excluded.graph_json,
                updated_at=excluded.updated_at
            """,
            (
                workflow_id,
                run_id,
                session_id,
                root_task_id,
                json.dumps(graph, ensure_ascii=False),
                created_at,
                now,
            ),
        )
        self._conn.commit()
        record = self.get(workflow_id)
        if record is None:
            raise RuntimeError(f"Failed to persist workflow graph {workflow_id}")
        return record

    def get(self, workflow_id: str) -> WorkflowGraphRecord | None:
        row = self._conn.execute(
            "SELECT * FROM workflow_graphs WHERE workflow_id=?",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self._to_record(row)

    def get_by_run(self, run_id: str) -> tuple[WorkflowGraphRecord, ...]:
        rows = self._conn.execute(
            "SELECT * FROM workflow_graphs WHERE run_id=? ORDER BY created_at ASC",
            (run_id,),
        ).fetchall()
        return tuple(self._to_record(row) for row in rows)

    def list_by_session(self, session_id: str) -> tuple[WorkflowGraphRecord, ...]:
        rows = self._conn.execute(
            "SELECT * FROM workflow_graphs WHERE session_id=? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return tuple(self._to_record(row) for row in rows)

    def delete_by_session(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM workflow_graphs WHERE session_id=?", (session_id,)
        )
        self._conn.commit()

    def _to_record(self, row: sqlite3.Row) -> WorkflowGraphRecord:
        return WorkflowGraphRecord(
            workflow_id=str(row["workflow_id"]),
            run_id=str(row["run_id"]),
            session_id=str(row["session_id"]),
            root_task_id=str(row["root_task_id"]),
            graph=json.loads(str(row["graph_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
