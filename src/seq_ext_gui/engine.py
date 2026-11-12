"""Plan and execute a flow module inside the worker process.

Only this module imports ``sequence_extensions`` or user flow code.  The web
process talks to it through :mod:`seq_ext_gui.worker`.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib
import importlib.util
import inspect
import os
import sys
import tempfile
import time
import tomllib
import traceback
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

from sequence_extensions.flow import (
    NodeFunction,
    NodePolicy,
    RunOptions,
    apply_override,
    execute_flow,
    jsonable,
    parameters_from_document,
    plan_document,
)
from sequence_extensions.flow_runner import RunnerConfig, find_nodes

from .contracts import (
    Overrides,
    Param,
    PlanEdge,
    PlanNode,
    PolicyEdit,
    RunResult,
    WirePlan,
    WorkerRequest,
    WorkerResult,
    decode_value,
    encode_value,
    policy_from_mapping,
)


class EngineError(ValueError):
    """A handled config/flow error that becomes ``ok=false``."""

    def __init__(self, message: str, *, available_flows: list[str] | None = None) -> None:
        super().__init__(message)
        self.available_flows = list(available_flows or [])


@dataclasses.dataclass
class _Prepared:
    fn: NodeFunction
    selected: str
    run_options: RunOptions
    root_kwargs: dict[str, Any]
    doc: dict[str, Any]
    config: dict[str, Any]
    warnings: list[str]
    available_flows: list[str]


def plan(request: WorkerRequest) -> WorkerResult:
    """Build the wire plan for ``request`` without executing user node bodies."""
    started = time.monotonic()
    try:
        with _working_directory(request) as flow_file:
            prepared = _prepare(request, flow_file, execute=False)
            wire_plan, plan_warnings = _wire_plan(prepared.doc)
        return WorkerResult(
            ok=True,
            mode="plan",
            flow_name=prepared.selected,
            available_flows=prepared.available_flows,
            plan=wire_plan,
            config=prepared.config,
            warnings=prepared.warnings + plan_warnings,
            duration_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return _error_result(request, exc, started, "plan")


def execute(request: WorkerRequest) -> WorkerResult:
    """Plan, apply node edits, and run the flow.  Flow failures are ``ok=false``."""
    started = time.monotonic()
    try:
        with _working_directory(request) as flow_file:
            prepared = _prepare(request, flow_file, execute=True)
            return _execute(request, prepared, started)
    except Exception as exc:
        return _error_result(request, exc, started, "execute")


# ---------------------------------------------------------------- #
# Shared prepare path (architecture steps 1-8)
# ---------------------------------------------------------------- #
@contextlib.contextmanager
def _working_directory(request: WorkerRequest) -> Iterator[Path]:
    """Change into the request cwd (or the flow file's directory)."""
    raw = Path(request.flow_file).expanduser()
    if request.cwd:
        target = Path(request.cwd).expanduser()
    elif raw.is_absolute():
        target = raw.parent
    else:
        target = Path.cwd()
    previous = Path.cwd()
    os.chdir(target)
    try:
        yield raw if raw.is_absolute() else Path.cwd() / raw
    finally:
        os.chdir(previous)


def _prepare(request: WorkerRequest, flow_file: Path, *, execute: bool) -> _Prepared:
    cfg, config_data = _load_config(request)
    module = _import_flow_module(flow_file)
    nodes = find_nodes(module)
    selected, fn = _select_flow(request, cfg, nodes)
    warnings = _apply_policy(request.overrides.policy, nodes)
    run_options = _build_run_options(cfg.options, request.overrides)
    if execute and request.log_dir:
        run_options = dataclasses.replace(run_options, log=Path(request.log_dir))
    root_kwargs = _root_kwargs(fn, cfg.inputs, request.overrides.root)
    doc = plan_document(fn, options=run_options, **root_kwargs)
    return _Prepared(
        fn=fn,
        selected=selected,
        run_options=run_options,
        root_kwargs=root_kwargs,
        doc=doc,
        config=jsonable(config_data) if config_data else {},
        warnings=warnings,
        available_flows=sorted(nodes),
    )


def _load_config(request: WorkerRequest) -> tuple[RunnerConfig, dict[str, Any]]:
    if request.config_text and request.config_text.strip():
        return _config_from_text(request.config_text)
    if request.config_file:
        path = Path(request.config_file)
        if hasattr(RunnerConfig, "from_dict"):
            try:
                with path.open("rb") as fh:
                    data = tomllib.load(fh)
            except OSError as exc:
                raise EngineError(f"cannot read config file {path}: {exc}") from None
            except tomllib.TOMLDecodeError as exc:
                raise EngineError(f"{path}: invalid TOML: {exc}") from None
            return RunnerConfig.from_dict(data, where=str(path)), data
        return RunnerConfig.from_toml(path), {}
    return RunnerConfig(), {}


def _config_from_text(text: str) -> tuple[RunnerConfig, dict[str, Any]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise EngineError(f"invalid TOML: {exc}") from None
    if hasattr(RunnerConfig, "from_dict"):
        return RunnerConfig.from_dict(data, where="config_text"), data

    # Older runners only accept a path; hand them a temporary TOML file.
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        name = fh.name
    try:
        return RunnerConfig.from_toml(name), data
    finally:
        Path(name).unlink(missing_ok=True)


def _import_flow_module(path: str | Path, *, module_name: str | None = None) -> ModuleType:
    """Verified import-by-path loader (spec §1.1)."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"flow module not found: {path}")

    # A file inside a package is imported under its real dotted name so that
    # relative imports and pickling by reference work.
    root = path.parent
    parts = [path.stem]
    while (root / "__init__.py").is_file():
        parts.insert(0, root.name)
        root = root.parent
    if len(parts) > 1:
        dotted = ".".join(parts)
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        importlib.invalidate_caches()
        return importlib.import_module(dotted)

    # Standalone file: unique synthetic name, registered before exec so that
    # dataclasses/pickle can find the module by name.
    name = module_name or "_gui_flow_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    importlib.invalidate_caches()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _select_flow(
    request: WorkerRequest, cfg: RunnerConfig, nodes: dict[str, NodeFunction]
) -> tuple[str, NodeFunction]:
    available = sorted(nodes)
    selected = request.flow_name or cfg.flow
    if selected is None:
        if len(available) != 1:
            listed = ", ".join(available) if available else "none"
            raise EngineError(
                f"no flow selected; {len(available)} available: {listed}",
                available_flows=available,
            )
        selected = available[0]
    fn = nodes.get(selected)
    if fn is None:
        listed = ", ".join(available) if available else "none"
        raise EngineError(
            f"no flow {selected!r} in module; available: {listed}",
            available_flows=available,
        )
    return selected, fn


def _apply_policy(edits: dict[str, PolicyEdit], nodes: dict[str, NodeFunction]) -> list[str]:
    """Mutate ``NodeFunction`` policy attributes; upstream has no public API."""
    warnings: list[str] = []
    for name in sorted(edits):
        edit = edits[name]
        target = nodes.get(name)
        if target is None:
            warnings.append(f"policy override ignored for unknown node {name!r}")
            continue
        changes: list[str] = []
        for field in ("retries", "retry_delay_seconds", "timeout"):
            value = getattr(edit, field)
            if value is not None:
                setattr(target, field, value)
                changes.append(f"{field}={value!r}")
        if changes:
            warnings.append(
                f"policy override applied to node {name!r}: {', '.join(changes)} "
                "(mutates NodeFunction attributes; unsupported upstream)"
            )
    return warnings


def _build_run_options(base: RunOptions, overrides: Overrides) -> RunOptions:
    options = base
    if overrides.options is not None:
        edit = overrides.options
        values = {name: getattr(edit, name) for name in edit.model_fields_set}
        if values:
            options = dataclasses.replace(options, **values)

    edit = overrides.node_defaults
    if edit is not None:
        current = options.node_defaults
        default = current if isinstance(current, NodePolicy) else NodePolicy()
        merged = NodePolicy(
            retries=edit.retries if edit.retries is not None else default.retries,
            retry_delay_seconds=(
                edit.retry_delay_seconds
                if edit.retry_delay_seconds is not None
                else default.retry_delay_seconds
            ),
            timeout=edit.timeout if "timeout" in edit.model_fields_set else default.timeout,
        )
        options = dataclasses.replace(options, node_defaults=merged)
    return options


def _root_kwargs(
    fn: NodeFunction, inputs: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    signature = inspect.signature(fn.fn)
    params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}
    ]
    types = {parameter.name: _annotation_name(parameter.annotation) for parameter in params}

    # [inputs] are raw TOML values, exactly as the CLI binds them.
    values = {name: value for name, value in inputs.items() if name in types}

    unknown = sorted(set(overrides) - set(types))
    if unknown:
        raise EngineError("unknown root parameter(s): " + ", ".join(repr(name) for name in unknown))
    for name, value in overrides.items():
        values[name] = decode_value(value, types[name])

    missing = [
        parameter.name
        for parameter in params
        if parameter.default is inspect.Parameter.empty and parameter.name not in values
    ]
    if missing:
        raise EngineError("missing required root parameter(s): " + ", ".join(missing))
    return values


def _annotation_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


# ---------------------------------------------------------------- #
# Execute path (architecture steps 9-11)
# ---------------------------------------------------------------- #
def _execute(request: WorkerRequest, prepared: _Prepared, started: float) -> WorkerResult:
    doc = prepared.doc
    node_types = {
        entry["name"]: {param["name"]: param.get("type", "") for param in entry.get("params", [])}
        for entry in doc["nodes"]
    }
    node_overrides = []
    for name, params in request.overrides.nodes.items():
        if name not in node_types:
            continue
        node_overrides.append(
            {
                "name": name,
                "params": [
                    {"name": param, "value": decode_value(value, node_types[name].get(param, ""))}
                    for param, value in params.items()
                ],
            }
        )
    edited = apply_override(doc, {"nodes": node_overrides}) if node_overrides else doc
    registry = parameters_from_document(edited)
    registry.pop(doc["root"], None)
    run_options = dataclasses.replace(prepared.run_options, parameters=registry)

    wire_plan, plan_warnings = _wire_plan(doc, edited=edited)
    warnings = prepared.warnings + plan_warnings
    try:
        run = execute_flow(prepared.fn, options=run_options, **prepared.root_kwargs)
    except Exception as exc:
        return WorkerResult(
            ok=False,
            mode="execute",
            flow_name=prepared.selected,
            available_flows=prepared.available_flows,
            plan=wire_plan,
            config=prepared.config,
            run=_run_result(getattr(exc, "run", None), exc),
            warnings=warnings,
            error=str(exc),
            error_type=type(exc).__name__,
            traceback=traceback.format_exc(),
            duration_ms=_elapsed_ms(started),
        )
    return WorkerResult(
        ok=True,
        mode="execute",
        flow_name=prepared.selected,
        available_flows=prepared.available_flows,
        plan=wire_plan,
        config=prepared.config,
        run=_run_result(run),
        warnings=warnings,
        duration_ms=_elapsed_ms(started),
    )


def _run_result(run: Any, exc: Exception | None = None) -> RunResult:
    if run is None:
        if exc is None:
            return RunResult(status="ok")
        return RunResult(status="error", error=str(exc), error_type=type(exc).__name__)
    error = run.error
    return RunResult(
        status=run.status,
        result=jsonable(run.result),
        run_id=run.run_id,
        node=run.node,
        duration_ms=run.duration_ms,
        attempt=run.attempt,
        started=run.started,
        ended=run.ended,
        log=str(run.log) if run.log is not None else None,
        error=str(error) if error is not None else None,
        error_type=type(error).__name__ if error is not None else None,
        failed_nodes=[list(path) for path in run.failed_nodes],
    )


# ---------------------------------------------------------------- #
# Wire plan and the documented editability heuristic
# ---------------------------------------------------------------- #
def _wire_plan(
    doc: dict[str, Any], *, edited: dict[str, Any] | None = None
) -> tuple[WirePlan, list[str]]:
    warnings: list[str] = []
    edited_nodes = edited["nodes"] if edited is not None else None
    nodes: list[PlanNode] = []
    params_by_name: dict[str, list[Param]] = {}

    for index, entry in enumerate(doc["nodes"]):
        value_entry = edited_nodes[index] if edited_nodes is not None else entry
        value_params = {
            param["name"]: param.get("value") for param in value_entry.get("params", [])
        }
        params = []
        if entry.get("kind") != "gather":
            for raw in entry.get("params", []):
                params.append(_node_param(raw, value_params.get(raw["name"], raw.get("value"))))
        nodes.append(
            PlanNode(
                id=entry["id"],
                name=entry["name"],
                kind=entry.get("kind", "node"),
                path=list(entry.get("path", [])),
                instance=entry.get("instance", 1),
                policy=policy_from_mapping(entry.get("policy")),
                params=params,
            )
        )
        params_by_name.setdefault(entry["name"], []).extend(params)

    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in doc["nodes"]:
        groups.setdefault(entry["name"], []).append(entry)
    for name, entries in groups.items():
        if len(entries) < 2:
            continue
        signatures = {_params_signature(entry) for entry in entries}
        if len(signatures) > 1:
            warnings.append(
                f"node {name!r} has multiple instances with differing parameter values; "
                "the edit applies to every instance"
            )
            for param in params_by_name.get(name, []):
                if not param.editable and param.note == "possibly set by flow code":
                    param.editable = True

    wire_plan = WirePlan(
        root=doc["root"],
        parameters=[_root_param(raw) for raw in doc.get("parameters", [])],
        nodes=nodes,
        edges=[PlanEdge.model_validate(edge) for edge in doc.get("edges", [])],
    )
    return wire_plan, warnings


def _params_signature(entry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((param["name"], repr(param.get("value"))) for param in entry["params"]))


def _root_param(raw: dict[str, Any]) -> Param:
    value, display, _editable, note = encode_value(raw.get("value"))
    default, _default_display, _default_editable, _default_note = encode_value(raw.get("default"))
    return Param(
        name=raw["name"],
        type=raw.get("type", ""),
        required=bool(raw.get("required")),
        default=default,
        value=value,
        display=display,
        editable=True,
        note=note,
    )


def _node_param(raw: dict[str, Any], value: Any) -> Param:
    encoded, display, encodable, encodable_note = encode_value(value)
    default, _default_display, _default_editable, _default_note = encode_value(raw.get("default"))
    required = bool(raw.get("required"))

    if not encodable:
        editable, note = False, encodable_note
    elif required and value is not None:
        editable, note = False, "set by flow code"
    elif not required and value == default:
        editable, note = True, None
    elif value != default:
        editable, note = False, "possibly set by flow code"
    else:
        editable, note = True, None

    return Param(
        name=raw["name"],
        type=raw.get("type", ""),
        required=required,
        default=default,
        value=encoded,
        display=display,
        editable=editable,
        note=note,
    )


# ---------------------------------------------------------------- #
# Result helpers
# ---------------------------------------------------------------- #
def _error_result(
    request: WorkerRequest, exc: Exception, started: float, mode: str
) -> WorkerResult:
    return WorkerResult(
        ok=False,
        mode=mode,
        flow_name=getattr(exc, "flow_name", None) or request.flow_name,
        available_flows=list(getattr(exc, "available_flows", [])),
        error=str(exc),
        error_type=type(exc).__name__,
        traceback=traceback.format_exc(),
        duration_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
