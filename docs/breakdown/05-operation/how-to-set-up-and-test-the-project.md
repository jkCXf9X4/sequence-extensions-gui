---
id: INFO-019
type: info
title: How to set up and test the project
summary: setup.sh venv, editable engine checkout, pytest, ruff
date: 2026-11-12
status: current
---

# How to set up and test the project

Run `./setup.sh`, activate the venv, then run pytest and ruff; the engine checkout sits beside the GUI repo.

- **Install:** `./setup.sh` creates `.venv` with `python3.11` and installs `requirements-dev.txt`.
- **Engine layout:** `requirements-dev.txt` installs `-e ../sequence_extensions`, so the engine checkout sits beside the GUI repo (`INFO-017`).
- **Test:** `pytest` collects 51 tests (`TEST-001`).
- **Lint:** `ruff check src tests`.
