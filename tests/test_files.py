"""Tests for project-root-confined file access."""

from __future__ import annotations

from pathlib import Path

import pytest

from seq_ext_gui.files import MAX_WRITE_BYTES, ProjectFiles


@pytest.fixture
def root(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "flow.py").write_text("x = 1\n", encoding="utf-8")
    (project / "sample.toml").write_text("value = 1\n", encoding="utf-8")
    return project


@pytest.fixture
def files(root: Path) -> ProjectFiles:
    return ProjectFiles(root)


def test_tree_filters_and_sorts(files: ProjectFiles, root: Path) -> None:
    for name in ("a_dir", "B_dir", ".hidden_dir", "__pycache__", ".git", ".venv", "runs"):
        (root / name).mkdir()
    (root / ".seq_ext_gui").mkdir()
    (root / "z.py").write_text("z = 1\n", encoding="utf-8")
    (root / "A.py").write_text("a = 1\n", encoding="utf-8")
    (root / "notes.txt").write_text("ignored\n", encoding="utf-8")
    (root / ".hidden.py").write_text("hidden = 1\n", encoding="utf-8")

    tree = files.tree("")

    assert tree.root == str(root.resolve())
    assert tree.path == ""
    entries = [(entry.kind, entry.name) for entry in tree.entries]
    assert entries == [
        ("dir", "a_dir"),
        ("dir", "B_dir"),
        ("file", "A.py"),
        ("file", "flow.py"),
        ("file", "sample.toml"),
        ("file", "z.py"),
    ]
    assert all(not entry.path.startswith("/") for entry in tree.entries)


def test_tree_rejects_traversal(files: ProjectFiles) -> None:
    with pytest.raises(ValueError):
        files.tree("..")
    with pytest.raises(ValueError):
        files.tree("../sibling")


def test_absolute_paths_confined_to_root(files: ProjectFiles, root: Path, tmp_path: Path) -> None:
    (tmp_path / "outside.txt").write_text("secret\n", encoding="utf-8")
    with pytest.raises(ValueError):
        files.read(tmp_path / "outside.txt")
    with pytest.raises(ValueError):
        files.read("../outside.txt")
    assert files.resolve("flow.py") == root.resolve() / "flow.py"


def test_symlink_escape_rejected(files: ProjectFiles, root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    (root / "link.py").symlink_to(outside)
    with pytest.raises(ValueError):
        files.read("link.py")


def test_read_rejects_non_text_and_directories(files: ProjectFiles, root: Path) -> None:
    (root / "notes.txt").write_text("ignored\n", encoding="utf-8")
    with pytest.raises(ValueError):
        files.read("notes.txt")
    with pytest.raises(ValueError):
        files.read("missing.py")
    with pytest.raises(ValueError):
        files.read(".")


def test_toml_round_trip(files: ProjectFiles, root: Path) -> None:
    content = '[run]\nflow = "root"\n'
    saved = files.write("new.toml", content)

    assert saved.path == "new.toml"
    assert saved.content == content
    assert files.read("new.toml").content == content
    assert (root / "new.toml").read_text(encoding="utf-8") == content

    files.write("new.toml", "value = 2\n")
    assert files.read("new.toml").content == "value = 2\n"
    assert not list(root.glob(".new.toml.*.tmp"))


def test_write_rules(files: ProjectFiles, root: Path) -> None:
    with pytest.raises(ValueError):
        files.write("flow.py", "x = 2\n")
    with pytest.raises(ValueError):
        files.write("../escape.toml", "x = 1\n")
    with pytest.raises(ValueError):
        files.write("missing/escape.toml", "x = 1\n")
    with pytest.raises(ValueError):
        files.write("big.toml", "x" * (MAX_WRITE_BYTES + 1))
    assert not (root / "big.toml").exists()
