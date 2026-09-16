/* FinOps Kanban frontend v2.
 * Multi-project (URL /p/{slug}), drag-drop, search+filter, collapsible cols,
 * compact mode, quick-add, keyboard shortcuts, polling /api/board every 10 s.
 */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const STATUS_TITLE = {
  draft: "Draft",
  backlog: "Backlog",
  plan_requested: "Plan requested",
  planning: "Planning",
    plan_review: "Plan approved",
  in_progress: "In progress",
  testing: "Testing",
  acceptance: "Integrate",
  done: "Done",
  blocked: "Blocked",
  cancelled: "Cancelled",
};

const STATUS_TITLE_RU = {
  draft: "Черновик", backlog: "Бэклог", plan_requested: "Запрос плана",
  planning: "Планирование", plan_review: "План согласован", in_progress: "В работе",
  testing: "Тестирование", acceptance: "Слияние", done: "Готово", blocked: "Заблокировано", cancelled: "Отменено",
};
const I18N = {
  en: { archive: "Archive", newProject: "+ New project", search: "Search (/) — title, id, description", blocker: "Blocker", agents: "Agents", unassigned: "Unassigned", snapshot: "Snapshot", newTask: "+ Task", title: "Title", priority: "Priority", high: "High", normal: "Normal", low: "Low", size: "Size", assignee: "Assignee", description: "Description", acceptance: "Acceptance criteria", externalBlocker: "External blocker", taskBlockers: "Task blockers", workspace: "Workspace", prepareBranch: "Prepare branch", links: "Links", history: "History", addComment: "Add comment", commentText: "Comment text", cancel: "Cancel", save: "Save", column: "Column", create: "Create", name: "Name", projectId: "ID (slug)", idHint: "Lowercase latin, digits, hyphen. 2 to 32 characters.", projectDirectory: "Project directory", choose: "Choose…", pathHint: "Optional. Path to the agent project on disk.", branchTemplate: "Branch template", branchHint: "Available variables: {task_id}, {slug}. Example: kanban/t-042-add-cart.", agentRules: "Agent rules for this project", agentRulesExample: "Example: use Python 3.13, run pytest, do not change public API without asking.", agentRulesHint: "These instructions are returned with the project metadata to a connected agent.", color: "Color", taskSource: "Task source", sourceNew: "New project", sourceLocal: "Existing plans", sourceGit: "Git repo", sourceNewHelp: "Kanban will create PLAN.md in the directory and add instructions to CLAUDE.md. The agent writes tasks to PLAN.md, and Kanban imports them.", sourceNoPath: "First specify the project directory (field above).", selected: "Selected", chooseOther: "Choose another folder…", sourceLocalHelp: "Choose Markdown plans with headings such as Backlog, In progress, or Done. The first chosen file is also added to CLAUDE.md so the agent can add tasks there.", gitTokenHint: "The token is stored locally in kanban_data/.env-secrets with mode 600 as KANBAN_GIT_TOKEN_<ID>.", currentSource: "Current source:", newProjectTitle: "New project", projectPrefix: "Project:", quickAdd: "Title (Enter — create, Esc — cancel)", tasks: "tasks", empty: "empty", scanning: "Scanning…", noMarkdown: "No .md files found in the directory. Use “Choose another folder…” below.", specifyDirectory: "Specify directory…", opening: "Opening…", pickerUnavailable: "Native picker not available — enter the path manually" },
  ru: { archive: "Архив", newProject: "+ Новый проект", search: "Поиск (/) — название, id, описание", blocker: "Блокеры", agents: "Агенты", unassigned: "Не назначены", snapshot: "Снимок", newTask: "+ Задача", title: "Название", priority: "Приоритет", high: "Высокий", normal: "Обычный", low: "Низкий", size: "Размер", assignee: "Исполнитель", description: "Описание", acceptance: "Критерии приёмки", externalBlocker: "Внешний блокер", taskBlockers: "Зависит от задач", workspace: "Рабочая папка", prepareBranch: "Создать ветку", links: "Ссылки", history: "История", addComment: "Добавить комментарий", commentText: "Текст комментария", cancel: "Отмена", save: "Сохранить", column: "Колонка", create: "Создать", name: "Название", projectId: "ID (slug)", idHint: "Латинские строчные буквы, цифры и дефис. От 2 до 32 символов.", projectDirectory: "Папка проекта", choose: "Выбрать…", pathHint: "Необязательно. Путь к проекту агента на диске.", branchTemplate: "Шаблон ветки", branchHint: "Доступные переменные: {task_id}, {slug}. Пример: kanban/t-042-add-cart.", agentRules: "Правила агента для проекта", agentRulesExample: "Например: используй Python 3.13, запусти pytest, не меняй публичный API без согласования.", agentRulesHint: "Эти инструкции передаются подключённому агенту вместе с данными проекта.", color: "Цвет", taskSource: "Источник задач", sourceNew: "Новый проект", sourceLocal: "Готовые планы", sourceGit: "Git-репозиторий", sourceNewHelp: "Kanban создаст PLAN.md в папке и добавит инструкции в CLAUDE.md. Агент будет записывать задачи в PLAN.md, а Kanban их импортирует.", sourceNoPath: "Сначала укажите папку проекта (поле выше).", selected: "Выбрано", chooseOther: "Выбрать другую папку…", sourceLocalHelp: "Выберите Markdown-планы с разделами вроде «Бэклог», «В работе» или «Готово». Первый выбранный файл также добавляется в CLAUDE.md, чтобы агент мог записывать туда задачи.", gitTokenHint: "Токен хранится локально в kanban_data/.env-secrets с правами 600 как KANBAN_GIT_TOKEN_<ID>.", currentSource: "Текущий источник:", newProjectTitle: "Новый проект", projectPrefix: "Проект:", quickAdd: "Название (Enter — создать, Esc — отмена)", tasks: "задач", empty: "пусто", scanning: "Сканирование…", noMarkdown: "В папке нет файлов .md. Выберите другую папку ниже.", specifyDirectory: "Указать папку…", opening: "Открытие…", pickerUnavailable: "Системный выбор папки недоступен — укажите путь вручную" },
};
Object.assign(I18N.en, { edit: "Edit", discussion: "Discussion", skipPlanning: "Start without plan review", directTask: "Start immediately", commentDirect: "Do this now, no new plan" });
Object.assign(I18N.en, { send: "Send" });
Object.assign(I18N.ru, { edit: "Редактировать", discussion: "Обсуждение", send: "Отправить", skipPlanning: "Без планирования: агент сразу начинает выполнение", directTask: "Сразу выполнить", commentDirect: "Сразу выполнить, без нового плана" });

function statusTitle(status) { return state.lang === "ru" ? (STATUS_TITLE_RU[status] || status) : (STATUS_TITLE[status] || status); }
function applyLocale() {
  document.documentElement.lang = state.lang;
  const strings = I18N[state.lang];
  $$('[data-i18n]').forEach(el => { el.textContent = strings[el.dataset.i18n] || el.textContent; });
  $$('[data-i18n-placeholder]').forEach(el => { el.placeholder = strings[el.dataset.i18nPlaceholder] || el.placeholder; });
  $$('[data-i18n-title]').forEach(el => { el.title = strings[el.dataset.i18nTitle] || el.title; });
  $$('[data-status-option]').forEach(el => { el.textContent = statusTitle(el.value); });
  $("#btn-language").textContent = state.lang === "ru" ? "EN" : "RU";
}
function toggleLanguage() { state.lang = state.lang === "ru" ? "en" : "ru"; localStorage.setItem(LS.LANG, state.lang); applyLocale(); render(state.board); }

const LS = {
  DENSITY: "kb.density",
  SIDEBAR: "kb.sidebar",
  COLLAPSED_COLS: "kb.collapsedCols",
  EXPANDED_COLS: "kb.expandedCols",
  ARCHIVE_OPEN: "kb.archiveOpen",
  THEME: "kb.theme",
  PROFILE: "kb.profile",
  LAST_PROJECT: "kb.lastProject",
  LANG: "kb.lang",
  GROUPS: "kb.dependencyGroups",
};

const PROFILES = ["standard", "cyberpunk", "horizon"];
const PROFILE_LABELS = {
  standard: "Standard",
  cyberpunk: "Cyberpunk",
  horizon:   "Horizon",
};

// ----------------------------------------------------------- State

const state = {
  projectId: null,                  // picked from URL or the first project
  project: null,                   // full metadata for the current project
  projects: [],                    // all projects (active + archived)
  board: { columns: [], tasks: {} },
  search: "",
  filters: new Set(),              // 'prio:high', 'blocked', 'assignee:claude', ...
  density: localStorage.getItem(LS.DENSITY) || "comfortable",
  theme: document.documentElement.getAttribute("data-theme") || "dark",
  sidebarCollapsed: localStorage.getItem(LS.SIDEBAR) === "collapsed",
  collapsedCols: _loadJSON(LS.COLLAPSED_COLS),
  expandedCols:  _loadJSON(LS.EXPANDED_COLS),
  isDragging: false,
  lang: localStorage.getItem(LS.LANG) || (navigator.language.startsWith("ru") ? "ru" : "en"),
};

