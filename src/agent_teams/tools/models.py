from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolError(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    suggested_fix: str | None = None


class ToolResultEnvelope(BaseModel):
    model_config = ConfigDict(extra='forbid')

    ok: bool
    tool: str = Field(min_length=1)
    data: Any = None
    error: ToolError | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

