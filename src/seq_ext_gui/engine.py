"""Plan and execute a flow module inside the worker process.

The only configuration artifact is the engine's ``flow-plan/2`` JSON document.
This module imports ``sequence_extensions`` and user flow code; the web process
talks to it through :mod:`seq_ext_gui.worker`.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import inspect
import json
import math
import os
import sys
import time
import traceback
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

from sequence_extensions.flow import (
    NodeFunction,
    RunOptions,
    apply_override,
    execute_plan,
    jsonable,
    plan_document,
)
from sequence_extensions.flow_runner import find_nodes

from .contracts import (
    PLAN_SCHEMA,
    NodeCard,
    Param,
    ParamSpec,
    PlanEdge,
    PlanNode,
    PlanOptions,
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


def plan(request: WorkerRequest) -> WorkerResult:
    """Build the wire plan for ``request`` without executing user node bodies."""
    started = time.monotonic()
    try:
        with _working_directory(request) as flow_file:
            selected, fn, available = _load_flow(request, flow_file)
            seed = request.plan
            if seed is not None:
                _require_document(seed)
            root_kwargs = _root_values(fn, seed, request.root_values)
            fresh = plan_document(fn, options=_run_options(seed), **root_kwargs)
            document = fresh
            if seed is not None:
                override = _override_from_seed(seed, fresh, root_kwargs)
                if override:
                    document = apply_override(fresh, override)
            wire_plan, warnings = _wire_plan(fresh, values=document)
        return WorkerResult(
            ok=True,
            mode="plan",
            flow_name=selected,
            available_flows=available,
            plan=wire_plan,
            warnings=warnings,
            duration_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return _error_result(request, exc, started, "plan")


def discover(request: WorkerRequest) -> WorkerResult:
    """List every ``@node`` in the flow module without running node bodies."""
    started = time.monotonic()
    try:
        with _working_directory(request) as flow_file:
            if flow_file.suffix != ".py":
                raise EngineError(f"flow file must be a .py file: {request.flow_file!r}")
            module = _import_flow_module(flow_file)
            cards = [_node_card(name, node) for name, node in find_nodes(module).items()]
        return WorkerResult(
            ok=True,
            mode="discover",
            nodes=cards,
            duration_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return _error_result(request, exc, started, "discover")


def execute(request: WorkerRequest) -> WorkerResult:
    """Run the request's plan document.  Flow failures are ``ok=false``."""
    started = time.monotonic()
    try:
        if request.plan is None:
            raise EngineError("execute requires a plan")
        with _working_directory(request) as flow_file:
            selected, fn, available = _load_flow(request, flow_file)
            try:
                run = execute_plan(fn, request.plan, log=request.log_dir)
            except Exception as exc:
                wire_plan, warnings = _wire_plan(request.plan)
                return WorkerResult(
                    ok=False,
                    mode="execute",
                    flow_name=selected,
                    available_flows=available,
                    plan=wire_plan,
                    run=_run_result(getattr(exc, "run", None), exc),
                    warnings=warnings,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    traceback=traceback.format_exc(),
                    duration_ms=_elapsed_ms(started),
                )
            wire_plan, warnings = _wire_plan(request.plan)
        return WorkerResult(
            ok=True,
            mode="execute",
            flow_name=selected,
            available_flows=available,
            plan=wire_plan,
            run=_run_result(run),
            warnings=warnings,
            duration_ms=_elapsed_ms(started),
        )
    except Exception as exc:
        return _error_result(request, exc, started, "execute")


# ---------------------------------------------------------------- #
# Import and flow selection
# ---------------------------------------------------------------- #
@contextlib.contextmanager
def _working_directory(request: WorkerRequest) -> Iterator[Path]:
    """Change into the flow file's directory; there is no separate ``cwd``."""
    flow_file = Path(request.flow_file).expanduser().resolve()
    previous = Path.cwd()
    os.chdir(flow_file.parent)
    try:
        yield flow_file
    finally:
        os.chdir(previous)


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


def _load_flow(
    request: WorkerRequest, flow_file: Path
) -> tuple[str, NodeFunction, list[str]]:
    module = _import_flow_module(flow_file)
    nodes = find_nodes(module)
    available = sorted(nodes)
    selected = request.flow_name
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
    return selected, fn, available


# ---------------------------------------------------------------- #
# Plan-document seeding
# ---------------------------------------------------------------- #
def _require_document(document: dict[str, Any]) -> None:
    schema = document.get("schema")
    if schema != PLAN_SCHEMA:
        raise EngineError(f"plan schema must be {PLAN_SCHEMA!r}, got {schema!r}")


