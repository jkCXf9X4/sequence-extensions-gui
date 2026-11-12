# Architecture and wire contract

Current-state facts live in `docs/breakdown/`; this document is derived
implementation narrative.

The GUI is a thin, offline, local presentation layer around the `sequence_extensions`
flow engine. It never imports user flow code into the web process.

```
browser (vanilla JS, SVG graph)
   |  JSON + SSE
FastAPI app (app.py, files.py, jobs.py)
   |  one subprocess per evaluate/execute, request/result JSON files
worker.py -> engine.py -> sequence_extensions API
```

## Hard invariants

1. `app.py`, `jobs.py`, `files.py` never import `sequence_extensions` or a user
   flow module. Only `engine.py` does, and only inside the worker process.
2. `engine.py` uses only `plan_document`, `apply_override`,
   `parameters_from_document`, `execute_flow`, `RunOptions`, `NodePolicy`,
   `jsonable`, `find_nodes`, `RunnerConfig`. No engine logic is copied.
3. Every evaluate/execute gets a fresh worker process and a fresh job directory.
4. Values the flow binds explicitly are not overridable and are shown read-only.
5. No CDN, no network assets, no build step in `static/`.

## Worker protocol

Invocation (cwd is arbitrary, the worker changes into the request `cwd`):

```
python -m seq_ext_gui.worker <request.json> <result.json>
```

`request.json` is a `contracts.WorkerRequest`; `result.json` is a
`contracts.WorkerResult`. The worker always writes a result file, exits 0 on a
handled flow error (`ok=false`) and non-zero only for catastrophic failures.
Nothing else is written to stdout/stderr except a short traceback on crash.

`log_dir` is an absolute per-job directory chosen by `jobs.py`. `engine.execute`
sets `RunOptions.log` to it; `jobs.py` tails the single `*.jsonl` file for SSE.

## engine.py

```python
def plan(request: WorkerRequest) -> WorkerResult
def execute(request: WorkerRequest) -> WorkerResult
```

Both share one prepare path:

1. `os.chdir(request.cwd or flow_file.parent)` so TOML-relative paths behave
   like the CLI.
2. Parse `config_text` (preferred) or `config_file` with `tomllib`, then
   `RunnerConfig.from_dict(data)`; validation errors become `ok=false`.
3. Import the flow file by absolute path (verified loader: package-aware branch,
   `sys.modules` registration before `exec_module`, parent on `sys.path`).
4. `find_nodes(module)`; select `request.flow_name or cfg.flow or` the only
   node. Ambiguity returns `ok=false` with `available_flows` populated.
5. Apply `request.overrides.policy` by mutating the `NodeFunction` attributes
   (`retries`, `retry_delay_seconds`, `timeout`). This is upstream-unsupported;
   add a warning string describing exactly what was mutated.
6. Build `RunOptions` from `cfg.options`, then apply `overrides.options`
   (`dataclasses.replace` with only the fields in `model_fields_set`), then merge
   `overrides.node_defaults` into `node_defaults`. `execute` additionally forces
   `log=Path(request.log_dir)`.
7. Root arguments: start from `cfg.inputs`, filter to the target signature,
   merge `overrides.root` after `decode_value(value, param_type)`. Root values
   are always passed as kwargs, never through the registry, because explicit
   kwargs win over the registry. A missing required root parameter is
   `ok=false` with the parameter names.
8. `plan_document(fn, options=..., **root_kwargs)` then encode to `WirePlan`.

`execute` then:

9. Re-apply node edits to the raw document with `apply_override(doc, override)`
   using `{"nodes": [{"name": n, "params": [{"name": p, "value": v}]}]}`;
   registry = `parameters_from_document(edited)` with the root entry removed.
10. `execute_flow(fn, options=run_options, **root_kwargs)`; on exception, use
    `exc.run` when present and map it to `RunResult`; never swallow.
11. Return `ok=true` with `run` and the post-edit plan. `run.result` is passed
    through `jsonable`.

### Parameter editability rule (documented heuristic)

- Root parameters: editable.
- Node parameter with `required=true` and a non-null value: read-only,
  `note="set by flow code"`.
- Node parameter with `required=false` and `value == default`: editable.
- Node parameter whose value differs from its default: read-only with
  `note="possibly set by flow code"`.
- `kind="gather"` nodes: no parameters.
- Overrides are keyed by node *name*, not instance. When a name has multiple
  instances with differing parameter values, keep them editable but add a
  warning: the edit applies to every instance.

## HTTP API (all JSON, same origin)

| Method | Path | Body / result |
|---|---|---|
| GET | `/api/health` | `HealthResponse` |
| GET | `/api/tree?path=` | `TreeResponse`; dirs plus `*.py`/`*.toml` files, hidden and `__pycache__`/`.git`/`.venv`/`runs` skipped |
| GET | `/api/file?path=` | `FileContent`; read `.py`/`.toml` under the project root |
| PUT | `/api/file?path=` | `SaveFileRequest`; only `.toml`, UTF-8, path confined to root |
| POST | `/api/evaluate` | `JobRequest` -> `WorkerResult` (synchronous, spawned worker) |
| POST | `/api/execute` | `JobRequest` -> `{"job_id": str}` |
| GET | `/api/jobs/{id}` | `JobStatus` |
| GET | `/api/jobs/{id}/events` | SSE: `status` | `log` | `done` events |
| POST | `/api/jobs/{id}/cancel` | `JobStatus`; kills the process group |

All `path`/`flow_file`/`config_file`/`cwd` values are resolved against the
configured project root; anything outside it is rejected with HTTP 400.
`project_root` comes from `seq-ext-gui --project-root`, else
`SEQ_EXT_GUI_PROJECT_ROOT`, else the current directory.

SSE event shapes:

```
event: status
data: {"state": "running"}          (also queued/cancelled)

event: log
data: {"record": {...}}             (one parsed JSONL run-log record)

event: done
data: {"state": "succeeded", "result": {...WorkerResult}}
```

The stream closes after `done`. Late subscribers get the current status first.

## Frontend

Two vertical panels, per the product request:

- Left: project file browser, flow `.py` selector, TOML config selector, TOML
  editor (plain textarea, monospace), run-option fields, **Evaluate** button.
- Right: SVG DAG (oriented top-to-bottom, layered by longest path), node click
  selects it and opens the parameter editor in a side column, **Execute**
  button, live run log, result banner.

Editable parameter widgets derive from `Param.type`: `bool` checkbox, `int`/
`float` number input, `Path`/`str` text input, `list`/`dict` JSON textarea.
Read-only params render disabled with their `note` as a tooltip.
Evaluate is required before Execute; changing a parameter marks the plan dirty
and re-enables Evaluate.
