---
id: IMP-001
type: imp
title: Expose per-node policy through the engine API
summary: Replace the NodeFunction attribute mutation with a supported hook
date: 2026-11-12
status: suggested
---

# Expose per-node policy through the engine API

- **Question:** Can per-node policy become a supported engine hook instead of private attribute mutation?
- **Evidence:** the GUI applies `retries`, `retry_delay_seconds`, and `timeout` by mutating `NodeFunction` attributes, which upstream does not support (`INFO-007`).
- **Change:** expose the policy through a public engine API and delete the attribute mutation.
- **Risk:** engine work outside the GUI; a new API must stay compatible with the pinned checkout.
- **Acceptance:** a policy edit takes effect through a public API with no private attribute writes.
