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
- **Engine:** clones `pyssporg/sequence_extensions` and checks out commit `3bf6f6d9aff007fd76265a7511017aa6dad64c2d`.
- **Install:** `python -m pip install -r requirements-dev.txt`, with pip caching keyed on that file.
- **Lint:** `python -m ruff check src tests`.
- **Test:** `python -m pytest` on Python 3.11 and 3.12, with `fail-fast` off so both finish.
- **Last run:** the run for commit `c84c773` passed.
