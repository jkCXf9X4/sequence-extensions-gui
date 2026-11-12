---
id: CP-002
type: capability
title: Choose which flow to run
summary: Pick the target when a module defines several node functions
date: 2026-11-12
status: current
---

# Choose which flow to run

When a module holds several flows the operator picks the target; when exactly one flow is configured, it is used without a choice.

- **Request:** "run the flow I mean from this module, or let the config decide."
- **Goal:** no doubt about which flow the preview describes.
- **Observable outcome:** a flow selector lists the module's flows and defaults to automatic; with one configured flow, Evaluate proceeds on its own.
- **Where it fits:** between loading a module (`CP-001`) and previewing it (`CP-003`).
- **Where it strains:** several flows and no selection stop Evaluate with an error that lists the available flows.
