"""Task worktrees live under <project>/.kanban-worktrees."""
from __future__ import annotations

import subprocess

import pytest

from kanban_store import Store
from kanban_store.workspace import (
    WORKTREE_DIR,
    WorkspaceError,
    branch_name,
    is_legacy_worktree,
    prepare_task_workspace,
    project_workspace_dir,
)


def test_branch_name_slug():
    assert branch_name("kanban/{task_id}-{slug}", "T-001", "Hello World") == "kanban/t-001-hello-world"


def test_legacy_worktree_detection():
    project = "/home/adam/Documents/Development/morington/ovelori"
    assert is_legacy_worktree("/tmp/.kanban-worktrees/ovelori/t-001", project)
    assert not is_legacy_worktree(project)
    assert not is_legacy_worktree(f"{project}/{WORKTREE_DIR}/kanban/t-001", project)


def test_project_workspace_dir_uses_configured_folder(tmp_path):
    root = tmp_path / "ovelori"
    root.mkdir()
    assert project_workspace_dir(str(root)) == root.resolve()


def test_prepare_uses_project_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    store = Store(tmp_path / "test.db")
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(project_dir)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project_dir), "config", "user.email", "t@t"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project_dir), "config", "user.name", "t"], check=True, capture_output=True)
    (project_dir / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project_dir), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project_dir), "commit", "-m", "init"], check=True, capture_output=True)
    store.update_project("test", path=str(project_dir))
    task = store.create_task("Init", project_id="test", status="in_progress")

    result = prepare_task_workspace(store, task.id, actor="cursor")
    worktree = result["worktree_path"]
    assert worktree.startswith(str((project_dir / WORKTREE_DIR).resolve()))
    assert (project_dir / WORKTREE_DIR).is_dir()
    assert ".kanban-worktrees/" in (project_dir / ".gitignore").read_text(encoding="utf-8")
    stored = store.get_task(task.id)
    assert stored is not None
    assert stored.worktree_path == worktree
    current = subprocess.run(
        ["git", "-C", str(project_dir), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert current == "main"


def test_prepare_rejects_unknown_status(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    store = Store(tmp_path / "test.db")
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    store.update_project("test", path=str(project_dir))
    task = store.create_task("Plan", project_id="test", status="planning")
    with pytest.raises(WorkspaceError):
        prepare_task_workspace(store, task.id, actor="cursor")
