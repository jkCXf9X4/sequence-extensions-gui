---
id: INFO-012
type: info
title: Which files make up the package
summary: Module roles under src/seq_ext_gui and tests
date: 2026-11-12
status: current
---

# Which files make up the package

The package is one Python package, one static directory, a pytest suite, and three project docs.

- **Core:** `contracts` holds the wire models, `engine` adapts the flow engine, `worker` is the subprocess entry point.
- **Server:** `app` defines the endpoints, `jobs` supervises workers, `files` confines browsing, `cli` starts uvicorn.
- **Static:** `index.html`, `app.js`, `graph.js`, `styles.css`; no build output.
- **Tests:** one module per concern — API, engine, files, jobs, worker, static — plus `conftest.py` fixtures.
- **Docs:** `README.md` for users, `AGENTS.md` for contributors, `docs/architecture.md` for the wire contract.
- **Packaging:** `pyproject.toml`, `requirements-dev.txt`, `setup.sh`, and `.github/workflows/tests.yml`.
