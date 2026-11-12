---
id: INFO-018
type: info
title: How to run the GUI locally
summary: One command, one URL, choose the project root
date: 2026-11-12
status: current
---

# How to run the GUI locally

Start the GUI with one command, open `http://127.0.0.1:8765`, choose `flows.py` and `campaign.toml`, then Evaluate and Execute.

- **Install:** `./setup.sh` creates `.venv` with Python 3.11 and installs the dev requirements.
- **Run:** `seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner` with the venv active.
- **URL:** `http://127.0.0.1:8765` by default; `--host` and `--port` change it (`INFO-015`).
- **Select:** pick `flows.py` then `campaign.toml` in the left panel; Evaluate fills the graph.
- **Inspect:** click a node to edit an unbound parameter, press Execute, and read the streamed log.
