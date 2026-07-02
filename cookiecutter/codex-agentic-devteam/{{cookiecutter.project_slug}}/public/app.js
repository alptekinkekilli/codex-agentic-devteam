const STATUS_FILES = {
  project: "./status/project.json",
  queue: "./status/queue.json",
  tasks: "./status/tasks.json",
  timeline: "./status/timeline.json",
  agents: "./status/agents.json",
  health: "./status/health.json",
  manifest: "./status/manifest.json",
  activity: "./status/activity.json",
  usage: "./status/usage.json",
  plan: "./status/plan.json",
};

const state = {
  tasks: [],
  timeline: [],
  activity: [],
  plan: { by_scope: {} },
  archiveEnabled: false,
  archiveSelected: new Set(),
  view: "table",
  role: "all",
  scope: "all",
  hasSnapshot: false,
  manifestGeneratedAt: "",
  lastRefreshAt: "",
  lastRefreshFailed: false,
};

const liveParams = new URLSearchParams(window.location.search);
const liveRefreshSeconds = liveParams.get("live") === "1" ? 15 : 0;

const KANBAN_STATUSES = ["pending", "in-progress", "done", "failed"];
const FRESHNESS_MS = {
  fresh: 2 * 60 * 1000,
  stale: 10 * 60 * 1000,
};

