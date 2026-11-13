---
id: INFO-023
type: info
title: How the GUI stays decoupled from the engine
summary: Separate repos; public API plus the engine's normative flow-plan/2 JSON Schema
date: 2026-11-13
status: current
---

# How the GUI stays decoupled from the engine

The GUI and the engine are separate packages, and merging them was rejected: coupling is public-API-only, the engine stays zero-runtime-dependency, and the GUI's FastAPI plus `jsonschema` stack would otherwise land in the engine. The contract is the engine's public API and its published plan schema.

- **Public API only:** two import statements carry seven symbols — `plan_document`, `apply_override`, `execute_plan`, `RunOptions`, `NodePolicy`, `jsonable` from `sequence_extensions.flow`, and `find_nodes` from `sequence_extensions.flow_runner` (`INFO-004`).
- **Schema boundary:** the engine publishes the normative `flow-plan/2` JSON Schema as `flow.plan_schema()` and `src/sequence_extensions/schemas/flow-plan-2.schema.json`; the GUI validates against that artifact (`INFO-024`).
- **Dependency asymmetry:** the engine has zero runtime dependencies; the GUI adds FastAPI, uvicorn, and `jsonschema` (`INFO-017`).
- **Git pin:** engine 3.1.0 is not on PyPI, so the GUI pins release tag `v3.1.0` and installs the engine from git (`INFO-017`).
