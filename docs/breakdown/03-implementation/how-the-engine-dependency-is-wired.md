---
id: INFO-017
type: info
title: How the engine dependency is wired
summary: Editable path dependency, pinned CI checkout, zero-dependency upstream
date: 2026-11-12
status: current
---

# How the engine dependency is wired

The engine is a separate package, installed editable during development and pinned to one commit in CI.

- **Declared:** `pyproject.toml` lists `sequence-extensions-flow>=3.0.1` as a runtime dependency.
- **Development:** `requirements-dev.txt` installs `-e ../sequence_extensions` before the GUI.
- **CI:** the workflow clones `pyssporg/sequence_extensions` and checks out `3bf6f6d9aff007fd76265a7511017aa6dad64c2d`.
- **Upstream:** the engine has zero runtime dependencies.
- **GUI deps:** the GUI adds FastAPI, uvicorn, and the dev tools.
