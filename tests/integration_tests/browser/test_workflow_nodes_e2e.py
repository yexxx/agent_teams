from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, Page, Playwright, expect, sync_playwright

from integration_tests.support.environment import IntegrationEnvironment
from integration_tests.support.api_helpers import (
    create_run,
    create_session,
    dispatch_task,
    new_session_id,
    stream_run_until_terminal,
)


def test_subagent_selector_lists_unique_roles(
    api_client: httpx.Client,
    integration_env: IntegrationEnvironment,
    page: Page,
) -> None:
    session_id = prepare_task_run(api_client)

    page.goto(integration_env.api_base_url, wait_until="networkidle")
    select_session(page, session_id)

    selector = page.locator("#subagent-role-select")
    expect(selector).to_be_visible(timeout=15000)
    expect(selector.locator("option")).to_have_count(2, timeout=15000)

    option_labels = [
        selector.locator("option").nth(index).inner_text().strip() for index in range(2)
    ]
    assert len(option_labels) == 2


def test_switching_roles_keeps_single_visible_panel(
    api_client: httpx.Client,
    integration_env: IntegrationEnvironment,
    page: Page,
) -> None:
    session_id = prepare_task_run(api_client)

    page.goto(integration_env.api_base_url, wait_until="networkidle")
    select_session(page, session_id)

    selector = page.locator("#subagent-role-select")
    expect(selector).to_be_visible(timeout=15000)

    first_label = selector.locator("option").nth(0).inner_text().strip().split(" · ")[0]
    second_label = (
        selector.locator("option").nth(1).inner_text().strip().split(" · ")[0]
    )

    selector.select_option(first_label)
    first_panel = page.locator(".agent-panel").filter(
        has=page.locator(".panel-role", has_text=role_label(first_label))
    )
    expect(first_panel).to_be_visible(timeout=15000)

    selector.select_option(second_label)
    second_panel = page.locator(".agent-panel").filter(
        has=page.locator(".panel-role", has_text=role_label(second_label))
    )
    expect(second_panel).to_be_visible(timeout=15000)
    expect(first_panel).not_to_be_visible()


@pytest.fixture()
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    chromium_path = Path(playwright.chromium.executable_path)
    if not chromium_path.exists():
        pytest.skip(
            "Chromium is not installed. Run: uv run playwright install chromium"
        )
    browser = playwright.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as p:
        yield p


def prepare_task_run(client: httpx.Client) -> str:
    role_ids = pick_subagent_roles(client)
    session_id = create_session(client, session_id=new_session_id("session-ui"))
    run_id = create_run(
        client,
        session_id=session_id,
        intent="Prepare subagent session rail data",
        execution_mode="manual",
    )
    _ = stream_run_until_terminal(client, run_id=run_id)

    response = client.post(
        f"/api/tasks/runs/{run_id}",
        json={
            "tasks": [
                {
                    "title": "Write code",
                    "objective": "Return a short coding status update.",
                    "role_id": role_ids[0],
                },
                {
                    "title": "Review code",
                    "objective": "Return a short review status update.",
                    "role_id": role_ids[1],
                },
            ],
            "auto_dispatch": False,
        },
    )
    response.raise_for_status()
    payload = response.json()
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise AssertionError(f"Invalid task payload: {payload}")

    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("task_id") or "")
        if not task_id:
            raise AssertionError(f"Missing task_id in payload: {payload}")
        dispatch = dispatch_task(client, task_id=task_id)
        if dispatch.get("ok") is not True:
            raise AssertionError(f"Task dispatch failed: {dispatch}")
    return session_id


def select_session(page: Page, session_id: str) -> None:
    target = page.locator(".session-item").filter(
        has=page.locator(".session-id", has_text=session_id)
    )
    expect(target).to_be_visible(timeout=20000)
    target.click()


def pick_subagent_roles(client: httpx.Client) -> tuple[str, str]:
    response = client.get("/api/roles")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise AssertionError(f"Invalid roles payload: {payload}")
    role_ids = [
        str(item.get("role_id") or "")
        for item in payload
        if isinstance(item, dict)
        and str(item.get("role_id") or "") != "coordinator_agent"
    ]
    if len(role_ids) < 2:
        pytest.skip("Integration role set does not expose at least two delegated roles")
    return role_ids[0], role_ids[1]


def role_label(role_id: str) -> str:
    return " ".join(part.capitalize() for part in role_id.split("_") if part)
