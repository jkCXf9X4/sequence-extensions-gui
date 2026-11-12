"""Contract tests for the offline static frontend."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "src" / "seq_ext_gui" / "static"
STATIC_FILES = ["index.html", "styles.css", "app.js", "graph.js"]


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"function {name}\([^)]*\) \{{(.*?)\n\}}", source, re.DOTALL)
    assert match, f"{name} helper not found"
    return match.group(1)


@pytest.mark.parametrize("name", STATIC_FILES)
def test_static_file_exists_and_is_not_empty(name: str) -> None:
    path = STATIC / name
    assert path.is_file(), f"missing src/seq_ext_gui/static/{name}"
    assert path.stat().st_size > 0, f"empty static asset: {name}"


def test_index_html_is_fully_local() -> None:
    html = read("index.html")
    assert not re.search(r"https?://", html, re.IGNORECASE), "external URL in index.html"
    assert "//cdn" not in html.lower(), "CDN reference in index.html"
    assert not re.search(r"\bcdn\.", html, re.IGNORECASE), "CDN host in index.html"

    refs = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html)
    assert refs, "index.html should reference its static assets"
    for ref in refs:
        assert ref.startswith("/static/"), f"non-local asset reference: {ref}"


def test_no_innerhtml_assignment() -> None:
    # Engine text is untrusted: the UI must build nodes with textContent only.
    for name in ("app.js", "graph.js"):
        source = read(name)
        assert not re.search(r"\.innerHTML\s*=", source), f"innerHTML assignment in {name}"
        assert not re.search(r"\.outerHTML\s*=", source), f"outerHTML assignment in {name}"


def test_app_js_references_http_api() -> None:
    source = read("app.js")
    for endpoint in ("/api/evaluate", "/api/execute", "/api/jobs/", "/api/file?path="):
        assert endpoint in source, f"app.js does not call {endpoint}"


@pytest.mark.parametrize("name", ["app.js", "graph.js"])
def test_javascript_parses_as_an_es_module(name: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    proc = subprocess.run(
        [node, "--check", str(STATIC / name)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"node --check failed for {name}:\n{proc.stderr}"


def test_app_js_dom_ids_exist_in_html() -> None:
    html = read("index.html")
    source = read("app.js")
    defined = set(re.findall(r"""\bid\s*=\s*["']([^"']+)["']""", html))
    referenced = set(re.findall(r"""\$\(\s*["']([^"']+)["']\s*\)""", source))
    referenced |= set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", source))
    missing = sorted(referenced - defined)
    assert not missing, f"app.js references missing DOM ids: {missing}"


def test_no_inline_event_handlers_or_external_assets() -> None:
    html = read("index.html")
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", html, re.IGNORECASE), "inline handler"
    for name in ("app.js", "graph.js"):
        source = read(name)
        urls = re.findall(r"https?://[^\s\"'`]+", source)
        external = [url for url in urls if not url.startswith("http://www.w3.org/")]
        assert not external, f"external URL in {name}: {external}"


def test_module_script_runs_after_dom() -> None:
    html = read("index.html")
    assert '<script type="module" src="/static/app.js"></script>' in html
    assert html.rindex("/static/app.js") > html.rindex("</main>")


def test_plan_document_emits_only_the_engine_fields() -> None:
    source = read("app.js")
    body = function_body(source, "planDocument")
    for field in ("schema", "parameters", "nodes", "edges", "options"):
        assert re.search(rf"\b{field}\b", body), f"planDocument omits {field}"
    assert "flow-plan/2" in source
    assert not re.search(r"\beditable\b", body), "planDocument leaks editable"
    assert not re.search(r"\bnote\b", body), "planDocument leaks note"
    assert re.search(r"\bfrom:\s*edge\.from\s*\?\?\s*edge\.source", body)
    assert re.search(r"\bto:\s*edge\.to\s*\?\?\s*edge\.target", body)


def test_build_payload_shape() -> None:
    body = function_body(read("app.js"), "buildPayload")
    for key in ("flow_file", "flow_name", "plan"):
        assert re.search(rf"\b{key}\b", body), f"buildPayload omits {key}"
    for removed in ("config_file", "config_text", "cwd", "overrides"):
        assert not re.search(rf"\b{removed}\b", body), f"buildPayload still sends {removed}"
    assert "planDocument(state.plan)" in body
    assert re.search(r"state\.plan\s*\?", body), "plan should be null when absent"


def test_execute_payload_and_endpoints() -> None:
    source = read("app.js")
    assert "new EventSource(" in source
    assert "/api/jobs/" in source and "/events" in source and "/cancel" in source
    assert "/api/tree?path=" in source
    assert 'method: "PUT"' not in source
    assert "content: state.configText" not in source


def test_plan_import_export_controls() -> None:
    html = read("index.html")
    source = read("app.js")
    for element_id in ("import-plan", "export-plan", "plan-file", "plan-status"):
        assert f'id="{element_id}"' in html, f"missing plan control #{element_id}"
    assert 'accept=".json,application/json"' in html
    assert 'type="file"' in html

    assert "function importPlanText" in source
    assert "document.schema !== PLAN_SCHEMA" in source
    assert "flow-plan/2" in source
    assert "function exportPlan" in source
    assert "JSON.stringify(planDocument(state.plan), null, 2)" in source
    assert '"plan.json"' in source
    assert "ui.importPlan.addEventListener" in source
    assert "ui.exportPlan.addEventListener" in source


def test_project_root_switch_controls() -> None:
    html = read("index.html")
    source = read("app.js")

    for element_id in ("project-root", "open-root", "root-status"):
        assert f'id="{element_id}"' in html, f"missing project root control #{element_id}"
    assert 'aria-label="Project root path"' in html
    assert re.search(
        r'<div id="root-status"[^>]*\brole="status"[^>]*\baria-live="polite"',
        html,
    ), "root status must be a polite live region"
    assert html.index('id="project-root"') < html.index('id="file-list"'), (
        "project root controls must sit above the file browser"
    )

    assert "/api/root" in source, "app.js does not call /api/root"
    assert 'putJson("/api/root", { path })' in source, "root switch must use PUT"
    assert "function switchRoot" in source
    assert 'ui.openRoot.addEventListener("click", switchRoot)' in source
    assert 'ui.projectRoot.addEventListener("keydown"' in source, "Enter wiring is missing"
    assert "health.project_root" in source

    for text in (html, source):
        assert not re.search(r"https?://", text, re.IGNORECASE), "external URL introduced"


def test_file_browser_routes_py_and_json() -> None:
    source = read("app.js")
    assert 'lower.endsWith(".py")' in source, "clicking .py must select the workflow"
    assert 'lower.endsWith(".json")' in source, "clicking .json must import a plan"
    assert "await importPlanText(" in source


def test_run_options_mutate_the_plan() -> None:
    source = read("app.js")
    body = function_body(source, "readOptions")
    assert "state.plan.options" in body
    assert "markDirty()" in body
    for key in (
        "max_workers",
        "summary",
        "fixed_clock",
        "retries",
        "retry_delay_seconds",
        "timeout",
    ):
        assert key in source, f"run option {key} is missing"


def test_parameter_edits_use_the_plan_not_overrides() -> None:
    source = read("app.js")
    assert "param.editable !== false" in source
    assert "input.disabled = !editable" in source
    assert "function buildParam(param, commit)" in source
    for removed in ("reconcileOverrides", "deleteOverride", "state.overrides", "emptyOverrides"):
        assert removed not in source, f"stale override helper remains: {removed}"
    assert "param.value = value" in source


def test_root_node_shows_the_flow_name() -> None:
    source = read("app.js")
    assert "ui.rootNode.textContent = state.flowName" in source
    assert "plan.root" not in source


@pytest.mark.parametrize("name", STATIC_FILES)
def test_no_toml_config_surface(name: str) -> None:
    source = read(name).lower()
    assert "toml" not in source, f"TOML surface remains in {name}"
    assert "save-config" not in source, f"save-config control remains in {name}"
    assert "config_file" not in source, f"config_file remains in {name}"
    assert "config_text" not in source, f"config_text remains in {name}"


def test_graph_layout_edge_cases(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = tmp_path / "graph.mjs"
    module.write_text(read("graph.js"), encoding="utf-8")
    script = tmp_path / "layout.mjs"
    script.write_text(
        f"""
