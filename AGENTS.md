# AGENTS

Local web GUI for the `sequence_extensions` flow engine. The GUI previews the
dependency graph of a flow and lets the user edit node parameters before
execution. It is a presentation and orchestration layer only; it does not
re-implement the engine.

## Layout

- `src/seq_ext_gui/` — Python package (src layout, Python >= 3.11).
  - `contracts.py` — wire models shared by API and worker, plus GUI-native
    envelopes. The plan document itself is schema-validated, not modelled.
  - `schema.py` — loads the engine's published `flow-plan/2` JSON Schema and
    validates plan documents against it.
  - `engine.py` — import a flow module by path, plan, apply plan edits, execute.
  - `worker.py` — one-shot subprocess entry point: request JSON in, result JSON out.
  - `app.py` — FastAPI application and endpoints.
  - `jobs.py` — job lifecycle, subprocess supervision, run-log tailing.
  - `files.py` — project-tree browsing restricted to the configured project root.
  - `cli.py` — `seq-ext-gui` entry point.
  - `static/` — browser UI (vanilla JS, no CDN, offline).
- `tests/` — pytest suite; `pytest`.
- `docs/breakdown/` — current state, use cases, and open work. Read
  `docs/breakdown/README.md` first; the breakdown is the source of truth.
- `docs/architecture.md` — derived implementation narrative.
- `requirements-dev.txt` — editable engine checkout, then this package with `[dev]`.
- `setup.sh` — idempotent venv creation and install.
- `../sequence_extensions/` — the engine checkout used during development,
  kept next to this repo so the editable path source resolves. Side-by-side
  checkouts are a local convenience for cross-repo work, not a rule about how
  the project must be laid out. Never edit the engine for GUI features.

## Commands

```bash
./setup.sh                   # create ../.venv and install requirements-dev.txt
source ../.venv/bin/activate
pytest                       # tests
ruff check src tests         # lint
seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner
```

## Rules

1. **Engine API only.** Call `plan_document`, `apply_override`,
   `execute_plan`, `RunOptions`, `NodePolicy`, `jsonable`, `find_nodes`.
   Never copy engine logic into the GUI. The `flow-plan/2` shape belongs to the
   engine: validate against its published JSON Schema (`schema.py`), never
   re-declare the document model locally.
2. **Isolation.** Every evaluate/execute runs in a fresh subprocess. The web
   process never imports user flow modules.
3. **Code wins.** Values a flow binds explicitly cannot be overridden. Mark
   such parameters read-only in the UI; do not pretend an edit took effect.
4. **Per-node policy goes through the plan.** It is supported upstream:
   edits live in `state.plan.nodes[].policy` and reach the engine as
   `RunOptions.node_policies`. Edits are keyed by node identity
   (name, path, instance), so each edit targets one occurrence; name-wide
   overrides remain an engine capability, not the GUI default. Never mutate
   `NodeFunction` attributes.
5. **Offline UI.** No CDN links, no network assets, no build step.
6. **Boring code.** Standard library first, minimal dependencies, no speculative
   abstractions.

## Verification

- `pytest` must pass.
- `ruff check src tests` must pass.
- Product-breakdown checks must pass after editing the tree:
  `pb check --strict` and `pb node-size --strict`.
- Manual: `seq-ext-gui` with `--project-root ../sequence_extensions/examples/flow_runner`,
  select `flows.py` + `plan.json`, press Evaluate, inspect the graph, press Execute.
  Switch the **Project root** field to verify another directory opens.

## Environment notes

- System `python3` is 3.10 and cannot run the engine. `setup.sh` uses `python3.11`.
- The upstream `flow-runner` installed globally is stale; the editable checkout
  in `../sequence_extensions/` is the development target.
- GitHub access uses HTTPS; SSH is blocked.
- The venv lives at `../.venv`, outside both repositories, so no repo tracks it.