function _loadJSON(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}
function saveCollapsed() {
  localStorage.setItem(LS.COLLAPSED_COLS, JSON.stringify(state.collapsedCols));
  localStorage.setItem(LS.EXPANDED_COLS, JSON.stringify(state.expandedCols));
}

// ----------------------------------------------------------- API

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text}`);
  }
  if (r.status === 204) return null;
  return r.json();
}

// ----------------------------------------------------------- Toast

function toast(msg, kind = "info") {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("toast--err", kind === "err");
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2400);
}

// ----------------------------------------------------------- URL routing

function parseRoute() {
  const m = location.pathname.match(/^\/p\/([a-z][a-z0-9-]*)\/?$/);
  return m ? m[1] : null;     // null = not picked yet, will fall back to first project
}

function navigateTo(projectId, { replace = false } = {}) {
  const url = `/p/${projectId}`;
  if (replace) history.replaceState({ projectId }, "", url);
  else history.pushState({ projectId }, "", url);
  state.projectId = projectId;
  localStorage.setItem(LS.LAST_PROJECT, projectId);
}

// ----------------------------------------------------------- Helpers

function escapeHTML(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[m]);
}

function actorLabel(actor) {
  if (actor === "user") return state.lang === "ru" ? "Вы" : "You";
  // "claude" is a legacy MCP identifier, not a product name shown to people.
  return state.lang === "ru" ? "Агент" : "Agent";
}

function renderInlineMarkdown(text) {
  return escapeHTML(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function renderMarkdown(source) {
  const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let paragraph = [];
  let list = null;
  let inCode = false;
  let code = [];
  const closeParagraph = () => {
    if (paragraph.length) out.push(`<p>${paragraph.map(renderInlineMarkdown).join("<br>")}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };
  for (const line of lines) {
    if (line.startsWith("```")) {
      closeParagraph(); closeList();
      if (inCode) { out.push(`<pre><code>${escapeHTML(code.join("\n"))}</code></pre>`); code = []; }
      inCode = !inCode;
      continue;
    }
    if (inCode) { code.push(line); continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (heading) {
      closeParagraph(); closeList();
      const level = heading[1].length;
      out.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
    } else if (bullet || numbered) {
      closeParagraph();
      const nextList = bullet ? "ul" : "ol";
      if (list !== nextList) { closeList(); out.push(`<${nextList}>`); list = nextList; }
      out.push(`<li>${renderInlineMarkdown((bullet || numbered)[1])}</li>`);
    } else if (!line.trim()) {
      closeParagraph(); closeList();
    } else {
      closeList();
      paragraph.push(line);
    }
  }
  if (inCode) out.push(`<pre><code>${escapeHTML(code.join("\n"))}</code></pre>`);
  closeParagraph(); closeList();
  return out.join("");
}

function ownerLabel(owner) {
  if (owner === "user") return "user";
  if (owner === "agent") return "agent";
  if (owner === "any") return "—";
  return "";
}

// ----------------------------------------------------------- Sidebar

function renderSidebar() {
  const list = $("#proj-list");
  list.innerHTML = "";
  const active = state.projects.filter(p => !p.archived);
  for (const p of active) list.appendChild(projectEl(p));

  // archive section
  const archived = state.projects.filter(p => p.archived);
  const archiveBox = $("#proj-archive");
  if (archived.length === 0) {
    archiveBox.hidden = true;
  } else {
    archiveBox.hidden = false;
    $("#archive-count").textContent = archived.length;
    const archList = $("#proj-archive-list");
    archList.innerHTML = "";
    for (const p of archived) archList.appendChild(projectEl(p));
    const open = localStorage.getItem(LS.ARCHIVE_OPEN) === "1";
    archiveBox.classList.toggle("is-open", open);
    archList.hidden = !open;
  }

  // sidebar collapsed state
  $("#sidebar").classList.toggle("is-collapsed", state.sidebarCollapsed);
}

function projectEl(p) {
  const a = document.createElement("a");
  a.className = "proj";
  if (p.id === state.projectId) a.classList.add("proj--active");
  a.dataset.proj = p.id;
  a.href = `/p/${p.id}`;
  a.title = p.path ? `${p.name} — ${p.path}` : p.name;
  a.innerHTML = `
    <span class="proj__mark" style="background:${escapeHTML(p.color)}">${escapeHTML((p.icon || p.name[0] || "?").toUpperCase().slice(0,2))}</span>
    <span class="proj__name">${escapeHTML(p.name)}</span>
    <span class="proj__count">${p.total_tasks || 0}</span>
    <button class="proj__menu" title="Edit" aria-label="Edit">⋯</button>
  `;
  a.addEventListener("click", (e) => {
    if (e.target.closest(".proj__menu")) {
      e.preventDefault();
      e.stopPropagation();
      openEditProj(p);
      return;
    }
    e.preventDefault();
    if (p.id === state.projectId) return;
    navigateTo(p.id);
    loadBoard();
    renderSidebar();
  });
  return a;
}

// ----------------------------------------------------------- Board render

const GROUP_COLORS = ["#E05263", "#B47CC7", "#338F83", "#C28A32", "#467FCF", "#B56E50", "#6A9A4A", "#527F92"];
const groupColorCache = new Map();

function dependencyGroups(tasks) {
  const byId = new Map(tasks.map(task => [task.id, task]));
  const parent = new Map(tasks.map(task => [task.id, task.id]));
  const find = id => {
    let root = parent.get(id);
    while (root !== parent.get(root)) root = parent.get(root);
    return root;
  };
  const join = (a, b) => {
    const left = find(a); const right = find(b);
    if (left !== right) parent.set(right, left);
  };
  for (const task of tasks) {
    for (const blocker of task.blockers || []) {
      if (byId.has(blocker)) join(task.id, blocker);
    }
  }
  const components = new Map();
  for (const task of tasks) {
    const root = find(task.id);
    if (!components.has(root)) components.set(root, []);
    components.get(root).push(task);
  }
  const groups = [];
  for (const members of components.values()) {
    if (members.length < 2) continue;
    const ids = new Set(members.map(task => task.id));
    // The root has no blocker inside this column; it is shown first.
    members.sort((a, b) => {
      const aBlocked = (a.blockers || []).some(id => ids.has(id));
      const bBlocked = (b.blockers || []).some(id => ids.has(id));
      return Number(aBlocked) - Number(bBlocked) || tasks.indexOf(a) - tasks.indexOf(b);
    });
    groups.push({ key: members.map(task => task.id).sort().join("|"), tasks: members });
  }
  return groups;
}

function groupCollapsed(group) {
  const collapsed = _loadJSON(`${LS.GROUPS}.${state.projectId}`);
  return collapsed[group.key] === true;
}

function toggleDependencyGroup(groupKey) {
  const key = `${LS.GROUPS}.${state.projectId}`;
  const collapsed = _loadJSON(key);
  collapsed[groupKey] = !collapsed[groupKey];
  localStorage.setItem(key, JSON.stringify(collapsed));
  render(state.board);
}

function assignGroupColors(groups) {
  const used = new Set();
  for (const group of groups) {
    const cacheKey = `${state.projectId}:${group.key}`;
    let color = groupColorCache.get(cacheKey);
    if (!color || used.has(color)) {
      const available = GROUP_COLORS.filter(item => !used.has(item));
      color = available.length > 0
        ? available[Math.floor(Math.random() * available.length)]
        : GROUP_COLORS[used.size % GROUP_COLORS.length];
    }
    groupColorCache.set(cacheKey, color);
    used.add(color);
    group.color = color;
  }
}

function drawGroupFrames(listEl, groups) {
  listEl.querySelectorAll(".task-group-frame").forEach(frame => frame.remove());
  requestAnimationFrame(() => {
    for (const group of groups) {
      const cards = group.tasks.map(task => listEl.querySelector(`.card[data-task-id="${task.id}"]`)).filter(Boolean);
      if (cards.length < 2) continue;
      const first = cards[0].getBoundingClientRect();
      const last = cards[cards.length - 1].getBoundingClientRect();
      const host = listEl.getBoundingClientRect();
      const frame = document.createElement("div");
      frame.className = "task-group-frame";
      frame.dataset.groupKey = group.key;
      frame.style.setProperty("--group-color", group.color);
      frame.style.top = `${first.top - host.top - 5 + listEl.scrollTop}px`;
      frame.style.left = "3px";
      frame.style.right = "3px";
      frame.style.height = `${last.bottom - first.top + 10}px`;
      listEl.prepend(frame);
    }
  });
}

