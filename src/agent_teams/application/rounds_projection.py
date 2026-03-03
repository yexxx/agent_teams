from __future__ import annotations

import json
from typing import Any, Callable

from agent_teams.core.enums import RunEventType, ScopeType
from agent_teams.core.models import ScopeRef


def collect_pending_tool_approvals(
    parsed_events: list[tuple[dict, dict[str, Any]]],
) -> dict[str, list[dict[str, str]]]:
    by_run_call: dict[str, dict[str, dict[str, Any]]] = {}

    for ev, payload in parsed_events:
        run_id = ev["trace_id"]
        event_type = ev.get("event_type")
        tool_call_id = payload.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            continue

        run_map = by_run_call.setdefault(run_id, {})
        if event_type == RunEventType.TOOL_APPROVAL_REQUESTED.value:
            entry = run_map.setdefault(
                tool_call_id,
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": str(payload.get("tool_name") or ""),
                    "args_preview": str(payload.get("args_preview") or ""),
                    "role_id": str(payload.get("role_id") or ""),
                    "instance_id": str(payload.get("instance_id") or ev.get("instance_id") or ""),
                    "requested_at": str(ev.get("occurred_at") or ""),
                    "status": "requested",
                    "feedback": "",
                    "has_tool_result": False,
                },
            )
            entry["tool_name"] = str(payload.get("tool_name") or entry["tool_name"])
            entry["args_preview"] = str(payload.get("args_preview") or entry["args_preview"])
            entry["role_id"] = str(payload.get("role_id") or entry["role_id"])
            entry["instance_id"] = str(payload.get("instance_id") or entry["instance_id"])
            entry["requested_at"] = str(ev.get("occurred_at") or entry["requested_at"])
            entry["status"] = "requested"
        elif event_type == RunEventType.TOOL_APPROVAL_RESOLVED.value:
            entry = run_map.get(tool_call_id)
            if entry is None:
                continue
            action = payload.get("action")
            if isinstance(action, str) and action:
                entry["status"] = action
            feedback = payload.get("feedback")
            if isinstance(feedback, str) and feedback:
                entry["feedback"] = feedback
        elif event_type == RunEventType.TOOL_RESULT.value:
            entry = run_map.get(tool_call_id)
            if entry is not None:
                entry["has_tool_result"] = True

    result: dict[str, list[dict[str, str]]] = {}
    for run_id, run_calls in by_run_call.items():
        pending: list[dict[str, str]] = []
        for entry in run_calls.values():
            if entry.get("has_tool_result"):
                continue
            if str(entry.get("status") or "requested") != "requested":
                continue
            pending.append(
                {
                    "tool_call_id": str(entry.get("tool_call_id") or ""),
                    "tool_name": str(entry.get("tool_name") or ""),
                    "args_preview": str(entry.get("args_preview") or ""),
                    "role_id": str(entry.get("role_id") or ""),
                    "instance_id": str(entry.get("instance_id") or ""),
                    "requested_at": str(entry.get("requested_at") or ""),
                    "status": str(entry.get("status") or "requested"),
                    "feedback": str(entry.get("feedback") or ""),
                }
            )
        pending.sort(key=lambda item: item.get("requested_at") or "")
        if pending:
            result[run_id] = pending
    return result


def build_session_rounds(
    *,
    session_id: str,
    event_log,
    agent_repo,
    task_repo,
    shared_store,
    get_session_messages: Callable[[str], list[dict]],
) -> list[dict]:
    events = event_log.list_by_session(session_id)
    parsed_events: list[tuple[dict, dict[str, Any]]] = []
    for ev in events:
        try:
            payload = json.loads(ev["payload_json"])
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        parsed_events.append((ev, payload))

    rounds_map: dict[str, dict] = {}
    by_run_instance_role: dict[str, dict[str, str]] = {}
    by_run_role_instance: dict[str, dict[str, str]] = {}
    pending_by_run = collect_pending_tool_approvals(parsed_events)

    for ev, payload in parsed_events:
        run_id = ev["trace_id"]
        ev_instance = ev.get("instance_id") or payload.get("instance_id")
        ev_role = payload.get("role_id")
        if isinstance(ev_instance, str) and isinstance(ev_role, str):
            by_run_instance_role.setdefault(run_id, {})[ev_instance] = ev_role
            by_run_role_instance.setdefault(run_id, {}).setdefault(ev_role, ev_instance)

    for rec in agent_repo.list_by_session(session_id):
        run_map = by_run_instance_role.setdefault(rec.run_id, {})
        run_map.setdefault(rec.instance_id, rec.role_id)
        role_map = by_run_role_instance.setdefault(rec.run_id, {})
        role_map.setdefault(rec.role_id, rec.instance_id)

    for ev in events:
        run_id = ev["trace_id"]
        if run_id not in rounds_map:
            rounds_map[run_id] = {
                "run_id": run_id,
                "created_at": ev["occurred_at"],
                "intent": None,
                "coordinator_messages": [],
                "pending_tool_approvals": pending_by_run.get(run_id, []),
                "workflows": [],
                "instance_role_map": by_run_instance_role.get(run_id, {}),
                "role_instance_map": by_run_role_instance.get(run_id, {}),
            }
        if ev["occurred_at"] < rounds_map[run_id]["created_at"]:
            rounds_map[run_id]["created_at"] = ev["occurred_at"]

    messages = get_session_messages(session_id)
    for msg in messages:
        run_id = msg["trace_id"]
        round_data = rounds_map.get(run_id)
        if round_data is None:
            continue

        role_id = by_run_instance_role.get(run_id, {}).get(msg["instance_id"])
        msg["role_id"] = role_id

        if msg["role"] == "user":
            content = msg.get("message", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            for pt in parts:
                if not isinstance(pt, dict):
                    continue
                if pt.get("part_kind") == "user-prompt" and not round_data["intent"]:
                    round_data["intent"] = pt.get("content", "")
                    break

        if role_id == "coordinator_agent":
            round_data["coordinator_messages"].append(msg)

    for task in task_repo.list_by_session(session_id):
        run_id = task.envelope.trace_id
        round_data = rounds_map.get(run_id)
        if round_data is None:
            continue
        scope = ScopeRef(scope_type=ScopeType.TASK, scope_id=task.envelope.task_id)
        wf_str = shared_store.get_state(scope, "workflow_graph")
        if wf_str:
            round_data["workflows"].append(json.loads(wf_str))

    return sorted(list(rounds_map.values()), key=lambda x: x["created_at"], reverse=True)


def paginate_rounds(
    rounds: list[dict],
    *,
    limit: int = 8,
    cursor_run_id: str | None = None,
) -> dict[str, object]:
    safe_limit = max(1, min(limit, 50))

    start = 0
    if cursor_run_id:
        for idx, item in enumerate(rounds):
            if item.get("run_id") == cursor_run_id:
                start = idx + 1
                break

    items = rounds[start : start + safe_limit]
    next_index = start + safe_limit
    has_more = next_index < len(rounds)
    next_cursor = items[-1]["run_id"] if has_more and items else None
    return {
        "items": items,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def find_round_by_run_id(
    rounds: list[dict],
    *,
    session_id: str,
    run_id: str,
) -> dict:
    for round_item in rounds:
        if round_item["run_id"] == run_id:
            return round_item
    raise KeyError(f"Round {run_id} not found in session {session_id}")
