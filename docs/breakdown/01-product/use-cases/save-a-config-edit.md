---
id: CP-008
type: capability
title: Save a config edit
summary: Persist TOML changes back to the project file
date: 2026-11-12
status: current
---

# Save a config edit

The operator edits the config text and saves it back to the project file on an explicit action; parse errors surface at Evaluate.

- **Request:** "keep this config change in the project."
- **Goal:** the file on disk matches the editor.
- **Observable outcome:** Save writes only the selected config and reports saved or failed; nothing is written until Save is pressed.
- **Where it fits:** after a failure points at the config (`CP-007`); the saved text feeds the next Evaluate (`CP-003`).
- **Where it strains:** Save does not parse; malformed TOML saves and fails at the next Evaluate.
