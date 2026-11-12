---
id: IMP-004
type: imp
title: Save and restore a session
summary: Keep the flow, edited TOML, and overrides across reloads
date: 2026-11-12
status: suggested
---

# Save and restore a session

- **Question:** Can the GUI keep the selected flow, edited TOML, and overrides across a reload?
- **Evidence:** a reload loses the flow selection, TOML edits, and overrides because no persistence exists today.
- **Change:** save and restore one session.
- **Risk:** stale state can outlive the config it came from.
- **Acceptance:** reload restores the flow, the config text, and the overrides.
