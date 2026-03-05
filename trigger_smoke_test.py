from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE_URL}{path}", method=method, data=body, headers=headers)
    with urlopen(req, timeout=15.0) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object for {path}")
    return data


def main() -> None:
    suffix = uuid4().hex[:8]
    trigger_name = f"smoke_trigger_{suffix}"

    created = request_json(
        "POST",
        "/api/triggers",
        {
            "name": trigger_name,
            "display_name": f"Smoke Trigger {suffix}",
            "source_type": "webhook",
            "source_config": {"scenario": "smoke"},
            "auth_policies": [{"mode": "none"}],
            "enabled": True,
        },
    )
    trigger_id = str(created["trigger_id"])
    public_token = str(created["public_token"])

    event_key = f"smoke_event_{suffix}"
    ingested = request_json(
        "POST",
        f"/api/triggers/webhooks/{public_token}",
        {
            "event_key": event_key,
            "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
            "payload": {"message": "trigger smoke event"},
            "metadata": {"source": "trigger_smoke_test.py"},
        },
    )
    if ingested.get("accepted") is not True:
        raise RuntimeError(f"Ingest failed: {ingested}")

    events = request_json("GET", f"/api/triggers/{trigger_id}/events?limit=10")
    items = events.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"Invalid events payload: {events}")
    if not any(isinstance(item, dict) and item.get("event_key") == event_key for item in items):
        raise RuntimeError(f"Event {event_key} not found in trigger events")

    print("Trigger smoke test passed")
    print(f"trigger_id={trigger_id}")
    print(f"event_key={event_key}")


if __name__ == "__main__":
    main()
