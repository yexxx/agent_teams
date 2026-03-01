from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable

from pydantic_ai import Agent, Tool

from agent_teams.skills.discovery import SkillsDirectory
from agent_teams.tools.runtime import ToolDeps, ToolContext
from agent_teams.tools.tool_helpers import execute_tool

@dataclass(frozen=True)
class SkillSpec:
    name: str

class SkillRegistry:
    def __init__(self, directory: SkillsDirectory) -> None:
        self.directory = directory
        self.directory.discover()
        # available skills
        known = [s.metadata.name for s in self.directory.list_skills()]
        self._specs = {name: SkillSpec(name=name) for name in known}

    def require(self, names: tuple[str, ...]) -> tuple[SkillSpec, ...]:
        missing = [name for name in names if name not in self._specs]
        if missing:
            raise ValueError(f'Unknown skills: {missing}')
        return tuple(self._specs[name] for name in names)

    def validate_known(self, names: tuple[str, ...]) -> None:
        self.require(names)

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs.keys()))

    def get_instructions(self, allowed_skills: tuple[str, ...]) -> str:
        """Return the concatenated instructions of all allowed skills to inject into prompt."""
        instructions = []
        for name in allowed_skills:
            skill = self.directory.get_skill(name)
            if skill and skill.metadata.instructions:
                instructions.append(f"--- SKILL INSTRUCTIONS: {name} ---\n{skill.metadata.instructions}")
        if instructions:
            return "\n\n".join(instructions)
        return ""

    def get_toolset_tools(self, allowed_skills: tuple[str, ...]) -> list[Tool]:
        """Provides the 4 core tools associated with the Skills Toolset."""
        
        allowed_set = set(allowed_skills)

        def list_skills(ctx: ToolContext) -> str:
            """Discover available skills in the environment."""
            def _action() -> str:
                lines = ["Available Skills:"]
                for s in self.directory.list_skills():
                    if s.metadata.name in allowed_set:
                        lines.append(f"- {s.metadata.name}: {s.metadata.description}")
                return "\\n".join(lines)
            return execute_tool(ctx, tool_name="list_skills", args_summary={}, action=_action)

        def load_skill(ctx: ToolContext, name: str) -> str:
            """Load instructions, resources, and scripts of a specific skill."""
            def _action() -> str:
                if name not in allowed_set:
                    return f"Skill {name} is not permitted for this role."
                skill = self.directory.get_skill(name)
                if not skill:
                    return f"Skill {name} not found."
                lines = [
                    f"# Skill: {skill.metadata.name}",
                    f"Description: {skill.metadata.description}",
                    f"Instructions: {skill.metadata.instructions}",
                    "Resources:"
                ]
                for r in skill.metadata.resources.values():
                    lines.append(f" - {r.name}: {r.description}")
                lines.append("Scripts:")
                for s in skill.metadata.scripts.values():
                    lines.append(f" - {s.name}: {s.description}")
                return "\\n".join(lines)
            return execute_tool(ctx, tool_name="load_skill", args_summary={"name": name}, action=_action)

        def read_skill_resource(ctx: ToolContext, skill_name: str, resource_name: str) -> str:
            """Read a specific resource (text file) provided by a skill."""
            def _action() -> str:
                if skill_name not in allowed_set:
                    return f"Skill {skill_name} is not permitted."
                skill = self.directory.get_skill(skill_name)
                if not skill:
                    return f"Skill {skill_name} not found."
                res = skill.metadata.resources.get(resource_name)
                if not res:
                    return f"Resource {resource_name} not found in {skill_name}."
                if not res.path or not res.path.exists():
                    return f"Resource file at {res.path} missing or unreadable."
                try:
                    return res.path.read_text(encoding="utf-8")
                except Exception as e:
                    return f"Failed to read resource: {e}"
            return execute_tool(ctx, tool_name="read_skill_resource", args_summary={"skill_name": skill_name, "resource_name": resource_name}, action=_action)

        def run_skill_script(ctx: ToolContext, skill_name: str, script_name: str, kwargs: dict) -> str:
            """Run a Python script provided by a skill with the given named arguments."""
            def _action() -> str:
                if skill_name not in allowed_set:
                    return f"Skill {skill_name} is not permitted."
                skill = self.directory.get_skill(skill_name)
                if not skill:
                    return f"Skill {skill_name} not found."
                script = skill.metadata.scripts.get(script_name)
                if not script:
                    return f"Script {script_name} not found in {skill_name}."
                if not script.path or not script.path.exists():
                    return f"Script file at {script.path} missing or unreadable."

                # Construct CLI arguments. 
                cmd = ["python", str(script.path)]
                for k, v in kwargs.items():
                    cmd.extend([f"--{k}", str(v)])
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(skill.directory))
                    if result.returncode == 0:
                        return result.stdout or "Script executed successfully with no output."
                    return f"Script failed with exit code {result.returncode}. STDERR: {result.stderr}"
                except subprocess.TimeoutExpired:
                    return "Script execution timed out after 30 seconds."
                except Exception as e:
                    return f"Script execution error: {e}"
            return execute_tool(ctx, tool_name="run_skill_script", args_summary={"skill_name": skill_name, "script_name": script_name, "kwargs": kwargs}, action=_action)

        return [
            Tool(list_skills),
            Tool(load_skill),
            Tool(read_skill_resource),
            Tool(run_skill_script)
        ]
