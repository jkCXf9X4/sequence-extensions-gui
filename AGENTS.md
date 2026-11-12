# AGENTS

Local web GUI for the `sequence_extensions` flow engine. The GUI previews the
dependency graph of a flow and lets the user edit node parameters before
execution. It is a presentation and orchestration layer only; it does not
re-implement the engine.

## Layout

- `src/seq_ext_gui/` — Python package (src layout, Python >= 3.11).
  - `contracts.py` — wire models shared by API and worker. Single source of truth.
  - `engine.py` — import a flow module by path, plan, apply overrides, execute.
  - `worker.py` — one-shot subprocess entry point: request JSON in, result JSON out.
  - `app.py` — FastAPI application and endpoints.
  - `jobs.py` — job lifecycle, subprocess supervision, run-log tailing.
  - `files.py` — project-tree browsing restricted to the configured project root.
  - `cli.py` — `seq-ext-gui` entry point.
  - `static/` — browser UI (vanilla JS, no CDN, offline).
- `tests/` — pytest suite; `uv run pytest`.
- `../sequence_extensions/` — the engine checkout used during development,
  kept next to this repo so the editable path source resolves. Side-by-side
  checkouts are a local convenience for cross-repo work, not a rule about how
  the project must be laid out. Never edit the engine for GUI features.

## Commands

```bash
uv sync --extra dev          # create/refresh .venv with the editable upstream checkout
uv run pytest                # tests
uv run ruff check src tests  # lint
uv run seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner
```

## Rules

1. **Engine API only.** Call `plan_document`, `apply_override`,
   `parameters_from_document`, `execute_flow`, `RunOptions`, `NodePolicy`.
   Never copy engine logic into the GUI.
2. **Isolation.** Every evaluate/execute runs in a fresh subprocess. The web
   process never imports user flow modules.
3. **Code wins.** Values a flow binds explicitly cannot be overridden. Mark
   such parameters read-only in the UI; do not pretend an edit took effect.
4. **Per-node policy is unsupported upstream.** It is applied by mutating
   `NodeFunction` attributes in the worker. Keep it isolated in `engine.py`,
   behind `overrides.policy`, and document it.
5. **Offline UI.** No CDN links, no network assets, no build step.
6. **Boring code.** Standard library first, minimal dependencies, no speculative
   abstractions.

## Verification

- `uv run pytest` must pass.
- `uv run ruff check src tests` must pass.
- Manual: `uv run seq-ext-gui` with `--project-root ../sequence_extensions/examples/flow_runner`,
  select `flows.py` + `campaign.toml`, press Evaluate, inspect the graph, press Execute.

## Environment notes

- System `python3` is 3.10 and cannot run the engine. Use the uv-managed 3.11 venv.
- The upstream `flow-runner` installed globally is stale; the editable checkout
  in `../sequence_extensions/` is the development target.
- GitHub access uses HTTPS; SSH is blocked.
- If `uv` fails with `invalid peer certificate: UnknownIssuer`, the network
  inspects TLS: prefix uv commands with `UV_NATIVE_TLS=1`.
