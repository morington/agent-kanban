"""Ready-queue: plan vs implement, blockers lift at testing."""
from __future__ import annotations

import pytest

from kanban_store import Store, ready_after, ready_next


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    return Store(tmp_path / "test.db")


def test_plan_requested_is_ready_for_plan(store):
    task = store.create_task("Write plan", project_id="test", status="plan_requested")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    assert ready_next(ready[0]) == "plan"


def test_skip_planning_is_ready_for_implement(store):
    task = store.create_task(
        "Direct", project_id="test", status="plan_requested", skip_planning=True
    )
    ready = store.ready_tasks("test")
    assert ready_next(ready[0]) == "implement"
    pulled = store.pull_task(task.id)
    assert pulled.status == "in_progress"


def test_plan_approved_is_ready_for_implement(store):
    task = store.create_task("Approved", project_id="test", status="plan_review")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    assert ready_next(ready[0]) == "implement"
    pulled = store.pull_task(task.id)
    assert pulled.status == "in_progress"


def test_planning_is_not_ready(store):
    store.create_task("Stay here", project_id="test", status="planning")
    assert store.ready_tasks("test") == []


def test_child_ready_when_parent_reaches_testing(store):
    parent = store.create_task("Parent", project_id="test", status="in_progress")
    child = store.create_task("Child", project_id="test", status="plan_requested")
    store.set_blockers(child.id, [parent.id])
    assert store.ready_tasks("test") == []
    store.move_task(parent.id, "testing")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [child.id]


def test_child_not_ready_while_parent_in_progress(store):
    parent = store.create_task("Parent", project_id="test", status="in_progress")
    child = store.create_task("Child", project_id="test", status="plan_requested")
    store.set_blockers(child.id, [parent.id])
    with pytest.raises(RuntimeError, match="unfinished blockers"):
        store.pull_task(child.id)


def test_integrate_column_is_ready(store):
    task = store.create_task("Merge", project_id="test", status="acceptance")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    assert ready_next(ready[0]) == "integrate"
    pulled = store.pull_task(task.id)
    assert pulled.status == "acceptance"


def test_pull_plan_requested_goes_to_planning(store):
    task = store.create_task("Plan me", project_id="test", status="plan_requested")
    pulled = store.pull_task(task.id)
    assert pulled.status == "planning"


def test_ready_queue_priority(store):
    planning = store.create_task("Replan", project_id="test", status="planning")
    store.add_comment(planning.id, "please replan", actor="user")
    approved = store.create_task("Approved", project_id="test", status="plan_review")
    testing = store.create_task("Fix", project_id="test", status="testing")
    store.add_comment(testing.id, "add alembic", actor="user", skip_planning=True)
    merge_b = store.create_task("Merge B", project_id="test", status="acceptance")
    merge_a = store.create_task("Merge A", project_id="test", status="acceptance")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [
        merge_b.id,
        merge_a.id,
        testing.id,
        approved.id,
        planning.id,
    ]


def test_ready_after_implement_requires_comment(store):
    task = store.create_task("Libs", project_id="test", status="testing")
    store.add_comment(task.id, "add alembic", actor="user", skip_planning=True)
    ready = store.ready_tasks("test")
    assert "kanban_comment" in ready_after(ready[0])
