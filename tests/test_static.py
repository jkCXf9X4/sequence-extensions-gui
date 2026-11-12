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