function statusUrl(path, refreshKey = "") {
  if (!refreshKey) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}refresh=${encodeURIComponent(refreshKey)}`;
}

async function readJson(path, refreshKey = "") {
  const response = await fetch(statusUrl(path, refreshKey), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function text(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? "";
}

function badge(value) {
  const span = document.createElement("span");
  span.className = `badge ${String(value).replace(/\s+/g, "-")}`;
  span.textContent = value || "unknown";
  return span;
}

function deploymentMetaItems(task) {
  return [
    ["source", task.deployment_source_commit],
    ["evidence", task.evidence_record_commit],
    ["deploy", task.deployment_id],
    ["env", task.deployment_environment],
    ["path", task.deployment_action_path],
  ].filter(([, value]) => value);
}

function renderDeploymentMeta(task) {
  const items = deploymentMetaItems(task);
  if (!items.length) return null;
  const meta = document.createElement("span");
  meta.className = "deployment-meta";
  for (const [label, value] of items) {
    const item = document.createElement("span");
    item.textContent = `${label}: ${value}`;
    meta.append(item);
  }
  return meta;
}

function renderProject(project, manifest) {
  const data = project.data || {};
  text("project-name", data.name || "Agentic Devteam");
  text("repo-role", data.repo_role || "Private devteam");
  text("generated-at", manifest.generated_at ? `Generated ${manifest.generated_at}` : "");
  renderScopeFilter(data.available_scopes || [], data.active_scope || "all");
}

function freshnessState(generatedAt, now = new Date()) {
  const generatedMs = Date.parse(generatedAt || "");
  if (!Number.isFinite(generatedMs)) return "unknown";
  const ageMs = now.getTime() - generatedMs;
  if (ageMs < FRESHNESS_MS.fresh) return "fresh";
  if (ageMs <= FRESHNESS_MS.stale) return "aging";
  return "stale";
}

function snapshotLabel(freshness) {
  const labels = {
    fresh: "Ready",
    aging: "Aging",
    stale: "Stale",
    offline: "Offline",
    unknown: "No snapshot",
  };
  return labels[freshness] || "No snapshot";
}

function compactTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function setRefreshBusy(isBusy) {
  const button = document.getElementById("refresh-snapshots");
  if (!button) return;
  button.disabled = isBusy;
  button.textContent = isBusy ? "Refreshing" : "Refresh";
}

function updateSnapshotStatus(isLoading = false) {
  const status = document.getElementById("snapshot-status");
  const detail = document.getElementById("snapshot-detail");
  let freshness = freshnessState(state.manifestGeneratedAt);
  if (state.lastRefreshFailed) {
    freshness = state.hasSnapshot ? "offline" : "unknown";
  }
  if (isLoading && !state.hasSnapshot) {
    status.textContent = "Loading";
    status.className = "status-pill loading";
  } else {
    status.textContent = snapshotLabel(freshness);
    const statusClass = { fresh: "ready", unknown: "error", offline: "error" }[freshness] || freshness;
    status.className = `status-pill ${statusClass}`;
  }
  const parts = [];
  if (state.manifestGeneratedAt) parts.push(`Generated ${state.manifestGeneratedAt}`);
  if (state.lastRefreshAt) parts.push(`Refreshed ${compactTime(state.lastRefreshAt)}`);
  if (state.lastRefreshFailed && state.hasSnapshot) parts.push("Last good snapshot kept");
  detail.textContent = parts.join(" · ");
}

function renderQueue(queue) {
  const counts = queue.data?.counts || {};
  text("metric-pending", counts.pending || 0);
  text("metric-in-progress", counts.in_progress || 0);
  text("metric-done", counts.done || 0);
  text("metric-failed", counts.failed || 0);
}

function renderScopedMetrics(tasks) {
  const counts = { pending: 0, "in-progress": 0, done: 0, failed: 0 };
  for (const task of tasks) {
    if (Object.hasOwn(counts, task.status)) counts[task.status] += 1;
  }
  text("metric-pending", counts.pending);
  text("metric-in-progress", counts["in-progress"]);
  text("metric-done", counts.done);
  text("metric-failed", counts.failed);
}

function renderHealth(health) {
  const list = document.getElementById("health-list");
  list.replaceChildren();
  const data = health.data || {};
  const fallbackItems = [
    { label: "Control", status: data.control_check_passed ? "ok" : "blocked" },
    { label: "Queue dirs", status: data.queue_dirs_present ? "ok" : "blocked" },
    { label: "jq", status: data.jq_available_at_generation ? "ok" : "blocked" },
    { label: "Memory", status: data.memory_redaction_checked ? "ok" : "not_checked" },
    { label: "Vercel", status: data.vercel_ready ? "ok" : "pending" },
  ];
  const items = Array.isArray(data.checks) ? data.checks : fallbackItems;
  const statusLabels = {
    ok: "OK",
    pending: "Pending",
    not_checked: "Not checked",
    blocked: "Blocked",
  };
  const statusColors = {
    ok: "var(--green)",
    pending: "var(--amber)",
    not_checked: "var(--muted)",
    blocked: "var(--red)",
  };
  for (const item of items) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    const status = item.status || "pending";
    term.textContent = item.label || "";
    detail.textContent = statusLabels[status] || status;
    detail.style.color = statusColors[status] || "var(--amber)";
    row.append(term, detail);
    list.append(row);
  }
}

function renderRoleFilter(tasks) {
  const filter = document.getElementById("role-filter");
  const roles = [...new Set(tasks.map((task) => task.role).filter(Boolean))].sort();
  filter.replaceChildren(new Option("All roles", "all"));
  for (const role of roles) {
    filter.append(new Option(role, role));
  }
}

function renderScopeFilter(scopes, activeScope) {
  const filter = document.getElementById("scope-filter");
  const currentValue = state.scope === "all" ? activeScope : state.scope;
  const normalizedScopes = Array.isArray(scopes) && scopes.length ? scopes : [{ id: "all", label: "All history" }];
  filter.replaceChildren();
  for (const scope of normalizedScopes) {
    filter.append(new Option(scope.label || scope.id, scope.id));
  }
  if ([...filter.options].some((option) => option.value === currentValue)) {
    state.scope = currentValue;
    filter.value = currentValue;
  }
}

function matchesScope(item, scope = state.scope) {
  if (scope === "all") return true;
  return item.scope === scope && item.snapshot_source === "queue";
}

function filteredTasks(role = state.role, scope = state.scope) {
  return state.tasks.filter((task) => matchesScope(task, scope) && (role === "all" || task.role === role));
}

function filteredTimeline(role = state.role, scope = state.scope) {
  return state.timeline.filter((item) => matchesScope(item, scope) && (role === "all" || item.role === role));
}

function renderTasks(role = state.role) {
  const table = document.getElementById("task-table");
  table.replaceChildren();
  const tasks = filteredTasks(role).slice(-18).reverse();
  if (!tasks.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.className = "empty";
    cell.textContent = "No tasks";
    row.append(cell);
    table.append(row);
    return;
  }

  for (const task of tasks) {
    const row = document.createElement("tr");
    const title = document.createElement("td");
    const titleText = document.createElement("span");
    const idText = document.createElement("span");
    titleText.className = "task-title";
    titleText.textContent = task.title || task.id;
    idText.className = "task-id";
    idText.textContent = [task.id, task.scope, task.snapshot_source].filter(Boolean).join(" / ");

    // Archive selection: only when the local server enabled it, and only for done tasks.
    if (state.archiveEnabled && task.status === "done") {
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "archive-checkbox";
      checkbox.value = task.id;
      checkbox.checked = state.archiveSelected.has(task.id);
      checkbox.setAttribute("aria-label", `Select ${task.id} to archive`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.archiveSelected.add(task.id);
        else state.archiveSelected.delete(task.id);
        updateArchiveButton();
      });
      title.append(checkbox);
    }

    title.append(titleText, idText);
    const deploymentMeta = renderDeploymentMeta(task);
    if (deploymentMeta) title.append(deploymentMeta);

    const status = document.createElement("td");
    status.append(badge(task.status));

    const role = document.createElement("td");
    role.textContent = task.role || "";

    const model = document.createElement("td");
    model.textContent = task.model_alias || task.model_tier || "";

    const validation = document.createElement("td");
    validation.textContent = String(task.validation_count || 0);

    row.append(title, status, role, model, validation);
    makePlanClickable(row, task.scope);
    table.append(row);
  }
}

function makePlanClickable(element, scope) {
  if (!scope) return;
  element.classList.add("plan-clickable");
  element.title = "Open plan";
  element.addEventListener("click", (event) => {
    // don't hijack the archive checkbox
    if (event.target && event.target.classList.contains("archive-checkbox")) return;
    openPlan(scope);
  });
}

function createKanbanCard(task) {
  const card = document.createElement("article");
  const title = document.createElement("strong");
  const meta = document.createElement("p");
  const deploymentMeta = renderDeploymentMeta(task);
  const footer = document.createElement("div");

  card.className = "kanban-card";
  title.textContent = task.title || task.id || "Untitled task";
  meta.textContent = [task.id, task.scope, task.role, task.model_alias || task.model_tier].filter(Boolean).join(" / ");
  footer.className = "kanban-card-footer";
  footer.append(badge(task.status), badge(`${task.validation_count || 0} checks`));
  card.append(title, meta);
  if (deploymentMeta) card.append(deploymentMeta);
  card.append(footer);
  makePlanClickable(card, task.scope);
  return card;
}

function groupTasksByStatus(tasks) {
  const groups = Object.fromEntries(KANBAN_STATUSES.map((status) => [status, []]));
  for (const task of tasks) {
    const status = KANBAN_STATUSES.includes(task.status) ? task.status : "pending";
    groups[status].push(task);
  }
  for (const status of KANBAN_STATUSES) {
    groups[status].sort((left, right) => String(right.id || "").localeCompare(String(left.id || "")));
  }
  return groups;
}

function renderKanban(role = state.role) {
  const groups = groupTasksByStatus(filteredTasks(role));
  for (const status of KANBAN_STATUSES) {
    const column = document.getElementById(`kanban-${status}`);
    const count = document.getElementById(`kanban-count-${status}`);
    const tasks = groups[status].slice(0, 12);
    column.replaceChildren();
    count.textContent = String(groups[status].length);
    if (!tasks.length) {
      const empty = document.createElement("p");
      empty.className = "empty kanban-empty";
      empty.textContent = "No tasks";
      column.append(empty);
      continue;
    }
    for (const task of tasks) {
      column.append(createKanbanCard(task));
    }
  }
}

function renderTimeline(role = state.role) {
  const list = document.getElementById("task-timeline");
  const items = filteredTimeline(role).slice(0, 30);
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No timeline events";
    list.append(empty);
    return;
  }

  for (const item of items) {
    const row = document.createElement("article");
    const marker = document.createElement("span");
    const body = document.createElement("div");
    const title = document.createElement("strong");
    const meta = document.createElement("p");
    const footer = document.createElement("div");
    const transition = [item.from_status, item.to_status].filter(Boolean).join(" -> ");
    const deploymentMeta = renderDeploymentMeta(item);

    row.className = "timeline-item";
    marker.className = "timeline-marker";
    body.className = "timeline-body";
    title.textContent = item.title || item.task_id || "Untitled task";
    meta.textContent = [
      item.task_id,
      item.scope,
      item.role,
      item.model_alias,
      item.observed_at,
    ].filter(Boolean).join(" / ");
    footer.className = "timeline-footer";
    footer.append(badge(item.event_type || "event"));
    if (transition) footer.append(badge(transition));
    footer.append(badge(`${item.validation_count || 0} checks`));

    body.append(title, meta);
    if (deploymentMeta) body.append(deploymentMeta);
    body.append(footer);
    row.append(marker, body);
    makePlanClickable(row, item.scope);
    list.append(row);
  }
}

function renderTaskViews() {
  renderTasks(state.role);
  renderKanban(state.role);
  renderTimeline(state.role);
}

function setTaskView(view) {
  state.view = view;
  const tableView = document.getElementById("task-table-view");
  const kanbanView = document.getElementById("task-kanban-view");
  const timelineView = document.getElementById("task-timeline-view");
  document.getElementById("tab-table").classList.toggle("active", view === "table");
  document.getElementById("tab-kanban").classList.toggle("active", view === "kanban");
  document.getElementById("tab-timeline").classList.toggle("active", view === "timeline");
  tableView.classList.toggle("hidden", view !== "table");
  kanbanView.classList.toggle("hidden", view !== "kanban");
  timelineView.classList.toggle("hidden", view !== "timeline");
}

function compactNumber(value) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatCost(value) {
  const n = Number(value || 0);
  return `$${n.toFixed(n < 1 ? 4 : 2)}`;
}

// Per-scope usage: filter the per-task report by the selected scope and aggregate
// per-role + totals, so agent boxes and the report reflect the scope you're viewing.
function usageForScope(scope) {
  const all = state.usage?.report || [];
  const rows = scope === "all" ? all : all.filter((r) => r.scope === scope);
  const byRole = {};
  const totals = { input: 0, output: 0, cost_usd: 0, tasks: 0 };
  for (const r of rows) {
    const agg = byRole[r.role] || (byRole[r.role] = { input: 0, output: 0, cost_usd: 0, tasks: 0 });
    const inp = Number(r.input || 0);
    const out = Number(r.output || 0);
    const cost = Number(r.cost_usd || 0);
    agg.input += inp; agg.output += out; agg.cost_usd += cost; agg.tasks += 1;
    totals.input += inp; totals.output += out; totals.cost_usd += cost; totals.tasks += 1;
  }
  return { rows, byRole, totals };
}

function renderAgents() {
  const grid = document.getElementById("agent-grid");
  grid.replaceChildren();
  const { byRole } = usageForScope(state.scope);
  for (const agent of state.agents || []) {
    const card = document.createElement("article");
    const title = document.createElement("strong");
    const body = document.createElement("p");
    card.className = "agent";
    title.textContent = agent.role || "agent";
    body.textContent = agent.responsibility || "";

    // Token performance for THIS agent within the selected scope.
    const usage = byRole[agent.role] || { input: 0, output: 0, cost_usd: 0, tasks: 0 };
    const tokenLine = document.createElement("div");
    tokenLine.className = "agent-usage";
    if (usage.tasks > 0) {
      tokenLine.innerHTML =
        `<span class="usage-cost">${formatCost(usage.cost_usd)}</span>` +
        `<span>↓${compactNumber(usage.input)} ↑${compactNumber(usage.output)} tok</span>` +
        `<span>${usage.tasks} task${usage.tasks === 1 ? "" : "s"}</span>`;
    } else {
      tokenLine.innerHTML = `<span class="usage-idle">no runs yet</span>`;
    }

    const modelBadge = badge(agent.model || agent.model_alias || agent.model_tier);
    modelBadge.classList.add(`model-${agent.model_tier || "fast"}`);

    card.append(title, body, modelBadge, tokenLine);
    grid.append(card);
  }
}

function renderUsageReport() {
  const { rows, totals } = usageForScope(state.scope);
  const scopeLabel = state.scope === "all" ? "all history" : state.scope;
  const totalsEl = document.getElementById("usage-totals");
  if (totalsEl) {
    totalsEl.textContent = totals.tasks
      ? `${scopeLabel}: ${totals.tasks} runs · ↓${compactNumber(totals.input)} ↑${compactNumber(totals.output)} tok · ${formatCost(totals.cost_usd)}`
      : `${scopeLabel}: no completed runs yet`;
  }

  const table = document.getElementById("usage-table");
  if (!table) return;
  table.replaceChildren();
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.className = "empty";
    cell.textContent = "No token reports yet — they appear here as agents complete tasks.";
    row.append(cell);
    table.append(row);
    return;
  }
  for (const entry of rows) {
    const row = document.createElement("tr");
    const cells = [
      (entry.completed_at || "").slice(0, 19).replace("T", " "),
      entry.role || "",
      entry.model || "",
      entry.task_id || "",
      compactNumber(entry.input),
      compactNumber(entry.output),
      formatCost(entry.cost_usd),
      String(entry.turns ?? ""),
    ];
    for (const value of cells) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    table.append(row);
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Minimal, safe markdown -> HTML (headings, bold, inline code, lists, hr, rules).
function mdToHtml(markdown) {
  const lines = String(markdown).split("\n");
  const out = [];
  let inList = false;
  let inCode = false;
  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };
  for (const raw of lines) {
    const line = raw;
    if (line.trim().startsWith("```")) {
      // skip fenced code fences (mermaid is rendered separately); toggle plain code
      if (line.trim().startsWith("```mermaid")) {
        inCode = "mermaid";
        continue;
      }
      if (inCode) {
        if (inCode !== "mermaid") out.push("</pre>");
        inCode = false;
      } else {
        closeList();
        out.push("<pre>");
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      if (inCode !== "mermaid") out.push(escapeHtml(line));
      continue;
    }
    let html = escapeHtml(line)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length + 1;
      out.push(`<h${level}>${escapeHtml(heading[2])}</h${level}>`);
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${html.replace(/^\s*[-*]\s+/, "")}</li>`);
    } else if (/^\s*---+\s*$/.test(line)) {
      closeList();
      out.push("<hr>");
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      out.push(`<p>${html}</p>`);
    }
  }
  closeList();
  return out.join("\n");
}

let planDiagramSeq = 0;

function planPrompt(decision, scope, feedback) {
  const repoName = state.project?.data?.name || "this Codex agentic devteam repo";
  if (decision === "approve") {
    return (
      `${repoName} reposunda "${scope}" planını ONAYLIYORUM. ` +
      `Şu komutu ÇALIŞTIR (işi sen yapma, sadece çalıştır ve raporla): ` +
      `scripts/loop.sh build ${scope} — coder→reviewer→tester→ops zincirini headless koştur. ` +
      `Push yok, PR yok.`
    );
  }
  return (
    `${repoName} reposunda "${scope}" planını ONAYLAMADIM. ` +
    `Mimar (architect) planı şu notlara göre REVİZE etsin: «${feedback || "(not girilmedi)"}». ` +
    `docs/architecture/${scope}.md ve docs/loops/${scope}/README.md'yi güncelle, ` +
    `Mermaid diyagramını da güncelle, mevcut pending coder task'ını supersede edip tek bir yeni ` +
    `coder follow-up enqueue et. Sadece tasarım — kod yazma, push yok, PR yok.`
  );
}

