---
id: INFO-018
type: info
title: How to run the GUI locally
summary: One command, one URL, choose the project root
date: 2026-11-12
status: current
---

# How to run the GUI locally

Start the GUI with one command, open `http://127.0.0.1:8765`, choose `flows.py` and `plan.json`, then Evaluate and Execute.

- **Install:** `./setup.sh` creates `../.venv` with Python 3.11, then `source ../.venv/bin/activate`.
- **Run:** `seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner` with the venv active.
- **URL:** `http://127.0.0.1:8765` by default; `--host` and `--port` change it (`INFO-015`).
- **Root:** the **Project root** field opens another directory; a running job must finish first (`CP-009`).
- **Select:** expand directories in the project file tree, then pick `flows.py` and `plan.json`; clicking the JSON imports it and selects the flow the plan was built from, and Evaluate fills the graph. A flow with required root inputs needs that import first.
- **Inspect:** click a node to edit an unbound parameter, press Execute, and read the streamed log.