function render(board) {
  state.board = board;
  if (board.project) {
    state.project = board.project;
    $("#topbar-title").textContent = board.project.name;
    $("#proj-mark").style.background = board.project.color;
    document.title = `Kanban — ${board.project.name}`;
  }
  const root = $("#board");
  root.innerHTML = "";
  const groupsByStatus = new Map(board.columns.map(column => [column.id, dependencyGroups(board.tasks[column.id] || [])]));
  assignGroupColors(Array.from(groupsByStatus.values()).flat());
  let total = 0;
  let visible = 0;
  for (const col of board.columns) {
    const list = board.tasks[col.id] || [];
    total += list.length;
    const colEl = document.createElement("section");
    colEl.className = "col";
    colEl.dataset.status = col.id;
    if (isColEffectivelyCollapsed(col.id, list.length > 0)) {
      colEl.classList.add("is-collapsed");
    }
    colEl.innerHTML = `
      <header class="col__head">
        <span class="col__chevron">▾</span>
        <span class="col__title">${escapeHTML(statusTitle(col.id))}</span>
        <span class="col__count">${list.length}</span>
        <button class="col__quickadd" title="Quick add (n)" aria-label="Add">+</button>
      </header>
      <div class="col__list" data-status="${col.id}"></div>
    `;
    root.appendChild(colEl);
    const listEl = colEl.querySelector(".col__list");
    const groups = groupsByStatus.get(col.id) || [];
    const groupByTask = new Map();
    for (const group of groups) group.tasks.forEach((task, index) => groupByTask.set(task.id, { group, index }));
    const renderedGroups = new Set();
    for (const original of list) {
      const meta = groupByTask.get(original.id);
      if (meta && renderedGroups.has(meta.group.key)) continue;
      const tasksToRender = meta ? meta.group.tasks : [original];
      if (meta) renderedGroups.add(meta.group.key);
      for (const t of tasksToRender) {
        const taskMeta = groupByTask.get(t.id);
        const card = cardEl(t, taskMeta);
        if (taskMeta && taskMeta.index > 0 && groupCollapsed(taskMeta.group)) card.classList.add("is-group-hidden");
        if (!matchesFilters(t)) card.classList.add("is-hidden");
        else visible++;
        listEl.appendChild(card);
      }
    }
    drawGroupFrames(listEl, groups.filter(group => !groupCollapsed(group)));
    Sortable.create(listEl, {
      group: "tasks",
      draggable: ".card",
      animation: 140,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      dragClass: "sortable-drag",
      onStart: () => {
        state.isDragging = true;
        // Frames describe the old layout and must not visually span cards
        // while Sortable is moving one of them.
        $$(".task-group-frame").forEach(frame => { frame.hidden = true; });
      },
      onEnd: handleDrop,
    });
    // col head click toggles collapse
    colEl.querySelector(".col__head").addEventListener("click", (e) => {
      if (e.target.closest(".col__quickadd")) return;
      toggleColCollapse(col.id, list.length > 0);
    });
    colEl.querySelector(".col__quickadd").addEventListener("click", (e) => {
      e.stopPropagation();
      // If the column is collapsed — expand first, then open quickadd
      if (colEl.classList.contains("is-collapsed")) {
        toggleColCollapse(col.id, list.length > 0);
        setTimeout(() => openQuickAdd(col.id, colEl), 220);
      } else {
        openQuickAdd(col.id, colEl);
      }
    });
  }
  // density
  root.classList.toggle("is-compact", state.density === "compact");
  // stats
  const filterLabel = (state.search || state.filters.size > 0)
    ? `${visible} / ${total}` : `${total}`;
  $("#stats").textContent = `${filterLabel} ${I18N[state.lang].tasks}`;
}

function cardEl(t, groupMeta = null) {
  const div = document.createElement("article");
  div.className = "card";
  div.dataset.taskId = t.id;
  if (groupMeta) div.dataset.groupKey = groupMeta.group.key;
  div.innerHTML = `
    <div class="card__row">
      <span class="card__id">${t.id}</span>
      ${t.skip_planning ? `<span class="card__direct" title="${state.lang === "ru" ? "Сразу выполнить" : "Start immediately"}" aria-label="${state.lang === "ru" ? "Сразу выполнить" : "Start immediately"}">✓</span>` : ""}
      ${groupMeta && groupMeta.index === 0 ? `<button class="card__group-toggle" type="button" title="${groupCollapsed(groupMeta.group) ? "Expand" : "Collapse"}">${groupCollapsed(groupMeta.group) ? "▸" : "▾"} ${groupMeta.group.tasks.length}</button>` : ""}
    </div>
    <div class="card__title">${escapeHTML(t.title)}</div>
    ${t.external_blocker ? `<div class="card__meta"><span class="card__blocker" title="${escapeHTML(t.external_blocker)}">${escapeHTML(t.external_blocker)}</span></div>` : ""}
  `;
  div.addEventListener("click", () => {
    if (state.isDragging) return;
    openTaskModal(t.id);
  });
  const toggle = $(".card__group-toggle", div);
  if (toggle && groupMeta) toggle.addEventListener("click", event => {
    event.stopPropagation();
    toggleDependencyGroup(groupMeta.group.key);
  });
  return div;
}

// ----------------------------------------------------------- Filters

function matchesFilters(t) {
  // search
  if (state.search) {
    const q = state.search.toLowerCase();
    const hay = `${t.id} ${t.title}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  // filter chips
  for (const f of state.filters) {
    if (f === "prio:high" && t.priority !== "high") return false;
    if (f === "blocked" && !t.external_blocker) return false;
    if (f === "unassigned" && t.assignee) return false;
    if (f.startsWith("assignee:")) {
      const want = f.slice("assignee:".length);
      const have = t.assignee || "";
      if (want === "agent") {
        if (!(have === "claude" || have.startsWith("agent:"))) return false;
      } else if (have !== want) return false;
    }
  }
  return true;
}

function applyFilters() {
  // hide/unhide cards without a full re-render (faster)
  let visible = 0; let total = 0;
  for (const col of state.board.columns) {
    const tasks = state.board.tasks[col.id] || [];
    total += tasks.length;
    for (const t of tasks) {
      const card = $(`.card[data-task-id="${t.id}"]`);
      if (!card) continue;
      if (matchesFilters(t)) {
        card.classList.remove("is-hidden");
        visible++;
      } else {
        card.classList.add("is-hidden");
      }
    }
  }
  $$(".task-group-frame").forEach(frame => {
    const key = CSS.escape(frame.dataset.groupKey || "");
    const visibleCards = $$(`.card[data-group-key="${key}"]`).some(card => !card.classList.contains("is-hidden") && !card.classList.contains("is-group-hidden"));
    frame.hidden = !visibleCards;
  });
  const filterLabel = (state.search || state.filters.size > 0)
    ? `${visible} / ${total}` : `${total}`;
  $("#stats").textContent = `${filterLabel} ${I18N[state.lang].tasks}`;
}

// ----------------------------------------------------------- Collapsed columns
//
// "Effectively collapsed" logic:
//   - manually collapsed (in collapsedCols) → ALWAYS collapsed
//   - manually expanded (in expandedCols)   → ALWAYS expanded
//   - default: empty column → collapsed, non-empty → expanded
//
// This auto-collapses empty columns but still respects an explicit user choice
// (click on the header).

function isColEffectivelyCollapsed(colId, hasTasks) {
  const proj = state.projectId;
  const manualC = (state.collapsedCols[proj] || []).includes(colId);
  if (manualC) return true;
  const manualE = (state.expandedCols[proj] || []).includes(colId);
  if (manualE) return false;
  return !hasTasks;
}

function toggleColCollapse(colId, hasTasks) {
  const proj = state.projectId;
  const collapsedList = state.collapsedCols[proj] || [];
  const expandedList = state.expandedCols[proj] || [];
  const wasCollapsed = isColEffectivelyCollapsed(colId, hasTasks);

  // remove colId from both lists (for cleanliness)
  const cIdx = collapsedList.indexOf(colId);
  if (cIdx >= 0) collapsedList.splice(cIdx, 1);
  const eIdx = expandedList.indexOf(colId);
  if (eIdx >= 0) expandedList.splice(eIdx, 1);

  // add to the opposite list
  if (wasCollapsed) expandedList.push(colId);
  else              collapsedList.push(colId);

  state.collapsedCols[proj] = collapsedList;
  state.expandedCols[proj]  = expandedList;
  saveCollapsed();

  const colEl = $(`.col[data-status="${colId}"]`);
  if (colEl) colEl.classList.toggle("is-collapsed");
}

// ----------------------------------------------------------- Quick-add

function openQuickAdd(status, colEl) {
  // If a quickadd-form already exists — focus it
  let form = colEl.querySelector(".col__quickadd-form");
  if (form) { form.querySelector("input").focus(); return; }
  form = document.createElement("div");
  form.className = "col__quickadd-form";
  form.innerHTML = `<input type="text" placeholder="${I18N[state.lang].quickAdd}" />`;
  const list = colEl.querySelector(".col__list");
  colEl.insertBefore(form, list);
  const input = form.querySelector("input");
  input.focus();
  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      const title = input.value.trim();
      if (!title) return;
      try {
        await api("POST", "/api/tasks", {
          title,
          status,
          priority: "normal",
          size: "M",
          project_id: state.projectId,
        });
        toast(state.lang === "ru" ? "Создано" : "Created");
        form.remove();
        await loadBoard();
        await loadProjects();
      } catch (err) {
        toast(`Error: ${err.message}`, "err");
      }
    } else if (e.key === "Escape") {
      form.remove();
    }
  });
  input.addEventListener("blur", () => {
    if (!input.value.trim()) form.remove();
  });
}

// ----------------------------------------------------------- Drag-drop

async function handleDrop(evt) {
  const taskId = evt.item.dataset.taskId;
  const toStatus = evt.to.dataset.status;
  // newDraggableIndex is among non-hidden; we pass newIndex relative to all elements
  const newOrder = evt.newDraggableIndex;
  try {
    await api("POST", `/api/tasks/${taskId}/move`, {
      to_status: toStatus,
      column_order: newOrder,
    });
    // loadBoard intentionally skips active drags. End the drag before
    // reloading so dependency groups are recalculated from server state.
    state.isDragging = false;
    toast(`${taskId} → ${statusTitle(toStatus)}`);
    await loadBoard();
    await loadProjects();
  } catch (e) {
    state.isDragging = false;
    toast(`Error: ${e.message}`, "err");
    await loadBoard();
  }
}

// ----------------------------------------------------------- Task modal

let modalBlockers = [];
let newTaskBlockers = [];
let currentTask = null;

function blockerCandidates(excludeId, selectedIds) {
  return Object.values(state.board.tasks)
    .flat()
    .filter(task => task.id !== excludeId)
    .filter(task => !selectedIds.includes(task.id))
    // A task is a valid dependency until it is cancelled or completed.
    .filter(task => task.status !== "done" && task.status !== "cancelled")
    .sort((a, b) => a.id.localeCompare(b.id));
}

function renderBlockerChips(prefix, selectedIds, excludeId, editable) {
  const chips = $(`#${prefix}-blocker-chips`);
  if (!chips) return;
  const allTasks = Object.values(state.board.tasks).flat();
  chips.innerHTML = "";
  for (const taskId of selectedIds) {
    const task = allTasks.find(item => item.id === taskId);
    const chip = document.createElement("span");
    chip.className = "blocker-chip";
    chip.textContent = task ? `${task.id} — ${task.title}` : taskId;
    if (editable) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.title = state.lang === "ru" ? "Убрать зависимость" : "Remove dependency";
      remove.addEventListener("click", () => {
        const target = prefix === "m" ? modalBlockers : newTaskBlockers;
        const index = target.indexOf(taskId);
        if (index >= 0) target.splice(index, 1);
        renderBlockerInput(prefix, target, excludeId);
      });
      chip.appendChild(remove);
    }
    chips.appendChild(chip);
  }
}