function showPlanPrompt(text) {
  const box = document.getElementById("plan-prompt-box");
  document.getElementById("plan-prompt-text").textContent = text;
  box.classList.remove("hidden");
}

async function openPlan(scope) {
  const modal = document.getElementById("plan-modal");
  if (!modal || !scope) return;
  state.planScope = scope;
  document.getElementById("plan-prompt-box").classList.add("hidden");
  document.getElementById("plan-feedback").value = "";
  const data = (state.plan?.by_scope || {})[scope];
  document.getElementById("plan-title").textContent = `Plan — ${scope}`;
  const diagrams = document.getElementById("plan-diagrams");
  const body = document.getElementById("plan-body");
  diagrams.replaceChildren();
  body.replaceChildren();

  if (!data) {
    body.innerHTML = "<p>No plan recorded for this scope yet.</p>";
    modal.classList.remove("hidden");
    return;
  }

  // Mermaid diagrams (rendered to SVG).
  for (const code of data.mermaid || []) {
    const holder = document.createElement("div");
    holder.className = "mermaid-diagram";
    diagrams.append(holder);
    if (window.mermaid) {
      try {
        const { svg } = await window.mermaid.render(`plan-m-${planDiagramSeq++}`, code);
        holder.innerHTML = svg;
      } catch {
        const pre = document.createElement("pre");
        pre.textContent = code;
        holder.replaceChildren(pre);
      }
    } else {
      const pre = document.createElement("pre");
      pre.textContent = code;
      holder.replaceChildren(pre);
    }
  }

  const designHtml = data.design ? mdToHtml(data.design) : "";
  const readmeHtml = data.readme ? `<hr><h2>Loop home</h2>${mdToHtml(data.readme)}` : "";
  body.innerHTML = designHtml + readmeHtml;
  modal.classList.remove("hidden");
}

