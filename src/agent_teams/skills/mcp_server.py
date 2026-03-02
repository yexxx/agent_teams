from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from agent_teams.skills.discovery import SkillsDirectory
from agent_teams.skills.models import Skill
from agent_teams.skills.registry import SkillRegistry


@dataclass(frozen=True)
class SkillsMcpServerConfig:
    config_dir: Path
    allowed_skills: tuple[str, ...] = ()


def build_skills_mcp_server(config: SkillsMcpServerConfig) -> FastMCP:
    skills_dir = config.config_dir / "skills"
    skill_registry = SkillRegistry(directory=SkillsDirectory(base_dir=skills_dir))
    allowed_set = set(config.allowed_skills)

    mcp = FastMCP(
        name="agent-teams-skills",
        instructions=(
            "Skill catalog server. List available skills, then load only the one needed for "
            "the current task. Use script/resource tools on demand."
        ),
    )

    def _resolve_skill(name: str) -> Skill:
        skill = skill_registry.get_skill(name)
        if allowed_set and name not in allowed_set:
            raise ValueError(f"Skill '{name}' is not enabled for this role")
        return skill

    @mcp.tool(name="skills_list", description="List enabled skills with lightweight metadata.")
    def skills_list() -> list[dict[str, object]]:
        skill_registry.directory.discover()
        rows: list[dict[str, object]] = []
        for skill in skill_registry.directory.list_skills():
            metadata = skill.metadata
            if allowed_set and metadata.name not in allowed_set:
                continue
            rows.append(
                {
                    "name": metadata.name,
                    "description": metadata.description,
                    "scripts": sorted(metadata.scripts.keys()),
                    "resources": sorted(metadata.resources.keys()),
                    "skill_file": str(skill.directory / "SKILL.md"),
                }
            )
        rows.sort(key=lambda item: str(item["name"]))
        return rows

    @mcp.tool(name="skill_load", description="Load one skill's full instructions and metadata.")
    def skill_load(name: str) -> dict[str, object]:
        skill = _resolve_skill(name)
        metadata = skill.metadata
        scripts = sorted(metadata.scripts.values(), key=lambda item: item.name)
        resources = sorted(metadata.resources.values(), key=lambda item: item.name)
        return {
            "name": metadata.name,
            "description": metadata.description,
            "instructions": metadata.instructions,
            "skill_file": str(skill.directory / "SKILL.md"),
            "scripts": [
                {
                    "name": script.name,
                    "description": script.description,
                    "path": str(script.path),
                }
                for script in scripts
            ],
            "resources": [
                {
                    "name": resource.name,
                    "description": resource.description,
                    "path": str(resource.path) if resource.path else "",
                }
                for resource in resources
            ],
        }

    @mcp.tool(
        name="skill_read_resource",
        description="Read a single skill resource file by skill name and resource name.",
    )
    def skill_read_resource(skill_name: str, resource_name: str) -> str:
        skill = _resolve_skill(skill_name)
        resource = skill.metadata.resources.get(resource_name)
        if resource is None or resource.path is None:
            raise FileNotFoundError(
                f"Resource '{resource_name}' not found in skill '{skill_name}'"
            )
        return resource.path.read_text(encoding="utf-8")

    @mcp.tool(
        name="skill_run_script",
        description=(
            "Run one script from a skill. Load skill metadata first, then run only the "
            "script needed for the current step."
        ),
    )
    async def skill_run_script(
        skill_name: str,
        script_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        skill = _resolve_skill(skill_name)
        script = skill.metadata.scripts.get(script_name)
        if script is None:
            raise KeyError(f"Script '{script_name}' not found in skill '{skill_name}'")

        spec = importlib.util.spec_from_file_location(
            f"skill_script_{skill_name}_{script_name}", script.path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load script '{script_name}' from {script.path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        fn = getattr(module, "run", None) or getattr(module, "main", None)
        if fn is None:
            raise AttributeError(
                f"Script '{script_name}' in skill '{skill_name}' has no run/main function"
            )

        call_args = args or {}
        if inspect.iscoroutinefunction(fn):
            try:
                result = await fn(**call_args)
            except TypeError:
                result = await fn()
        else:
            try:
                result = fn(**call_args)
            except TypeError:
                result = fn()
            if inspect.isawaitable(result):
                result = await result

        return {
            "skill_name": skill_name,
            "script_name": script_name,
            "result": result,
        }

    return mcp


def run_skills_mcp_server(config: SkillsMcpServerConfig) -> None:
    server = build_skills_mcp_server(config)
    server.run(transport="stdio", show_banner=False)
