# sequence-extensions-gui

Local web GUI for the [`sequence_extensions`](https://github.com/pyssporg/sequence_extensions)
flow engine. Point it at a workflow module, import a `flow-plan/2` JSON plan
(or build one from the module), press **Evaluate** to see the dependency
graph, edit parameters and run options, then press **Execute** and watch the
run log stream in. The plan imports and exports as one JSON document and is
the only runner configuration.

Offline by design: no CDN, no build step, no telemetry. The web process never
imports your flow code; every evaluate or execute runs in a fresh subprocess.

## Install (development)

```bash
# check out the GUI and the engine side by side
git clone https://github.com/jkCXf9X4/sequence-extensions-gui
git clone https://github.com/pyssporg/sequence_extensions
cd sequence-extensions-gui
./setup.sh
source ../.venv/bin/activate
pytest
ruff check src tests
```

`setup.sh` creates `../.venv` (beside both repositories) with `python3.11` and installs
`requirements-dev.txt`, which installs the sibling engine checkout editable
before this package. Point that path elsewhere if your checkout lives in a
different place.

## Run

```bash
source ../.venv/bin/activate
seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner
# open http://127.0.0.1:8765
```

Pick `flows.py` and its `plan.json` in the left panel (clicking the JSON imports
it), press **Evaluate**, click a node, edit a parameter or policy that the flow
leaves unset, press **Execute**. A flow with required root inputs needs its plan
imported first; Evaluate alone cannot invent those values. Use **Export plan**
to download the current document as `plan.json`.

Options: `--host`, `--port`, `--project-root`; `SEQ_EXT_GUI_PROJECT_ROOT` is the
environment fallback. The **Project root** field switches directories without a
restart; a running job must finish first.

## What it can and cannot change

- **Root inputs and unbound node parameters** can be edited in the plan. Values
  the flow passes explicitly always win; those parameters are shown read-only.
- **Run options** (`max_workers`, `summary`, `fixed_clock`, run-level
  `retries`/`retry_delay_seconds`/`timeout`) are bound directly to the plan's
  `options`; the log directory stays per run and is not part of the document.
- **Per-node policy** is supported upstream: edits go into
  `plan.nodes[].policy` and reach the engine as `RunOptions.node_policies`.
- **Flow selection is external**: the dropdown chooses the root node and is
  never written into the plan.
- Edits are keyed by node **name**: all instances of a repeated node share an
  edit.

See [`docs/architecture.md`](docs/architecture.md) for the wire contract and
the subprocess protocol.

## Breakdown

[`docs/breakdown/`](docs/breakdown/README.md) holds the project's current state:
intent, use cases, architecture, verification, operation, review, and the open
improvements. Start at its `README.md`. It is the source of truth; this README is
the front door.

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
