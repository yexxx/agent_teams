from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class PausedSubagent:
    session_id: str
    run_id: str
    instance_id: str
    role_id: str
    task_id: str | None
    reason: str
    paused_at: datetime


class RunControlManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._run_tasks: dict[str, asyncio.Task[None]] = {}
        self._run_stop_requested: set[str] = set()
        self._instance_tasks: dict[tuple[str, str], asyncio.Task[str]] = {}
        self._instance_context: dict[tuple[str, str], tuple[str, str, str | None]] = {}
        self._subagent_stop_requested: set[tuple[str, str]] = set()
        self._paused_by_session: dict[str, PausedSubagent] = {}

    def register_run_task(
        self,
        *,
        run_id: str,
        session_id: str,
        task: asyncio.Task[None],
    ) -> None:
        with self._lock:
            self._run_tasks[run_id] = task
            self._run_stop_requested.discard(run_id)

    def unregister_run_task(self, run_id: str) -> None:
        with self._lock:
            self._run_tasks.pop(run_id, None)
            self._run_stop_requested.discard(run_id)

    def request_run_stop(self, run_id: str) -> bool:
        with self._lock:
            task = self._run_tasks.get(run_id)
            self._run_stop_requested.add(run_id)
            if task is not None and not task.done():
                task.cancel()
            for (rid, _), inst_task in list(self._instance_tasks.items()):
                if rid == run_id and not inst_task.done():
                    inst_task.cancel()
            return task is not None

    def is_run_stop_requested(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._run_stop_requested

    def register_instance_task(
        self,
        *,
        run_id: str,
        session_id: str,
        instance_id: str,
        role_id: str,
        task_id: str | None,
        task: asyncio.Task[str],
    ) -> None:
        key = (run_id, instance_id)
        with self._lock:
            self._instance_tasks[key] = task
            self._instance_context[key] = (session_id, role_id, task_id)

    def unregister_instance_task(self, *, run_id: str, instance_id: str) -> None:
        key = (run_id, instance_id)
        with self._lock:
            self._instance_tasks.pop(key, None)
            self._instance_context.pop(key, None)

    def request_subagent_stop(self, *, run_id: str, instance_id: str) -> PausedSubagent | None:
        key = (run_id, instance_id)
        with self._lock:
            context = self._instance_context.get(key)
            if context is None:
                return None
            session_id, role_id, task_id = context
            paused = PausedSubagent(
                session_id=session_id,
                run_id=run_id,
                instance_id=instance_id,
                role_id=role_id,
                task_id=task_id,
                reason='stopped_by_user',
                paused_at=datetime.now(tz=timezone.utc),
            )
            self._paused_by_session[session_id] = paused
            self._subagent_stop_requested.add(key)
            task = self._instance_tasks.get(key)
            if task is not None and not task.done():
                task.cancel()
            return paused

    def pause_subagent(
        self,
        *,
        session_id: str,
        run_id: str,
        instance_id: str,
        role_id: str,
        task_id: str | None,
        reason: str = 'stopped_by_user',
    ) -> PausedSubagent:
        paused = PausedSubagent(
            session_id=session_id,
            run_id=run_id,
            instance_id=instance_id,
            role_id=role_id,
            task_id=task_id,
            reason=reason,
            paused_at=datetime.now(tz=timezone.utc),
        )
        with self._lock:
            self._paused_by_session[session_id] = paused
            self._subagent_stop_requested.add((run_id, instance_id))
        return paused

    def is_subagent_stop_requested(self, *, run_id: str, instance_id: str) -> bool:
        with self._lock:
            return (run_id, instance_id) in self._subagent_stop_requested

    def get_paused_subagent(self, session_id: str) -> PausedSubagent | None:
        with self._lock:
            return self._paused_by_session.get(session_id)

    def is_subagent_paused(self, *, session_id: str, instance_id: str) -> bool:
        with self._lock:
            paused = self._paused_by_session.get(session_id)
            return paused is not None and paused.instance_id == instance_id

    def release_paused_subagent(
        self,
        *,
        session_id: str,
        instance_id: str | None = None,
    ) -> PausedSubagent | None:
        with self._lock:
            paused = self._paused_by_session.get(session_id)
            if paused is None:
                return None
            if instance_id is not None and paused.instance_id != instance_id:
                return None
            self._paused_by_session.pop(session_id, None)
            self._subagent_stop_requested.discard((paused.run_id, paused.instance_id))
            return paused

    def clear_paused_subagent_for_run(self, run_id: str) -> None:
        with self._lock:
            for session_id, paused in list(self._paused_by_session.items()):
                if paused.run_id == run_id:
                    self._paused_by_session.pop(session_id, None)
                    self._subagent_stop_requested.discard((paused.run_id, paused.instance_id))
