from __future__ import annotations

from json import dumps, loads
from pathlib import Path

from agent_teams.mcp.registry import McpRegistry, McpServerSpec
from agent_teams.skills.registry import SkillRegistry


class ConfigManager:
    def __init__(self, *, config_dir: Path) -> None:
        self._config_dir = config_dir

    def get_model_config(self) -> dict:
        model_file = self._config_dir / "model.json"
        if model_file.exists():
            return loads(model_file.read_text("utf-8"))
        return {}

    def get_model_profiles(self) -> dict:
        model_file = self._config_dir / "model.json"
        if not model_file.exists():
            return {}
        config = loads(model_file.read_text("utf-8"))
        result: dict[str, dict] = {}
        for name, profile in config.items():
            result[name] = {
                "model": profile.get("model", ""),
                "base_url": profile.get("base_url", ""),
                "has_api_key": bool(profile.get("api_key")),
                "temperature": profile.get("temperature", 0.7),
                "top_p": profile.get("top_p", 1.0),
                "max_tokens": profile.get("max_tokens", 4096),
            }
        return result

    def save_model_profile(self, name: str, profile: dict) -> None:
        model_file = self._config_dir / "model.json"
        config = {}
        if model_file.exists():
            config = loads(model_file.read_text("utf-8"))
        config[name] = profile
        model_file.write_text(dumps(config, indent=2), encoding="utf-8")

    def delete_model_profile(self, name: str) -> None:
        model_file = self._config_dir / "model.json"
        if not model_file.exists():
            return
        config = loads(model_file.read_text("utf-8"))
        if name in config:
            del config[name]
            model_file.write_text(dumps(config, indent=2), encoding="utf-8")

    def save_model_config(self, config: dict) -> None:
        model_file = self._config_dir / "model.json"
        model_file.write_text(dumps(config, indent=2), encoding="utf-8")

    def load_mcp_registry(self) -> McpRegistry:
        mcp_specs: list[McpServerSpec] = []
        mcp_file = self._config_dir / "mcp.json"
        if mcp_file.exists():
            try:
                mcp_data = loads(mcp_file.read_text("utf-8"))
                servers = mcp_data.get("mcpServers", mcp_data)
                for name, cfg in servers.items():
                    wrapped_cfg = {"mcpServers": {name: cfg}}
                    mcp_specs.append(McpServerSpec(name=name, config=wrapped_cfg))
            except Exception as e:
                print(f"Warning: Failed to load mcp.json: {e}")
        return McpRegistry(tuple(mcp_specs))

    def load_skill_registry(self) -> SkillRegistry:
        from agent_teams.skills.discovery import SkillsDirectory

        skills_dir = self._config_dir / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_directory = SkillsDirectory(base_dir=skills_dir)
        return SkillRegistry(directory=skill_directory)
