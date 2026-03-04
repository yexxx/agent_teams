# Architecture Refactor Plan (Clean-Split, Big-Bang Friendly)

## Goals

- Reduce cross-layer coupling and hidden dependencies.
- Keep **`/api/*` as the only backend public contract** for CLI/SDK/frontend.
- Make orchestration easier to evolve (AI/auto/human/workflow modes).
- Replace "god service" composition with explicit bounded contexts.
- Preserve current behavior while allowing large directory restructuring.

## Current Pain Points

1. `application/service.py` is a large facade with runtime reload, run lifecycle, session/task access, and orchestration control all together.
2. `providers/llm.py` has too many dependencies and currently mixes model adapter concerns with orchestration-side concerns.
3. `coordination/` and `providers/` share responsibilities around events, run control, and tool/injection flow.
4. `workflow/` is only partially integrated with run orchestration.
5. Composition root (`application/bootstrap.py`) is valid but currently wires many concrete internals directly, making substitution/testing hard.

## Target Structure (Proposed)

```text
src/agent_teams/
  domain/
    run/
      entities.py
      value_objects.py
      events.py
      policies.py
    task/
      entities.py
      policies.py
    role/
      entities.py
    shared/
      enums.py
      ids.py

  application/
    ports/
      repositories.py
      providers.py
      runtime.py
      event_bus.py
    use_cases/
      runs/
        create_run.py
        stream_run_events.py
        stop_run.py
        inject_message.py
      sessions/
        create_session.py
        list_rounds.py
      tasks/
        dispatch_task.py
        resolve_gate.py
    services/
      orchestration_service.py
      config_reload_service.py

  infrastructure/
    persistence/
      sqlite/
        db.py
        task_repository.py
        session_repository.py
        message_repository.py
        event_repository.py
    providers/
      llm/
        openai_compatible_provider.py
        echo_provider.py
    tools/
    mcp/
    skills/
    observability/
      logging/
      tracing/
    execution_control/
      run_control/
      gate_control/
      tool_approval/
    eventing/
      run_event_hub/

  interfaces/
    server/
      app.py
      deps.py
      routers/
    cli/
      app.py
    sdk/
      client.py

  composition/
    container.py
    bootstrap.py
```

## Refactor Principles

## Why name it `use_cases/`?

The directory is intentionally named `use_cases/` to express **application intent orchestration** (what the system does for a request) instead of technical transport or storage concerns.

- `runs/create_run.py`, `runs/stop_run.py`, `runs/inject_message.py` map to concrete run lifecycle intents.
- `sessions/create_session.py`, `sessions/list_rounds.py` map to session-facing application actions.
- `tasks/dispatch_task.py`, `tasks/resolve_gate.py` map to task control actions.

This naming is chosen to keep routers/CLI thin: interface layer translates HTTP/CLI input -> calls one use-case -> maps output DTO.

If the team prefers a stricter CQRS style, it can be renamed to:

- `application/commands/*` and `application/queries/*` (recommended when read/write paths diverge strongly), or
- `application/handlers/*` (neutral naming),

but the **boundary rule remains the same**: these modules are the primary application entrypoints and should depend on ports/domain, not concrete infrastructure.

1. **Dependency direction**: `interfaces -> application -> domain`; `infrastructure` implements `application/ports`.
2. **No direct repo access from interface layer** (already mostly true).
3. **Provider isolation**: LLM provider only handles model IO and tool-calling protocol; orchestration decisions live in application/orchestration services.
4. **Use-case first**: each API endpoint maps to one use-case object (thin router, explicit inputs/outputs).
5. **State changes behind ports**: all task/session/run writes via repository interfaces.
6. **Event contract stable**: one internal run event schema and one external SSE DTO mapping layer.

## Why not keep a big `runtime/` bucket?

The earlier draft used `infrastructure/runtime/*` as a temporary umbrella for implementations that are active only while a run is executing. That naming is understandable, but it tends to become a "misc" folder and blur ownership over time.

For a cleaner long-term structure, this plan now recommends splitting by **capability** instead of execution phase:

- `observability/*`: logging, tracing, metrics concerns
- `execution_control/*`: cancellation, gating, and approval control concerns
- `eventing/*`: event hub and event fan-out concerns

This keeps boundaries explicit and avoids mixing unrelated modules just because they are all "runtime-ish".

## Concrete Moves (Large but Safe)

### Phase 1: Carve Ports and Use Cases

- Introduce `application/ports/*` protocols for repositories, event publishing, run control, and provider factory.
- Move logic from `AgentTeamsService` into focused use-cases under:
  - `application/use_cases/runs/*`
  - `application/use_cases/sessions/*`
  - `application/use_cases/tasks/*`
