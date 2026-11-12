---
id: INFO-007
type: info
title: How overrides reach the engine
summary: Root kwargs, node registry, code wins, policy mutation
date: 2026-11-12
status: current
---

# How overrides reach the engine

Overrides reach the engine through root kwargs, a node registry, and policy; flow code always wins.

- **Root parameters:** passed as keyword arguments, which always beat the registry.
- **Node parameters:** `apply_override` edits the plan document, then `parameters_from_document` rebuilds the registry without the root entry.
- **Policy:** run-level `node_defaults` go through `RunOptions`; per-node edits mutate `NodeFunction` attributes and warn (`IMP-001`).
- **Code wins:** a value the flow binds explicitly stays read-only and its edit is not applied (`REQ-001`).
- **Name-keyed:** node edits match by name, so one edit hits every instance; differing instances stay editable with a warning.
