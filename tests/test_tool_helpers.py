import asyncio
from dataclasses import dataclass

from agent_teams.core.enums import RunEventType
from agent_teams.tools.tool_helpers import execute_tool


class _FakeRunEventHub:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


class _FakeApprovalManager:
    def __init__(self, wait_result: tuple[str, str] | None = None, timeout: bool = False) -> None:
        self.wait_result = wait_result
        self.timeout = timeout

    def open_approval(self, **kwargs) -> None:
        return None

    def wait_for_approval(self, **kwargs):
        if self.timeout:
            raise TimeoutError('timeout')
        return self.wait_result or ('approve', '')

    def close_approval(self, **kwargs) -> None:
        return None


@dataclass(frozen=True)
class _FakePolicy:
    needs_approval: bool
    timeout_seconds: float = 0.01

    def requires_approval(self, tool_name: str) -> bool:
        return self.needs_approval


class _FakeDeps:
    def __init__(self, *, manager: _FakeApprovalManager, policy: _FakePolicy) -> None:
        self.run_id = 'run-1'
        self.trace_id = 'trace-1'
        self.task_id = 'task-1'
        self.session_id = 'session-1'
        self.instance_id = 'inst-1'
        self.role_id = 'spec_coder'
        self.run_event_hub = _FakeRunEventHub()
        self.tool_approval_manager = manager
        self.tool_approval_policy = policy


class _FakeCtx:
    def __init__(self, deps: _FakeDeps) -> None:
        self.deps = deps


def test_execute_tool_returns_standard_envelope() -> None:
    deps = _FakeDeps(
        manager=_FakeApprovalManager(wait_result=('approve', '')),
        policy=_FakePolicy(needs_approval=False),
    )
    ctx = _FakeCtx(deps)
    result = asyncio.run(
        execute_tool(
            ctx,
            tool_name='read',
            args_summary={'path': 'README.md'},
            action=lambda: 'hello',
        )
    )
    assert result['ok'] is True
    assert result['tool'] == 'read'
    assert result['data'] == 'hello'
    assert result['error'] is None
    assert result['meta']['approval_required'] is False


def test_execute_tool_returns_denied_error_when_approval_rejected() -> None:
    deps = _FakeDeps(
        manager=_FakeApprovalManager(wait_result=('deny', 'not safe')),
        policy=_FakePolicy(needs_approval=True),
    )
    ctx = _FakeCtx(deps)
    result = asyncio.run(
        execute_tool(
            ctx,
            tool_name='write',
            args_summary={'path': 'a.txt'},
            action=lambda: 'should_not_run',
        )
    )
    assert result['ok'] is False
    assert result['error']['type'] == 'approval_denied'
    assert result['meta']['approval_required'] is True
    assert result['meta']['approval_status'] == 'deny'
    assert any(e.event_type == RunEventType.TOOL_APPROVAL_REQUESTED for e in deps.run_event_hub.events)
    assert any(e.event_type == RunEventType.TOOL_APPROVAL_RESOLVED for e in deps.run_event_hub.events)


def test_execute_tool_returns_timeout_error_when_approval_times_out() -> None:
    deps = _FakeDeps(
        manager=_FakeApprovalManager(timeout=True),
        policy=_FakePolicy(needs_approval=True, timeout_seconds=0.01),
    )
    ctx = _FakeCtx(deps)
    result = asyncio.run(
        execute_tool(
            ctx,
            tool_name='shell',
            args_summary={'command': 'echo hi'},
            action=lambda: 'should_not_run',
        )
    )
    assert result['ok'] is False
    assert result['error']['type'] == 'approval_timeout'
    assert result['meta']['approval_status'] == 'timeout'

