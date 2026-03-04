# Repository Guidelines (Simplified)

Database schema and API changes do not need to maintain backward compatibility; after making changes, sync the corresponding documentation in the docs/ directory.

## Project Layout
- Core code: `src/agent_teams/`
- Main modules:
  - `application/`: application service/facade
  - `core/`: models, enums, IDs, config
  - `agents/`, `coordination/`, `workflow/`: orchestration
  - `providers/`: LLM providers
  - `state/`, `runtime/`: persistence and runtime event/injection
  - `interfaces/server`: FastAPI HTTP/SSE API
  - `interfaces/cli`: CLI (HTTP client)
  - `interfaces/sdk`: Python HTTP client
- Frontend: `frontend/` (served from `frontend/dist`)
- Tests: `tests/` (mirrors `src/agent_teams/` structure)

## Dev Commands
- Install deps: `uv sync --extra dev`（至少在运行测试前使用该命令，确保 pytest/pytest-asyncio 已安装）
- Start server: `uv run agent-teams serve`
- CLI prompt: `uv run agent-teams prompt -m "hello"`
- Validate roles: `uv run agent-teams roles-validate`
- Run tests: `uv run pytest -q`

## Coding Rules
- Python 3.12+, 4 spaces, type annotations required.
- Prefer Pydantic models/enums over loose dicts.
- `from __future__ import annotations` in Python modules.
- Imports order: stdlib / third-party / local.
- 禁止在项目代码中使用 `typing.Any`（包括参数、返回值、字段、局部变量）；必须使用强类型（如 Pydantic 模型、具体类、`JsonValue/JsonObject` 等）。
- Logging via runtime logger; avoid `print()` in production paths.

## API & Data Contracts
- Backend public contract is `/api/*`.
- CLI/frontend/SDK must communicate via HTTP/SSE only.
- Do not directly access backend internal repositories from interface layer.

## Testing
- Tests directory `tests/` must mirror the structure of `src/agent_teams/`
- When adding new tests, create corresponding subdirectories and `__init__.py`
- Add/update tests for behavior changes, especially orchestration and streaming.
- Use focused unit tests first; add integration tests for run/SSE flows when needed.

## Security
- Secrets only in `.agent_teams/.env`.
- Never commit keys/tokens.