def _run_options(document: dict[str, Any] | None) -> RunOptions:
    raw = (document or {}).get("options") or {}
    options = PlanOptions.model_validate(raw)
    return RunOptions(**options.model_dump())


def _root_values(
    fn: NodeFunction,
    document: dict[str, Any] | None,
    root_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decode root parameters into keyword arguments.

    Seed document values are read first; explicit ``root_values`` win by name.
    """
    signature = inspect.signature(fn.fn)
    params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}
    ]
    types = {parameter.name: _annotation_name(parameter.annotation) for parameter in params}
    values: dict[str, Any] = {}
    unknown: list[str] = []
    for entry in (document or {}).get("parameters", ()):
        name = entry.get("name")
        if name not in types:
            if name is not None:
                unknown.append(name)
            continue
        value = entry.get("value")
        if value is not None:
            values[name] = decode_value(value, types[name])
    for name, value in (root_values or {}).items():
        if name not in types:
            unknown.append(name)
            continue
        if value is not None:
            values[name] = decode_value(value, types[name])
    if unknown:
        listed = ", ".join(sorted({repr(name) for name in unknown}))
        raise EngineError(f"unknown root parameter(s): {listed}")

    missing = [
        parameter.name
        for parameter in params
        if parameter.default is inspect.Parameter.empty and parameter.name not in values
    ]
    if missing:
        raise EngineError("missing required root parameter(s): " + ", ".join(missing))
    return values


def _override_from_seed(
    seed: dict[str, Any], fresh: dict[str, Any], root_kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Re-apply the seed plan's edits on top of the freshly planned document."""
    override: dict[str, Any] = {}
    if root_kwargs:
        override["parameters"] = [
            {"name": name, "value": value} for name, value in root_kwargs.items()
        ]

    param_types: dict[str, dict[str, str]] = {}
    for entry in fresh["nodes"]:
        types = param_types.setdefault(entry["name"], {})
        for param in entry.get("params", ()):
            types[param["name"]] = param.get("type", "")

    node_overrides: list[dict[str, Any]] = []
    for entry in seed.get("nodes", ()):
        name = entry.get("name")
        types = param_types.get(name, {})
        spec: dict[str, Any] = {"name": name}
        params = [
            {
                "name": param["name"],
                "value": decode_value(param.get("value"), types.get(param["name"], "")),
            }
            for param in entry.get("params", ())
        ]
        if params:
            spec["params"] = params
        policy = entry.get("policy")
        if isinstance(policy, dict) and policy:
            spec["policy"] = dict(policy)
        if len(spec) > 1:
            node_overrides.append(spec)
    if node_overrides:
        override["nodes"] = node_overrides
    return override


def _node_card(name: str, node: Any) -> NodeCard:
    doc = (inspect.getdoc(node) or "").strip()
    summary = doc.splitlines()[0] if doc else ""
    wrapped = getattr(node, "fn", node)
    return NodeCard(
        name=name,
        summary=summary,
        signature=_signature_preview(wrapped),
        params=_param_specs(wrapped),
    )


def _param_specs(fn: Any) -> list[ParamSpec]:
    """Describe the root parameters discovery exposes, by signature only."""
    signature = inspect.signature(fn)
    return [
        _param_spec(parameter)
        for parameter in signature.parameters.values()
        if parameter.kind
        in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}
    ]


def _param_spec(parameter: inspect.Parameter) -> ParamSpec:
    default, note = _display_default(parameter.default)
    return ParamSpec(
        name=parameter.name,
        type=_annotation_name(parameter.annotation),
        required=parameter.default is inspect.Parameter.empty,
        default=default,
        default_note=note,
    )


def _display_default(value: Any) -> tuple[Any, str | None]:
    """Return a JSON-safe default and an optional note explaining a lossy one."""
    if value is inspect.Parameter.empty:
        return None, None
    if isinstance(value, Path):
        return str(value), None
    if isinstance(value, bool | int | str):
        return value, None
    if isinstance(value, float):
        if math.isfinite(value):
            return value, None
        return repr(value), "non-finite float"
    if isinstance(value, list | tuple | dict):
        try:
            return json.loads(json.dumps(value)), None
        except (TypeError, ValueError):
            return None, f"unsupported value type: {type(value).__name__}"
    return None, f"unsupported value type: {type(value).__name__}"


