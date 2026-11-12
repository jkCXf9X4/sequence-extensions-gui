# sequence-extensions-gui

Local web GUI for the [`sequence_extensions`](https://github.com/pyssporg/sequence_extensions)
flow engine. Point it at a flow module and a TOML runner config, press
**Evaluate** to see the dependency graph, edit node parameters, then press
**Execute** and watch the run log stream in.

Offline by design: no CDN, no build step, no telemetry. The web process never
imports your flow code; every evaluate or execute runs in a fresh subprocess.

## Install (development)

```bash
# check out the GUI and the engine side by side
git clone https://github.com/jkCXf9X4/sequence-extensions-gui
git clone https://github.com/pyssporg/sequence_extensions
cd sequence-extensions-gui
UV_NATIVE_TLS=1 uv sync --extra dev   # only needed behind a TLS-inspecting proxy
uv run pytest
uv run ruff check src tests
```

The engine is a sibling checkout (`../sequence_extensions`), not a nested
repository; `pyproject.toml` installs it editable through `[tool.uv.sources]`.

## Run

```bash
uv run seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner
# open http://127.0.0.1:8765
```

Pick `flows.py` and `campaign.toml` in the left panel, press **Evaluate**, click
a node, edit a parameter that the flow leaves unset, press **Execute**.

Options: `--host`, `--port`, `--project-root`; `SEQ_EXT_GUI_PROJECT_ROOT` is the
environment fallback.

## What it can and cannot change

- **Root inputs and unbound node parameters** can be overridden. Values the flow
  passes explicitly always win; those parameters are shown read-only.
- **Run options** (`max_workers`, `log`, `summary`, `fixed_clock`, run-level
  `retries`/`retry_delay_seconds`/`timeout`) are editable per run.
- **Per-node policy** edits work by mutating `NodeFunction` attributes, which is
  not upstream public API. The UI labels this and the engine keeps it isolated
  in `engine.py`.
- Overrides are keyed by node **name**: all instances of a repeated node share
  an edit.

See `docs/architecture.md` for the wire contract and the subprocess protocol.

## Layout

```
src/seq_ext_gui/
  contracts.py   wire models shared by API and worker
  engine.py      flow import, plan, override, execute
  worker.py      one-shot subprocess entry point
  app.py         FastAPI endpoints
  jobs.py        subprocess supervision and run-log tailing
  files.py       project-root-confined browsing
  cli.py         seq-ext-gui entry point
  static/        index.html, app.js, graph.js, styles.css
```
