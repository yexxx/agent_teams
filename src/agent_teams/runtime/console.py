from __future__ import annotations

import json
import logging

from agent_teams.core.types import JsonObject
from agent_teams.runtime.logging import get_logger, log_event

_debug_enabled = False
_open_model_stream_role_id: str | None = None
logger = get_logger(__name__)

ROLE_LABELS = {
    'coordinator_agent': 'Coordinator Agent',
    'spec_spec': 'Spec Spec',
    'spec_design': 'Spec Design',
    'spec_coder': 'Spec Coder',
    'spec_verify': 'Spec Verify',
}


def set_debug(enabled: bool) -> None:
    global _debug_enabled
    _debug_enabled = enabled


def is_debug() -> bool:
    return _debug_enabled


def role_label(role_id: str) -> str:
    if role_id in ROLE_LABELS:
        return ROLE_LABELS[role_id]
    return role_id.replace('_', ' ').title()


def log_debug(message: str) -> None:
    if _debug_enabled:
        close_model_stream()
        print(message)
    log_event(logger, logging.DEBUG, event='runtime.debug', message=message)


def log_model_output(role_id: str, message: str) -> None:
    close_model_stream()
    if _debug_enabled:
        print(f'[{role_label(role_id)}] {message}')
    log_event(
        logger,
        logging.INFO,
        event='model.output',
        message='Model output emitted',
        payload={'role_id': role_id, 'output': _safe_json(message)},
    )


def log_tool_call(role_id: str, tool_name: str, params: JsonObject) -> None:
    close_model_stream()
    short = _safe_json(params)
    if _debug_enabled:
        print(f'[{role_label(role_id)}] tool call [{tool_name} {short}]')
    log_event(
        logger,
        logging.INFO,
        event='tool.call.started',
        message='Tool call started',
        payload={'role_id': role_id, 'tool_name': tool_name, 'params': short},
    )


def log_tool_error(role_id: str, payload: str) -> None:
    close_model_stream()
    if _debug_enabled:
        print(f'[{role_label(role_id)}] tool error {payload}')
    log_event(
        logger,
        logging.ERROR,
        event='tool.call.failed',
        message='Tool call failed',
        payload={'role_id': role_id, 'detail': payload},
    )


def log_model_stream_chunk(role_id: str, text: str) -> None:
    global _open_model_stream_role_id
    if _debug_enabled:
        if _open_model_stream_role_id != role_id:
            close_model_stream()
            print(f'[{role_label(role_id)}] ', end='', flush=True)
            _open_model_stream_role_id = role_id
        print(text, end='', flush=True)


def close_model_stream() -> None:
    global _open_model_stream_role_id
    if _open_model_stream_role_id is not None:
        print()
        _open_model_stream_role_id = None


def _safe_json(value: object) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    if len(text) > 300:
        return text[:300] + '...(truncated)'
    return text
