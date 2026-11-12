"""Shared fixtures: a tiny project whose flow is fast and deterministic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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

SAMPLE_CONFIG = """\
[run]
module = "flow"
flow = "root"
log = "_out/runs"
max_workers = 2

[node]
retries = 0

[inputs]
n = 3
"""


@dataclass(frozen=True)
class SampleProject:
    root: Path
    flow: Path
    config: Path

    def read_config(self) -> str:
        return self.config.read_text(encoding="utf-8")


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
    (root / "failing.py").write_text(FAILING_FLOW, encoding="utf-8")
    config = root / "sample.toml"
    config.write_text(SAMPLE_CONFIG, encoding="utf-8")
    return SampleProject(root=root, flow=flow, config=config)