import {{ computeLayout }} from {module.as_uri()!r};

function check(value, message) {{
  if (!value) throw new Error(message);
}}

const empty = computeLayout(null);
check(empty.nodes.length === 0 && empty.positions.size === 0, "empty plan");

const one = computeLayout({{ nodes: [{{ id: 7, name: "solo" }}], edges: [] }});
const single = one.positions.get("7");
check(single && single.x === 0 && single.y === 0, "single node");

const plan = {{
  nodes: [
    {{ id: 3, name: "same" }},
    {{ id: 10, name: "same" }},
    {{ id: 42, name: "other" }},
  ],
  edges: [
    {{ from: 10, to: 3 }},
    {{ from: 42, to: 10 }},
  ],
}};
const laid = computeLayout(plan);
check(laid.positions.size === 3, "non-contiguous ids");
check(laid.positions.get("3").y < laid.positions.get("10").y, "dependency above dependent");
check(laid.positions.get("10").y < laid.positions.get("42").y, "transitive rank");

const alias = computeLayout({{
  nodes: [{{ id: 1, name: "a" }}, {{ id: 2, name: "b" }}],
  edges: [{{ source: 1, target: 2 }}],
}});
check(alias.links.length === 1, "source/target alias");
check(alias.links[0].source === "1" && alias.links[0].target === "2", "alias direction");
""",
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"graph layout test failed:\n{proc.stderr}"