function renderBlockerInput(prefix, selectedIds, excludeId) {
  const input = $(`#${prefix}-blocker-query`);
  const menu = $(`#${prefix}-blocker-menu`);
  if (!input || !menu) return;
  // The menu is portalled to <body> so a scrollable modal cannot clip it.
  if (menu.parentElement !== document.body) document.body.appendChild(menu);
  renderBlockerChips(prefix, selectedIds, excludeId, true);
  const query = input.value.trim().toLowerCase();
  const matches = blockerCandidates(excludeId, selectedIds)
    .filter(task => !query || `${task.id} ${task.title}`.toLowerCase().includes(query));
  menu.innerHTML = "";
  for (const task of matches.slice(0, 8)) {
    const option = document.createElement("button");
    option.type = "button";
    option.textContent = `${task.id} — ${task.title}`;
    option.addEventListener("click", () => addBlocker(prefix, task.id, excludeId));
    menu.appendChild(option);
  }
  const visible = document.activeElement === input && matches.length > 0;
  menu.hidden = !visible;
  if (visible) requestAnimationFrame(() => positionBlockerMenu(prefix));
}

function positionBlockerMenu(prefix) {
  const input = $(`#${prefix}-blocker-query`);
  const menu = $(`#${prefix}-blocker-menu`);
  if (!input || !menu || menu.hidden) return;
  const rect = input.closest(".chips-input").getBoundingClientRect();
  const height = menu.offsetHeight;
  const above = rect.top - height - 8;
  const top = above >= 8 ? above : rect.bottom + 8;
  menu.style.left = `${rect.left}px`;
  menu.style.top = `${top}px`;
  menu.style.width = `${rect.width}px`;
}

function addBlocker(prefix, taskId, excludeId) {
  const target = prefix === "m" ? modalBlockers : newTaskBlockers;
  if (!target.includes(taskId)) target.push(taskId);
  const input = $(`#${prefix}-blocker-query`);
  if (input) input.value = "";
  renderBlockerInput(prefix, target, excludeId);
  input?.focus();
}

function setupBlockerInput(prefix, getExcludeId) {
  const input = $(`#${prefix}-blocker-query`);
  const root = $(`#${prefix}-blockers-input`);
  if (!input || !root) return;
  const redraw = () => renderBlockerInput(prefix, prefix === "m" ? modalBlockers : newTaskBlockers, getExcludeId());
  input.addEventListener("input", redraw);
  input.addEventListener("focus", redraw);
  input.addEventListener("keydown", event => {
    if (event.key === "Backspace" && !input.value) {
      const target = prefix === "m" ? modalBlockers : newTaskBlockers;
      target.pop(); redraw();
    }
    if (event.key === "Enter") {
      const first = blockerCandidates(getExcludeId(), prefix === "m" ? modalBlockers : newTaskBlockers)
        .find(task => `${task.id} ${task.title}`.toLowerCase().includes(input.value.trim().toLowerCase()));
      if (first) { event.preventDefault(); addBlocker(prefix, first.id, getExcludeId()); }
    }
  });
  document.addEventListener("click", event => {
    const menu = $(`#${prefix}-blocker-menu`);
    if (!root.contains(event.target) && !menu.contains(event.target)) menu.hidden = true;
  });
}

async function openTaskModal(taskId) {
  let t;
  try {
    t = await api("GET", `/api/tasks/${taskId}`);
  } catch (e) {
    toast(`Failed to load ${taskId}`, "err");
    return;
  }
  currentTask = t;
  $("#modal").dataset.taskId = t.id;
  $("#m-id").textContent = t.id;
  $("#m-direct-badge").hidden = !Boolean(t.skip_planning);
  $("#m-edit-id").textContent = t.id;
  $("#m-title-view").textContent = t.title || "—";
  $("#m-description-view").textContent = t.description || (state.lang === "ru" ? "Описание не добавлено." : "No description.");
  $("#m-acceptance-view").textContent = t.acceptance || "";
  $("#m-acceptance-section").hidden = !t.acceptance;
  $("#m-branch-view").textContent = t.branch ? `${state.lang === "ru" ? "Ветка:" : "Branch:"} ${t.branch}` : (state.lang === "ru" ? "Не в работе" : "Not in progress");
  const moveSelect = $("#m-move-status");
  moveSelect.innerHTML = "";
  for (const column of state.board.columns) {
    const option = document.createElement("option");
    option.value = column.id;
    option.textContent = statusTitle(column.id);
    option.selected = column.id === t.status;
    moveSelect.appendChild(option);
  }
  $("#m-title").value = t.title || "";
  $("#m-description").value = t.description || "";
  $("#m-acceptance").value = t.acceptance || "";
  $("#m-skip-planning").checked = Boolean(t.skip_planning);
  modalBlockers = [...(t.blockers || [])];
  renderBlockerChips("m", modalBlockers, t.id, false);
  $("#m-dependencies-section").hidden = modalBlockers.length === 0;
  renderHistory(t.history);
  $("#m-comment").value = "";
  setTaskEditMode(false);
  $("#modal").hidden = false;
}

function setTaskEditMode(editing) {
  if (editing && currentTask) {
    $("#modal").hidden = true;
    $("#task-edit-modal").hidden = false;
    renderBlockerInput("m", modalBlockers, currentTask.id);
    $("#m-title").focus();
  } else {
    $("#task-edit-modal").hidden = true;
    if (currentTask) $("#modal").hidden = false;
  }
}

