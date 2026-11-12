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
- **Request file:** written with `exclude_unset=True`, so absent fields stay absent instead of becoming null.
- **Partial options:** `model_fields_set` survives the dump, so an unset `overrides.options` field is not reset.
- **Result file:** written with `by_alias=True`; `schema`, `from`, and `to` are aliases the browser expects.
- **Direction:** the API writes a request; the worker writes a result; neither shares memory with the other.
