"""agent-kanban — MCP server.

stdio transport. Registered in ``~/.claude.json`` (Claude Code) or
``.mcp.json`` (workspace scope) using the format:

    {
      "mcpServers": {
        "agent-kanban": {
          "type": "stdio",
          "command": "<repo>/.venv/bin/python",
          "args":    ["-m", "kanban_mcp"],
          "cwd":     "<repo>"
        }
      }
    }

The same setup works for Cline (Settings → MCP Servers → Add).

Tools (actor = "claude" by default, overridable via parameter):

* ``kanban_list``    — list tasks (filter by status / assignee)
* ``kanban_ready``   — list tasks that may be claimed now
* ``kanban_claim``   — take exactly one highest-priority card (for parallel agents)
* ``kanban_get``     — full card with history
* ``kanban_pull``    — claim a specific ready task
* ``kanban_prepare_workspace`` — git worktree under the project
* ``kanban_commit``  — commit on the task branch
* ``kanban_integrate`` — merge the task branch into main (from Integrate)
* ``kanban_move``    — move a task to a new status
* ``kanban_comment`` — comment in history
* ``kanban_create``  — new card
* ``kanban_link``    — add a link (memory / file / pr / url)
* ``kanban_columns`` — column descriptions (so the agent gets oriented)

On failure a human-readable message is returned; the MCP layer does not crash.
"""
from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from kanban_store import Store, STATUSES, status_meta, ready_next, ready_after, latest_pending_feedback
from kanban_store.store import DEFAULT_PROJECT_ID
from kanban_store.workspace import (
    WorkspaceError,
    commit_task,
    integrate_task,
    prepare_task_workspace,
)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _err(msg: str) -> dict[str, Any]:
    return {"ok": False, "error": msg}


def _ok(payload: Any) -> dict[str, Any]:
    return {"ok": True, "data": payload}


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("agent-kanban")


@mcp.tool()
def kanban_columns() -> dict[str, Any]:
    """Describe every kanban column and who typically moves cards in/out.

    Do not call this on every board check — statuses are stable.
    """
    return _ok({"columns": status_meta(), "statuses": STATUSES})


def _short_task(t: Any, *, ready: bool = False, store: Any = None) -> dict[str, Any]:
    data = {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "priority": t.priority,
        "size": t.size,
        "assignee": t.assignee,
        "external_blocker": t.external_blocker,
        "skip_planning": t.skip_planning,
        "moved_at": t.moved_at,
        "blockers": t.blockers,
        "project_id": t.project_id,
    }
    if ready:
        nxt = ready_next(t)
        data["next"] = nxt
        data["after"] = ready_after(t)
        data["parallel"] = nxt in {"plan", "implement"}
        if store is not None:
            blocked_by = store.blocker_release_state(t)
            data["blocked_by"] = blocked_by
            data["blockers_released"] = all(item["released"] for item in blocked_by)
        pending = latest_pending_feedback(t.history)
        if pending and pending.comment:
            data["feedback"] = pending.comment
    return data


