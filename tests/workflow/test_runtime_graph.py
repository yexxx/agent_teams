from __future__ import annotations

from agent_teams.core.enums import TaskStatus
from agent_teams.core.models import TaskEnvelope, TaskRecord, VerificationPlan
from agent_teams.workflow.runtime_graph import decide_review_action, normalize_strategy


def _record(task_id: str, status: TaskStatus) -> TaskRecord:
    envelope = TaskEnvelope(
        task_id=task_id,
        session_id='s1',
        trace_id='r1',
        parent_task_id='root',
        objective='demo',
        verification=VerificationPlan(checklist=('non_empty_response',)),
    )
    return TaskRecord(
        envelope=envelope,
        status=status,
        assigned_instance_id=None,
        result='',
        error_message='',
    )


def test_normalize_strategy_defaults() -> None:
    strategy = normalize_strategy({})
    assert strategy == {
        'orchestrator': 'ai',
        'planning_mode': 'sop',
        'review_state': 'review',
    }


def test_decide_review_action_finish_when_all_done() -> None:
    graph = {
        'tasks': {
            'spec': {'task_id': 't1'},
            'design': {'task_id': 't2'},
        }
    }
    records = {
        't1': _record('t1', TaskStatus.COMPLETED),
        't2': _record('t2', TaskStatus.COMPLETED),
    }
    assert decide_review_action(graph=graph, task_records=records) == 'finish'


def test_decide_review_action_replan_on_failure() -> None:
    graph = {
        'tasks': {
            'spec': {'task_id': 't1'},
            'design': {'task_id': 't2'},
        }
    }
    records = {
        't1': _record('t1', TaskStatus.COMPLETED),
        't2': _record('t2', TaskStatus.FAILED),
    }
    assert decide_review_action(graph=graph, task_records=records) == 'replan'
