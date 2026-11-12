"""Worker subprocess protocol test."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from seq_ext_gui.contracts import WorkerRequest, WorkerResult


def test_worker_cli_writes_a_parseable_result(tmp_path: Path, sample_project) -> None:
    request = WorkerRequest(
        mode="plan",
        flow_file=str(sample_project.flow),
        config_text=sample_project.read_config(),
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
    assert result.plan.root == "root"
