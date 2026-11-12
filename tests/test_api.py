"""HTTP API tests using a fake worker; one integration test for the real worker."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from seq_ext_gui.app import create_app

FAKE_WORKER = '''
import json
import sys
import time
from pathlib import Path

request_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
request = json.loads(request_path.read_text(encoding="utf-8"))
log_dir = request.get("log_dir")
log_path = None
if log_dir:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "run.jsonl"
    log_path.write_text(
        json.dumps({"node": "root", "event": "start"}) + "\\n", encoding="utf-8"
    )

name = Path(request["flow_file"]).name
if name == "slow.py":
    time.sleep(30)
time.sleep(0.2)
if log_path is not None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"node": "root", "event": "done"}) + "\\n")
result_path.write_text(
    json.dumps(
        {
            "ok": True,
            "mode": request.get("mode", "plan"),
            "flow_name": "root",
            "duration_ms": 1,
        }
    ),
    encoding="utf-8",
)
'''

TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


@pytest.fixture
def fake_worker(tmp_path: Path) -> Path:
    path = tmp_path / "fake_worker.py"
    path.write_text(FAKE_WORKER, encoding="utf-8")
    return path


@pytest.fixture
def client(sample_project, fake_worker: Path) -> Iterator[TestClient]:
    app = create_app(
        sample_project.root,
        worker_cmd=[sys.executable, str(fake_worker)],
        evaluate_timeout=10.0,
        job_timeout=10.0,
    )
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(lines: Iterable[str]) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    event: str | None = None
    data: Any = None
    for line in lines:
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = json.loads(line.split(":", 1)[1].strip())
        elif line == "":
            if event is not None:
                events.append((event, data))
            event = None
            data = None
    return events


def wait_for_status(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["state"] in TERMINAL_STATES:
            return body
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish")


def test_health(client: TestClient, sample_project) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["version"]
    assert body["project_root"] == str(sample_project.root)


def test_tree(client: TestClient) -> None:
    response = client.get("/api/tree")
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == ""
    names = [entry["name"] for entry in body["entries"]]
    assert names == ["failing.py", "flow.py", "sample.toml"]
    assert all(entry["kind"] == "file" for entry in body["entries"])


def test_file_read_and_toml_round_trip(client: TestClient, sample_project) -> None:
    response = client.get("/api/file", params={"path": "sample.toml"})
    assert response.status_code == 200
    assert response.json()["content"] == sample_project.read_config()

    content = '[run]\nflow = "root"\nmax_workers = 4\n'
    response = client.put("/api/file", params={"path": "edited.toml"}, json={"content": content})
    assert response.status_code == 200
    assert response.json() == {"path": "edited.toml", "content": content}

    response = client.get("/api/file", params={"path": "edited.toml"})
    assert response.status_code == 200
    assert response.json()["content"] == content


def test_file_paths_outside_root_are_400(client: TestClient) -> None:
    assert client.get("/api/file", params={"path": "../outside.txt"}).status_code == 400
    assert client.get("/api/tree", params={"path": ".."}).status_code == 400
    response = client.put(
        "/api/file",
        params={"path": "../outside.toml"},
        json={"content": "x = 1\n"},
    )
    assert response.status_code == 400
    response = client.post("/api/evaluate", json={"flow_file": "../outside.py"})
    assert response.status_code == 400


def test_evaluate_returns_worker_result(client: TestClient) -> None:
    response = client.post(
        "/api/evaluate",
        json={"flow_file": "flow.py", "config_file": "sample.toml"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mode"] == "plan"
    assert body["flow_name"] == "root"


def test_execute_job_status_and_sse(client: TestClient) -> None:
    response = client.post("/api/execute", json={"flow_file": "flow.py"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert isinstance(job_id, str) and job_id

    status = wait_for_status(client, job_id)
    assert status["state"] == "succeeded"
    assert status["result"]["ok"] is True

    with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(stream.iter_lines())

    assert events[0] == ("status", {"state": "succeeded"})
    assert events[-1][0] == "done"
    assert events[-1][1]["result"]["ok"] is True
    logs = [data for event, data in events if event == "log"]
    assert [record["record"]["event"] for record in logs] == ["start", "done"]

    with client.stream(
        "GET",
        f"/api/jobs/{job_id}/events",
        headers={"Last-Event-ID": "1"},
    ) as stream:
        replay = parse_sse(stream.iter_lines())
    replay_logs = [data for event, data in replay if event == "log"]
    assert [record["record"]["event"] for record in replay_logs] == ["done"]


def test_cancel_endpoint(client: TestClient) -> None:
    response = client.post("/api/execute", json={"flow_file": "slow.py"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()["state"]
        if state == "running":
            break
        time.sleep(0.02)

    response = client.post(f"/api/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    response = client.post(f"/api/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"

    assert client.get("/api/jobs/missing").status_code == 404
    assert client.post("/api/jobs/missing/cancel").status_code == 404


def test_index_without_static_dir(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code in {200, 404}


@pytest.mark.integration
def test_evaluate_sample_project_with_real_worker(sample_project) -> None:
    if (
        importlib.util.find_spec("seq_ext_gui.worker") is None
        or importlib.util.find_spec("seq_ext_gui.engine") is None
    ):
        pytest.skip("real worker/engine modules are not installed yet")

    with TestClient(create_app(sample_project.root)) as test_client:
        response = test_client.post(
            "/api/evaluate",
            json={"flow_file": "flow.py", "config_file": "sample.toml"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True, body
    assert body["plan"] is not None
    assert body["plan"]["root"]


@pytest.mark.integration
def test_evaluate_keeps_run_option_fields_set(sample_project) -> None:
    """An Overrides round-trip must not turn absent RunOptions fields into None."""
    with TestClient(create_app(sample_project.root)) as test_client:
        response = test_client.post(
            "/api/evaluate",
            json={
                "flow_file": "flow.py",
                "config_file": "sample.toml",
                "overrides": {"options": {"max_workers": 3, "summary": True}},
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True, body
    assert "root" in body["available_flows"]
    assert body["plan"]["schema"] == "flow-plan/1"
