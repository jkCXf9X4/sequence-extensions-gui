---
id: INFO-007
type: info
title: How overrides reach the engine
summary: Root kwargs, plan document registry, per-node policies, code wins
date: 2026-11-12
status: current
---

# How overrides reach the engine

Plan edits reach the engine through root kwargs, a node registry, and per-node policy; values the flow binds explicitly always win.

- **Root parameters:** passed as keyword arguments, which always beat the registry.
- **Node parameters:** `apply_override` edits the plan document; `execute_plan` rebuilds the node registry from `nodes[].params` (later occurrence wins).
- **Policy:** the document's `nodes[].policy` reaches the engine as `RunOptions.node_policies`, which beats an explicit `@node` keyword; runtime-only `node_defaults` fill the rest. No attribute mutation.
- **Code wins:** a value the flow binds explicitly stays read-only and its edit is not applied (`REQ-001`).
- **Name-keyed:** node edits match by name, so one edit hits every instance; differing instances stay editable with a warning.
