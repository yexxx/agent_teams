# Orchestration Strategy: Entry × Planning Mode × Review Loop

This repository now supports a unified orchestration strategy model for both AI and human orchestrators.

## Strategy Dimensions

- **Entry (orchestrator)**
  - `ai`: LLM coordinator controls the orchestration cycle.
  - `human`: human operator controls task dispatch and plan changes.
- **Planning mode**
  - `sop`: use built-in SOP templates (e.g. `spec_flow`) for predictable delivery.
  - `freeform`: design custom workflow tasks and dependencies dynamically.
- **Review state**
  - `review`: normal execution and monitoring.
  - `replan`: adjust workflow plan and strategy.
  - `finish`: finalize with summary/output.

## Workflow Graph Contract

`create_workflow_graph` now writes strategy metadata into `workflow_graph`:

- `orchestrator`
- `planning_mode`
- `review_state`

## New Workflow Tools

- `set_workflow_strategy`: update `orchestrator`, `planning_mode`, and `review_state` for an existing workflow.
- `review_workflow_progress`: analyze workflow records and return a review decision:
  - `review` (continue dispatch)
  - `replan` (adjust plan)
  - `finish` (finalize)

## Suggested Operating Loop

1. Create or continue workflow graph.
2. Execute a bounded dispatch step.
3. Review progress.
4. Choose one action:
   - continue dispatch
   - replan
   - finish

This loop applies equally to AI-driven and human-driven orchestration.
