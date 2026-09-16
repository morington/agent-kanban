"""Unanswered human comments bring planning/testing cards back to ready."""
from __future__ import annotations

import pytest

from kanban_store import Store, latest_pending_feedback, ready_next


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    return Store(tmp_path / "test.db")


def test_planning_user_comment_is_ready_for_new_plan(store):
    task = store.create_task("Hello", project_id="test", status="plan_requested")
    store.pull_task(task.id)
    store.add_comment(task.id, "plan: print hello", actor="claude")
    assert store.ready_tasks("test") == []

    store.add_comment(task.id, "Hello my Kanban", actor="user")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    assert ready_next(ready[0]) == "plan"
    pending = latest_pending_feedback(ready[0].history)
    assert pending is not None
    assert pending.comment == "Hello my Kanban"


def test_planning_direct_comment_is_ready_to_implement(store):
    task = store.create_task("Hello", project_id="test", status="plan_requested")
    store.pull_task(task.id)
    store.add_comment(task.id, "plan", actor="claude")
    store.add_comment(task.id, "just change the string", actor="user", skip_planning=True)
    ready = store.ready_tasks("test")
    assert ready_next(ready[0]) == "implement"
    pulled = store.pull_task(task.id)
    assert pulled.status == "in_progress"


def test_testing_comment_without_direct_stays_ready_to_replan(store):
    task = store.create_task("Libs", project_id="test", status="testing")
    store.add_comment(task.id, "add one more library", actor="user")
    updated = store.get_task(task.id)
    assert updated is not None
    assert updated.status == "testing"
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    assert ready_next(ready[0]) == "plan"
    pulled = store.pull_task(task.id)
    assert pulled.status == "planning"


def test_testing_direct_comment_stays_ready_to_implement(store):
    task = store.create_task("Libs", project_id="test", status="testing")
    store.add_comment(task.id, "also add httpx", actor="user", skip_planning=True)
    updated = store.get_task(task.id)
    assert updated is not None
    assert updated.status == "testing"
    ready = store.ready_tasks("test")
    assert ready_next(ready[0]) == "implement"
    pulled = store.pull_task(task.id)
    assert pulled.status == "in_progress"


def test_plan_requested_comment_is_ready_with_feedback(store):
    task = store.create_task("Hello", project_id="test", status="plan_requested")
    store.add_comment(task.id, "please use uv", actor="user")
    ready = store.ready_tasks("test")
    assert [t.id for t in ready] == [task.id]
    pending = latest_pending_feedback(ready[0].history)
    assert pending is not None
    assert pending.comment == "please use uv"


def test_plan_approved_comment_replans(store):
    task = store.create_task("Hello", project_id="test", status="plan_review")
    store.add_comment(task.id, "change the greeting", actor="user")
    ready = store.ready_tasks("test")
    assert ready_next(ready[0]) == "plan"
    pulled = store.pull_task(task.id)
    assert pulled.status == "planning"


def test_agent_reply_clears_pending_feedback(store):
    task = store.create_task("Hello", project_id="test", status="planning")
    store.add_comment(task.id, "please change text", actor="user")
    assert store.ready_tasks("test")
    store.add_comment(task.id, "new plan", actor="claude")
    assert store.ready_tasks("test") == []


def test_agent_cannot_move_planning_to_in_progress(store):
    task = store.create_task("Hello", project_id="test", status="plan_requested")
    store.pull_task(task.id)
    store.add_comment(task.id, "plan: print hello", actor="claude")
    with pytest.raises(RuntimeError, match="leave the card in Planning"):
        store.move_task(task.id, "in_progress", actor="claude")
    with pytest.raises(RuntimeError, match="leave the card in Planning"):
        store.move_task(task.id, "plan_review", actor="agent:t-002")
    held = store.get_task(task.id)
    assert held is not None
    assert held.status == "planning"


def test_human_can_approve_plan(store):
    task = store.create_task("Hello", project_id="test", status="planning")
    moved = store.move_task(task.id, "plan_review", actor="user")
    assert moved.status == "plan_review"


def test_second_pull_after_plan_stays_in_planning(store):
    task = store.create_task("Hello", project_id="test", status="plan_requested")
    store.pull_task(task.id)
    store.add_comment(task.id, "plan", actor="claude")
    again = store.pull_task(task.id)
    assert again.status == "planning"
