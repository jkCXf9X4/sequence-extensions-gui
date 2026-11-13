---
id: INFO-017
type: info
title: How the engine dependency is wired
summary: Editable sibling for development; git tag v3.1.0 for installs, which also ships the plan schema
date: 2026-11-13
status: current
---

# How the engine dependency is wired

The engine is a separate package, installed editable from the sibling checkout for development and from a pinned git tag otherwise.

- **Declared:** `pyproject.toml` requires `sequence-extensions-flow` from `git+https://github.com/pyssporg/sequence_extensions.git@v3.1.0`; engine 3.1.0 is not on PyPI, so no version range resolves.
- **Schema input:** the pinned engine ships `schemas/flow-plan-2.schema.json` and `flow.plan_schema()`; the GUI validates against that artifact (`INFO-024`).
- **Development:** `requirements-dev.txt` installs `-e ../sequence_extensions` before the GUI, and `setup.sh` builds `../.venv` (`INFO-019`).
- **CI:** checks out the same `v3.1.0` tag before installing (`TEST-003`).
- **Upstream:** the engine has zero runtime dependencies; the GUI adds FastAPI, uvicorn, and `jsonschema`.
