from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from pydantic_ai import Agent
from agent_teams.tools.runtime import ToolDeps


SkillMount = Callable[[Agent[ToolDeps, str]], None]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    mount: SkillMount


class SkillRegistry:
    def __init__(self, specs: tuple[SkillSpec, ...] = ()) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def require(self, names: tuple[str, ...]) -> tuple[SkillSpec, ...]:
        missing = [name for name in names if name not in self._specs]
        if missing:
            raise ValueError(f'Unknown skills: {missing}')
        return tuple(self._specs[name] for name in names)

    def validate_known(self, names: tuple[str, ...]) -> None:
        self.require(names)

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs.keys()))
