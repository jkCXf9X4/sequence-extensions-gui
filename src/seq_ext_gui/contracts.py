"""Wire models shared by the HTTP API and the worker subprocess.

Everything that crosses a process boundary is defined here exactly once.  The
configuration artifact is the engine's ``flow-plan/2`` JSON document: the GUI
imports and exports it, and the worker consumes it verbatim.
"""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PLAN_SCHEMA = "flow-plan/2"


class Policy(BaseModel):
    """Effective node policy as reported by the plan document."""

    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout: float | None = None


class PlanOptions(BaseModel):
    """The six run options a ``flow-plan/2`` document carries."""

    max_workers: int = 16
    summary: bool = False
    fixed_clock: bool = False
    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout: float | None = None


class Param(BaseModel):
    name: str
    type: str = ""
    required: bool = False
    default: Any = None
    value: Any = None
    editable: bool = True
    note: str | None = None


class ParamSpec(BaseModel):
    """One root parameter of a ``@node`` as discovery reports it."""

    name: str
    type: str = ""
    required: bool = False
    default: Any = None
    default_note: str | None = None


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
    """Plan document plus the GUI editability annotations.

    ``to_document`` strips the annotations and returns the engine document the
    GUI imports, exports, and executes.  The root node is deliberately not part
    of the plan: flow selection lives in the GUI dropdown.
    """

    schema_name: str = Field(default=PLAN_SCHEMA, alias="schema")
    parameters: list[Param] = Field(default_factory=list)
    nodes: list[PlanNode] = Field(default_factory=list)
    edges: list[PlanEdge] = Field(default_factory=list)
    options: PlanOptions = Field(default_factory=PlanOptions)

    model_config = ConfigDict(populate_by_name=True)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": self.schema_name,
            "parameters": [_param_document(param) for param in self.parameters],
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "kind": node.kind,
                    "path": list(node.path),
                    "instance": node.instance,
                    "policy": node.policy.model_dump(),
                    "params": [_param_document(param) for param in node.params],
                }
                for node in self.nodes
            ],
            "edges": [{"from": edge.source, "to": edge.target} for edge in self.edges],
            "options": self.options.model_dump(),
        }


class JobRequest(BaseModel):
    flow_file: str
    flow_name: str | None = None
    plan: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class WorkerRequest(JobRequest):
    mode: Literal["plan", "execute", "discover"]
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


class NodeCard(BaseModel):
    """One ``@node`` as the discovery view reports it."""

    name: str
    summary: str = ""
    signature: str = ""
    params: list[ParamSpec] = Field(default_factory=list)


class WorkerResult(BaseModel):
    ok: bool
    mode: str = "plan"
    flow_name: str | None = None
    available_flows: list[str] = Field(default_factory=list)
    nodes: list[NodeCard] = Field(default_factory=list)
    plan: WirePlan | None = None
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


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    project_root: str


class RootRequest(BaseModel):
    """An absolute directory to make the active project root."""

    path: str


def _param_document(param: Param) -> dict[str, Any]:
    return {
        "name": param.name,
        "type": param.type,
        "required": param.required,
        "default": param.default,
        "value": param.value,
    }


def _file_sha256(path: Path) -> str | None:
    """Hex sha256 of a readable regular file, else ``None``.

    Mirrors the engine's ``jsonable`` Path payload so an exported plan can be
    decoded by ``execute_plan`` again.
    """
    try:
        mode = path.stat().st_mode
    except OSError:
        return None
    if not stat.S_ISREG(mode):
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def encode_value(value: Any) -> tuple[Any, bool, str | None]:
    """Return ``(json_value, editable, note)`` for a raw Python value.

    ``Path`` follows the engine's JSON-safe ``jsonable`` form (``{"path": ...,
    "sha256": ...}``) so an exported plan can be decoded by ``execute_plan``.
    """
    if isinstance(value, Path):
        return {"path": str(value), "sha256": _file_sha256(value)}, True, None
    if value is None or isinstance(value, bool | int | float | str):
        return value, True, None
    if isinstance(value, list | tuple | dict):
        try:
            return json.loads(json.dumps(value)), True, None
        except (TypeError, ValueError):
            return None, False, f"unsupported value type: {type(value).__name__}"
    return None, False, f"unsupported value type: {type(value).__name__}"


def decode_value(value: Any, type_hint: str) -> Any:
    """Coerce a JSON value back to the Python type named by ``type_hint``."""
    hint = (type_hint or "").strip()
    if hint.endswith("Path") and value is not None:
        if isinstance(value, dict):
            raw = value.get("path")
            if raw is None:
                raise ValueError(f"cannot read {value!r} as Path")
            value = raw
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
