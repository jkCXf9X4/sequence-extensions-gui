"""Engine tests: plan and execute real flow files."""

from __future__ import annotations

from pathlib import Path

from seq_ext_gui.contracts import Overrides, PolicyEdit, WorkerRequest
from seq_ext_gui.engine import execute, plan


def test_plan_example_flow(examples_dir: Path) -> None:
    result = plan(
        WorkerRequest(
            mode="plan",
            flow_file=str(examples_dir / "flows.py"),
            config_file=str(examples_dir / "campaign.toml"),
            cwd=str(examples_dir),
        )
    )

    assert result.ok, result.error
    assert result.plan is not None
    assert result.plan.root == "campaign"
    names = {node.name for node in result.plan.nodes}
    assert {"simulate", "evaluate", "summarize", "gather"} <= names
    assert result.plan.edges


def test_plan_requires_a_flow_when_ambiguous(sample_project) -> None:
    result = plan(
        WorkerRequest(
            mode="plan",
            flow_file=str(sample_project.flow),
            config_text="[inputs]\nn = 3\n",
        )
    )

    assert result.ok is False
    assert {"double", "root", "scale"} <= set(result.available_flows)
    assert "no flow selected" in (result.error or "")


def test_plan_applies_the_editability_heuristic(sample_project) -> None:
    result = plan(
        WorkerRequest(
            mode="plan",
            flow_file=str(sample_project.flow),
            config_text=sample_project.read_config(),
        )
    )

    assert result.ok, result.error
    assert result.plan is not None
    scale = next(node for node in result.plan.nodes if node.name == "scale")
    factor = next(param for param in scale.params if param.name == "factor")
    assert factor.editable is True

    double = next(node for node in result.plan.nodes if node.name == "double")
    bound = next(param for param in double.params if param.name == "x")
    assert bound.editable is False
    assert bound.note == "set by flow code"

    # ``double`` has several instances with different values.
    assert any("double" in warning and "every instance" in warning for warning in result.warnings)


def test_policy_override_mutates_nodes_and_warns(sample_project) -> None:
    result = plan(
        WorkerRequest(
            mode="plan",
            flow_file=str(sample_project.flow),
            config_text=sample_project.read_config(),
            overrides=Overrides(
                policy={"scale": PolicyEdit(retries=2, timeout=5.0)},
                node_defaults=PolicyEdit(retry_delay_seconds=0.5),
            ),
        )
    )

    assert result.ok, result.error
    assert result.plan is not None
    scale = [node for node in result.plan.nodes if node.name == "scale"]
    assert scale
    assert all(node.policy.retries == 2 for node in scale)
    assert all(node.policy.timeout == 5.0 for node in scale)
    assert any("scale" in warning and "retries=2" in warning for warning in result.warnings)


def test_execute_applies_node_override_and_writes_log(
    sample_project, tmp_path: Path
) -> None:
    log_dir = tmp_path / "logs"
    result = execute(
        WorkerRequest(
            mode="execute",
            flow_file=str(sample_project.flow),
            config_text=sample_project.read_config(),
            log_dir=str(log_dir),
            overrides=Overrides(nodes={"scale": {"factor": 10}}),
        )
    )

    assert result.ok, result.error
    assert result.run is not None
    assert result.run.status == "ok"
    # double(i) for i in range(3) is [0, 2, 4]; scale.factor=10.
    assert result.run.result == [0, 20, 40]
    assert result.run.log is not None
    assert Path(result.run.log).parent == log_dir
    assert list(log_dir.glob("*.jsonl"))


def test_execute_maps_flow_failure_to_result(
    sample_project, tmp_path: Path
) -> None:
    result = execute(
        WorkerRequest(
            mode="execute",
            flow_file=str(sample_project.root / "failing.py"),
            config_text='[run]\nflow = "failing"\n',
            log_dir=str(tmp_path / "logs"),
        )
    )

    assert result.ok is False
    assert result.run is not None
    assert result.run.status == "error"
    assert "kaboom" in (result.error or "")
    assert "kaboom" in (result.run.error or "")
    assert result.run.failed_nodes == [["failing", "boom"]]
    assert result.traceback
