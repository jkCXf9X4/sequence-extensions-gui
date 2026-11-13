---
id: INFO-024
type: info
title: How a plan document is validated
summary: schema.py loads the engine artifact, caches a draft 2020-12 validator, reports capped path errors
date: 2026-11-13
status: current
---

# How a plan document is validated

`schema.py` validates a `flow-plan/2` document against the engine's JSON Schema; the GUI keeps no pydantic mirror of the plan.

- **Load:** `importlib.resources` reads `sequence_extensions/schemas/flow-plan-2.schema.json`; when absent, `sequence_extensions.flow.plan_schema()` is the fallback; both load once per process.
- **Validate:** one cached `Draft202012Validator`; `validate_plan` raises `PlanValidationError` with errors sorted by JSON path and capped at five.
- **Partial seeds:** `is_complete_document` requires every top-level `required` key and every `$defs/options` property; an incomplete seed is validated only after the engine re-plans it.
- **Defaults:** `option_defaults` and `policy_defaults` read `RunOptions().resolve("plan")` and `NodePolicy()` in schema property order, filling imported plans.
- **Annotations:** `editable` and `note` are GUI-only dict keys; `to_document()` strips them before export or execution (`INFO-009`).
