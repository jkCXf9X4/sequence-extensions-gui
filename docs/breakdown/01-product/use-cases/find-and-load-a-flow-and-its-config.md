---
id: CP-001
type: capability
title: Find and load a flow and its config
summary: Browse a project, pick a flow module, open its TOML config
date: 2026-11-12
status: current
---

# Find and load a flow and its config

The operator browses the project, opens one flow module and one TOML config, and sees both selections.

- **Request:** "show me this project's flow modules and configs, and let me pick one of each."
- **Goal:** preview the real project files, not a copy.
- **Observable outcome:** the browser lists folders plus flow modules and TOML configs; the selection area names the chosen module, config, and flow, and browsing stays inside the configured project root (`INFO-010`).
- **Where it fits:** the first step of every session, and the input to the preview (`CP-003`).
- **Where it strains:** a config written for a different module still loads; the mismatch shows only at Evaluate as an unknown flow.
