---
id: INFO-004
type: info
title: How the GUI relates to the engine and CLI
summary: Same engine API as the CLI; the CLI stays the batch path
date: 2026-11-12
status: current
---

# How the GUI relates to the engine and CLI

The GUI shares the engine API with the CLI; the CLI stays the batch path, GUI adds preview and overrides.

- **Same API:** the GUI calls `plan_document`, `apply_override`, `parameters_from_document`, `execute_flow`, `RunOptions`, and `NodePolicy`; it copies no engine logic (`INFO-007`).
- **Shared inputs:** both paths read one flow module and one TOML config.
- **CLI role:** `flow-runner config.toml` runs a prepared config as the batch path, with no preview or edit step.
- **GUI adds:** graph preview, per-run overrides, and a run log that streams while the run runs (`REQ-004`).
- **Isolation:** every GUI evaluate or execute runs in a fresh subprocess; the web process never imports flow code (`INFO-006`).
- **Limitation:** a value the flow binds explicitly stays read-only; the GUI cannot override code (`INFO-007`, `REQ-001`).
