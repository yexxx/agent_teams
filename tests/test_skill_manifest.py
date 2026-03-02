from __future__ import annotations

from pathlib import Path

from agent_teams.acp.manifest import build_skill_manifest
from agent_teams.skills.discovery import SkillsDirectory
from agent_teams.skills.registry import SkillRegistry


def test_build_skill_manifest_uses_progressive_catalog(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "time"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: time\n"
            "description: Time utilities\n"
            "---\n"
            "## Usage\n"
            "Use on demand.\n"
            "\n"
            "## Scripts\n"
            "- get_current_time: Return current time.\n"
        ),
        encoding="utf-8",
    )
    (scripts_dir / "get_current_time.py").write_text(
        "def main():\n    return 'ok'\n", encoding="utf-8"
    )

    registry = SkillRegistry(directory=SkillsDirectory(base_dir=tmp_path / "skills"))
    manifest = build_skill_manifest(registry, ("time",))

    assert len(manifest) == 1
    row = manifest[0]
    assert row["name"] == "time"
    assert row["loading_mode"] == "progressive"
    assert "instructions" not in row
    assert str(skill_dir / "SKILL.md") == row["skill_file"]
    scripts = row["scripts"]
    assert isinstance(scripts, tuple)
    assert scripts
    assert scripts[0]["name"] == "get_current_time"
