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


@pytest.mark.parametrize("name", STATIC_FILES)
def test_static_file_exists_and_is_not_empty(name: str) -> None:
    path = STATIC / name
    assert path.is_file(), f"missing src/seq_ext_gui/static/{name}"
    assert path.stat().st_size > 0, f"empty static asset: {name}"


def test_index_html_is_fully_local() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
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
        source = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"\.innerHTML\s*=", source), f"innerHTML assignment in {name}"
        assert not re.search(r"\.outerHTML\s*=", source), f"outerHTML assignment in {name}"


def test_app_js_references_http_api() -> None:
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    for endpoint in ("/api/evaluate", "/api/execute", "/api/jobs/"):
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
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    defined = set(re.findall(r"""\bid\s*=\s*["']([^"']+)["']""", html))
    referenced = set(re.findall(r"""\$\(\s*["']([^"']+)["']\s*\)""", source))
    referenced |= set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", source))
    missing = sorted(referenced - defined)
    assert not missing, f"app.js references missing DOM ids: {missing}"


def test_no_inline_event_handlers_or_external_assets() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", html, re.IGNORECASE), "inline handler"
    for name in ("app.js", "graph.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"'`]+", source)
        external = [url for url in urls if not url.startswith("http://www.w3.org/")]
        assert not external, f"external URL in {name}: {external}"


def test_module_script_runs_after_dom() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<script type="module" src="/static/app.js"></script>' in html
    assert html.rindex("/static/app.js") > html.rindex("</main>")


def test_overrides_match_contract_shape() -> None:
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    match = re.search(
        r"function emptyOverrides\(\) \{\s*return \{(.*?)\};\s*\}", source, re.DOTALL
    )
    assert match, "emptyOverrides helper not found"
    keys = set(re.findall(r"(\w+):", match.group(1)))
    assert keys == {"root", "nodes", "policy", "node_defaults", "options"}


def test_execute_payload_and_endpoints() -> None:
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    match = re.search(r"function buildPayload\(\) \{(.*?)\n\}", source, re.DOTALL)
    assert match, "buildPayload helper not found"
    for key in ("flow_file", "config_file", "config_text", "flow_name", "cwd", "overrides"):
        assert re.search(rf"\b{key}\b", match.group(1)), f"buildPayload omits {key}"
    assert "new EventSource(" in source
    assert "/api/jobs/" in source and "/events" in source and "/cancel" in source
    assert 'method: "PUT"' in source and "/api/file?path=" in source
    assert "content: state.configText" in source
    assert "/api/tree?path=" in source


def test_readonly_params_are_disabled_and_pruned() -> None:
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "param.editable !== false" in source
    assert "input.disabled = !editable" in source
    assert "function reconcileOverrides()" in source
    assert "deleteOverride(" in source


def test_graph_layout_edge_cases(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    module = tmp_path / "graph.mjs"
    module.write_text((STATIC / "graph.js").read_text(encoding="utf-8"), encoding="utf-8")
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

