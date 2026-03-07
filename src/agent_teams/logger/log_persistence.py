from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import cast, override

from agent_teams.shared_types.json_types import JsonObject
from agent_teams.state.log_repo import LogRepository


class PersistentLogHandler(logging.Handler):
    def __init__(
        self,
        *,
        db_path: Path,
        queue_size: int = 5000,
        flush_batch_size: int = 200,
        flush_interval_seconds: float = 0.3,
    ) -> None:
        super().__init__()
        self._repo: LogRepository = LogRepository(db_path=db_path)
        self._queue: Queue[JsonObject] = Queue(maxsize=queue_size)
        self._flush_batch_size: int = flush_batch_size
        self._flush_interval_seconds: float = flush_interval_seconds
        self._pending_rows: list[JsonObject] = []
        self._stop: Event = Event()
        self._worker: Thread = Thread(
            target=self._run, name="log-persistence-worker", daemon=True
        )
        self._worker.start()

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = self.format(record)
            parsed_raw = cast(object, json.loads(rendered))
            parsed: JsonObject = (
                cast(JsonObject, parsed_raw)
                if isinstance(parsed_raw, dict)
                else {"message": rendered, "level": record.levelname}
            )
            self._queue.put_nowait(parsed)
        except Full:
            # Intentionally drop when saturated to avoid blocking business flows.
            return
        except Exception:
            return

    @override
    def close(self) -> None:
        self._stop.set()
        self._worker.join(timeout=1.0)
        for _ in range(8):
            self._drain_once(force=True)
            if not self._pending_rows and self._queue.empty():
                break
        super().close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._drain_once(force=False)
            except Exception:
                time.sleep(self._flush_interval_seconds)

    def _drain_once(self, *, force: bool) -> None:
        rows = list(self._pending_rows)
        self._pending_rows = []
        timeout = 0.0 if force else self._flush_interval_seconds
        if not rows:
            try:
                first = self._queue.get(timeout=timeout)
                rows.append(first)
            except Empty:
                return

        while len(rows) < self._flush_batch_size:
            try:
                rows.append(self._queue.get_nowait())
            except Empty:
                break

        try:
            self._repo.append_many(rows)
        except sqlite3.OperationalError as exc:
            self._pending_rows = rows + self._pending_rows
            if _is_locked_error(exc):
                if not force:
                    time.sleep(min(self._flush_interval_seconds, 0.1))
                return
            raise
        except Exception:
            self._pending_rows = rows + self._pending_rows
            raise


def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return (
        "database is locked" in message
        or "database table is locked" in message
        or "another row available" in message
    )
