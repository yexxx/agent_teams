from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from agent_teams.tools.registry import ToolRegistry
from agent_teams.tools.runtime import ToolDeps
from agent_teams.mcp.registry import McpRegistry
from agent_teams.skills.registry import SkillRegistry


def build_collaboration_agent(
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    system_prompt: str,
    allowed_tools: tuple[str, ...],
    allowed_mcp_servers: tuple[str, ...] = (),
    allowed_skills: tuple[str, ...] = (),
    tool_registry: ToolRegistry,
    mcp_registry: McpRegistry | None = None,
    skill_registry: SkillRegistry | None = None,
) -> Agent[ToolDeps, str]:
    toolsets = []
    if mcp_registry and allowed_mcp_servers:
        toolsets.extend(mcp_registry.get_toolsets(allowed_mcp_servers))
        
    model = OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )
    agent: Agent[ToolDeps, str] = Agent(
        model=model,
        deps_type=ToolDeps,
        output_type=str,
        system_prompt=system_prompt,
        toolsets=toolsets,
    )
    specs = tool_registry.require(allowed_tools)
    for spec in specs:
        spec.mount(agent)
    
    if skill_registry:
        skills = skill_registry.require(allowed_skills)
        for skill in skills:
            skill.mount(agent)
            
    return agent
