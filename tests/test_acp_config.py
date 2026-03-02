import json
from pathlib import Path

from agent_teams.core.acp_config import load_acp_config, resolve_acp_provider_name


def test_load_acp_config_and_resolve_routes() -> None:
    config = load_acp_config(Path(".agent_teams"))
    assert "default" in config.providers
    assert resolve_acp_provider_name(config, "coordinator_agent") == "local_wrapper"
    assert resolve_acp_provider_name(config, "spec_coder") == "default"


def test_provider_protocol_defaults_to_auto(tmp_path: Path) -> None:
    path = tmp_path / "acp.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "default": {
                        "transport": "stdio",
                        "command": "opencode",
                        "args": ["acp"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_acp_config(tmp_path)
    assert config.providers["default"].protocol == "auto"
