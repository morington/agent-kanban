# agent-kanban

> Local-first kanban for AI coding agents. SQLite, FastAPI, no auth, no cloud.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)

A board you run on your machine. You drag cards; Cursor / Claude Code / Cline
do the work through MCP. Each card gets its own git branch. Related cards
branch from the parent. When you move a card to **Integrate**, the agent
merges that branch into `main`.

![Board — light theme](docs/screenshots/board-light.png)

<details>
<summary>More themes & profiles</summary>

| Dark theme | Cyberpunk profile | Horizon profile |
|---|---|---|
| ![dark](docs/screenshots/board-dark.png) | ![cyberpunk](docs/screenshots/board-cyberpunk.png) | ![horizon](docs/screenshots/board-horizon.png) |

Toggle theme with `t`, cycle profiles with `p`. Or pin via URL: `?theme=light&profile=cyberpunk`.

</details>

## Workflow

```
Draft → Backlog → Plan requested → Planning → Plan approved
      → In progress → Testing → Integrate → Done
```

Blocked and Cancelled sit on the side.

| Column | Who | What happens |
|---|---|---|
| Plan requested | Agent | New cards, plus any new human comments. |
| Planning | Agent | Writes a short plan, **leaves the card here**. You move it to Plan approved. A new comment without the “do this now” tick means write a new plan. |
| Plan approved | Agent | Plan accepted — start implementation. |
| In progress | Agent | Works in the task **worktree**, commits, then Testing. |
| Testing | You / agent | You review. A comment asks for a fix (plan or immediate). |
| Integrate | Agent | Merges the task branch into the project default branch (`main`), then Done. |
| Done | You | Finished. |

**Git**

- Independent cards branch from `main` (the project start), never from a sibling task.
- If card B lists card A as a blocker, B’s branch is created from A’s branch.
- `kanban_prepare_workspace` adds a git worktree at `<project>/.kanban-worktrees/<branch>/` (gitignored). The main checkout stays on `main`, so unrelated tasks can run in parallel.
- Work and `kanban_commit` happen in that worktree. Done or Cancelled deletes the folder.
- `kanban_integrate` (from Integrate) merges the branch into `main`, then removes the worktree.

**Discussion**

In the card, a comment can tick **Do this now, no new plan**. Then the agent implements instead of writing another plan. Comments are picked up on Plan requested, Planning, Plan approved, Testing, and Integrate.

A child card becomes ready when its parent reaches **Testing** (you do not wait for Done).

A card can be marked **Start without plan** so Plan requested goes straight to implementation.

## Install

**Docker Compose (recommended if this is how you already run it):**

```bash
cp -n .env.example .env    # UID/GID + KANBAN_WORKSPACES_DIR
docker compose up --build -d
# board: http://localhost:7777
```

Code changes: `docker compose restart`. Dependency / Dockerfile changes: `docker compose up --build -d`.

`KANBAN_WORKSPACES_DIR` must contain the git repos whose paths you store on projects (so the container can create branches and merge).

**Without Docker:**

```bash
# uv: curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/<your-user>/agent-kanban.git
cd agent-kanban
uv run python -m kanban_ui          # http://localhost:7777
```

Walkthrough: [QUICKSTART.md](QUICKSTART.md). Agent wiring: [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Use with Cursor

1. Run the board (Compose or `uv run`).
2. Create a project, set **Project directory** to the real git repo path.
3. Point Cursor MCP at the kanban (stdio `python -m kanban_mcp` with `KANBAN_DB`, or HTTP `http://localhost:7777/mcp`).
4. Put this in the project’s **Agent rules**:

```text
When I say “check the board”, call kanban_ready for this project.
Handle cards in the returned order (Integrate, then Testing, then Plan approved, then Planning).
Read `feedback` if present (latest human comment). Always follow `after`.
Use `next`:
- plan: pull, kanban_comment a short plan or reply, leave in Planning. No code.
- implement: pull, kanban_prepare_workspace, work only in worktree_path, kanban_commit, kanban_comment what you did, move to Testing.
- integrate: kanban_integrate (merge into main and move to Done).
Call kanban_ready again. Stop when empty.
Do not call kanban_columns. Do not kanban_move to Done yourself. Keep comments short and technical.
```

5. Say “check the board”. Reload the MCP server after kanban code changes.

## MCP tools

| Tool | Purpose |
|---|---|
| `kanban_ready` | Queue in order (Integrate → Testing → Plan approved → Planning), with `next`, `after`, optional `feedback` |
| `kanban_get` | Full card + history |
| `kanban_pull` | Claim a ready card |
| `kanban_prepare_workspace` | Worktree under `<project>/.kanban-worktrees/` |
| `kanban_commit` | Commit in that worktree |
| `kanban_integrate` | Merge into `main` from Integrate, then Done |
| `kanban_move` / `kanban_comment` | Status and discussion |
| `kanban_create` / `kanban_update` / `kanban_blockers` / `kanban_link` | Card edits |
| `kanban_board` / `kanban_list` / `kanban_search` / `kanban_projects` / `kanban_my_active` / `kanban_columns` | Browse |

Also: REST + OpenAPI (`/docs`, `/openapi.json`), PLAN.md import, inbox watcher, automation rules, webhooks. Details in [docs/INTEGRATION.md](docs/INTEGRATION.md) and [docs/USECASES.md](docs/USECASES.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `KANBAN_HOST` | `127.0.0.1` | bind address (`0.0.0.0` in Docker) |
| `KANBAN_PORT` | `7777` | port |
| `KANBAN_DB` | `<repo>/tasks.db` | SQLite path |
| `KANBAN_ACTOR` | `user` | author name in history |
| `KANBAN_WORKSPACES_DIR` | (Compose) | host path mounted so git repos are visible |
| `KANBAN_INBOX_DIR` | `kanban_data/inbox` | drop `.md` files → cards |
| `KANBAN_RULES_FILE` | `kanban_data/rules.json` | automation rules |
| `KANBAN_WEBHOOKS_FILE` | `kanban_data/webhooks.json` | outbound webhooks |
| `KANBAN_CORS_ORIGINS` | (empty) | CORS for remote Open WebUI |
| `KANBAN_PROJECT_ID` | (empty) | default project for `kanban_create` |

## Layout

```
agent-kanban/
├── docker-compose.yml · Dockerfile
├── kanban_store/     SQLite + git workspace (branch / commit / merge)
├── kanban_ui/        FastAPI UI + automation
├── kanban_mcp/       MCP tools
├── tests/
└── docs/
```

Board data: `tasks.db`, `kanban_data/` (gitignored).

## License

[MIT](LICENSE)
