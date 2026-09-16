"""Kanban — SQLite store.

Single source of truth: ``tasks.db`` (gitignored), or the path from env
``KANBAN_DB`` (see Store.__init__).

Public API:
    Store.list_tasks(status=..., assignee=...)
    Store.get_task(task_id)
    Store.create_task(title, status="backlog", ...)
    Store.move_task(task_id, to_status, actor, comment=None)
    Store.assign_task(task_id, assignee, actor)
    Store.add_comment(task_id, text, actor)
    Store.add_link(task_id, type, value)
    Store.set_blockers(task_id, blocker_ids)
    Store.snapshot()  -> dict (for JSON snapshots)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

DEFAULT_PROJECT_ID = os.environ.get("KANBAN_DEFAULT_PROJECT_ID", "default")
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ============================================================================
# Status model
# ============================================================================

# Blockers stop blocking once the parent is in testing (not only done).
BLOCKER_RELEASED_STATUSES: frozenset[str] = frozenset(
    {"testing", "acceptance", "done"}
)
READY_STATUSES: frozenset[str] = frozenset(
    {
        "plan_requested",
        "plan_review",
        "planning",
        "in_progress",
        "testing",
        "acceptance",
    }
)
_BLOCKER_OPEN_SQL = "NOT IN ('testing', 'acceptance', 'done')"
_AGENT_ACTORS = frozenset({"claude", "automation", "cursor"})
_HUMAN_ACTORS = frozenset({"user"})
# After a plan the agent must wait; only a human moves the card forward.
_PLANNING_HOLD_STATUSES = frozenset(
    {"plan_review", "in_progress", "testing", "acceptance", "done"}
)


def is_human_actor(actor: str) -> bool:
    return (actor or "").strip().lower() in _HUMAN_ACTORS


def is_agent_actor(actor: str) -> bool:
    name = (actor or "").strip().lower()
    return name in _AGENT_ACTORS or name.startswith("agent:")


def latest_pending_feedback(history: list[TaskHistory]) -> TaskHistory | None:
    """Latest human comment that the agent has not answered yet."""
    comments = [h for h in history if h.action == "comment"]
    if not comments:
        return None
    last_agent_id = max((h.id for h in comments if is_agent_actor(h.actor)), default=0)
    pending = [h for h in comments if not is_agent_actor(h.actor) and h.id > last_agent_id]
    return pending[-1] if pending else None


READY_STATUS_PRIORITY: dict[str, int] = {
    "acceptance": 0,
    "testing": 1,
    "plan_review": 2,
    "planning": 3,
    "in_progress": 4,
    "plan_requested": 5,
}


def sort_tasks_by_blockers(tasks: list[Task]) -> list[Task]:
    """Parents before children so merges and dependent work run in order."""
    by_id = {t.id: t for t in tasks}
    ordered: list[Task] = []
    seen: set[str] = set()

    def visit(task: Task) -> None:
        if task.id in seen:
            return
        seen.add(task.id)
        for blocker_id in task.blockers:
            parent = by_id.get(blocker_id)
            if parent is not None:
                visit(parent)
        ordered.append(task)

    for task in tasks:
        visit(task)
    return ordered


def sort_ready_tasks(tasks: list[Task]) -> list[Task]:
    """Integrate, then Testing, then Plan approved, then Planning."""
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        grouped.setdefault(task.status, []).append(task)
    ordered: list[Task] = []
    for status in sorted(grouped, key=lambda s: READY_STATUS_PRIORITY.get(s, 99)):
        ordered.extend(sort_tasks_by_blockers(grouped[status]))
    return ordered


def ready_next(task: Task) -> str:
    """What an agent should do with a ready card: plan, implement, or integrate."""
    pending = latest_pending_feedback(task.history)
    if pending is not None:
        return "implement" if pending.skip_planning else "plan"
    if task.status == "acceptance":
        return "integrate"
    if task.status == "plan_review" or task.skip_planning:
        return "implement"
    return "plan"


def ready_after(task: Task) -> str:
    """What the agent must record on the card after the current step."""
    nxt = ready_next(task)
    if nxt == "plan":
        return (
            "kanban_comment a short reply on this card (the plan, or an answer "
            "to feedback); leave in Planning"
        )
    if nxt == "implement":
        return (
            "kanban_comment a short reply of what you did (this is the card "
            "history), then move to Testing"
        )
    return "kanban_integrate (merges into main and moves the card to Done)"


# Columns in left-to-right UI order.
STATUSES: list[str] = [
    "draft",
    "backlog",
    "plan_requested",
    "planning",
    "plan_review",
    "in_progress",
    "testing",
    "acceptance",
    "done",
    "blocked",
    "cancelled",
]


def status_meta() -> list[dict[str, str]]:
    """Column metadata for the UI (label + cssClass)."""
    return [
        {"id": "draft",       "title": "Draft",        "owner": "user"},
        {"id": "backlog",     "title": "Backlog",      "owner": "user"},
        {"id": "plan_requested", "title": "Plan requested", "owner": "agent"},
        {"id": "planning",    "title": "Planning",     "owner": "agent"},
        {"id": "plan_review", "title": "Plan approved", "owner": "agent"},
        {"id": "in_progress", "title": "In progress",  "owner": "agent"},
        {"id": "testing",     "title": "Testing",      "owner": "agent"},
        {"id": "acceptance",  "title": "Integrate",    "owner": "agent"},
        {"id": "done",        "title": "Done",         "owner": "user"},
        {"id": "blocked",     "title": "Blocked",      "owner": "any"},
        {"id": "cancelled",   "title": "Cancelled",    "owner": "user"},
    ]


# ============================================================================
# Models
# ============================================================================


@dataclass
class TaskHistory:
    id: int
    task_id: str
    ts: str
    actor: str
    action: str
    from_status: str | None
    to_status: str | None
    comment: str | None
    skip_planning: bool = False


@dataclass
class Task:
    id: str
    title: str
    status: str
    priority: str
    size: str
    assignee: str | None
    description: str
    acceptance: str
    skip_planning: bool
    external_blocker: str | None
    created_at: str
    moved_at: str
    column_order: int
    project_id: str = DEFAULT_PROJECT_ID
    branch: str | None = None
    worktree_path: str | None = None
    base_commit: str | None = None
    links: list[dict[str, str]] = field(default_factory=list)
    history: list[TaskHistory] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        d = asdict(self)
        d["history"] = [asdict(h) for h in self.history]
        return d


@dataclass
class Project:
    id: str
    name: str
    color: str
    icon: str
    sort_order: int
    archived: bool
    created_at: str
    path: str | None = None
    branch_template: str = "kanban/{task_id}-{slug}"
    agent_rules: str = ""
    task_counts: dict[str, int] = field(default_factory=dict)
    total_tasks: int = 0

    def to_public(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# Store
# ============================================================================


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    """Thread-safe wrapper around SQLite. One instance per process."""

    _lock = threading.RLock()

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get("KANBAN_DB") or (Path(__file__).resolve().parent.parent / "tasks.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; explicit transactions use BEGIN
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(schema)
            self._migrate_v2()
            self._migrate_v3()
            self._migrate_v4()
            self._migrate_v5()
            self._migrate_v6()
            self._migrate_v7()
            self._migrate_v8()
            self._migrate_v9()

    def _schema_version(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row["value"]) if row else 1

    def _bump_schema(self, n: int) -> None:
        if self._schema_version() < n:
            self._conn.execute(
                "UPDATE meta SET value=? WHERE key='schema_version'", (str(n),)
            )

    def _migrate_v9(self) -> None:
        """Keep Integrate (status=acceptance). Never rewrite those cards."""
        self._bump_schema(9)

    def _migrate_v8(self) -> None:
        """v8 briefly dropped Acceptance; that change was reverted."""
        self._bump_schema(8)

    def _migrate_v7(self) -> None:
        """v6 → v7: per-comment opt-in to implement without a new plan."""
        hist_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(task_history)").fetchall()}
        if "skip_planning" not in hist_cols:
            self._conn.execute(
                "ALTER TABLE task_history ADD COLUMN skip_planning INTEGER NOT NULL DEFAULT 0"
            )
        self._bump_schema(7)

    def _migrate_v6(self) -> None:
        """v5 → v6: per-task opt-in to direct implementation."""
        task_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "skip_planning" not in task_cols:
            self._conn.execute("ALTER TABLE tasks ADD COLUMN skip_planning INTEGER NOT NULL DEFAULT 0")
        self._bump_schema(6)

    def _migrate_v5(self) -> None:
        project_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(projects)").fetchall()}
        task_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "branch_template" not in project_cols:
            self._conn.execute("ALTER TABLE projects ADD COLUMN branch_template TEXT NOT NULL DEFAULT 'kanban/{task_id}-{slug}'")
        if "agent_rules" not in project_cols:
            self._conn.execute("ALTER TABLE projects ADD COLUMN agent_rules TEXT NOT NULL DEFAULT ''")
        for name in ("branch", "worktree_path", "base_commit"):
            if name not in task_cols:
                self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} TEXT")
        self._conn.execute("UPDATE tasks SET status='plan_requested' WHERE status='approved'")
        self._conn.execute("UPDATE tasks SET status='planning' WHERE status='analyst'")
        self._conn.execute("UPDATE tasks SET status='acceptance' WHERE status='uat'")
        self._bump_schema(5)

    def _migrate_v4(self) -> None:
        """v3 → v4: project_sources table (created via schema.sql,
        this method only bumps the version)."""
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if row and int(row["value"]) < 4:
            self._conn.execute("UPDATE meta SET value='4' WHERE key='schema_version'")

    def _migrate_v3(self) -> None:
        """v2 → v3: projects.path TEXT (Claude Code project directory)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(projects)").fetchall()}
        if "path" not in cols:
            self._conn.execute("ALTER TABLE projects ADD COLUMN path TEXT")
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if row and int(row["value"]) < 3:
            self._conn.execute("UPDATE meta SET value='3' WHERE key='schema_version'")

    def _migrate_v2(self) -> None:
        """v1 → v2: adds tasks.project_id for existing databases and
        creates a default project (id/name are configurable via env).

        Idempotent: checks PRAGMA table_info before running ALTER.
        """
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        version = int(row["value"]) if row else 1
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "project_id" not in cols:
            # old pre-v2 database — add the column with a default
            default_id = os.environ.get("KANBAN_DEFAULT_PROJECT_ID", "default")
            self._conn.execute(
                f"ALTER TABLE tasks ADD COLUMN project_id TEXT NOT NULL DEFAULT '{default_id}'"
            )
        # The project_id index is always created (idempotent). For a fresh
        # database the column appeared from CREATE TABLE in schema.sql; for
        # older databases it is created after the ALTER above.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_project_status "
            "ON tasks(project_id, status, column_order)"
        )
        # The default project is created ONLY when the database has no
        # projects at all (fresh install). Existing databases keep their
        # own projects without an extra "default" being added on top.
        row = self._conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()
        if row["n"] == 0:
            default_id = os.environ.get("KANBAN_DEFAULT_PROJECT_ID", "default")
            default_name = os.environ.get("KANBAN_DEFAULT_PROJECT_NAME", "Default")
            default_color = os.environ.get("KANBAN_DEFAULT_PROJECT_COLOR", "#F10D30")
            default_icon = os.environ.get(
                "KANBAN_DEFAULT_PROJECT_ICON", default_name[:1].upper()
            )
            self._conn.execute(
                "INSERT INTO projects (id, name, color, icon, sort_order, archived, created_at) "
                "VALUES (?, ?, ?, ?, 0, 0, ?)",
                (default_id, default_name, default_color, default_icon, _now()),
            )
        if version < 2:
            self._conn.execute(
                "UPDATE meta SET value='2' WHERE key='schema_version'"
            )

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key='next_id'"
            ).fetchone()
            n = int(row["value"]) if row else 1
            self._conn.execute(
                "UPDATE meta SET value=? WHERE key='next_id'", (str(n + 1),)
            )
            return f"T-{n:03d}"

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        status: str | Iterable[str] | None = None,
        assignee: str | None = None,
        project_id: str | None = None,
    ) -> list[Task]:
        """List of tasks with filters, sorted by (status, column_order).

        ``project_id=None`` means "all projects". The board UI always
        passes a concrete project_id.
        """
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if status is not None:
            if isinstance(status, str):
                statuses = [status]
            else:
                statuses = list(status)
            placeholders = ",".join("?" * len(statuses))
            sql += f" AND status IN ({placeholders})"
            params.extend(statuses)
        if assignee is not None:
            sql += " AND assignee = ?"
            params.append(assignee)
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY status, column_order, id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_task(r, eager_links=True) for r in rows]

    def ready_tasks(self, project_id: str, *, assignee: str | None = None) -> list[Task]:
        """Tasks an agent may safely claim right now.

        Includes Plan requested, Plan approved, Integrate, and unanswered
        human comments on Planning / In progress / Testing. Blockers release
        once the parent reaches testing. Cards assigned to another agent
        are hidden when ``assignee`` is set.
        """
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM tasks
                WHERE project_id = ? AND status IN (
                    'plan_requested', 'plan_review', 'planning', 'in_progress',
                    'testing', 'acceptance'
                )
                ORDER BY status, column_order, id
                """,
                (project_id,),
            ).fetchall()
            tasks = [
                self._row_to_task(r, eager_links=True, eager_history=True)
                for r in rows
            ]
            return sort_ready_tasks(
                [t for t in tasks if self._task_is_ready(t, assignee=assignee)]
            )

    def claim_next(self, project_id: str, assignee: str = "claude") -> Task | None:
        """Atomically claim the highest-priority ready card for this worker."""
        tried: set[str] = set()
        while True:
            ready = [
                t for t in self.ready_tasks(project_id, assignee=assignee)
                if t.id not in tried
            ]
            if not ready:
                return None
            task = ready[0]
            tried.add(task.id)
            try:
                return self.pull_task(task.id, assignee=assignee)
            except RuntimeError:
                continue

    def _task_is_ready(self, task: Task, *, assignee: str | None = None) -> bool:
        if assignee and task.assignee and task.assignee != assignee:
            return False
        if any(
            self._blocker_status(bid) not in BLOCKER_RELEASED_STATUSES
            for bid in task.blockers
        ):
            return False
        if task.status in {"plan_requested", "plan_review", "acceptance"}:
            return True
        return latest_pending_feedback(task.history) is not None

    def _blocker_status(self, task_id: str) -> str | None:
        row = self._conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        return None if row is None else row["status"]

    def blocker_release_state(self, task: Task) -> list[dict[str, Any]]:
        """Parent cards: released once the parent is in Testing (not only Done)."""
        out: list[dict[str, Any]] = []
        for bid in task.blockers:
            status = self._blocker_status(bid)
            out.append(
                {
                    "id": bid,
                    "status": status,
                    "released": status in BLOCKER_RELEASED_STATUSES,
                }
            )
        return out

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row, eager_links=True, eager_history=True)

    def board(self) -> dict[str, list[Task]]:
        """Group tasks by status, in column order."""
        result: dict[str, list[Task]] = {s: [] for s in STATUSES}
        for t in self.list_tasks():
            result.setdefault(t.status, []).append(t)
        return result

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create_task(
        self,
        title: str,
        *,
        status: str = "draft",
        priority: str = "normal",
        size: str = "M",
        description: str = "",
        acceptance: str = "",
        skip_planning: bool = False,
        assignee: str | None = None,
        external_blocker: str | None = None,
        actor: str = "user",
        links: list[dict[str, str]] | None = None,
        task_id: str | None = None,
        project_id: str = DEFAULT_PROJECT_ID,
    ) -> Task:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        ts = _now()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                tid = task_id or self._next_id()
                # column_order — last in the column + 1 (per project)
                row = self._conn.execute(
                    "SELECT COALESCE(MAX(column_order), -1) AS m FROM tasks "
                    "WHERE status=? AND project_id=?",
                    (status, project_id),
                ).fetchone()
                col_order = (row["m"] + 1) if row else 0
                self._conn.execute(
                    """
                    INSERT INTO tasks (id, title, status, priority, size, assignee,
                                        description, acceptance, skip_planning, external_blocker,
                                        created_at, moved_at, column_order, project_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tid,
                        title,
                        status,
                        priority,
                        size,
                        assignee,
                        description,
                        acceptance,
                        int(skip_planning),
                        external_blocker,
                        ts,
                        ts,
                        col_order,
                        project_id,
                    ),
                )
                if links:
                    for ln in links:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO task_links (task_id, type, value) VALUES (?, ?, ?)",
                            (tid, ln["type"], ln["value"]),
                        )
                self._conn.execute(
                    """
                    INSERT INTO task_history (task_id, ts, actor, action, from_status, to_status, comment)
                    VALUES (?, ?, ?, 'create', NULL, ?, ?)
                    """,
                    (tid, ts, actor, status, None),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        task = self.get_task(tid)
        assert task is not None
        return task

    def move_task(
        self,
        task_id: str,
        to_status: str,
        *,
        actor: str = "user",
        comment: str | None = None,
        column_order: int | None = None,
    ) -> Task:
        if to_status not in STATUSES:
            raise ValueError(f"unknown status: {to_status}")
        ts = _now()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                row = self._conn.execute(
                    "SELECT status, project_id FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    raise KeyError(task_id)
                from_status = row["status"]
                project_id = row["project_id"]
                if from_status == "planning" and to_status in _PLANNING_HOLD_STATUSES:
                    if not is_human_actor(actor):
                        raise RuntimeError(
                            "leave the card in Planning after the plan; "
                            "a human moves it to Plan approved before any code"
                        )
                if (
                    from_status == "plan_requested"
                    and to_status in _PLANNING_HOLD_STATUSES
                    and not is_human_actor(actor)
                ):
                    raise RuntimeError(
                        "do not skip Planning with kanban_move; "
                        "write the plan and leave the card, or pull with skip_planning"
                    )
                # column_order — append to the end of the project's column when not specified
                if column_order is None:
                    r2 = self._conn.execute(
                        "SELECT COALESCE(MAX(column_order), -1) AS m FROM tasks "
                        "WHERE status=? AND project_id=?",
                        (to_status, project_id),
                    ).fetchone()
                    column_order = (r2["m"] + 1) if r2 else 0
                self._conn.execute(
                    """UPDATE tasks SET status=?, moved_at=?, column_order=?
                       WHERE id=?""",
                    (to_status, ts, column_order, task_id),
                )
                self._conn.execute(
                    """INSERT INTO task_history
                       (task_id, ts, actor, action, from_status, to_status, comment)
                       VALUES (?, ?, ?, 'move', ?, ?, ?)""",
                    (task_id, ts, actor, from_status, to_status, comment),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        if to_status in {"done", "cancelled"}:
            from kanban_store.workspace import maybe_drop_worktree_for_status

            try:
                maybe_drop_worktree_for_status(self, task_id, to_status)
            except Exception:
                pass
        task = self.get_task(task_id)
        assert task is not None
        return task

    def assign_task(self, task_id: str, assignee: str | None, *, actor: str) -> Task:
        ts = _now()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                row = self._conn.execute(
                    "SELECT assignee FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    raise KeyError(task_id)
                self._conn.execute(
                    "UPDATE tasks SET assignee=? WHERE id=?", (assignee, task_id)
                )
                self._conn.execute(
                    """INSERT INTO task_history
                       (task_id, ts, actor, action, from_status, to_status, comment)
                       VALUES (?, ?, ?, 'assign', NULL, NULL, ?)""",
                    (task_id, ts, actor, f"assignee → {assignee}"),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        t = self.get_task(task_id)
        assert t is not None
        return t

    def pull_task(self, task_id: str, assignee: str = "claude") -> Task:
        """Atomic claim of a ready task.

        ``plan_requested`` → planning, or in_progress when ``skip_planning``.
        ``plan_review`` (plan approved) → in_progress.
        """
        ts = _now()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                row = self._conn.execute(
                    "SELECT assignee, status, project_id, skip_planning FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    raise KeyError(task_id)
                from_status = row["status"]
                if (
                    row["assignee"] is not None
                    and row["assignee"] != assignee
                    and from_status not in {"plan_requested", "plan_review", "acceptance"}
                ):
                    raise RuntimeError(
                        f"task {task_id} already assigned to {row['assignee']}"
                    )
                blockers = self._conn.execute(
                    "SELECT t.id FROM task_blockers b JOIN tasks t ON t.id=b.blocker_id "
                    f"WHERE b.task_id=? AND t.status {_BLOCKER_OPEN_SQL}",
                    (task_id,),
                ).fetchall()
                if blockers:
                    raise RuntimeError("unfinished blockers: " + ", ".join(r["id"] for r in blockers))
                pending_skip = self._pending_skip_locked(task_id)
                if from_status == "plan_requested":
                    target_status = "in_progress" if row["skip_planning"] else "planning"
                    comment = "pulled without planning" if row["skip_planning"] else "pulled"
                elif from_status == "plan_review":
                    if pending_skip is False:
                        target_status = "planning"
                        comment = "pulled discussion to replan"
                    else:
                        target_status = "in_progress"
                        comment = "pulled approved plan"
                elif from_status == "planning":
                    if pending_skip is True:
                        target_status = "in_progress"
                        comment = "pulled discussion to implement"
                    else:
                        target_status = "planning"
                        comment = "pulled discussion to replan"
                elif from_status == "in_progress":
                    target_status = "in_progress"
                    comment = "pulled discussion"
                elif from_status == "testing":
                    if pending_skip is True:
                        target_status = "in_progress"
                        comment = "pulled testing discussion to implement"
                    else:
                        target_status = "planning"
                        comment = "pulled testing discussion to replan"
                elif from_status == "acceptance":
                    if pending_skip is False:
                        target_status = "planning"
                        comment = "pulled merge discussion to replan"
                    else:
                        target_status = "acceptance"
                        comment = "pulled merge"
                else:
                    raise RuntimeError(
                        f"task {task_id} is in '{from_status}', not a ready status"
                    )
                if from_status == target_status:
                    self._conn.execute(
                        "UPDATE tasks SET assignee=? WHERE id=?",
                        (assignee, task_id),
                    )
                    self._conn.execute("COMMIT")
                else:
                    r2 = self._conn.execute(
                        "SELECT COALESCE(MAX(column_order), -1) AS m FROM tasks "
                            "WHERE status=? AND project_id=?",
                        (target_status, row["project_id"]),
                    ).fetchone()
                    col_order = (r2["m"] + 1) if r2 else 0
                    self._conn.execute(
                        """UPDATE tasks SET status=?, assignee=?, moved_at=?, column_order=?
                           WHERE id=?""",
                        (target_status, assignee, ts, col_order, task_id),
                    )
                    self._conn.execute(
                        """INSERT INTO task_history
                           (task_id, ts, actor, action, from_status, to_status, comment)
                           VALUES (?, ?, ?, 'move', ?, ?, ?)""",
                        (task_id, ts, assignee, from_status, target_status, comment),
                    )
                    self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        t = self.get_task(task_id)
        assert t is not None
        return t

    def _pending_skip_locked(self, task_id: str) -> bool | None:
        rows = self._conn.execute(
            """
            SELECT id, actor, skip_planning FROM task_history
            WHERE task_id=? AND action='comment' ORDER BY id
            """,
            (task_id,),
        ).fetchall()
        last_agent_id = 0
        pending: bool | None = None
        for row in rows:
            if is_agent_actor(row["actor"]):
                last_agent_id = row["id"]
                pending = None
            elif row["id"] > last_agent_id:
                pending = bool(row["skip_planning"]) if "skip_planning" in row.keys() else False
        return pending

    def add_comment(
        self,
        task_id: str,
        text: str,
        *,
        actor: str,
        skip_planning: bool = False,
    ) -> None:
        ts = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                raise KeyError(task_id)
            self._conn.execute(
                """INSERT INTO task_history
                   (task_id, ts, actor, action, from_status, to_status, comment, skip_planning)
                   VALUES (?, ?, ?, 'comment', NULL, NULL, ?, ?)""",
                (task_id, ts, actor, text, int(skip_planning)),
            )

    def update_comment(self, task_id: str, history_id: int, text: str) -> None:
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE task_history SET comment=?
                   WHERE id=? AND task_id=? AND action='comment'""",
                (text, history_id, task_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(history_id)

    def delete_comment(self, task_id: str, history_id: int) -> None:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM task_history WHERE id=? AND task_id=? AND action='comment'",
                (history_id, task_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(history_id)

    def add_link(self, task_id: str, type_: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO task_links (task_id, type, value) VALUES (?, ?, ?)",
                (task_id, type_, value),
            )

    def set_blockers(self, task_id: str, blocker_ids: list[str]) -> None:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                task = self._conn.execute("SELECT project_id FROM tasks WHERE id=?", (task_id,)).fetchone()
                if not task:
                    raise KeyError(task_id)
                if task_id in blocker_ids or len(set(blocker_ids)) != len(blocker_ids):
                    raise ValueError("invalid blocker list")
                for blocker_id in blocker_ids:
                    row = self._conn.execute("SELECT project_id FROM tasks WHERE id=?", (blocker_id,)).fetchone()
                    if not row:
                        raise KeyError(f"blocker {blocker_id} not found")
                    if row["project_id"] != task["project_id"]:
                        raise ValueError("blockers must belong to the same project")
                self._conn.execute(
                    "DELETE FROM task_blockers WHERE task_id=?", (task_id,)
                )
                for b in blocker_ids:
                    self._conn.execute(
                        "INSERT INTO task_blockers (task_id, blocker_id) VALUES (?, ?)",
                        (task_id, b),
                    )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def update_fields(
        self,
        task_id: str,
        *,
        actor: str,
        title: str | None = None,
        priority: str | None = None,
        size: str | None = None,
        description: str | None = None,
        acceptance: str | None = None,
        skip_planning: bool | None = None,
        external_blocker: str | None = None,
    ) -> Task:
        ts = _now()
        sets: list[str] = []
        params: list[Any] = []
        for col, val in (
            ("title", title),
            ("priority", priority),
            ("size", size),
            ("description", description),
            ("acceptance", acceptance),
            ("skip_planning", None if skip_planning is None else int(skip_planning)),
            ("external_blocker", external_blocker),
        ):
            if val is not None:
                sets.append(f"{col} = ?")
                params.append(val)
        if not sets:
            t = self.get_task(task_id)
            if t is None:
                raise KeyError(task_id)
            return t
        params.append(task_id)
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                row = self._conn.execute(
                    "SELECT 1 FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                if not row:
                    raise KeyError(task_id)
                self._conn.execute(
                    f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params
                )
                self._conn.execute(
                    """INSERT INTO task_history
                       (task_id, ts, actor, action, from_status, to_status, comment)
                       VALUES (?, ?, ?, 'update', NULL, NULL, ?)""",
                    (task_id, ts, actor, ", ".join(s.split(" = ")[0] for s in sets)),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        t = self.get_task(task_id)
        assert t is not None
        return t

    def set_workspace(
        self,
        task_id: str,
        branch: str | None,
        worktree_path: str,
        base_commit: str | None,
    ) -> None:
        with self._lock:
            updated = self._conn.execute(
                "UPDATE tasks SET branch=?, worktree_path=?, base_commit=? WHERE id=?",
                (branch, worktree_path, base_commit, task_id),
            )
            if updated.rowcount == 0:
                raise KeyError(task_id)

    def reorder(self, task_id: str, new_order: int) -> None:
        """Change the order within the current column."""
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET column_order=? WHERE id=?", (new_order, task_id)
            )

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def list_projects(self, *, include_archived: bool = False) -> list[Project]:
        """All projects with task_counts aggregated by status."""
        sql = "SELECT * FROM projects"
        if not include_archived:
            sql += " WHERE archived = 0"
        sql += " ORDER BY sort_order, name"
        with self._lock:
            rows = self._conn.execute(sql).fetchall()
            counts_rows = self._conn.execute(
                "SELECT project_id, status, COUNT(*) AS n "
                "FROM tasks GROUP BY project_id, status"
            ).fetchall()
        counts: dict[str, dict[str, int]] = {}
        totals: dict[str, int] = {}
        for r in counts_rows:
            counts.setdefault(r["project_id"], {})[r["status"]] = r["n"]
            totals[r["project_id"]] = totals.get(r["project_id"], 0) + r["n"]
        result = []
        for r in rows:
            p = self._row_to_project(r)
            p.task_counts = counts.get(p.id, {})
            p.total_tasks = totals.get(p.id, 0)
            result.append(p)
        return result

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_project(row)

    def create_project(
        self,
        project_id: str,
        name: str,
        *,
        color: str = "#F10D30",
        icon: str = "",
        sort_order: int | None = None,
        path: str | None = None,
        branch_template: str = "kanban/{task_id}-{slug}",
        agent_rules: str = "",
    ) -> Project:
        ts = _now()
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                if sort_order is None:
                    r = self._conn.execute(
                        "SELECT COALESCE(MAX(sort_order), -1) AS m FROM projects"
                    ).fetchone()
                    sort_order = (r["m"] + 1) if r else 0
                self._conn.execute(
                    """INSERT INTO projects
                       (id, name, color, icon, sort_order, archived, path, branch_template, agent_rules, created_at)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                    (project_id, name, color, icon or name[:1].upper(), sort_order, path, branch_template, agent_rules, ts),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        p = self.get_project(project_id)
        assert p is not None
        return p

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        color: str | None = None,
        icon: str | None = None,
        sort_order: int | None = None,
        path: str | None = None,
        branch_template: str | None = None,
        agent_rules: str | None = None,
    ) -> Project:
        sets: list[str] = []
        params: list[Any] = []
        # path is forwarded as-is (None means "leave alone", "" means "clear").
        for col, val in (
            ("name", name), ("color", color), ("icon", icon),
            ("sort_order", sort_order), ("path", path), ("branch_template", branch_template), ("agent_rules", agent_rules),
        ):
            if val is not None:
                sets.append(f"{col} = ?")
                # an empty string for path becomes NULL in the database
                params.append(None if (col == "path" and val == "") else val)
        if not sets:
            p = self.get_project(project_id)
            if p is None:
                raise KeyError(project_id)
            return p
        params.append(project_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if not row:
                raise KeyError(project_id)
            self._conn.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id=?", params
            )
        p = self.get_project(project_id)
        assert p is not None
        return p

    # ------------------------------------------------------------------
    # Project sources (one source per project)
    # ------------------------------------------------------------------

    def set_project_source(
        self, project_id: str, type_: str, config: dict[str, Any]
    ) -> None:
        ts = _now()
        with self._lock:
            self._conn.execute(
                """INSERT INTO project_sources (project_id, type, config, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(project_id) DO UPDATE
                   SET type=excluded.type, config=excluded.config""",
                (project_id, type_, json.dumps(config, ensure_ascii=False), ts),
            )

    def get_project_source(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM project_sources WHERE project_id=?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "project_id": row["project_id"],
            "type": row["type"],
            "config": json.loads(row["config"]),
            "last_sync_at": row["last_sync_at"],
            "created_at": row["created_at"],
        }

    def update_source_sync_time(self, project_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE project_sources SET last_sync_at=? WHERE project_id=?",
                (_now(), project_id),
            )

    def delete_project_source(self, project_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM project_sources WHERE project_id=?", (project_id,)
            )

    def archive_project(self, project_id: str, archived: bool = True) -> Project:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if not row:
                raise KeyError(project_id)
            self._conn.execute(
                "UPDATE projects SET archived=? WHERE id=?",
                (1 if archived else 0, project_id),
            )
        p = self.get_project(project_id)
        assert p is not None
        return p

    def delete_archived_project(self, project_id: str) -> None:
        """Permanently remove an archived project and its board data.

        Git branches and worktrees intentionally remain untouched: they may
        contain work that must be reviewed or recovered outside the board.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT archived FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if not row:
                raise KeyError(project_id)
            if not row["archived"]:
                raise ValueError("archive the project before deleting it")
            try:
                self._conn.execute("BEGIN")
                # task-related tables use ON DELETE CASCADE; tasks themselves
                # predate project foreign keys, so remove them explicitly.
                self._conn.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
                self._conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            icon=row["icon"],
            sort_order=row["sort_order"],
            archived=bool(row["archived"]),
            created_at=row["created_at"],
            path=row["path"] if "path" in row.keys() else None,
            branch_template=row["branch_template"] if "branch_template" in row.keys() else "kanban/{task_id}-{slug}",
            agent_rules=row["agent_rules"] if "agent_rules" in row.keys() else "",
        )

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Dump the whole board as a plain dict for JSON persistence."""
        tasks = self.list_tasks()
        projects = self.list_projects(include_archived=True)
        return {
            "exported_at": _now(),
            "schema_version": 2,
            "projects": [p.to_public() for p in projects],
            "tasks": [t.to_public() for t in tasks],
        }

    def save_snapshot(self, dest_dir: str | Path | None = None) -> Path:
        if dest_dir is None:
            dest_dir = Path(__file__).resolve().parent.parent / "snapshots"
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fp = dest_dir / f"{date_part}.json"
        fp.write_text(
            json.dumps(self.snapshot(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return fp

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_task(
        self,
        row: sqlite3.Row,
        *,
        eager_links: bool = False,
        eager_history: bool = False,
    ) -> Task:
        t = Task(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            priority=row["priority"],
            size=row["size"],
            assignee=row["assignee"],
            description=row["description"],
            acceptance=row["acceptance"],
            skip_planning=bool(row["skip_planning"]) if "skip_planning" in row.keys() else False,
            external_blocker=row["external_blocker"],
            created_at=row["created_at"],
            moved_at=row["moved_at"],
            column_order=row["column_order"],
            project_id=row["project_id"] if "project_id" in row.keys() else DEFAULT_PROJECT_ID,
            branch=row["branch"] if "branch" in row.keys() else None,
            worktree_path=row["worktree_path"] if "worktree_path" in row.keys() else None,
            base_commit=row["base_commit"] if "base_commit" in row.keys() else None,
        )
        if eager_links:
            link_rows = self._conn.execute(
                "SELECT type, value FROM task_links WHERE task_id=? ORDER BY type, value",
                (t.id,),
            ).fetchall()
            t.links = [{"type": r["type"], "value": r["value"]} for r in link_rows]
            blocker_rows = self._conn.execute(
                "SELECT blocker_id FROM task_blockers WHERE task_id=?", (t.id,)
            ).fetchall()
            t.blockers = [r["blocker_id"] for r in blocker_rows]
        if eager_history:
            h_rows = self._conn.execute(
                "SELECT * FROM task_history WHERE task_id=? ORDER BY ts ASC, id ASC",
                (t.id,),
            ).fetchall()
            t.history = [
                TaskHistory(
                    id=r["id"],
                    task_id=r["task_id"],
                    ts=r["ts"],
                    actor=r["actor"],
                    action=r["action"],
                    from_status=r["from_status"],
                    to_status=r["to_status"],
                    comment=r["comment"],
                    skip_planning=bool(r["skip_planning"]) if "skip_planning" in r.keys() else False,
                )
                for r in h_rows
            ]
        return t

    def close(self) -> None:
        with self._lock:
            self._conn.close()
