"""Wire models shared by the HTTP API and the worker subprocess.

Everything that crosses a process boundary is defined here exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PLAN_SCHEMA = "flow-plan/1"


class Policy(BaseModel):
    """Effective node policy as reported by the plan document."""

    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout: float | None = None


class PolicyEdit(BaseModel):
    """Policy delta; unset fields are left alone."""

    retries: int | None = None
    retry_delay_seconds: float | None = None
    timeout: float | None = None

    model_config = ConfigDict(extra="forbid")


class OptionsEdit(BaseModel):
    """``RunOptions`` delta; unset fields are left alone."""

    max_workers: int | None = None
    log: str | None = None
    summary: bool | None = None
    fixed_clock: bool | None = None
    retries: int | None = None
    retry_delay_seconds: float | None = None
    timeout: float | None = None

    model_config = ConfigDict(extra="forbid")


class Param(BaseModel):
    name: str
    type: str = ""
    required: bool = False
    default: Any = None
    value: Any = None
    display: str = ""
    editable: bool = True
    note: str | None = None


class PlanNode(BaseModel):
    id: int
    name: str
    kind: str = "node"
    path: list[str] = Field(default_factory=list)
    instance: int = 1
    policy: Policy = Field(default_factory=Policy)
    params: list[Param] = Field(default_factory=list)


class PlanEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: int = Field(alias="from")
    target: int = Field(alias="to")


class WirePlan(BaseModel):
    schema_name: str = Field(default=PLAN_SCHEMA, alias="schema")
    root: str
    parameters: list[Param] = Field(default_factory=list)
    nodes: list[PlanNode] = Field(default_factory=list)
    edges: list[PlanEdge] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class Overrides(BaseModel):
    """User edits applied on top of the planned flow."""

    root: dict[str, Any] = Field(default_factory=dict)
    nodes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    policy: dict[str, PolicyEdit] = Field(default_factory=dict)
    node_defaults: PolicyEdit | None = None
    options: OptionsEdit | None = None


class JobRequest(BaseModel):
    flow_file: str
    config_file: str | None = None
    config_text: str | None = None
    flow_name: str | None = None
    cwd: str | None = None
    overrides: Overrides = Field(default_factory=Overrides)


class WorkerRequest(JobRequest):
    mode: Literal["plan", "execute"]
    log_dir: str | None = None


class RunResult(BaseModel):
    status: str
    result: Any = None
    run_id: str = ""
    node: str = ""
    duration_ms: int = 0
    attempt: int = 1
    started: str = ""
    ended: str = ""
    log: str | None = None
    error: str | None = None
    error_type: str | None = None
    failed_nodes: list[list[str]] = Field(default_factory=list)


class WorkerResult(BaseModel):
    ok: bool
    mode: str = "plan"
    flow_name: str | None = None
    available_flows: list[str] = Field(default_factory=list)
    plan: WirePlan | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    run: RunResult | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_type: str | None = None
    traceback: str | None = None
    duration_ms: int = 0


class JobStatus(BaseModel):
    id: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    created: str
    started: str | None = None
    ended: str | None = None
    exit_code: int | None = None
    error: str | None = None
    result: WorkerResult | None = None
    log_dir: str | None = None


class FileEntry(BaseModel):
    path: str
    name: str
    kind: Literal["dir", "file"]
    size: int | None = None
    mtime: float | None = None


class TreeResponse(BaseModel):
    root: str
    path: str
    entries: list[FileEntry] = Field(default_factory=list)


class FileContent(BaseModel):
    path: str
    content: str


class SaveFileRequest(BaseModel):
    content: str


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    project_root: str


def encode_value(value: Any) -> tuple[Any, str, bool, str | None]:
    """Return ``(json_value, display, editable, note)`` for a raw Python value."""
    if isinstance(value, Path):
        text = str(value)
        return text, text, True, None
    if value is None or isinstance(value, bool | int | float | str):
        return value, repr(value), True, None
    if isinstance(value, list | tuple | dict):
        try:
            return json.loads(json.dumps(value)), repr(value), True, None
        except (TypeError, ValueError):
            return None, repr(value), False, f"unsupported value type: {type(value).__name__}"
    return None, repr(value), False, f"unsupported value type: {type(value).__name__}"


def decode_value(value: Any, type_hint: str) -> Any:
    """Coerce a JSON value back to the Python type named by ``type_hint``."""
    hint = (type_hint or "").strip()
    if hint.endswith("Path") and value is not None:
        return Path(str(value)).expanduser()
    if hint in {"int", "float", "str", "bool"} and isinstance(value, str):
        text = value.strip()
        if hint == "int":
            return int(text)
        if hint == "float":
            return float(text)
        if hint == "bool":
            lowered = text.lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no", ""}:
                return False
            raise ValueError(f"cannot read {value!r} as bool")
        return text
    return value


def policy_from_mapping(mapping: dict[str, Any] | None) -> Policy:
    mapping = mapping or {}
    return Policy(
        retries=int(mapping.get("retries") or 0),
        retry_delay_seconds=float(mapping.get("retry_delay_seconds") or 0.0),
        timeout=None if mapping.get("timeout") is None else float(mapping["timeout"]),
    )
