from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | dict[str, 'JsonValue'] | list['JsonValue']
JsonObject: TypeAlias = dict[str, JsonValue]
JsonArray: TypeAlias = list[JsonValue]

ReadonlyJsonObject: TypeAlias = Mapping[str, JsonValue]
ReadonlyJsonArray: TypeAlias = Sequence[JsonValue]
