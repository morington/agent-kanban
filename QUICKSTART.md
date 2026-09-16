# Quickstart — agent-kanban in 5 minutes

End-to-end path: clone → run → AI agent picks up an Approved task on its own.
If you don't need AI, skip Part 2 and use it as a regular kanban board.

## Part 1 — Basic kanban (2 minutes)

### Requirements

- Python 3.12+
- macOS / Linux (Windows — via WSL2)
- A browser for the UI

### Install uv (once, ~5 sec)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: brew install uv
```

### Clone + run

```bash
git clone https://github.com/<user>/agent-kanban.git
cd agent-kanban
uv run python -m kanban_ui     # auto-creates .venv, installs deps, runs
# open http://localhost:7777
```

That's it — one command from clone to a running UI on `localhost:7777`. `uv` creates `.venv/`, installs the dependencies from `pyproject.toml` (cached after the first run), and starts the server.

<details>
<summary>Legacy pip / venv path (no uv)</summary>

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m kanban_ui
```

`requirements.txt` is kept in sync with `pyproject.toml`. The pip path is supported indefinitely — uv is just the faster default.

</details>

A `default` project shows up in the sidebar with an empty board (Draft through Done, plus Blocked and Cancelled).
Hit `+ Task` (or press `n`) and create your first card.

### macOS auto-start (optional)

```bash
bash scripts/install_launchd.sh install
# kanban now starts on login; status: scripts/install_launchd.sh status
```

Logs: `~/Library/Logs/agent-kanban/{stdout,stderr}.log`.

---

## Part 2 — AI agent picks up tasks itself (3 minutes)

The flow: you drag a card to **Plan requested** (or **Plan approved** if the plan is already written), and the agent:
1. Calls `kanban_ready` / `kanban_pull`,
2. Writes a short plan and leaves the card in Planning (you move it to Plan approved),
3. Implements on a **task git branch**, `kanban_commit`, moves to Testing,
4. After you drag to **Integrate**, merges that branch into `main` (`kanban_integrate`).

Independent cards branch from the project `main`. A child that lists a parent as a blocker branches from the parent's task branch.

### Step 1 — create a kanban project and bind it to your code directory

In the UI:
- `+ New project` → name, slug (e.g. `myproj`).
- "Choose…" button in the "Project directory" field → native Finder dialog.
  Pick the directory of your Claude Code project (e.g. `~/code/myproj`).

### Step 2 — connect the kanban MCP server to the project

At the root of the code directory, create `.mcp.json`:

```jsonc
{
  "mcpServers": {
    "agent-kanban": {
      "type": "stdio",
      "command": "/abs/path/to/agent-kanban/.venv/bin/python",
      "args":    ["-m", "kanban_mcp"],
      "cwd":     "/abs/path/to/agent-kanban",
      "env": {
        "PYTHONPATH": "/abs/path/to/agent-kanban",
        "KANBAN_DB":  "/abs/path/to/agent-kanban/tasks.db",
        "KANBAN_PROJECT_ID": "myproj",
        "KANBAN_ACTOR": "claude"
      }
    }
  }
}
```

Heads up: `PYTHONPATH` is required — without it Claude ignores `cwd` and
won't find the `kanban_mcp` module. Replace `/abs/path/to/agent-kanban` and
`myproj` with your values.

Verify the connection:
```bash
claude mcp list
# should show: agent-kanban: ... ✓ Connected
```

### Step 3 — log into Claude CLI (one-time)

```bash
claude auth login --claudeai
```

A browser opens with OAuth. After you finish, the `C` button in the kanban
topbar turns orange and tooltips read "Claude CLI: logged in".

### Step 4 — add an auto-launch rule

Create `kanban_data/rules.json`:

```json
{
  "rules": [
    {
      "name": "Auto-launch Claude on approved",
      "enabled": true,
      "trigger": {
        "type": "task_moved",
        "to_status": "approved",
        "project_id": "myproj"
      },
      "action": {
        "type": "run_command",
        "cmd": "/abs/path/to/agent-kanban/examples/agent-launcher/launch-claude.sh",
        "args": ["{task_id}", "{project_id}"],
        "log_file": "/Users/<you>/Library/Logs/agent-kanban/launcher.log",
        "env": { "KANBAN_MCP_ALIAS": "agent-kanban" }
      }
    }
  ]
}
```

`KANBAN_MCP_ALIAS` must match the key under `mcpServers` in `.mcp.json`
(in the example above — `agent-kanban`). Hot-reload by mtime — no server
restart needed.

### Step 5 — try it

1. Create a task with a clear description (`+ Task` or `n`):
   - Title: "Add /api/health endpoint"
   - Description: `GET /api/health → 200 {"status":"ok","ts":...}`
   - Acceptance: `curl localhost:7777/api/health returns 200`
2. Drag it to **Approved** (or press space on the card).
3. Within ~5 seconds → Claude moves it to `analyst`. A minute or two later → `testing`.
4. Session logs: `tail -f ~/Library/Logs/agent-kanban/launcher-T-XXX-*.log`.

---

## What's next

- [`README.md`](README.md) — features, env vars, project layout
- [`docs/USECASES.md`](docs/USECASES.md) — 11 scenarios (solo dev, team Slack, legacy import, multi-project, ...)
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — Claude Code, Cline, opencode, Open WebUI, any function-calling LLM
- [`examples/agent-launcher/`](examples/agent-launcher/) — launcher scripts for Claude Code and other agents
- [`examples/llm-tool-calling/`](examples/llm-tool-calling/) — Python demos for OpenAI SDK / Ollama / curl
- Slack/Telegram/generic webhooks — `kanban_data/webhooks.json`, see [INTEGRATION.md](docs/INTEGRATION.md#outbound-webhooks-slack--telegram--generic)
- OpenAPI 3.1: [`docs/openapi.yaml`](docs/openapi.yaml), live `/docs`

## Troubleshooting

| Symptom | Where to look |
|---|---|
| `claude mcp list` → `Failed to connect` | check that `PYTHONPATH` in `.mcp.json` points at the agent-kanban root |
| Task doesn't move from approved → analyst | `tail ~/Library/Logs/agent-kanban/launcher-T-*.log`; make sure `KANBAN_MCP_ALIAS` matches the key in `.mcp.json` |
| Claude headless: "tool not allowed" | `--allowedTools` in `launch-claude.sh` must include `mcp__<alias>__kanban_*` |
| `C` button in topbar is grey | not logged in — clicking it kicks off the OAuth flow in your browser |
| Drag-drop works but webhooks are silent | check the syntax of `kanban_data/webhooks.json`; status: `/api/automation/status.webhooks` |

All event logs and errors are exposed at `GET /api/automation/status` (JSON).

## License

MIT — see [LICENSE](LICENSE).