function closePlan() {
  document.getElementById("plan-modal")?.classList.add("hidden");
}

function renderTicker() {
  const track = document.getElementById("ticker-track");
  if (!track) return;
  track.replaceChildren();

  const items = (state.activity || []).filter(
    (entry) => state.scope === "all" || entry.scope === state.scope
  );

  if (!items.length) {
    track.style.animation = "none";
    const empty = document.createElement("span");
    empty.className = "ticker-empty";
    empty.textContent = "Henüz aktivite yok — bir görev başladığında burada akacak.";
    track.append(empty);
    return;
  }

  // Keep a readable scroll speed regardless of how many lines there are.
  track.style.animation = "";
  track.style.animationDuration = `${Math.max(30, items.length * 4)}s`;

  const statusClass = {
    "in-progress": "is-running",
    done: "is-done",
    failed: "is-failed",
  };

  for (const entry of items) {
    const chip = document.createElement("span");
    chip.className = `ticker-item ${statusClass[entry.status] || ""}`.trim();

    const time = document.createElement("span");
    time.className = "ticker-time";
    time.textContent = (entry.observed_at || "").slice(11, 19);

    const icon = document.createElement("span");
    icon.className = "ticker-icon";
    icon.textContent = entry.icon || "•";

    const label = document.createElement("span");
    label.textContent = entry.text || "";

    chip.append(time, icon, label);
    track.append(chip);
  }
}

