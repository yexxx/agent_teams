import yaml
from pathlib import Path

from agent_teams.skills.models import Skill, SkillMetadata, SkillResource, SkillScript

class SkillsDirectory:
    def __init__(self, base_dir: Path, max_depth: int = 3):
        self.base_dir = base_dir
        self.max_depth = max_depth
        self._skills: dict[str, Skill] = {}

    def discover(self) -> None:
        """Scan the directory for SKILL.md files and load them."""
        if not self.base_dir.exists():
            return
            
        self._skills.clear()
        
        # We do a basic glob search here. For max_depth, a simple approach is rglob and manual check.
        for path in self.base_dir.rglob("SKILL.md"):
            try:
                rel = path.relative_to(self.base_dir)
                if len(rel.parts) <= self.max_depth + 1:
                    skill = self._load_skill(path)
                    if skill:
                        self._skills[skill.metadata.name] = skill
            except Exception as e:
                print(f"Failed to load skill at {path}: {e}")

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def _split_front_matter(self, content: str) -> tuple[str, str]:
        if not content.startswith('---'):
            raise ValueError("SKILL.md must start with YAML front matter")

        lines = content.splitlines(keepends=True)
        if not lines or lines[0].strip() != '---':
            raise ValueError("SKILL.md must start with YAML front matter")

        end_index = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == '---':
                end_index = idx
                break

        if end_index is None:
            raise ValueError("Invalid YAML front matter delimiters")

        front_matter = "".join(lines[1:end_index])
        body = "".join(lines[end_index + 1 :])
        return front_matter, body

    def _load_skill(self, path: Path) -> Skill | None:
        raw = path.read_text(encoding="utf-8")
        try:
            front_matter, body = self._split_front_matter(raw)
            data = yaml.safe_load(front_matter)
        except Exception as e:
            print(f"Skipping {path} due to parsing error: {e}")
            return None

        if not isinstance(data, dict):
            return None

        name = data.get("name")
        description = data.get("description", "")
        if not name:
            return None

        # Parse resources from YAML and auto-discover in resources/ or assets/
        resources = {}
        if "resources" in data and isinstance(data["resources"], dict):
            for r_name, r_data in data["resources"].items():
                r_path = None
                if "path" in r_data:
                    r_path = path.parent / r_data["path"]
                resources[r_name] = SkillResource(
                    name=r_name,
                    description=r_data.get("description", ""),
                    path=r_path
                )
        
        # Auto-discover in resources/ directory
        for r_dir_name in ["resources", "assets"]:
            r_dir = path.parent / r_dir_name
            if r_dir.exists() and r_dir.is_dir():
                for r_path in r_dir.glob("*"):
                    if r_path.is_file() and r_path.name not in resources:
                        resources[r_path.name] = SkillResource(
                            name=r_path.name,
                            description=f"Auto-discovered resource: {r_path.name}",
                            path=r_path
                        )

        # Parse scripts from scripts/ directory and correlate with markdown body
        scripts = {}
        scripts_dir = path.parent / "scripts"
        
        # Simple extraction of descriptions from markdown: look for lines like "- name: description (path)"
        import re
        script_meta = {}
        # Find lines in the format: - name: description (optional path)
        # or - name: description
        matches = re.finditer(r'^- ([\w-]+):\s*(.*?)(?:\s*\((.*?)\))?$', body, re.MULTILINE)
        for m in matches:
            s_name, s_desc, s_path = m.groups()
            script_meta[s_name] = (s_desc.strip(), s_path)

        if scripts_dir.exists() and scripts_dir.is_dir():
            for script_path in scripts_dir.glob("*.py"):
                s_name = script_path.stem
                desc, _ = script_meta.get(s_name, (f"Execute {s_name} script.", None))
                scripts[s_name] = SkillScript(
                    name=s_name,
                    description=desc,
                    path=script_path
                )

        metadata = SkillMetadata(
            name=name,
            description=description,
            instructions=body.strip(),
            resources=resources, # Retaining existing resource parsing for now
            scripts=scripts
        )

        return Skill(metadata=metadata, directory=path.parent)
