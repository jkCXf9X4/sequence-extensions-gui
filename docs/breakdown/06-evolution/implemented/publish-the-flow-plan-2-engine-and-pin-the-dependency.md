---
id: IMP-008
type: imp
title: Publish the flow-plan/2 engine and pin the dependency
summary: Implemented. The engine publishes the flow-plan/2 JSON Schema at v3.1.0; the GUI git-pins that tag
date: 2026-11-13
status: implemented
---

# Publish the flow-plan/2 engine and pin the dependency

Implemented: the engine publishes the schema and the GUI pins the published release tag.

- **Question:** How do the git dependency and the CI pin point at the engine revision that supports `flow-plan/2`?
- **Evidence:** the GUI needed `execute_plan` and `flow-plan/2`, which existed only in a local engine commit; upstream `main` was behind it and PyPI had no `sequence-extensions-flow` package (`INFO-017`, `TEST-003`).
- **Change:** the engine publishes the `flow-plan/2` JSON Schema as `flow.plan_schema()` and `schemas/flow-plan-2.schema.json`; the GUI pins `v3.1.0` in `pyproject.toml` and CI.
- **Risk:** the GUI and engine must move together when the document changes; a stale pin fails at validation time.
- **Acceptance:** a clean install of the GUI resolves the engine from git, and CI checks out the same tag and passes (`TEST-003`).