- Keep `AgentTeamsService` as compatibility facade delegating to use-cases.

**Exit criteria**
- Routers call use-cases (possibly through facade), not broad service methods.
- Unit tests cover each use-case with fake ports.

### Phase 2: Split Orchestration from Provider

- Keep provider request/response abstraction minimal (`LLMRequest`, `LLMResponse`, stream chunks, tool-calls).
- Move run-event publication, cancellation checks, injection boundary handling, and message persistence out of provider and into orchestration executor.
- Create `application/services/orchestration_service.py` to manage step loop.

**Exit criteria**
- `OpenAICompatibleProvider` constructor reduced to model config + tool protocol deps only.
- Orchestration tests no longer need concrete provider internals.

### Phase 3: Integrate Workflow as First-Class Run Mode

- Merge `workflow/` runtime functions into orchestration use-cases.
- Add explicit mode strategy classes:
  - `AiModeStrategy`
  - `AutoModeStrategy`
  - `HumanModeStrategy`
  - `WorkflowModeStrategy`
- `CoordinatorGraph` becomes a strategy coordinator, not the primary large state manager.

**Exit criteria**
- Single entrypoint selects strategy by execution mode.
- Workflow status/dispatch APIs are use-cases, not ad-hoc helper calls.

### Phase 4: Infrastructure Re-home

- Move concrete sqlite repos from `state/` into `infrastructure/persistence/sqlite/`.
- Keep temporary re-export shims in `state/` to reduce migration breakage.
- Move runtime-specific concrete implementations under `infrastructure/runtime/*`.

**Exit criteria**
- `application/*` imports only from `application/ports` and `domain/*`.
- No concrete sqlite imports inside use-cases.

### Phase 5: Interface Cleanup

- Server routers -> validate DTO -> call use-case -> map response DTO.
- CLI/SDK remain HTTP-only clients.
- Keep API path stable where possible (`/api/*`), but if breaking changes are accepted, version once (`/api/v2/*`) for a clean cut.

**Exit criteria**
- Endpoint handlers < 40 lines average and no business branching in routers.

## Suggested Module Ownership Matrix

- **Domain**: business models/invariants (no infra deps).
- **Application**: orchestration and use-cases (depends on ports/domain only).
- **Infrastructure**: adapters (sqlite, llm provider impl, runtime/event backends).
- **Interfaces**: transport adapters (FastAPI/Typer/SDK client).
- **Composition**: wiring only.

## Testing Strategy During Refactor

1. Add characterization tests for current run lifecycle behavior before moving logic.
2. Build use-case tests with fake ports (fast, deterministic).
3. Keep integration tests for:
   - run create + SSE stream
   - human gate resolve flow
   - tool approval flow
   - stop semantics
4. Add import-boundary checks (simple script or pytest) to ensure layer rules.

## Migration Sequence (Pragmatic)

1. Introduce ports + adapters with zero behavior changes.
2. Move one vertical slice first (`create_run` + `stream_run_events`).
3. Migrate remaining run/task/session operations.
4. Refactor provider/orchestration boundary.
5. Re-home directories to final target layout.
6. Remove compatibility shims.

## Risks and Controls

- **Risk**: SSE/event ordering regressions.
  - **Control**: snapshot tests for event sequence.
- **Risk**: cancellation/timeout edge behavior drift.
  - **Control**: dedicated run-control tests before and after move.
- **Risk**: workflow mode behavior inconsistency.
  - **Control**: scenario tests per strategy.

## Implemented Baseline (Current Big-Bang Refactor)

This repository now includes a first clean-split baseline aligned with this plan:

- Added `composition/` and moved concrete bootstrap wiring to `composition/bootstrap.py` (with backward-compatible shim kept in `application/bootstrap.py`).
- Added `infrastructure/persistence/sqlite/*` and moved sqlite repositories there (legacy `state/*` kept as re-export shims).
- Added `infrastructure/execution_control/*`, `infrastructure/eventing/*`, and `infrastructure/observability/*` for runtime control/event/logging implementations (legacy `runtime/*` modules kept as re-export shims).
- Added `domain/shared/*` aliases so future domain migration can switch from `core/*` without breaking interfaces immediately.
- Added `application/use_cases/*` as primary application entrypoints for run/session/task flows.

This gives a full target skeleton now, while preserving compatibility during follow-up cleanup.

## Definition of Done

- Layer import rules enforced.
- `AgentTeamsService` reduced to thin composition facade or removed.
- Provider layer no longer handles orchestration policy.
- Workflow mode integrated under shared orchestration contract.
- Tests mirror new directory layout and pass.
