from __future__ import annotations

from agent_teams.mcp.registry import McpRegistry
from agent_teams.skills.registry import SkillRegistry


def build_tool_manifest(allowed_tools: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": tool_name,
            "description": f"Internal role tool: {tool_name}",
            "input_schema": {"type": "object", "additionalProperties": True},
        }
        for tool_name in allowed_tools
    )


def build_skill_manifest(
    skill_registry: SkillRegistry, allowed_skills: tuple[str, ...]
) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for skill_name in allowed_skills:
        skill = skill_registry.get_skill(skill_name)
        metadata = skill.metadata
        skill_file = skill.directory / "SKILL.md"
        scripts = sorted(metadata.scripts.values(), key=lambda item: item.name)
        resources = sorted(metadata.resources.values(), key=lambda item: item.name)
        items.append(
            {
                "name": metadata.name,
                "description": metadata.description,
                "loading_mode": "progressive",
                "skill_file": str(skill_file),
                "scripts": tuple(
                    {
                        "name": script.name,
                        "description": script.description,
                        "path": str(script.path),
                    }
                    for script in scripts
                ),
                "resources": tuple(
                    {
                        "name": resource.name,
                        "description": resource.description,
                        "path": str(resource.path) if resource.path else "",
                    }
                    for resource in resources
                ),
            }
        )
    return tuple(items)


def build_mcp_manifest(
    mcp_registry: McpRegistry, allowed_mcp_servers: tuple[str, ...]
) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for name in allowed_mcp_servers:
        spec = mcp_registry.get_spec(name)
        items.append({"name": name, "config": spec.config})
    return tuple(items)
