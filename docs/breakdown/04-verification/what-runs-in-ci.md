---
id: TEST-003
type: test
title: What runs in CI
summary: Pinned engine checkout, pip install, ruff, pytest on 3.11 and 3.12
date: 2026-11-12
status: current
---

# What runs in CI

CI checks out the GUI and the pinned engine, installs the dev requirements with pip, lints, then runs pytest on two Pythons.

- **Trigger:** every push to `main` and every pull request.
- **Engine:** clones `pyssporg/sequence_extensions` and checks out `3bf6f6d9aff007fd76265a7511017aa6dad64c2d`, the last published `main`.
- **Pin gap:** the GUI's `flow-plan/2` code needs local engine commit `3c40bcb`; the pin cannot pass until that commit is published (`IMP-008`).
- **Install:** `python -m pip install -r requirements-dev.txt`, with pip caching keyed on that file.
- **Lint:** `python -m ruff check src tests`.
- **Test:** `python -m pytest` on Python 3.11 and 3.12, with `fail-fast` off so both finish.
- **Last run:** the remote run for `c84c773` passed; the local `flow-plan/2` commit is not pushed, so CI has not seen it.
