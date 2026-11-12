"""Worker subprocess protocol test."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from seq_ext_gui.contracts import WorkerRequest, WorkerResult


def test_worker_cli_writes_a_parseable_result(tmp_path: Path, sample_project) -> None:
    plan = {
        "schema": "flow-plan/2",
        "parameters": [
            {"name": "n", "type": "int", "required": False, "default": 2, "value": 3}
        ],
        "nodes": [
            {
                "name": "scale",
                "params": [{"name": "factor", "type": "int", "default": 1, "value": 10}],
                "policy": {"retries": 2},
            }
        ],
        "edges": [],
        "options": {"max_workers": 2},
    }
    request = WorkerRequest(
        mode="plan",
        flow_file=str(sample_project.flow),
        flow_name="root",
        plan=plan,
    )
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(request.model_dump_json(by_alias=True), encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "seq_ext_gui.worker", str(request_path), str(result_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    result = WorkerResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    assert result.ok, result.error
    assert result.mode == "plan"
    assert result.plan is not None
    assert result.plan.schema_name == "flow-plan/2"
    document = result.plan.to_document()
    assert "root" not in document
    parameters = {param["name"]: param["value"] for param in document["parameters"]}
    assert parameters["n"] == 3
    assert document["options"]["max_workers"] == 2
    scale = next(node for node in result.plan.nodes if node.name == "scale")
    assert scale.policy.retries == 2
