"""Per-task git worktrees under ``<project>/.kanban-worktrees``."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from kanban_store.store import Store, Task

WORKTREE_DIR = ".kanban-worktrees"
IGNORE_LINE = ".kanban-worktrees/"
_PREPARE_STATUSES = frozenset({"plan_review", "in_progress", "testing"})
_INTEGRATE_STATUSES = frozenset({"acceptance"})
_DROP_STATUSES = frozenset({"done", "cancelled"})


class WorkspaceError(Exception):
    """Workspace or git operation cannot continue."""


def branch_name(template: str, task_id: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "task"
    branch = template.format(task_id=task_id.lower(), slug=slug)
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or branch.startswith("/") or ".." in branch:
        raise WorkspaceError("template generated an invalid branch name")
    return branch


def project_workspace_dir(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(f"project directory does not exist: {root}")
    return root


def task_worktree_path(root: Path, branch: str) -> Path:
    return (root / WORKTREE_DIR / branch).resolve()


def is_legacy_worktree(path: str | Path, project_root: str | Path | None = None) -> bool:
    """True for worktrees that are not under this project's ``.kanban-worktrees``."""
    resolved = Path(path).expanduser().resolve()
    if WORKTREE_DIR not in resolved.parts:
        return False
    if project_root is None:
        return True
    nested = (Path(project_root).expanduser().resolve() / WORKTREE_DIR).resolve()
    try:
        resolved.relative_to(nested)
    except ValueError:
        return True
    return False


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", env.get("KANBAN_ACTOR", "kanban"))
    env.setdefault("GIT_AUTHOR_EMAIL", "kanban@local")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
        env=_git_env(),
    )


