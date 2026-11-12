---
id: CP-007
type: capability
title: Understand why a run failed
summary: See the failing node path, the error, and the verdict
date: 2026-11-12
status: current
---

# Understand why a run failed

A failed run shows the failing node path, the error, the status, and the log; a plan or import error is reported before any node runs.

- **Request:** "tell me what broke and where."
- **Goal:** fix the flow or the plan without guessing.
- **Observable outcome:** the verdict names failed nodes by path, the error, the status, and the log, while a plan or import error arrives with no run at all.
- **Where it fits:** closes a run (`CP-005`) and drives the next edit (`CP-004`) or plan export (`CP-008`).
- **Where it strains:** an error raised outside the flow's own record can arrive without a node path.