function updateArchiveButton() {
  const button = document.getElementById("archive-selected");
  if (!button) return;
  const count = state.archiveSelected.size;
  button.textContent = `Archive selected (${count})`;
  button.disabled = count === 0;
}

async function probeArchiveCapability() {
  const bar = document.getElementById("archive-bar");
  try {
    const response = await fetch("./api/capabilities", { cache: "no-store" });
    if (!response.ok) throw new Error("no capability endpoint");
    const data = await response.json();
    state.archiveEnabled = Boolean(data.archive);
  } catch {
    // Static host (e.g. Vercel) has no endpoint -> stay read-only.
    state.archiveEnabled = false;
  }
  if (bar) bar.classList.toggle("hidden", !state.archiveEnabled);
}

async function archiveSelectedTasks() {
  const ids = [...state.archiveSelected];
  if (!ids.length) return;
  const button = document.getElementById("archive-selected");
  if (button) {
    button.disabled = true;
    button.textContent = "Archiving…";
  }
  try {
    const response = await fetch("./api/archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_ids: ids }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "archive failed");
    state.archiveSelected.clear();
    await loadDashboard(); // refreshes counts + drops archived rows
    const skipped = (result.skipped || []).length;
    const archived = (result.archived || []).length;
    setSnapshotNote(`Archived ${archived} task(s)${skipped ? `, skipped ${skipped}` : ""}.`);
  } catch (error) {
    setSnapshotNote(`Archive error: ${error.message}`);
  } finally {
    updateArchiveButton();
  }
}

function setSnapshotNote(message) {
  const detail = document.getElementById("snapshot-detail");
  if (detail) detail.textContent = message;
}

async function loadDashboard(retry = 0) {
  const refreshKey = String(Date.now());
  setRefreshBusy(true);
  updateSnapshotStatus(true);
  try {
    const [project, queue, tasks, timeline, agents, health, manifest, activity, usage, plan] = await Promise.all(
      Object.values(STATUS_FILES).map((path) => readJson(path, refreshKey))
    );
    state.tasks = tasks.data?.items || [];
    state.timeline = timeline.data?.items || [];
    state.activity = activity.data?.items || [];
    state.usage = usage.data || { report: [], by_role: {}, totals: {} };
    state.agents = agents.data?.items || [];
    state.plan = plan.data || { by_scope: {} };
    state.hasSnapshot = true;
    state.manifestGeneratedAt = manifest.generated_at || "";
    state.lastRefreshAt = new Date().toISOString();
    state.lastRefreshFailed = false;
    renderProject(project, manifest);
    renderScopedMetrics(filteredTasks("all"));
    renderHealth(health);
    renderRoleFilter(filteredTasks("all"));
    renderTaskViews();
    renderAgents();
    renderTicker();
    renderUsageReport();
    updateArchiveButton();
    updateSnapshotStatus();
  } catch (error) {
    // Transient blip (origin restart, mobile network hiccup): retry a few times before
    // declaring "No snapshot", and keep the last-good data instead of blanking to zeros.
    if (retry < 4) {
      setRefreshBusy(false);
      setTimeout(() => loadDashboard(retry + 1), 1500);
      return;
    }
    state.lastRefreshAt = new Date().toISOString();
    state.lastRefreshFailed = true;
    updateSnapshotStatus();
    renderTaskViews();
  } finally {
    setRefreshBusy(false);
  }
}

document.getElementById("role-filter").addEventListener("change", (event) => {
  state.role = event.target.value;
  renderTaskViews();
  renderScopedMetrics(filteredTasks("all"));
});

document.getElementById("scope-filter").addEventListener("change", (event) => {
  state.scope = event.target.value;
  state.role = "all";
  renderRoleFilter(filteredTasks("all"));
  renderTaskViews();
  renderScopedMetrics(filteredTasks("all"));
  renderTicker();
  renderAgents();
  renderUsageReport();
});

document.getElementById("tab-table").addEventListener("click", () => {
  setTaskView("table");
});

document.getElementById("tab-kanban").addEventListener("click", () => {
  setTaskView("kanban");
});

document.getElementById("tab-timeline").addEventListener("click", () => {
  setTaskView("timeline");
});

document.getElementById("refresh-snapshots").addEventListener("click", () => {
  loadDashboard();
});

document.getElementById("archive-selected").addEventListener("click", () => {
  archiveSelectedTasks();
});

document.getElementById("plan-close").addEventListener("click", closePlan);
document.getElementById("plan-modal").addEventListener("click", (event) => {
  if (event.target === document.getElementById("plan-modal")) closePlan();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closePlan();
});

document.getElementById("plan-approve").addEventListener("click", () => {
  showPlanPrompt(planPrompt("approve", state.planScope));
});
document.getElementById("plan-reject").addEventListener("click", () => {
  const feedback = document.getElementById("plan-feedback").value.trim();
  showPlanPrompt(planPrompt("reject", state.planScope, feedback));
});
document.getElementById("plan-prompt-copy").addEventListener("click", async () => {
  const text = document.getElementById("plan-prompt-text").textContent;
  const button = document.getElementById("plan-prompt-copy");
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Kopyalandı ✓";
  } catch {
    // mobile/secure-context fallback: select the text so the user can long-press copy
    const range = document.createRange();
    range.selectNodeContents(document.getElementById("plan-prompt-text"));
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    button.textContent = "Seçildi — kopyala";
  }
  setTimeout(() => {
    button.textContent = "Kopyala";
  }, 2000);
});

probeArchiveCapability().finally(() => loadDashboard());

if (liveRefreshSeconds > 0) {
  window.setInterval(() => {
    loadDashboard();
  }, liveRefreshSeconds * 1000);
}
