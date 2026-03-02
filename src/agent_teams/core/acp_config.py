from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AcpProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["stdio"] = "stdio"
    protocol: Literal["auto", "legacy_session_v1", "opencode_v1"] = "auto"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)
    methods: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None


class AcpTimeoutsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_init_ms: int = Field(default=10_000, ge=1)
    turn_ms: int = Field(default=120_000, ge=1)


class AcpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: dict[str, AcpProviderConfig]
    routing: dict[str, str] = Field(
        default_factory=lambda: {"coordinator_agent": "local_wrapper", "*": "default"}
    )
    timeouts: AcpTimeoutsConfig = Field(default_factory=AcpTimeoutsConfig)


def load_acp_config(config_dir: Path) -> AcpConfig:
    path = config_dir / "acp.json"
    if not path.exists():
        raise FileNotFoundError(
            f"acp.json not found in {config_dir}. "
            "Please create .agent_teams/acp.json."
        )
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse acp.json: {exc}") from exc
    config = AcpConfig.model_validate(data)
    _validate_routes(config)
    return config


def resolve_acp_provider_name(config: AcpConfig, role_id: str) -> str:
    name = config.routing.get(role_id) or config.routing.get("*")
    if not name:
        raise ValueError(
            f"No ACP route configured for role '{role_id}', and no wildcard route '*'"
        )
    return name


def _validate_routes(config: AcpConfig) -> None:
    for role_id, provider_name in config.routing.items():
        if provider_name == "local_wrapper":
            continue
        if provider_name not in config.providers:
            raise ValueError(
                f"ACP routing for role '{role_id}' references unknown provider "
                f"'{provider_name}'. Known providers: {sorted(config.providers.keys())}"
            )