@mcp.tool()
def kanban_list(
    status: str | None = None,
    assignee: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """List tasks with optional filters.

    Args:
        status: one of backlog/plan_requested/planning/plan_review/in_progress/testing/done/blocked/cancelled,
                or None for all.
        assignee: claude / agent:<name> / user, or None for all.
        project_id: project slug (see kanban_projects); None = all projects.

    Returns:
        {"ok": true, "data": {"tasks": [{...short fields}], "count": N}}
    """
    try:
        tasks = _get_store().list_tasks(
            status=status, assignee=assignee, project_id=project_id,
        )
    except Exception as e:
        return _err(str(e))
    return _ok({
        "tasks": [_short_task(t) for t in tasks],
        "count": len(tasks),
    })


@mcp.tool()
def kanban_ready(project_id: str, assignee: str | None = None) -> dict[str, Any]:
    """List tasks that can be claimed now.

    Parent agent: do ``next=integrate`` yourself, one by one (they share
    ``main``). For each card with ``parallel=true``, launch a Cursor
    **Task subagent** in the **same turn** (one Task call per card). Do
    not implement those cards in the parent. Each subagent ``kanban_pull``s
    its ``id`` only. If a card is in this list, parent blockers are already
    released (Testing is enough — do not wait for Done).
    """
    try:
        project = _get_store().get_project(project_id)
        if project is None:
            return _err(f"project {project_id} not found")
        tasks = _get_store().ready_tasks(project_id, assignee=assignee)
    except Exception as e:
        return _err(str(e))
    store = _get_store()
    return _ok({"tasks": [_short_task(t, ready=True, store=store) for t in tasks], "count": len(tasks)})


@mcp.tool()
def kanban_claim(project_id: str, assignee: str = "claude") -> dict[str, Any]:
    """Claim the highest-priority free card. Prefer ``kanban_pull`` when
    the parent already assigned you a task id. Integrate cards should be
    claimed by the parent, not by parallel subagents.
    """
    try:
        project = _get_store().get_project(project_id)
        if project is None:
            return _err(f"project {project_id} not found")
        task = _get_store().claim_next(project_id, assignee=assignee)
    except Exception as e:
        return _err(str(e))
    if task is None:
        return _ok({"task": None, "count": 0})
    data = task.to_public()
    data["next"] = ready_next(task)
    data["after"] = ready_after(task)
    pending = latest_pending_feedback(task.history)
    if pending and pending.comment:
        data["feedback"] = pending.comment
    return _ok({"task": data, "count": 1})


@mcp.tool()
def kanban_projects() -> dict[str, Any]:
    """List projects with task counts per column."""
    try:
        projects = _get_store().list_projects(include_archived=False)
    except Exception as e:
        return _err(str(e))
    return _ok({"projects": [p.to_public() for p in projects]})


@mcp.tool()
def kanban_board(project_id: str) -> dict[str, Any]:
    """Compact overview of a project board: counts + first 5 tasks per column.

    Perfect for a quick "what's in progress?" answer without enumerating
    all 100+ tasks.

    Args:
        project_id: project slug (see kanban_projects).
    """
    try:
        proj = _get_store().get_project(project_id)
        if proj is None:
            return _err(f"project {project_id} not found")
        tasks = _get_store().list_tasks(project_id=project_id)
    except Exception as e:
        return _err(str(e))
    by_status: dict[str, list[dict[str, Any]]] = {s: [] for s in STATUSES}
    for t in tasks:
        by_status[t.status].append(_short_task(t))
    summary = {
        "project": {"id": proj.id, "name": proj.name, "path": proj.path},
        "total": len(tasks),
        "by_status": {
            s: {
                "count": len(by_status[s]),
                "first_5": by_status[s][:5],
            }
            for s in STATUSES if by_status[s]
        },
    }
    return _ok(summary)


@mcp.tool()
def kanban_search(query: str, project_id: str | None = None) -> dict[str, Any]:
    """Search tasks by substring in title/description (case-insensitive).

    Args:
        query: search term; rejected if shorter than 2 characters.
        project_id: limit the search to one project; None = all.
    """
    if not query or len(query.strip()) < 2:
        return _err("query must be at least 2 characters")
    q = query.strip().lower()
    try:
        tasks = _get_store().list_tasks(project_id=project_id)
    except Exception as e:
        return _err(str(e))
    hits = [t for t in tasks if q in t.title.lower() or q in (t.description or "").lower()]
    return _ok({
        "tasks": [_short_task(t) for t in hits],
        "count": len(hits),
        "query": query,
    })


@mcp.tool()
def kanban_my_active(
    assignee: str = "claude",
    project_id: str | None = None,
) -> dict[str, Any]:
    """Active tasks for the given assignee — in planning/in_progress/testing.

    Perfect as the first query of a session: "what am I working on right now?"

    Args:
        assignee: claude (default), agent:<name>, user, ...
        project_id: project slug; None = all projects.
    """
    try:
        tasks = _get_store().list_tasks(assignee=assignee, project_id=project_id)
    except Exception as e:
        return _err(str(e))
    active = [t for t in tasks if t.status in ("planning", "in_progress", "testing")]
    return _ok({
        "tasks": [_short_task(t) for t in active],
        "count": len(active),
        "assignee": assignee,
    })


@mcp.tool()
def kanban_get(task_id: str) -> dict[str, Any]:
    """Full task card: description, acceptance, links, history."""
    try:
        t = _get_store().get_task(task_id)
    except Exception as e:
        return _err(str(e))
    if not t:
        return _err(f"task {task_id} not found")
    return _ok(t.to_public())


@mcp.tool()
def kanban_pull(task_id: str, assignee: str = "claude") -> dict[str, Any]:
    """Atomically claim a ready task.

    Plan requested → Planning (or In progress if skip_planning).
    Plan approved → In progress. Planning discussion → replan or In progress.
    """
    try:
        t = _get_store().pull_task(task_id, assignee=assignee)
    except KeyError:
        return _err(f"task {task_id} not found")
    except Exception as e:
        return _err(str(e))
    return _ok(t.to_public())


@mcp.tool()
def kanban_prepare_workspace(task_id: str, actor: str = "claude") -> dict[str, Any]:
    """Create a git worktree. Only from Plan approved, In progress, or Testing.

    Never call this when ``next=plan`` or the card is in Planning. After a
    plan the human moves the card to Plan approved.
    """
    try:
        result = prepare_task_workspace(_get_store(), task_id, actor=actor)
    except KeyError:
        return _err(f"task {task_id} not found")
    except WorkspaceError as e:
        return _err(str(e))
    return _ok(result)


@mcp.tool()
def kanban_commit(task_id: str, message: str, actor: str = "claude") -> dict[str, Any]:
    """Commit all current changes in the task worktree."""
    try:
        return _ok(commit_task(_get_store(), task_id, message, actor=actor))
    except KeyError:
        return _err(f"task {task_id} not found")
    except WorkspaceError as e:
        return _err(str(e))


@mcp.tool()
def kanban_integrate(task_id: str, actor: str = "claude") -> dict[str, Any]:
    """Merge the task branch into the project default branch from Integrate."""
    try:
        return _ok(integrate_task(_get_store(), task_id, actor=actor))
    except KeyError:
        return _err(f"task {task_id} not found")
    except WorkspaceError as e:
        return _err(str(e))


@mcp.tool()
def kanban_move(
    task_id: str,
    to_status: str,
    comment: str | None = None,
    actor: str = "claude",
) -> dict[str, Any]:
    """Move a task. Agents must not leave Planning for In progress / Plan approved /
    Testing — that is a human action after they accept the plan.
    """
    if to_status not in STATUSES:
        return _err(f"unknown status: {to_status}; valid: {STATUSES}")
    try:
        t = _get_store().move_task(task_id, to_status, actor=actor, comment=comment)
    except KeyError:
        return _err(f"task {task_id} not found")
    except Exception as e:
        return _err(str(e))
    return _ok(t.to_public())


@mcp.tool()
def kanban_comment(
    task_id: str,
    text: str,
    actor: str = "claude",
) -> dict[str, Any]:
    """Add a comment to the task's history.

    Required after plan or implement: a short reply so the card keeps a
    record of what you did (especially after a human comment).
    """
    try:
        _get_store().add_comment(task_id, text, actor=actor)
    except KeyError:
        return _err(f"task {task_id} not found")
    except Exception as e:
        return _err(str(e))
    return _ok({"task_id": task_id, "comment_added": True})


@mcp.tool()
def kanban_create(
    title: str,
    description: str = "",
    acceptance: str = "",
    status: str = "backlog",
    priority: str = "normal",
    size: str = "M",
    skip_planning: bool = False,
    external_blocker: str | None = None,
    actor: str = "claude",
    project_id: str | None = None,
) -> dict[str, Any]:
    """Create a new card. Defaults to Backlog.

    Args:
        title: a short single-line title.
        description: markdown with the details.
        acceptance: acceptance criteria (what counts as "done").
        priority: high / normal / low.
        size: S (<30 min) / M (<2 h) / L (>2 h).
        skip_planning: after Plan requested, start implementation without waiting for plan approval.
        project_id: project slug; None = default (see KANBAN_DEFAULT_PROJECT_ID
                    or KANBAN_PROJECT_ID env).
    """
    if status not in STATUSES:
        return _err(f"unknown status: {status}")
    pid = project_id or os.environ.get("KANBAN_PROJECT_ID") or DEFAULT_PROJECT_ID
    try:
        t = _get_store().create_task(
            title=title,
            description=description,
            acceptance=acceptance,
            status=status,
            priority=priority,
            size=size,
            skip_planning=skip_planning,
            external_blocker=external_blocker,
            actor=actor,
            project_id=pid,
        )
    except Exception as e:
        return _err(str(e))
    return _ok(t.to_public())


@mcp.tool()
def kanban_link(task_id: str, link_type: str, value: str) -> dict[str, Any]:
    """Attach a link (memory/file/pr/url) to a task.

    Args:
        link_type: memory | file | pr | url
        value: file name or URL.
    """
    if link_type not in {"memory", "file", "pr", "url"}:
        return _err(f"unknown link_type: {link_type}")
    try:
        _get_store().add_link(task_id, link_type, value)
    except Exception as e:
        return _err(str(e))
    return _ok({"task_id": task_id, "link": {"type": link_type, "value": value}})


@mcp.tool()
def kanban_blockers(task_id: str, blocker_ids: list[str]) -> dict[str, Any]:
    """Replace the list of internal blockers (dependencies)."""
    try:
        _get_store().set_blockers(task_id, blocker_ids)
    except Exception as e:
        return _err(str(e))
    return _ok({"task_id": task_id, "blockers": blocker_ids})


@mcp.tool()
def kanban_update(
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    acceptance: str | None = None,
    priority: str | None = None,
    size: str | None = None,
    skip_planning: bool | None = None,
    external_blocker: str | None = None,
    actor: str = "claude",
) -> dict[str, Any]:
    """Update any card fields (except status/assignee — use kanban_move/kanban_pull for those)."""
    try:
        t = _get_store().update_fields(
            task_id,
            actor=actor,
            title=title,
            description=description,
            acceptance=acceptance,
            priority=priority,
            size=size,
            skip_planning=skip_planning,
            external_blocker=external_blocker,
        )
    except KeyError:
        return _err(f"task {task_id} not found")
    except Exception as e:
        return _err(str(e))
    return _ok(t.to_public())


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