function renderLinks(links) {
  const el = $("#m-links");
  el.innerHTML = "";
  for (const l of (links || [])) {
    const a = document.createElement("a");
    if (l.type === "url" || l.type === "pr") a.href = l.value;
    a.target = "_blank";
    a.rel = "noopener";
    a.innerHTML = `<span class="link-type">${l.type}</span>${escapeHTML(l.value)}`;
    el.appendChild(a);
  }
}

function renderHistory(history) {
  const el = $("#m-history");
  const title = $("#m-discussion-title");
  const comments = (history || []).filter(item => item.action === "comment");
  el.innerHTML = "";
  title.hidden = comments.length === 0;
  for (const h of comments) {
    const row = document.createElement("div");
    row.className = "comment-message";
    if (h.actor !== "user") row.classList.add("is-agent");
    const ts = h.ts.slice(5, 16).replace("T", " ");
    const displayActor = actorLabel(h.actor);
    const avatar = displayActor.slice(0, 1).toUpperCase();
    const directMark = h.skip_planning ? `<span class="comment-message__direct" title="${escapeHTML(I18N[state.lang].commentDirect)}">✓</span>` : "";
    row.innerHTML = `
      <div class="comment-message__avatar">${escapeHTML(avatar)}</div>
      <div class="comment-message__content"><div class="comment-message__meta">${escapeHTML(displayActor)} · ${ts}${directMark}<span class="comment-message__actions"><button type="button">${state.lang === "ru" ? "Изменить" : "Edit"}</button><button type="button">${state.lang === "ru" ? "Удалить" : "Delete"}</button></span></div><div class="comment-message__body markdown">${renderMarkdown(h.comment)}</div></div>
    `;
    const [editButton, deleteButton] = $$(".comment-message__actions button", row);
    editButton.addEventListener("click", () => editComment(h, row));
    deleteButton.addEventListener("click", () => deleteComment(h.id));
    el.appendChild(row);
  }
}

async function refreshDiscussion() {
  if (!currentTask) return;
  const task = await api("GET", `/api/tasks/${currentTask.id}`);
  currentTask = task;
  renderHistory(task.history);
}

function editComment(comment, message) {
  const row = $(".comment-message__body", message);
  if (!row) return;
  const textarea = document.createElement("textarea");
  textarea.className = "comment-edit-input";
  textarea.value = comment.comment || "";
  row.replaceWith(textarea);
  textarea.focus();
  const content = textarea.parentElement;
  const actions = document.createElement("div");
  actions.className = "comment-edit-actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = state.lang === "ru" ? "Отмена" : "Cancel";
  cancel.addEventListener("click", refreshDiscussion);
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn btn--primary";
  save.textContent = state.lang === "ru" ? "Сохранить" : "Save";
  save.addEventListener("click", async () => {
    const text = textarea.value.trim();
    if (!text) return;
    try {
      await api("PATCH", `/api/tasks/${currentTask.id}/comments/${comment.id}`, { text });
      await refreshDiscussion();
    } catch (error) { toast(`Error: ${error.message}`, "err"); }
  });
  content.appendChild(actions);
  actions.append(cancel, save);
}

async function deleteComment(historyId) {
  const question = state.lang === "ru" ? "Удалить этот комментарий?" : "Delete this comment?";
  if (!window.confirm(question)) return;
  try {
    await api("DELETE", `/api/tasks/${currentTask.id}/comments/${historyId}`);
    await refreshDiscussion();
  } catch (error) { toast(`Error: ${error.message}`, "err"); }
}

function closeModal() {
  $("#modal").hidden = true;
  $("#task-edit-modal").hidden = true;
  delete $("#modal").dataset.taskId;
  currentTask = null;
}