def _signature_preview(fn: Any) -> str:
    """Render ``inspect.signature`` using readable annotation names."""
    signature = inspect.signature(fn)
    parameters = list(signature.parameters.values())
    rendered: list[str] = []
    keyword_only_marker = False
    positional_only_marker = False

    for index, parameter in enumerate(parameters):
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY and not keyword_only_marker:
            if not any(
                earlier.kind is inspect.Parameter.VAR_POSITIONAL
                for earlier in parameters[:index]
            ):
                rendered.append("*")
            keyword_only_marker = True

        prefix = ""
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            prefix = "*"
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            prefix = "**"
        text = prefix + parameter.name
        annotation = _annotation_name(parameter.annotation)
        if annotation:
            text += f": {annotation}"
        if parameter.default is not inspect.Parameter.empty:
            text += f" = {parameter.default!r}"
        rendered.append(text)

        if (
            parameter.kind is inspect.Parameter.POSITIONAL_ONLY
            and not positional_only_marker
            and (
                index + 1 == len(parameters)
                or parameters[index + 1].kind is not inspect.Parameter.POSITIONAL_ONLY
            )
        ):
            rendered.append("/")
            positional_only_marker = True

    preview = f"({', '.join(rendered)})"
    returns = _annotation_name(signature.return_annotation)
    return f"{preview} -> {returns}" if returns else preview


def _annotation_name(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", str(annotation))


# ---------------------------------------------------------------- #
# Wire plan and the documented editability heuristic
# ---------------------------------------------------------------- #
def _wire_plan(
    document: dict[str, Any], *, values: dict[str, Any] | None = None
) -> tuple[WirePlan, list[str]]:
    """Annotate ``document`` for the wire, taking values from ``values``."""
    warnings: list[str] = []
    value_document = values if values is not None else document
    value_parameters = {
        param["name"]: param.get("value") for param in value_document.get("parameters", ())
    }
    value_nodes = value_document.get("nodes", ())

    nodes: list[PlanNode] = []
    params_by_name: dict[str, list[Param]] = {}

    for index, entry in enumerate(document.get("nodes", ())):
        value_entry = value_nodes[index] if index < len(value_nodes) else entry
        value_params = {
            param["name"]: param.get("value") for param in value_entry.get("params", ())
        }
        params = []
        if entry.get("kind") != "gather":
            for raw in entry.get("params", ()):
                params.append(_node_param(raw, value_params.get(raw["name"], raw.get("value"))))
        nodes.append(
            PlanNode(
                id=entry["id"],
                name=entry["name"],
                kind=entry.get("kind", "node"),
                path=list(entry.get("path", ())),
                instance=entry.get("instance", 1),
                policy=policy_from_mapping(value_entry.get("policy")),
                params=params,
            )
        )
        params_by_name.setdefault(entry["name"], []).extend(params)

    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in document.get("nodes", ()):
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
        schema_name=value_document.get("schema", PLAN_SCHEMA),
        parameters=[
            _root_param(raw, value_parameters.get(raw["name"], raw.get("value")))
            for raw in document.get("parameters", ())
        ],
        nodes=nodes,
        edges=[PlanEdge.model_validate(edge) for edge in document.get("edges", ())],
        options=PlanOptions.model_validate(value_document.get("options") or {}),
    )
    return wire_plan, warnings


def _params_signature(entry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((param["name"], repr(param.get("value"))) for param in entry["params"]))


def _root_param(raw: dict[str, Any], value: Any) -> Param:
    encoded, _editable, note = encode_value(value)
    default, _default_editable, _default_note = encode_value(raw.get("default"))
    return Param(
        name=raw["name"],
        type=raw.get("type", ""),
        required=bool(raw.get("required")),
        default=default,
        value=encoded,
        editable=True,
        note=note,
    )


def _node_param(raw: dict[str, Any], value: Any) -> Param:
    encoded, encodable, encodable_note = encode_value(value)
    default, _default_editable, _default_note = encode_value(raw.get("default"))
    required = bool(raw.get("required"))
    # Editability comes from the freshly planned code values, not from an
    # imported edit: an edited-but-re-evaluated parameter stays editable.
    code_value = raw.get("value")

    if not encodable:
        editable, note = False, encodable_note
    elif required and code_value is not None:
        editable, note = False, "set by flow code"
    elif not required and code_value == raw.get("default"):
        editable, note = True, None
    elif code_value != raw.get("default"):
        editable, note = False, "possibly set by flow code"
    else:
        editable, note = True, None

    return Param(
        name=raw["name"],
        type=raw.get("type", ""),
        required=required,
        default=default,
        value=encoded,
        editable=editable,
        note=note,
    )


# ---------------------------------------------------------------- #
# Result helpers
# ---------------------------------------------------------------- #
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
