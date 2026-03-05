from __future__ import annotations

import httpx


def test_create_trigger_and_ingest_webhook_event(api_client: httpx.Client) -> None:
    create_response = api_client.post(
        "/api/triggers",
        json={
            "name": "repo_push_integration",
            "source_type": "webhook",
            "source_config": {"provider": "github"},
            "auth_policies": [{"mode": "none"}],
        },
    )
    create_response.raise_for_status()
    trigger = create_response.json()
    trigger_id = trigger.get("trigger_id")
    public_token = trigger.get("public_token")
    assert isinstance(trigger_id, str) and trigger_id
    assert isinstance(public_token, str) and public_token

    webhook_response = api_client.post(
        f"/api/triggers/webhooks/{public_token}",
        json={
            "event_key": "integration-evt-1",
            "payload": {"action": "push"},
            "metadata": {"source": "integration"},
        },
    )
    webhook_response.raise_for_status()
    ingest_result = webhook_response.json()
    assert ingest_result["accepted"] is True
    assert ingest_result["duplicate"] is False

    events_response = api_client.get(f"/api/triggers/{trigger_id}/events")
    events_response.raise_for_status()
    body = events_response.json()
    items = body.get("items")
    assert isinstance(items, list)
    assert len(items) >= 1
    assert items[0]["event_key"] == "integration-evt-1"


def test_webhook_auth_rejects_missing_header_token(api_client: httpx.Client) -> None:
    create_response = api_client.post(
        "/api/triggers",
        json={
            "name": "secure_webhook_integration",
            "source_type": "webhook",
            "auth_policies": [
                {
                    "mode": "header_token",
                    "header_name": "X-Trigger-Token",
                    "token": "abc123",
                }
            ],
        },
    )
    create_response.raise_for_status()
    public_token = create_response.json().get("public_token")
    assert isinstance(public_token, str) and public_token

    response = api_client.post(
        f"/api/triggers/webhooks/{public_token}",
        json={"payload": {"action": "push"}},
    )
    assert response.status_code == 403