async function saveModal() {
  const taskId = $("#modal").dataset.taskId;
  if (!taskId) return;
  // Typed text is only a search query; only chosen card IDs may be persisted.
  $("#m-blocker-query").value = "";
  const knownIds = new Set(Object.values(state.board.tasks).flat().map(task => task.id));
  modalBlockers = modalBlockers.filter(taskId => knownIds.has(taskId));
  const payload = {
    title: $("#m-title").value.trim(),
    description: $("#m-description").value,
    acceptance: $("#m-acceptance").value,
    skip_planning: $("#m-skip-planning").checked,
  };
  try {
    await api("PATCH", `/api/tasks/${taskId}`, payload);
    await api("POST", `/api/tasks/${taskId}/blockers`, { blocker_ids: modalBlockers });
    toast(state.lang === "ru" ? "Изменения сохранены" : "Changes saved");
    await openTaskModal(taskId);
    await loadBoard();
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

async function moveTaskFromModal() {
  const taskId = currentTask?.id;
  const toStatus = $("#m-move-status").value;
  if (!taskId || toStatus === currentTask.status) return;
  try {
    await api("POST", `/api/tasks/${taskId}/move`, { to_status: toStatus });
    await loadBoard();
    await openTaskModal(taskId);
    toast(`${taskId} → ${statusTitle(toStatus)}`);
  } catch (error) {
    toast(`Error: ${error.message}`, "err");
    $("#m-move-status").value = currentTask.status;
  }
}

async function prepareWorkspace() {
  const taskId = $("#modal").dataset.taskId;
  if (!taskId) return;
  try {
    const result = await api("POST", `/api/tasks/${taskId}/workspace`, {});
    $("#m-workspace").value = `${result.branch} — ${result.worktree_path}`;
    toast(`Workspace prepared: ${result.branch}`);
    await loadBoard();
  } catch (e) { toast(`Error: ${e.message}`, "err"); }
}

async function addLink() {
  const taskId = $("#modal").dataset.taskId;
  if (!taskId) return;
  const type = $("#m-link-type").value;
  const value = $("#m-link-value").value.trim();
  if (!value) return;
  try {
    await api("POST", `/api/tasks/${taskId}/links`, { type, value });
    $("#m-link-value").value = "";
    const t = await api("GET", `/api/tasks/${taskId}`);
    renderLinks(t.links);
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

async function addComment() {
  const taskId = $("#modal").dataset.taskId;
  if (!taskId) return;
  const text = $("#m-comment").value.trim();
  if (!text) return;
  try {
    const skipPlanning = Boolean($("#m-comment-direct")?.checked);
    await api("POST", `/api/tasks/${taskId}/comment`, { text, skip_planning: skipPlanning });
    $("#m-comment").value = "";
    if ($("#m-comment-direct")) $("#m-comment-direct").checked = false;
    const t = await api("GET", `/api/tasks/${taskId}`);
    currentTask = t;
    renderHistory(t.history);
    const statusSelect = $("#m-move-status");
    if (statusSelect) statusSelect.value = t.status;
    loadBoard();
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

// ----------------------------------------------------------- New task

function openNewModal() {
  $("#n-title").value = "";
  $("#n-description").value = "";
  $("#n-acceptance").value = "";
  $("#n-skip-planning").checked = false;
  $("#n-status").value = "backlog";
  newTaskBlockers = [];
  renderBlockerInput("n", newTaskBlockers, null);
  $("#n-proj-chip").textContent = state.project ? state.project.name : state.projectId;
  $("#new-modal").hidden = false;
  $("#n-title").focus();
}

function closeNewModal() {
  $("#new-modal").hidden = true;
}

async function createTask() {
  const title = $("#n-title").value.trim();
  if (!title) {
    toast("Title is required", "err");
    return;
  }
  const payload = {
    title,
    description: $("#n-description").value,
    acceptance: $("#n-acceptance").value,
    skip_planning: $("#n-skip-planning").checked,
    status: $("#n-status").value,
    project_id: state.projectId,
  };
  try {
    const t = await api("POST", `/api/tasks`, payload);
    // The query input is never a dependency. Persist only explicitly selected cards.
    $("#n-blocker-query").value = "";
    const knownIds = new Set(Object.values(state.board.tasks).flat().map(task => task.id));
    newTaskBlockers = newTaskBlockers.filter(taskId => knownIds.has(taskId));
    if (newTaskBlockers.length > 0) {
      await api("POST", `/api/tasks/${t.id}/blockers`, { blocker_ids: newTaskBlockers });
    }
    toast(`${t.id} created`);
    closeNewModal();
    await loadBoard();
    await loadProjects();
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

// ----------------------------------------------------------- Project modal (create + edit)

// editingProjId — null when creating a new project, otherwise id of the project being edited.
let editingProjId = null;
// activeSourceTab — which task-source tab is selected in the wizard ('new'|'local'|'git').
let activeSourceTab = "new";
// selectedPlanFiles — Set of plan-file paths selected in the current wizard session.
let selectedPlanFiles = new Set();

function resetSourceWizard() {
  activeSourceTab = "new";
  $$(".source-tab").forEach(t =>
    t.classList.toggle("is-active", t.dataset.source === "new")
  );
  $$(".source-pane").forEach(p =>
    p.hidden = p.dataset.pane !== "new"
  );
  selectedPlanFiles = new Set();
  $("#src-git-url").value = "";
  $("#src-git-token").value = "";
  $("#source-current").hidden = true;
  $("#source-current-text").textContent = "—";
}

function selectSourceTab(name) {
  activeSourceTab = name;
  $$(".source-tab").forEach(t =>
    t.classList.toggle("is-active", t.dataset.source === name)
  );
  $$(".source-pane").forEach(p =>
    p.hidden = p.dataset.pane !== name
  );
  if (name === "local") loadPlanCandidates();
}

// ----- Plan candidates list -----

function _humanSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function _humanTime(ts) {
  const now = Date.now() / 1000;
  const diff = now - ts;
  if (diff < 60)        return "just now";
  if (diff < 3600)      return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400)     return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

async function loadPlanCandidates() {
  const box = $("#src-candidates");
  const path = $("#p-path").value.trim();
  if (!path) {
    box.innerHTML = `
      <div class="src-candidates__empty">
        ${I18N[state.lang].sourceNoPath}<br>
        <button type="button" class="btn btn--ghost" data-action="pick-folder" style="margin-top:8px;">${I18N[state.lang].specifyDirectory}</button>
      </div>`;
    return;
  }
  box.innerHTML = `<div class="src-candidates__empty">${I18N[state.lang].scanning}</div>`;
  try {
    // Always use path from input — in edit mode the user may have just
    // picked a new path via the picker, and it isn't saved to the DB yet.
    const r = await api("GET", `/api/system/list-md-files?path=${encodeURIComponent(path)}`);
    if (!r.items || r.items.length === 0) {
      box.innerHTML = `<div class="src-candidates__empty">${I18N[state.lang].noMarkdown}</div>`;
      $("#src-local-file").value = "";
      return;
    }
    renderCandidates(r.items);
  } catch (e) {
    box.innerHTML = `<div class="src-candidates__empty">Error: ${escapeHTML(e.message)}</div>`;
  }
}

function renderCandidates(items) {
  const box = $("#src-candidates");
  box.innerHTML = "";
  // Auto-select all plan-files (prio ≤ 5: PLAN/BACKLOG/TASKS/TODO/ROADMAP).
  // CLAUDE.md/README.md/etc. are prio 7+, left unchecked.
  selectedPlanFiles = new Set(
    items.filter(it => it.prio <= 5).map(it => it.file)
  );
  // If none qualify (all low-priority) — check the first so the wizard isn't empty.
  if (selectedPlanFiles.size === 0 && items.length > 0) {
    selectedPlanFiles.add(items[0].file);
  }
  for (const it of items) {
    box.appendChild(_candidateEl(it));
  }
  _updateCandidatesCounter();
}

function _candidateEl(it) {
  const sel = selectedPlanFiles.has(it.file);
  const el = document.createElement("div");
  el.className = "src-candidate";
  if (sel) el.classList.add("is-selected");
  el.dataset.file = it.file;
  el.innerHTML = `
    <span class="src-candidate__check">${sel ? "☑" : "☐"}</span>
    <span class="src-candidate__name">${escapeHTML(it.file)}</span>
    <span class="src-candidate__meta">${_humanSize(it.size)} · ${_humanTime(it.modified)}</span>
  `;
  el.addEventListener("click", () => toggleCandidate(it.file));
  return el;
}

function toggleCandidate(file) {
  if (selectedPlanFiles.has(file)) selectedPlanFiles.delete(file);
  else selectedPlanFiles.add(file);
  const el = $(`.src-candidate[data-file="${CSS.escape(file)}"]`);
  if (el) {
    const sel = selectedPlanFiles.has(file);
    el.classList.toggle("is-selected", sel);
    const check = el.querySelector(".src-candidate__check");
    if (check) check.textContent = sel ? "☑" : "☐";
  }
  _updateCandidatesCounter();
}

function _updateCandidatesCounter() {
  const counter = $("#src-candidates-counter");
  if (counter) counter.textContent = `${I18N[state.lang].selected}: ${selectedPlanFiles.size}`;
}


async function showCurrentSource(projectId) {
  // Fetch the project's current source (if any). 404 = none.
  try {
    const src = await api("GET", `/api/projects/${projectId}/source`);
    let label;
    if (src.type === "plan_md") {
      const files = src.config.files || (src.config.file ? [src.config.file] : []);
      label = files.length > 0
        ? `Plan files (${files.length}): ${files.join(", ")}`
        : `Plan: ${JSON.stringify(src.config)}`;
    } else if (src.type === "git") {
      label = `Git: ${src.config.repo_url}`;
    } else {
      label = `${src.type}: ${JSON.stringify(src.config)}`;
    }
    if (src.last_sync_at) label += ` · sync: ${src.last_sync_at.slice(5,16).replace("T"," ")}`;
    $("#source-current").hidden = false;
    $("#source-current-text").textContent = label;
  } catch (e) {
    $("#source-current").hidden = true;
  }
}

function openNewProj() {
  editingProjId = null;
  $("#proj-modal-title").textContent = I18N[state.lang].newProjectTitle;
  $("#btn-create-proj").textContent = I18N[state.lang].create;
  $("#btn-archive-proj").hidden = true;
  $("#btn-delete-proj").hidden = true;
  $("#p-name").value = "";
  $("#p-id").value = "";
  $("#p-id").disabled = false;
  $("#p-path").value = "";
  $("#p-branch-template").value = "kanban/{task_id}-{slug}";
  $("#p-agent-rules").value = "";
  $$(".swatch").forEach(s => s.classList.toggle("is-active", s.dataset.color === "#F10D30"));
  resetSourceWizard();
  $("#proj-modal").hidden = false;
  $("#p-name").focus();
}

function openEditProj(p) {
  editingProjId = p.id;
  $("#proj-modal-title").textContent = `${I18N[state.lang].projectPrefix} ${p.name}`;
  $("#btn-create-proj").textContent = I18N[state.lang].save;
  const russian = state.lang === "ru";
  const archiveButton = $("#btn-archive-proj");
  archiveButton.hidden = false;
  archiveButton.textContent = p.archived
    ? (russian ? "Восстановить" : "Restore")
    : (russian ? "Архивировать" : "Archive");
  const deleteButton = $("#btn-delete-proj");
  deleteButton.hidden = !p.archived;
  deleteButton.textContent = russian ? "Удалить навсегда" : "Delete permanently";
  $("#p-name").value = p.name;
  $("#p-id").value = p.id;
  $("#p-id").disabled = true;     // id is immutable (FK on tasks)
  $("#p-path").value = p.path || "";
  $("#p-branch-template").value = p.branch_template || "kanban/{task_id}-{slug}";
  $("#p-agent-rules").value = p.agent_rules || "";
  $$(".swatch").forEach(s => s.classList.toggle("is-active", s.dataset.color === p.color));
  resetSourceWizard();
  showCurrentSource(p.id);
  $("#proj-modal").hidden = false;
  $("#p-name").focus();
}

function closeNewProj() {
  $("#proj-modal").hidden = true;
  editingProjId = null;
}

async function archiveProject() {
  if (!editingProjId) return;
  const project = state.projects.find(p => p.id === editingProjId);
  if (!project) return;
  const archived = !project.archived;
  const russian = state.lang === "ru";
  const action = archived ? "archive" : "restore";
  const question = russian
    ? `Вы хотите ${archived ? "архивировать" : "восстановить"} проект «${project.name}»?`
    : `Do you want to ${action} project “${project.name}”?`;
  if (!window.confirm(question)) return;
  try {
    await api("POST", `/api/projects/${project.id}/archive`, { archived });
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
    return;
  }
  closeNewProj();
  await loadProjects();
  if (archived && state.projectId === project.id) {
    const fallback = state.projects.find(p => !p.archived);
    if (fallback) navigateTo(fallback.id, { replace: true });
  }
  await loadBoard();
  toast(russian
    ? (archived ? `Проект ${project.name} архивирован` : `Проект ${project.name} восстановлен`)
    : (archived ? `Project ${project.name} archived` : `Project ${project.name} restored`));
}

async function deleteProject() {
  if (!editingProjId) return;
  const project = state.projects.find(p => p.id === editingProjId);
  if (!project || !project.archived) return;
  const russian = state.lang === "ru";
  const promptText = russian
    ? `Удалить проект «${project.name}» и все его карточки навсегда?\n\nВведите ID проекта ${project.id} для подтверждения.\nВетки и worktree Git останутся.`
    : `Permanently delete “${project.name}” and all its cards?\n\nEnter project ID ${project.id} to confirm.\nGit branches and worktrees will remain.`;
  const entered = window.prompt(promptText);
  if (entered !== project.id) return;
  try {
    await api("DELETE", `/api/projects/${project.id}`, { confirm: true });
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
    return;
  }
  const wasCurrent = state.projectId === project.id;
  closeNewProj();
  await loadProjects();
  if (wasCurrent) {
    const fallback = state.projects.find(p => !p.archived);
    if (fallback) navigateTo(fallback.id, { replace: true });
  }
  await loadBoard();
  toast(russian ? `Проект ${project.name} удалён навсегда` : `Project ${project.name} permanently deleted`);
}

async function saveProj() {
  const name = $("#p-name").value.trim();
  const id = $("#p-id").value.trim();
  const path = $("#p-path").value.trim();
  const branch_template = $("#p-branch-template").value.trim();
  const agent_rules = $("#p-agent-rules").value;
  const colorEl = $(".swatch.is-active");
  const color = colorEl ? colorEl.dataset.color : "#F10D30";
  // The icon is auto-generated from the first letter of the name; the
  // backend does the same when icon is empty (see Store.create_project).
  const icon = "";
  if (!name) { toast("Name is required", "err"); return; }

  // Pre-validation: types new/local require a path. Otherwise the wizard does
  // nothing and the user ends up with an empty board (as happened with Aizav2).
  if ((activeSourceTab === "new" || activeSourceTab === "local") && !path) {
    toast("First specify the project directory (field \"Project directory\")", "err");
    $("#p-path").focus();
    $("#p-path").classList.add("field--error");
    setTimeout(() => $("#p-path").classList.remove("field--error"), 2000);
    return;
  }
  if (activeSourceTab === "local") {
    if (selectedPlanFiles.size === 0) {
      toast("Tick at least one plan file", "err");
      return;
    }
  }
  if (activeSourceTab === "git") {
    const url = $("#src-git-url").value.trim();
    if (!url) {
      toast("Enter the repository URL (or switch to another source)", "err");
      $("#src-git-url").focus();
      return;
    }
  }

  // Save base project (create or edit)
  let savedId = editingProjId;
  if (editingProjId) {
    try {
      await api("PATCH", `/api/projects/${editingProjId}`, { name, color, icon, path, branch_template, agent_rules });
    } catch (e) {
      toast(`Error: ${e.message}`, "err");
      return;
    }
  } else {
    if (!id) { toast("ID is required", "err"); return; }
    if (!/^[a-z][a-z0-9-]{1,31}$/.test(id)) {
      toast("ID: latin lowercase, 2-32 characters", "err");
      return;
    }
    try {
      await api("POST", "/api/projects", { id, name, color, icon, path, branch_template, agent_rules });
      savedId = id;
    } catch (e) {
      toast(`Error: ${e.message}`, "err");
      return;
    }
  }

  // Setup source
  const sourceResult = await applySourceWizard(savedId, path);

  toast(editingProjId ? `Project ${name} saved${sourceResult ? " · " + sourceResult : ""}` : `Project ${name} created${sourceResult ? " · " + sourceResult : ""}`);
  closeNewProj();
  await loadProjects();
  if (!editingProjId) navigateTo(savedId);
  await loadBoard();
  renderSidebar();
}

// Apply the source-wizard outcome for `projectId`. Returns a short
// description for the toast, or null if nothing was done.
async function applySourceWizard(projectId, path) {
  const tab = activeSourceTab;
  // Types new/local need a path. Git does not.
  if ((tab === "new" || tab === "local") && !path) {
    return null;          // user did not specify a directory — skip setup
  }
  try {
    if (tab === "new") {
      const r = await api("POST", `/api/projects/${projectId}/source/plan-new`);
      return `created ${r.plan_md.split("/").pop()}`;
    }
    if (tab === "local") {
      const files = Array.from(selectedPlanFiles);
      if (files.length === 0) return null;
      const r = await api("POST", `/api/projects/${projectId}/source/plan-local`, { files });
      const c = r.imported || {};
      return `imported from ${files.length} file(s): ${c.created || 0} created, ${c.skipped || 0} skipped`;
    }
    if (tab === "git") {
      const repo_url = $("#src-git-url").value.trim();
      const token = $("#src-git-token").value;
      if (!repo_url) return null;
      await api("POST", `/api/projects/${projectId}/source/git`, { repo_url, token });
      return token ? "git connected · token saved" : "git connected";
    }
  } catch (e) {
    toast(`Task source: ${e.message}`, "err");
  }
  return null;
}

// Open the native folder picker (macOS Finder / Linux zenity / Windows FBD).
async function pickFolder() {
  const btn = $("#btn-pick-folder");
  if (btn) {
    btn.disabled = true;
    btn.dataset.oldText = btn.textContent;
    btn.textContent = I18N[state.lang].opening;
  }
  try {
    const r = await api("POST", "/api/system/pick-folder");
    if (r.cancelled) return;
    if (r.path) {
      $("#p-path").value = r.path;
      $("#p-path").classList.remove("field--error");
      // If local is active — reload candidates with the new path.
      if (activeSourceTab === "local") loadPlanCandidates();
    }
  } catch (e) {
    if (String(e.message).includes("HTTP 501")) {
      toast(I18N[state.lang].pickerUnavailable, "err");
    } else {
      toast(`Picker: ${e.message}`, "err");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = btn.dataset.oldText || I18N[state.lang].choose;
    }
  }
}

// Auto-fill id from name (only in create mode)
function autoFillProjId() {
  if (editingProjId) return;
  const idInput = $("#p-id");
  if (idInput.value) return;
  const slug = $("#p-name").value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
  if (slug && /^[a-z]/.test(slug)) idInput.value = slug;
}

// ----------------------------------------------------------- Snapshot

async function snapshot() {
  try {
    const r = await api("POST", `/api/snapshot`);
    toast(`Snapshot → ${r.path.split("/").pop()}`);
  } catch (e) {
    toast(`Error: ${e.message}`, "err");
  }
}

// ----------------------------------------------------------- Density

function toggleDensity() {
  state.density = state.density === "compact" ? "comfortable" : "compact";
  localStorage.setItem(LS.DENSITY, state.density);
  $("#board").classList.toggle("is-compact", state.density === "compact");
}

// ----------------------------------------------------------- Sidebar toggle

function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  localStorage.setItem(LS.SIDEBAR, state.sidebarCollapsed ? "collapsed" : "open");
  $("#sidebar").classList.toggle("is-collapsed", state.sidebarCollapsed);
}

// ----------------------------------------------------------- Theme

function toggleTheme() {
  state.theme = state.theme === "light" ? "dark" : "light";
  localStorage.setItem(LS.THEME, state.theme);
  document.documentElement.setAttribute("data-theme", state.theme);
}

// ----------------------------------------------------------- Claude auth indicator

async function refreshClaudeAuth() {
  const btn = $("#btn-claude-auth");
  if (!btn) return;
  try {
    const r = await api("GET", "/api/system/claude-auth-status");
    btn.classList.remove("claude-auth--ok", "claude-auth--no", "claude-auth--unknown", "is-busy");
    if (!r.available) {
      btn.classList.add("claude-auth--no");
      btn.title = "Claude CLI not found — install Claude Code";
    } else if (r.loggedIn) {
      btn.classList.add("claude-auth--ok");
      btn.title = `Claude CLI: signed in (${r.authMethod || "ok"})`;
    } else {
      btn.classList.add("claude-auth--no");
      btn.title = "Claude CLI: NOT signed in — click to log in";
    }
  } catch (e) {
    btn.classList.remove("claude-auth--ok", "claude-auth--unknown");
    btn.classList.add("claude-auth--no");
    btn.title = `Status check failed: ${e.message}`;
  }
}

async function clickClaudeAuth() {
  const btn = $("#btn-claude-auth");
  if (!btn) return;
  // If already signed in — click does nothing (just a status toast).
  if (btn.classList.contains("claude-auth--ok")) {
    toast("Claude CLI is signed in");
    return;
  }
  btn.classList.add("is-busy");
  try {
    const r = await api("POST", "/api/system/claude-auth-login");
    toast(`Browser login launched (pid ${r.pid}). Finish OAuth and wait ~10 s.`);
    // Re-poll after 10/30/60 s.
    [10, 25, 60].forEach(sec => setTimeout(refreshClaudeAuth, sec * 1000));
  } catch (e) {
    toast(`Auth login: ${e.message}`, "err");
    btn.classList.remove("is-busy");
  }
}

// ----------------------------------------------------------- Profile

function toggleProfile() {
  const cur = document.documentElement.getAttribute("data-profile") || "standard";
  const idx = PROFILES.indexOf(cur);
  const next = PROFILES[(idx + 1) % PROFILES.length];
  document.documentElement.setAttribute("data-profile", next);
  localStorage.setItem(LS.PROFILE, next);
  toast(`Profile: ${PROFILE_LABELS[next]}`);
}

// ----------------------------------------------------------- Loaders

async function loadProjects() {
  try {
    const r = await api("GET", "/api/projects?include_archived=true");
    state.projects = r.projects;
    renderSidebar();
  } catch (e) {
    toast(`Failed to load projects: ${e.message}`, "err");
  }
}

async function loadBoard() {
  if (!state.projectId) return;
  if (state.isDragging) return;
  if ($("#modal").hidden === false || $("#task-edit-modal").hidden === false) return;
  if ($("#new-modal").hidden === false) return;
  if ($("#proj-modal").hidden === false) return;
  try {
    const board = await api("GET", `/api/board?project=${encodeURIComponent(state.projectId)}`);
    render(board);
  } catch (e) {
    if (String(e.message).includes("HTTP 404")) {
      // Project not found — fall back to the first available
      const fallback = state.projects.find(p => !p.archived);
      if (fallback && fallback.id !== state.projectId) {
        navigateTo(fallback.id, { replace: true });
        await loadBoard();
      } else {
        toast("No projects available", "err");
      }
    } else {
      toast(`Network: ${e.message}`, "err");
    }
  }
}

// ----------------------------------------------------------- Search

let searchDebounce = null;
function onSearchInput(e) {
  const v = e.target.value;
  $("#btn-search-clear").hidden = !v;
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    state.search = v.trim();
    applyFilters();
  }, 120);
}

function clearSearch() {
  $("#search").value = "";
  $("#btn-search-clear").hidden = true;
  state.search = "";
  applyFilters();
}

// ----------------------------------------------------------- Filter chips

function toggleFilter(filter) {
  if (state.filters.has(filter)) state.filters.delete(filter);
  else state.filters.add(filter);
  $$(`#filters .filter-chip`).forEach(b => {
    b.classList.toggle("is-on", state.filters.has(b.dataset.filter));
  });
  applyFilters();
}

// ----------------------------------------------------------- Middle-click pan

function initMiddleClickPan() {
  const board = $("#board");
  if (!board) return;
  let panning = false;
  let startX = 0;
  let startScrollLeft = 0;

  board.addEventListener("mousedown", (e) => {
    if (e.button !== 1) return;     // middle button only
    e.preventDefault();             // suppress the native autoscroll cursor
    panning = true;
    startX = e.clientX;
    startScrollLeft = board.scrollLeft;
    document.body.style.cursor = "grabbing";
    board.style.cursor = "grabbing";
  });

  document.addEventListener("mousemove", (e) => {
    if (!panning) return;
    e.preventDefault();
    const dx = e.clientX - startX;
    board.scrollLeft = startScrollLeft - dx;
  });

  const stop = () => {
    if (!panning) return;
    panning = false;
    document.body.style.cursor = "";
    board.style.cursor = "";
  };
  document.addEventListener("mouseup", (e) => {
    if (e.button === 1) stop();
  });
  // Release if the window loses focus
  window.addEventListener("blur", stop);
}

// ----------------------------------------------------------- Init

document.addEventListener("DOMContentLoaded", async () => {
  state.projectId = parseRoute();

  // Modal close handlers
  $$("[data-close]").forEach((el) => el.addEventListener("click", closeModal));
  $$("[data-close-edit]").forEach((el) => el.addEventListener("click", () => setTaskEditMode(false)));
  $$("[data-close-new]").forEach((el) => el.addEventListener("click", closeNewModal));
  $$("[data-close-proj]").forEach((el) => el.addEventListener("click", closeNewProj));

  // Buttons
  $("#btn-save").addEventListener("click", saveModal);
  $("#btn-add-comment").addEventListener("click", addComment);
  $("#m-comment").addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      addComment();
    }
  });
  $("#btn-edit-task").addEventListener("click", () => setTaskEditMode(true));
  $("#m-title-view").addEventListener("click", () => setTaskEditMode(true));
  $("#btn-cancel-edit").addEventListener("click", () => setTaskEditMode(false));
  $("#m-move-status").addEventListener("change", moveTaskFromModal);
  setupBlockerInput("m", () => currentTask?.id || null);
  setupBlockerInput("n", () => null);
  $("#btn-new").addEventListener("click", openNewModal);
  $("#btn-create").addEventListener("click", createTask);
  $("#btn-refresh").addEventListener("click", () => { loadBoard(); loadProjects(); });
  $("#btn-snapshot").addEventListener("click", snapshot);
  $("#btn-density").addEventListener("click", toggleDensity);
  $("#btn-theme").addEventListener("click", toggleTheme);
  $("#btn-profile").addEventListener("click", toggleProfile);
  $("#btn-language").addEventListener("click", toggleLanguage);
  $("#btn-claude-auth").addEventListener("click", clickClaudeAuth);
  $("#btn-sidebar").addEventListener("click", toggleSidebar);
  applyLocale();
  // Initial claude auth state + periodic refresh every 60 s
  refreshClaudeAuth();
  setInterval(refreshClaudeAuth, 60000);
  $("#btn-new-proj").addEventListener("click", openNewProj);
  $("#btn-create-proj").addEventListener("click", saveProj);
  $("#btn-archive-proj").addEventListener("click", archiveProject);
  $("#btn-delete-proj").addEventListener("click", deleteProject);
  // Source-wizard tabs
  $$(".source-tab").forEach(t =>
    t.addEventListener("click", () => selectSourceTab(t.dataset.source))
  );
  // On path change — refetch candidates (if local mode is active)
  $("#p-path").addEventListener("change", () => {
    if (activeSourceTab === "local") loadPlanCandidates();
  });

  // Delegated click handler for [data-action="..."] — works for
  // dynamically inserted buttons (inline in src-candidates__empty)
  // and across pane re-renders.
  document.body.addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;
    const action = target.dataset.action;
    console.log("[kanban] action:", action);   // diagnostic
    if (action === "pick-folder") {
      e.preventDefault();
      pickFolder();
    } else if (action === "refresh-candidates") {
      e.preventDefault();
      loadPlanCandidates();
    }
  });

  // Project name → auto-slug
  $("#p-name").addEventListener("input", autoFillProjId);

  // Color palette
  $$(".swatch").forEach(s => s.addEventListener("click", () => {
    $$(".swatch").forEach(x => x.classList.remove("is-active"));
    s.classList.add("is-active");
  }));

  // Archive section toggle
  $("#btn-archive-toggle").addEventListener("click", () => {
    const box = $("#proj-archive");
    const list = $("#proj-archive-list");
    const open = !box.classList.contains("is-open");
    box.classList.toggle("is-open", open);
    list.hidden = !open;
    localStorage.setItem(LS.ARCHIVE_OPEN, open ? "1" : "0");
  });

  // Search
  $("#search").addEventListener("input", onSearchInput);
  $("#btn-search-clear").addEventListener("click", clearSearch);

  // Filter chips
  $$("#filters .filter-chip").forEach(b => {
    b.addEventListener("click", () => toggleFilter(b.dataset.filter));
  });

  // Keyboard
  document.addEventListener("keydown", (e) => {
    // skip if typing in input/textarea
    const tag = (e.target.tagName || "").toLowerCase();
    const inField = tag === "input" || tag === "textarea" || tag === "select";
    if (e.key === "Escape") {
      closeModal();
      closeNewModal();
      closeNewProj();
      if (state.search) clearSearch();
      return;
    }
    if (inField) return;
    if (e.key === "/" || e.key === "?") {
      e.preventDefault();
      $("#search").focus();
    } else if (e.key === "n") {
      e.preventDefault();
      openNewModal();
    } else if (e.key === "d") {
      toggleDensity();
    } else if (e.key === "t") {
      toggleTheme();
    } else if (e.key === "p") {
      toggleProfile();
    } else if (e.key === "\\") {
      toggleSidebar();
    } else if (e.key === "r") {
      loadBoard();
    }
  });

  // Middle-click panning: hold the wheel on the board and drag left/right.
  // Does not conflict with SortableJS drag-drop (which reacts to left-click).
  initMiddleClickPan();

  // Browser back/forward
  window.addEventListener("popstate", () => {
    const next = parseRoute();
    if (next) {
      state.projectId = next;
      loadBoard();
      renderSidebar();
    }
  });

  // Initial load: projects first, then select + board
  await loadProjects();
  if (!state.projectId && state.projects.length > 0) {
    // URL without /p/X — priority:
    // 1) last opened from localStorage (if it still exists and isn't archived)
    // 2) first active project
    const last = localStorage.getItem(LS.LAST_PROJECT);
    const lastP = last && state.projects.find(p => p.id === last && !p.archived);
    const first = lastP || state.projects.find(p => !p.archived) || state.projects[0];
    state.projectId = first.id;
    navigateTo(state.projectId, { replace: true });
  }
  if (state.projectId) {
    await loadBoard();
    renderSidebar();
  }

  // Polling
  setInterval(() => { loadBoard(); loadProjects(); }, 10000);
});
