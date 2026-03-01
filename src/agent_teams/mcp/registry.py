from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

from pydantic_ai.toolsets.fastmcp import FastMCPToolset
from pydantic_ai import Tool
from agent_teams.tools.tool_helpers import execute_tool
from agent_teams.tools.runtime import ToolContext

@dataclass(frozen=True)
class McpServerSpec:
    name: str
    config: Any

class ProjectMcpToolset:
    """Wrapper for FastMCPToolset to ensure tool calls are wrapped with execute_tool."""
    def __init__(self, inner: FastMCPToolset, server_name: str):
        self.inner = inner
        self.server_name = server_name

    def get_tools(self, deps: Any) -> list[Tool]:
        inner_tools = self.inner.get_tools(deps)
        wrapped_tools = []
        for t in inner_tools:
            wrapped_tools.append(self._wrap_tool(t))
        return wrapped_tools

    def _wrap_tool(self, tool: Tool) -> Tool:
        inner_func = tool.function

        def wrapped_func(ctx: ToolContext, **kwargs) -> Any:
            def _action():
                return inner_func(ctx, **kwargs)
            
            # Use a slightly different tool name to indicate it's from MCP
            display_name = f"mcp:{self.server_name}:{tool.name}"
            return execute_tool(
                ctx,
                tool_name=display_name,
                args_summary=kwargs,
                action=_action
            )
        
        # Create a new Tool with the same metadata but wrapped function
        return Tool(
            wrapped_func,
            name=tool.name,
            description=tool.description,
            takes_ctx=True # FastMCPToolset tools always take context in our setup
        )

class McpRegistry:
    def __init__(self, specs: tuple[McpServerSpec, ...] = ()) -> None:
        self._specs = {spec.name: spec for spec in specs}
        self._toolsets: dict[str, ProjectMcpToolset] = {}

    def get_toolsets(self, names: tuple[str, ...]) -> tuple[ProjectMcpToolset, ...]:
        missing = [name for name in names if name not in self._specs]
        if missing:
            raise ValueError(f'Unknown MCP servers: {missing}')
        
        toolsets = []
        for name in names:
            if name not in self._toolsets:
                spec = self._specs[name]
                inner = FastMCPToolset(spec.config)
                self._toolsets[name] = ProjectMcpToolset(inner, name)
            toolsets.append(self._toolsets[name])
        return tuple(toolsets)

    def validate_known(self, names: tuple[str, ...]) -> None:
        missing = [name for name in names if name not in self._specs]
        if missing:
            raise ValueError(f'Unknown MCP servers: {missing}')

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs.keys()))
