---
id: INFO-009
type: info
title: What crosses the wire between API and worker
summary: One contracts module; request and result JSON files
date: 2026-11-12
status: current
---

# What crosses the wire between API and worker

`contracts.py` defines every model that crosses between API and worker; the wire data is JSON files.

- **Single model:** `JobRequest`, `WorkerRequest`, `WorkerResult`, `JobStatus`, `WirePlan`, and the file payloads live in one module.
- **Request file:** `JobRequest` carries `flow_file`, optional `flow_name`, and the optional `plan` document; `WorkerRequest` adds `mode` and `log_dir`. Absent fields stay absent, and the plan, when present, is authoritative.
- **Result file:** written with `by_alias=True`; `schema`, `from`, and `to` are aliases the browser expects. It carries the plan, the run account, warnings, and any error.
- **Direction:** the API writes a request; the worker writes a result; neither shares memory with the other.