def _ref_exists(root: Path, ref: str) -> bool:
    return _git(root, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 0


def default_base_ref(root: Path) -> str:
    """Independent tasks branch from the project's main line, not from HEAD."""
    origin = _git(root, "rev-parse", "--abbrev-ref", "origin/HEAD", check=False)
    if origin.returncode == 0:
        name = origin.stdout.strip().rsplit("/", 1)[-1]
        if name:
            return name
    for name in ("main", "master"):
        if _ref_exists(root, f"refs/heads/{name}"):
            return name
    current = _git(root, "branch", "--show-current", check=False).stdout.strip()
    if current:
        return current
    raise WorkspaceError("could not determine the project default branch")


def parent_branch_ref(store: Store, task: Task, root: Path) -> str | None:
    """Related tasks branch from the parent's task branch."""
    for blocker_id in task.blockers:
        parent = store.get_task(blocker_id)
        if parent is None or not parent.branch:
            continue
        if parent.status == "cancelled":
            continue
        if _ref_exists(root, f"refs/heads/{parent.branch}"):
            return parent.branch
    return None


def _current_branch(root: Path) -> str:
    return _git(root, "branch", "--show-current").stdout.strip()


def _main_is_dirty(root: Path) -> bool:
    """Ignore the worktree dir and a local gitignore line we may have added."""
    out = _git(root, "status", "--porcelain").stdout
    for line in out.splitlines():
        path = line[3:].split(" -> ", 1)[-1].strip()
        if path == ".gitignore" or path.startswith(WORKTREE_DIR):
            continue
        return True
    return False


def _ensure_ignored(root: Path) -> None:
    exclude = Path(_git(root, "rev-parse", "--git-path", "info/exclude").stdout.strip())
    if not exclude.is_absolute():
        exclude = root / exclude
    _append_ignore_line(exclude)
    _append_ignore_line(root / ".gitignore")


def _append_ignore_line(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = {line.strip() for line in text.splitlines()}
    if IGNORE_LINE.rstrip("/") in lines or IGNORE_LINE in lines:
        return
    prefix = "" if not text or text.endswith("\n") else "\n"
    path.write_text(text + prefix + IGNORE_LINE + "\n", encoding="utf-8")


def _worktrees_by_branch(root: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    current: Path | None = None
    listed = _git(root, "worktree", "list", "--porcelain")
    for line in listed.stdout.splitlines():
        if line.startswith("worktree "):
            current = Path(line[9:])
        elif line.startswith("branch ") and current is not None:
            mapping[line[7:].removeprefix("refs/heads/")] = current
        elif line == "":
            current = None
    return mapping


def _remove_worktree_dir(root: Path, path: Path) -> None:
    _git(root, "worktree", "remove", "--force", str(path), check=False)
    _git(root, "worktree", "prune", check=False)
    if path.exists() and WORKTREE_DIR in path.parts:
        shutil.rmtree(path, ignore_errors=True)


def _ensure_worktree(root: Path, branch: str, base_ref: str) -> Path:
    dest = task_worktree_path(root, branch)
    existing = _worktrees_by_branch(root).get(branch)
    if existing is not None and existing.exists():
        return existing.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    try:
        if _ref_exists(root, f"refs/heads/{branch}"):
            _git(root, "worktree", "add", "--quiet", str(dest), branch)
        else:
            _git(root, "worktree", "add", "--quiet", "-b", branch, str(dest), base_ref)
    except subprocess.CalledProcessError as exc:
        raise WorkspaceError(exc.stderr.strip() or "git worktree add failed") from exc
    return dest


def _drop_legacy_worktree(project_root: Path, legacy_path: Path) -> None:
    if not is_legacy_worktree(legacy_path, project_root):
        return
    _remove_worktree_dir(project_root, legacy_path)


def drop_task_worktree(store: Store, task_id: str) -> None:
    """Remove the task worktree folder; keep the git branch."""
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(task_id)
    project = store.get_project(task.project_id)
    if project is None or not project.path:
        return
    try:
        root = project_workspace_dir(project.path)
    except WorkspaceError:
        return
    path = Path(task.worktree_path) if task.worktree_path else None
    if path is None and task.branch:
        candidate = task_worktree_path(root, task.branch)
        if candidate.exists():
            path = candidate
    if path is not None:
        _remove_worktree_dir(root, path)
    if task.worktree_path:
        store.set_workspace(task_id, task.branch, "", task.base_commit)


def _task_git_dir(store: Store, task: Task, root: Path) -> Path:
    if task.worktree_path:
        path = Path(task.worktree_path)
        if path.is_dir():
            return path
    if task.branch:
        dest = task_worktree_path(root, task.branch)
        if dest.is_dir():
            return dest
    raise WorkspaceError("prepare the workspace before committing")


def prepare_task_workspace(store: Store, task_id: str, *, actor: str) -> dict[str, Any]:
    """Create the task branch in a worktree under ``.kanban-worktrees``."""
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(task_id)
    if task.status not in _PREPARE_STATUSES:
        raise WorkspaceError(
            "no workspace until Plan approved / In progress / Testing "
            "(after a plan, leave the card in Planning)"
        )
    project = store.get_project(task.project_id)
    if project is None or not project.path:
        raise WorkspaceError("set the project directory first")
    root = project_workspace_dir(project.path)
    if not (root / ".git").exists():
        raise WorkspaceError("project directory is not a git repository")

    if task.worktree_path and is_legacy_worktree(task.worktree_path, root):
        _drop_legacy_worktree(root, Path(task.worktree_path))

    _ensure_ignored(root)
    branch = task.branch or branch_name(project.branch_template, task.id, task.title)
    base_ref = parent_branch_ref(store, task, root) or default_base_ref(root)
    try:
        if _ref_exists(root, f"refs/heads/{branch}"):
            base = task.base_commit or _git(root, "rev-parse", branch).stdout.strip()
        else:
            base = _git(root, "rev-parse", base_ref).stdout.strip()
        dest = _ensure_worktree(root, branch, base_ref)
    except subprocess.CalledProcessError as exc:
        raise WorkspaceError(exc.stderr.strip() or "git failed while preparing workspace") from exc

    store.set_workspace(task_id, branch, str(dest), base)
    if not task.branch:
        origin = parent_branch_ref(store, task, root) or default_base_ref(root)
        store.add_comment(
            task_id,
            f"Worktree `{dest}` on `{branch}` from `{origin}` (`{base[:12]}`).",
            actor=actor,
        )
    return {"branch": branch, "worktree_path": str(dest), "base_commit": base}


def commit_task(store: Store, task_id: str, message: str, *, actor: str) -> dict[str, Any]:
    """Stage all changes and commit them in the task worktree."""
    text = message.strip()
    if not text:
        raise WorkspaceError("commit message is required")
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(task_id)
    project = store.get_project(task.project_id)
    if project is None or not project.path:
        raise WorkspaceError("set the project directory first")
    root = project_workspace_dir(project.path)
    if not task.branch:
        raise WorkspaceError("prepare the workspace before committing")
    cwd = _task_git_dir(store, task, root)
    try:
        _git(cwd, "add", "-A")
        staged = _git(cwd, "diff", "--cached", "--quiet", check=False)
        if staged.returncode == 0:
            return {"committed": False, "branch": task.branch, "reason": "no changes"}
        _git(cwd, "commit", "-m", text)
        sha = _git(cwd, "rev-parse", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise WorkspaceError(exc.stderr.strip() or "git commit failed") from exc
    store.add_comment(task_id, f"Commit `{sha[:12]}` on `{task.branch}`: {text}", actor=actor)
    return {"committed": True, "branch": task.branch, "sha": sha, "worktree_path": str(cwd)}


def integrate_task(store: Store, task_id: str, *, actor: str) -> dict[str, Any]:
    """Merge the task branch into the project default branch, then drop the worktree."""
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(task_id)
    if task.status not in _INTEGRATE_STATUSES:
        raise WorkspaceError("integrate only from the merge column")
    if not task.branch:
        raise WorkspaceError("this task has no branch to merge")
    project = store.get_project(task.project_id)
    if project is None or not project.path:
        raise WorkspaceError("set the project directory first")
    root = project_workspace_dir(project.path)
    main = default_base_ref(root)
    if _current_branch(root) != main:
        if _main_is_dirty(root):
            raise WorkspaceError(
                f"uncommitted changes on `{_current_branch(root)}`; cannot merge into `{main}`"
            )
        try:
            _git(root, "switch", "--quiet", main)
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(exc.stderr.strip() or "git switch failed") from exc
    elif _main_is_dirty(root):
        raise WorkspaceError(f"uncommitted changes on `{main}`; cannot merge")
    try:
        _git(
            root,
            "merge",
            "--no-ff",
            task.branch,
            "-m",
            f"Merge {task.id}: {task.title}",
        )
        sha = _git(root, "rev-parse", "HEAD").stdout.strip()
    except subprocess.CalledProcessError as extra:
        _git(root, "merge", "--abort", check=False)
        raise WorkspaceError(extra.stderr.strip() or "git merge failed") from extra
    store.add_comment(
        task_id,
        f"Merged `{task.branch}` into `{main}` at `{sha[:12]}`.",
        actor=actor,
    )
    drop_task_worktree(store, task_id)
    store.move_task(task_id, "done", actor=actor, comment="merged")
    return {"merged": True, "branch": task.branch, "into": main, "sha": sha}


def maybe_drop_worktree_for_status(store: Store, task_id: str, to_status: str) -> None:
    if to_status in _DROP_STATUSES:
        drop_task_worktree(store, task_id)
