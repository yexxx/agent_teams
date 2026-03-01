from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class SkillResource:
    name: str
    description: str
    path: Path | None = None
    content: str | None = None

@dataclass
class SkillScript:
    name: str
    description: str
    path: Path

@dataclass
class SkillMetadata:
    name: str
    description: str
    instructions: str
    resources: dict[str, SkillResource] = field(default_factory=dict)
    scripts: dict[str, SkillScript] = field(default_factory=dict)
    
@dataclass
class Skill:
    metadata: SkillMetadata
    directory: Path
