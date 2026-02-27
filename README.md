# agent-teams

Role-driven multi-agent orchestration framework built with strong typing and tool-only collaboration flow.

## Quick start

### 1) Install dependencies

```bash
uv sync
```

### 2) Create runtime config file

Linux/macOS:

```bash
cp .agent_teams/.env.example .agent_teams/.env
```

Windows PowerShell:

```powershell
Copy-Item .agent_teams/.env.example .agent_teams/.env
```

Then edit `.agent_teams/.env`.

- If you set `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, it will use your OpenAI-compatible endpoint.
- If those fields are empty, the app falls back to local `EchoProvider` (still runnable for smoke test).

### 3) Validate roles

```bash
uv run agent-teams roles-validate
```

### 4) Run an intent

```bash
uv run agent-teams run-intent --intent "Draft a release note"
```

### 5) Query task records

```bash
uv run agent-teams tasks-list
# then:
uv run agent-teams tasks-query --task-id <task_id>
```
