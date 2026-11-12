---
id: TEST-001
type: test
title: What the test suite proves
summary: Static, engine, API, integration, and browser checks
date: 2026-11-12
status: current
---

# What the test suite proves

The suite proves the static assets, engine adapter, API, job lifecycle, and real-worker path; it cannot prove the browser runs them together.

- **Static assets:** `test_static.py` checks every asset exists, stays local, avoids `innerHTML`, parses with `node --check`, and lays out empty, sparse, and aliased graphs.
- **Engine:** `test_engine.py` plans the campaign example and executes the sample flow, covering the plan document shape, the editability heuristic, plan-seeded parameter and policy edits, options, logs, and mapped flow failure.
- **API and jobs:** `test_api.py` and `test_jobs.py` drive every endpoint, SSE replay, cancel, timeout, and crash path through a fake worker.
- **Fake isolation:** the fake worker keeps HTTP and job tests free of engine startup cost and flow behaviour, so a job bug shows without a real flow.
- **Integration:** two `@pytest.mark.integration` API tests and one worker CLI test start the real worker and engine.
- **Manual browser:** the evaluate-edit-execute walkthrough is a hand check, not an automated test (`TEST-004`).
- **Count:** `pytest` collects 72 tests: static 26, jobs 11, API 17, files 6, engine 11, worker 1.
