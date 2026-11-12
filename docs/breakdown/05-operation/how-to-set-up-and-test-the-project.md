---
id: INFO-019
type: info
title: How to set up and test the project
summary: setup.sh builds ../.venv, editable engine checkout, pytest, ruff
date: 2026-11-12
status: current
---

# How to set up and test the project

Run `./setup.sh`, activate the shared venv one level above the repos, then run pytest and ruff.

- **Install:** `./setup.sh` creates `../.venv` with `python3.11` and installs `requirements-dev.txt`.
- **Venv:** lives beside both repositories, so neither repo tracks or deletes it.
- **Engine layout:** `requirements-dev.txt` installs `-e ../sequence_extensions`, so the engine checkout sits beside the GUI repo (`INFO-017`).
- **Test:** `pytest` collects 72 tests (`TEST-001`).
- **Lint:** `ruff check src tests`.
