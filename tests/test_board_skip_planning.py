"""GET /api/board must include skip_planning so mini-cards can show the badge."""
from __future__ import annotations

import pytest

from kanban_store import Store
from kanban_ui import main as ui


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_ID", "test")
    monkeypatch.setenv("KANBAN_DEFAULT_PROJECT_NAME", "Test")
    store = Store(tmp_path / "test.db")
    monkeypatch.setattr(ui, "_store", store)
    return store


def test_board_includes_skip_planning_for_mini_cards(temp_store):
    skipped = temp_store.create_task(
        "Direct", skip_planning=True, project_id="test"
    )
    planned = temp_store.create_task(
        "Needs plan", skip_planning=False, project_id="test"
    )

    board = ui.get_board("test")
    cards = [c for col in board["tasks"].values() for c in col]
    by_id = {c["id"]: c for c in cards}

    assert by_id[skipped.id]["skip_planning"] is True
    assert by_id[planned.id]["skip_planning"] is False
    assert "skip_planning" in by_id[skipped.id]
