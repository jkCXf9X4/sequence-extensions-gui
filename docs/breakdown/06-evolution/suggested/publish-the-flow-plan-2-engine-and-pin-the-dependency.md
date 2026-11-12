---
id: IMP-008
type: imp
title: Publish the flow-plan/2 engine and pin the dependency
summary: Make the git dependency and the CI pin refer to a published commit
date: 2026-11-12
status: suggested
---

# Publish the flow-plan/2 engine and pin the dependency

- **Question:** How do the git dependency and the CI pin point at the engine revision that supports `flow-plan/2`?
- **Evidence:** the GUI needs `execute_plan` and `flow-plan/2`, which exist only in local engine commit `3c40bcb`; upstream `main` is `3bf6f6d` and PyPI has no `sequence-extensions-flow` package (`INFO-017`, `TEST-003`).
- **Change:** publish the engine commit, then set the git dependency and the CI checkout to that commit.
- **Risk:** a breaking engine change reaches other consumers; CI and the GUI install stay broken until both repositories move together.
- **Acceptance:** a clean `pip install` of the GUI resolves the engine from git, and CI pins the same commit and passes.
