"""Shared fixtures: a tiny project whose flow is fast and deterministic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

SAMPLE_FLOW = '''\
"""Sample flow used by the test suite."""

from __future__ import annotations

from sequence_extensions.flow import gather, node


@node
def double(x: int) -> int:
    return x * 2


@node
def scale(value: int, factor: int = 1) -> int:
    return value * factor


@node
def root(n: int = 2, factor: int = 3) -> list:
    doubled = [double.submit(i) for i in range(n)]
    # factor is left unset so the GUI can override it.
    return gather([scale.submit(item) for item in doubled])
'''

REQUIRED_FLOW = '''\
"""Sample flow with a required root input."""

from __future__ import annotations

from pathlib import Path

from sequence_extensions.flow import node


@node
def needs_input(cases_dir: Path) -> str:
    return str(cases_dir)
'''

FAILING_FLOW = '''\
"""Sample flow whose child always fails."""

from __future__ import annotations

from sequence_extensions.flow import node


@node
def boom() -> None:
    raise ValueError("kaboom")


@node
def failing() -> None:
    return boom.submit()
'''

#: A hand-written ``flow-plan/2`` seed: only the values a user edited.  The GUI
#: imports a document like this, and ``engine.plan`` folds it onto fresh code.
SAMPLE_PLAN: dict[str, Any] = {
    "schema": "flow-plan/2",
    "parameters": [
        {"name": "n", "type": "int", "required": False, "default": 2, "value": 3}
    ],
    "nodes": [
        {
            "name": "scale",
            "params": [
                {"name": "factor", "type": "int", "required": False, "default": 1, "value": 10}
            ],
            "policy": {"retries": 2},
        }
    ],
    "edges": [],
    "options": {"max_workers": 2},
}


@dataclass(frozen=True)
class SampleProject:
    root: Path
    flow: Path
    required: Path
    failing: Path

    def write_plan(self, document: dict[str, Any], name: str = "plan.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return path


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def examples_dir(repo_root: Path) -> Path:
    return repo_root.parent / "sequence_extensions" / "examples" / "flow_runner"


@pytest.fixture
def sample_project(tmp_path: Path) -> SampleProject:
    root = tmp_path / "project"
    root.mkdir()
    flow = root / "flow.py"
    flow.write_text(SAMPLE_FLOW, encoding="utf-8")
    required = root / "required.py"
    required.write_text(REQUIRED_FLOW, encoding="utf-8")
    failing = root / "failing.py"
    failing.write_text(FAILING_FLOW, encoding="utf-8")
    return SampleProject(root=root, flow=flow, required=required, failing=failing)


@pytest.fixture
def sample_plan(sample_project: SampleProject) -> dict[str, Any]:
    """A full ``flow-plan/2`` document generated from the hand-written seed."""
    from seq_ext_gui.contracts import WorkerRequest
    from seq_ext_gui.engine import plan

    result = plan(
        WorkerRequest(
            mode="plan",
            flow_file=str(sample_project.flow),
            flow_name="root",
            plan=SAMPLE_PLAN,
        )
    )
    assert result.ok, result.error
    assert result.plan is not None
    return result.plan.to_document()
