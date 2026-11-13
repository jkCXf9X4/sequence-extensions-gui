---
id: TEST-003
type: test
title: What runs in CI
summary: Pinned engine checkout at v3.1.0, pip install, ruff, pytest on 3.11 and 3.12
date: 2026-11-13
status: current
---

# What runs in CI

CI checks out the GUI and the pinned engine, installs the dev requirements with pip, lints, then runs pytest on two Pythons.

- **Trigger:** every push to `main` and every pull request.
- **Engine:** clones `pyssporg/sequence_extensions` and checks out `v3.1.0`, the release the suite was verified against.
- **Install:** `python -m pip install -r requirements-dev.txt`, with pip caching keyed on that file.
- **Lint:** `python -m ruff check src tests`.
- **Test:** `python -m pytest` on Python 3.11 and 3.12, with `fail-fast` off so both finish.
- **Same pin:** the workflow, `pyproject.toml`, and the development checkout name the same engine tag (`INFO-017`).
