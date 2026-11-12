---
id: INFO-017
type: info
title: How the engine dependency is wired
summary: Editable sibling for development; git dependency still blocked on a published plan/2 commit
date: 2026-11-12
status: current
---

# How the engine dependency is wired

The engine is a separate package, installed editable from the sibling checkout; a portable git dependency waits on an upstream push.

- **Declared:** `pyproject.toml` lists `sequence-extensions-flow>=3.0.1`, but that distribution is not on PyPI.
- **Development:** `requirements-dev.txt` installs `-e ../sequence_extensions` before the GUI, and `setup.sh` builds `../.venv` (`INFO-019`).
- **Plan interface:** the GUI needs `execute_plan` and `flow-plan/2` from local engine commit `3c40bcb`, which is not published; upstream `main` is `3bf6f6d` (`IMP-008`).
- **CI:** pins `3bf6f6d`, so the plan/2 code cannot pass CI until the pin moves (`TEST-003`, `IMP-008`).
- **Upstream:** the engine has zero runtime dependencies; the GUI adds FastAPI and uvicorn.
