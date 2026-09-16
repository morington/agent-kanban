"""Task branches: independent from main, children from the parent branch."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kanban_store import Store
from kanban_store.workspace import (
    commit_task,
    default_base_ref,
    integrate_task,
    prepare_task_workspace,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("start\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


@pytest.fixture
def repo_store(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    root = tmp_path / "app"
    root.mkdir()
    _init_repo(root)
    store = Store(tmp_path / "test.db")
    store.update_project("test", path=str(root))
    return store, root


def test_independent_tasks_branch_from_main(repo_store):
    store, root = repo_store
    base = _git(root, "rev-parse", "main")
    first = store.create_task("One", project_id="test", status="in_progress")
    second = store.create_task("Two", project_id="test", status="in_progress")
    a = prepare_task_workspace(store, first.id, actor="claude")
    b = prepare_task_workspace(store, second.id, actor="claude")
    assert a["base_commit"] == base
    assert b["base_commit"] == base
    assert a["branch"] != b["branch"]
    assert a["worktree_path"] != b["worktree_path"]
    assert Path(a["worktree_path"]).is_relative_to(root / ".kanban-worktrees")
    assert Path(b["worktree_path"]).is_relative_to(root / ".kanban-worktrees")
    assert _git(root, "branch", "--show-current") == "main"
    assert default_base_ref(root) == "main"


def test_parallel_worktrees_do_not_touch_main(repo_store):
    store, root = repo_store
    first = store.create_task("One", project_id="test", status="in_progress")
    second = store.create_task("Two", project_id="test", status="in_progress")
    a = prepare_task_workspace(store, first.id, actor="claude")
    b = prepare_task_workspace(store, second.id, actor="claude")
    Path(a["worktree_path"], "a.txt").write_text("a\n", encoding="utf-8")
    Path(b["worktree_path"], "b.txt").write_text("b\n", encoding="utf-8")
    assert commit_task(store, first.id, "a", actor="claude")["committed"] is True
    assert commit_task(store, second.id, "b", actor="claude")["committed"] is True
    assert not (root / "a.txt").exists()
    assert not (root / "b.txt").exists()
    assert _git(root, "branch", "--show-current") == "main"


def test_acceptance_survives_store_reopen(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    db = tmp_path / "test.db"
    first = Store(db)
    task = first.create_task("Merge me", project_id="test", status="acceptance")
    again = Store(db)
    stored = again.get_task(task.id)
    assert stored is not None
    assert stored.status == "acceptance"


def test_child_task_branches_from_parent(repo_store):
    store, root = repo_store
    parent = store.create_task("Parent", project_id="test", status="in_progress")
    child = store.create_task("Child", project_id="test", status="in_progress")
    store.set_blockers(child.id, [parent.id])
    parent_ws = prepare_task_workspace(store, parent.id, actor="claude")
    Path(parent_ws["worktree_path"], "parent.txt").write_text("from parent\n", encoding="utf-8")
    commit_task(store, parent.id, "parent work", actor="claude")
    parent_sha = _git(root, "rev-parse", store.get_task(parent.id).branch)
    child_ws = prepare_task_workspace(store, child.id, actor="claude")
    assert child_ws["base_commit"] == parent_sha
    stored = store.get_task(child.id)
    assert stored is not None
    assert _git(root, "merge-base", stored.branch, parent_sha) == parent_sha


def test_commit_and_integrate_to_main(repo_store):
    store, root = repo_store
    task = store.create_task("Ship", project_id="test", status="in_progress")
    ws = prepare_task_workspace(store, task.id, actor="claude")
    Path(ws["worktree_path"], "hello.txt").write_text("hi\n", encoding="utf-8")
    result = commit_task(store, task.id, "add hello", actor="claude")
    assert result["committed"] is True
    store.move_task(task.id, "acceptance", actor="user")
    merged = integrate_task(store, task.id, actor="claude")
    assert merged["into"] == "main"
    assert _git(root, "branch", "--show-current") == "main"
    assert (root / "hello.txt").read_text(encoding="utf-8") == "hi\n"
    assert not Path(ws["worktree_path"]).exists()
    done = store.get_task(task.id)
    assert done is not None
    assert done.status == "done"
    assert not done.worktree_path


def test_cancel_removes_worktree(repo_store):
    store, root = repo_store
    task = store.create_task("Nope", project_id="test", status="in_progress")
    ws = prepare_task_workspace(store, task.id, actor="claude")
    assert Path(ws["worktree_path"]).is_dir()
    store.move_task(task.id, "cancelled", actor="user")
    assert not Path(ws["worktree_path"]).exists()
