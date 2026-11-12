// Browser UI for the sequence_extensions flow engine. Vanilla ES module.
// All engine-provided text is inserted with textContent; there is no innerHTML.

import { fitGraph, ROOT_NODE_ID, renderGraph, selectGraphNode } from "./graph.js";

const $ = (id) => document.getElementById(id);

const ui = {
  health: $("health"),
  projectRoot: $("project-root"),
  openRoot: $("open-root"),
  rootStatus: $("root-status"),
  crumbs: $("crumbs"),
  fileList: $("file-list"),
  refreshTree: $("refresh-tree"),
  flowFile: $("flow-file"),
  flowSelect: $("flow-select"),
  planStatus: $("plan-status"),
  importPlan: $("import-plan"),
  exportPlan: $("export-plan"),
  planFile: $("plan-file"),
  evaluate: $("evaluate"),
  evalError: $("eval-error"),
  warnings: $("warnings"),
  graph: $("graph"),
  graphEmpty: $("graph-empty"),
  fitGraph: $("fit-graph"),
  execute: $("execute"),
  cancel: $("cancel"),
  dirtyHint: $("dirty-hint"),
  selectedNode: $("selected-node"),
  nodeEditor: $("node-editor"),
  jobStatus: $("job-status"),
  resultBanner: $("result-banner"),
  log: $("log-console"),
  clearLog: $("clear-log"),
  optMaxWorkers: $("opt-max-workers"),
  optRetries: $("opt-retries"),
  optRetryDelay: $("opt-retry-delay"),
  optTimeout: $("opt-timeout"),
  optSummary: $("opt-summary"),
  optFixedClock: $("opt-fixed-clock"),
};

const PLAN_SCHEMA = "flow-plan/2";
const PUT_METHOD = "PUT";

const OPTION_DEFAULTS = {
  max_workers: 16,
  summary: false,
  fixed_clock: false,
  retries: 0,
  retry_delay_seconds: 0.0,
  timeout: null,
};

const state = {
  projectRoot: "",
  dir: "",
  entries: [],
  flowFile: null,
  flowName: null,
  plan: null,
  selectedId: null,
  dirty: false,
  jobId: null,
  source: null,
};

let widgetSeq = 0;

function nextId(prefix) {
  widgetSeq += 1;
  return `${prefix}-${widgetSeq}`;
}

async function api(path, init = {}) {
  const response = await fetch(path, init);
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const detail =
      typeof data === "string" ? data : data?.detail != null ? JSON.stringify(data.detail) : text;
    const error = new Error(
      `${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`,
    );
    error.status = response.status;
    throw error;
  }
  return data;
}

function postJson(path, payload) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function putJson(path, payload) {
  return api(path, {
    method: PUT_METHOD,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------- startup ----

async function boot() {
  try {
    const health = await api("/api/health");
    state.projectRoot = health.project_root || "";
    ui.projectRoot.value = state.projectRoot;
    ui.health.textContent = `ok · v${health.version ?? "?"} · ${state.projectRoot}`;
    ui.health.classList.remove("bad");
  } catch (error) {
    ui.health.textContent = `backend unreachable: ${error.message}`;
    ui.health.classList.add("bad");
  }
  await loadTree("");
}

async function loadTree(path) {
  try {
    const data = await api(`/api/tree?path=${encodeURIComponent(path || "")}`);
    state.dir = data.path || "";
    state.entries = Array.isArray(data.entries) ? data.entries : [];
    renderCrumbs(state.dir);
    renderFiles(state.entries);
  } catch (error) {
    state.entries = [];
    renderCrumbs(state.dir);
    ui.fileList.replaceChildren(message(`Cannot list files: ${error.message}`, "error"));
  }
}

// -------------------------------------------------------------- project root ----

function setRootStatus(text, tone) {
  ui.rootStatus.textContent = text || "";
  ui.rootStatus.classList.toggle("ok", tone === "ok");
  ui.rootStatus.classList.toggle("bad", tone === "error");
}

function runActive() {
  return (
    state.source !== null ||
    state.jobId !== null ||
    !ui.cancel.classList.contains("hidden")
  );
}

function setRootBusy(busy) {
  ui.openRoot.disabled = busy;
}

function lockRootForRun() {
  setRootBusy(true);
  setRootStatus("cancel or wait for the run to finish", "error");
}

function unlockRootAfterRun() {
  setRootBusy(runActive());
  if (ui.rootStatus.textContent.includes("wait for the run to finish")) {
    setRootStatus("");
  }
}

async function switchRoot() {
  if (runActive()) {
    setRootStatus("cancel or wait for the run to finish", "error");
    return;
  }
  const path = ui.projectRoot.value.trim();
  if (!path) {
    setRootStatus("enter an absolute path", "error");
    return;
  }

  setRootBusy(true);
  setRootStatus("switching…");
  try {
    const health = await putJson("/api/root", { path });
    const root = health?.project_root || path;
    state.projectRoot = root;
    ui.projectRoot.value = root;
    ui.health.textContent = `ok · v${health?.version ?? "?"} · ${root}`;
    ui.health.classList.remove("bad");
    resetForRoot();
    setRootStatus("project root updated", "ok");
    await loadTree("");
  } catch (error) {
    setRootStatus(`switch failed: ${error.message}`, "error");
  } finally {
    setRootBusy(runActive());
  }
}

function resetForRoot() {
  state.dir = "";
  state.flowFile = null;
  state.flowName = null;
  state.selectedId = null;
  ui.flowFile.textContent = "none";
  ui.flowSelect.value = "";
  populateFlowSelect([]);
  ui.planFile.value = "";
  clearPlan();
  ui.log.replaceChildren();
  ui.resultBanner.classList.add("hidden");
  ui.resultBanner.replaceChildren();
  setJobStatus("idle");
  hideEvalError();
  renderWarnings([]);
}

function renderCrumbs(path) {
  ui.crumbs.replaceChildren();
  const root = document.createElement("button");
  root.type = "button";
  root.textContent = "root";
  root.dataset.path = "";
  ui.crumbs.append(root);

  let accumulated = "";
  for (const part of String(path || "").split("/").filter(Boolean)) {
    accumulated = accumulated ? `${accumulated}/${part}` : part;
    const separator = document.createElement("span");
    separator.textContent = "/";
    ui.crumbs.append(separator);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = part;
    button.dataset.path = accumulated;
    ui.crumbs.append(button);
  }
}

function renderFiles(entries) {
  ui.fileList.replaceChildren();
  if (!entries.length) {
    ui.fileList.append(message("No .py or .json files here.", "empty"));
    return;
  }
  for (const entry of entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "file-entry";
    button.dataset.path = entry.path;
    button.dataset.kind = entry.kind;
    button.setAttribute("role", "option");
    const selected = entry.path === state.flowFile;
    button.setAttribute("aria-selected", selected ? "true" : "false");
    if (selected) {
      button.classList.add("selected");
    }
    const glyph = document.createElement("span");
    glyph.className = "glyph";
    glyph.textContent = entry.kind === "dir" ? "▸" : "·";
    const name = document.createElement("span");
    name.textContent = entry.name;
    button.append(glyph, name);
    ui.fileList.append(button);
  }
}

function message(text, className) {
  const node = document.createElement("p");
  node.className = className || "muted";
  node.textContent = text;
  return node;
}

// --------------------------------------------------------------- selection ----

async function selectFile(path) {
  const lower = path.toLowerCase();
  if (lower.endsWith(".py")) {
    if (state.flowFile !== path) {
      state.flowFile = path;
      state.flowName = null;
      ui.flowFile.textContent = path;
      hideEvalError();
      renderWarnings([]);
      populateFlowSelect([]);
      if (state.plan) {
        // Keep an imported/edited plan so it can be evaluated against this flow.
        markDirty();
      } else {
        clearPlan();
      }
    }
    renderFiles(state.entries);
    return;
  }
  if (lower.endsWith(".json")) {
    try {
      const data = await api(`/api/file?path=${encodeURIComponent(path)}`);
      await importPlanText(data?.content ?? "", path);
    } catch (error) {
      showEvalError(`Cannot load ${path}: ${error.message}`);
    }
  }
}

function clearPlan() {
  state.plan = null;
  state.selectedId = null;
  state.dirty = false;
  ui.execute.disabled = true;
  ui.exportPlan.disabled = true;
  ui.dirtyHint.classList.add("hidden");
  ui.graphEmpty.classList.remove("hidden");
  ui.graphEmpty.textContent = "Evaluate a flow to see its graph";
  ui.selectedNode.textContent = "none";
  ui.nodeEditor.replaceChildren(message("Select a node in the graph.", "muted"));
  ui.planStatus.textContent = "none";
  renderGraph(ui.graph, null);
  syncOptions();
  setOptionsEnabled(false);
}

function populateFlowSelect(flows) {
  const names = Array.isArray(flows) ? flows : [];
  const previous = state.flowName || "";
  ui.flowSelect.replaceChildren();
  const auto = document.createElement("option");
  auto.value = "";
  auto.textContent = "(auto)";
  ui.flowSelect.append(auto);
  for (const name of names) {
    const option = document.createElement("option");
    option.value = String(name);
    option.textContent = String(name);
    ui.flowSelect.append(option);
  }
  if (previous && names.includes(previous)) {
    ui.flowSelect.value = previous;
  } else {
    ui.flowSelect.value = "";
    if (state.flowName && !names.includes(state.flowName)) state.flowName = null;
  }
  ui.flowSelect.disabled = names.length === 0;
}

// ------------------------------------------------------------------- plan ----

function markDirty() {
  if (!state.plan) return;
  state.dirty = true;
  ui.dirtyHint.classList.remove("hidden");
}

// Convert a wire/imported plan into the pure engine document. Display-only
// fields (`editable`, `note`) and wire aliases are stripped.
function planDocument(plan) {
  if (!plan) return null;
  const cleanParams = (params) =>
    (Array.isArray(params) ? params : []).map((param) => ({
      name: param.name,
      type: param.type ?? "",
      required: Boolean(param.required),
      default: param.default ?? null,
      value: param.value ?? null,
    }));
  const parameters = cleanParams(plan.parameters);
  const nodes = (Array.isArray(plan.nodes) ? plan.nodes : []).map((node) => ({
    id: node.id,
    name: node.name,
    kind: node.kind ?? "node",
    path: Array.isArray(node.path) ? node.path : [],
    instance: node.instance ?? 1,
    policy: {
      retries: node.policy?.retries ?? 0,
      retry_delay_seconds: node.policy?.retry_delay_seconds ?? 0.0,
      timeout: node.policy?.timeout ?? null,
    },
    params: cleanParams(node.params),
  }));
  const edges = (Array.isArray(plan.edges) ? plan.edges : []).map((edge) => ({
    from: edge.from ?? edge.source,
    to: edge.to ?? edge.target,
  }));
  const source = plan.options || {};
  const options = {};
  for (const [key, fallback] of Object.entries(OPTION_DEFAULTS)) {
    options[key] = Object.prototype.hasOwnProperty.call(source, key) ? source[key] : fallback;
  }
  return { schema: PLAN_SCHEMA, parameters, nodes, edges, options };
}

function buildPayload() {
  return {
    flow_file: state.flowFile,
    flow_name: state.flowName || null,
    plan: state.plan ? planDocument(state.plan) : null,
  };
}

function applyPlan(plan) {
  state.plan = plan;
  state.selectedId = ROOT_NODE_ID;
  state.dirty = false;
  ui.dirtyHint.classList.add("hidden");
  ui.execute.disabled = false;
  ui.exportPlan.disabled = false;
  ui.planStatus.textContent = PLAN_SCHEMA;
  ui.graphEmpty.classList.add("hidden");
  syncOptions();
  setOptionsEnabled(true);
  renderGraph(ui.graph, plan, {
    onSelect: selectNode,
    selectedId: ROOT_NODE_ID,
    rootLabel: state.flowName || "",
    emptyText: "Root flow — no child nodes.",
  });
  renderNodeEditor();
}

async function importPlanText(text, label) {
  let document;
  try {
    document = JSON.parse(text);
  } catch (error) {
    showEvalError(`Cannot import ${label}: invalid JSON (${error.message})`);
    return;
  }
  if (!document || document.schema !== PLAN_SCHEMA) {
    showEvalError(`Cannot import ${label}: schema must be "${PLAN_SCHEMA}".`);
    return;
  }
  applyPlan(document);
  markDirty();
  if (!state.flowFile) {
    showEvalError("Plan imported. Select a .py flow file, then press Evaluate.");
    return;
  }
  await evaluate();
}

function exportPlan() {
  if (!state.plan) {
    showEvalError("Nothing to export: evaluate or import a plan first.");
    return;
  }
  const text = JSON.stringify(planDocument(state.plan), null, 2);
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "plan.json";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function evaluate() {
  if (!state.flowFile) {
    showEvalError("Select a .py flow file first.");
    return;
  }
  hideEvalError();
  ui.evaluate.disabled = true;
  ui.evaluate.textContent = "Evaluating…";
  try {
    const result = await postJson("/api/evaluate", buildPayload());
    handleEvaluateResult(result);
  } catch (error) {
    showEvalError(`Evaluate failed: ${error.message}`);
  } finally {
    ui.evaluate.disabled = false;
    ui.evaluate.textContent = "Evaluate";
  }
}

function handleEvaluateResult(result) {
  if (!result || typeof result !== "object") {
    showEvalError("Evaluate returned an unexpected response.");
    return;
  }
  if (Array.isArray(result.available_flows)) populateFlowSelect(result.available_flows);
  renderWarnings(result.warnings);

  if (!result.ok) {
    showEvalError(result.error || "Evaluate failed.", result.traceback);
    markDirty();
    return;
  }
  if (!result.plan) {
    showEvalError("Evaluate succeeded but returned no plan.");
    markDirty();
    return;
  }

  hideEvalError();
  if (result.flow_name) {
    state.flowName = result.flow_name;
    const known = [...ui.flowSelect.options].some(
      (option) => option.value === result.flow_name,
    );
    if (!known) {
      const option = document.createElement("option");
      option.value = result.flow_name;
      option.textContent = result.flow_name;
      ui.flowSelect.append(option);
      ui.flowSelect.disabled = false;
    }
    ui.flowSelect.value = result.flow_name;
  }
  applyPlan(result.plan);
}

function selectNode(id) {
  state.selectedId = id;
  selectGraphNode(ui.graph, id);
  renderNodeEditor();
}

// -------------------------------------------------------- parameter editor ----

function widgetKind(type) {
  const text = String(type || "").toLowerCase();
  if (text.includes("list") || text.includes("dict") || text.includes("tuple") || text.includes("set")) {
    return "json";
  }
  if (text.includes("bool")) return "bool";
  if (text.includes("float") || text.includes("decimal")) return "float";
  if (text.includes("int")) return "int";
  return "text";
}

function buildParam(param, commit) {
  const editable = param.editable !== false;
  const kind = widgetKind(param.type);
  const value = param.value;

  const row = document.createElement("div");
  row.className = `param${editable ? "" : " readonly"}`;
  if (!editable && param.note) row.title = param.note;

  const inputId = nextId("param");
  const head = document.createElement("label");
  head.className = "param-head";
  head.htmlFor = inputId;
  const name = document.createElement("span");
  name.className = "param-name";
  name.textContent = param.name;
  const type = document.createElement("span");
  type.className = "param-type";
  type.textContent = param.type || "value";
  head.append(name, type);
  if (param.required) {
    const required = document.createElement("span");
    required.className = "param-required";
    required.textContent = "required";
    head.append(required);
  }
  row.append(head);

  let input;
  let error = null;

  const setError = (text) => {
    if (!error) return;
    error.textContent = text || "";
    error.classList.toggle("hidden", !text);
  };

  if (kind === "bool") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.id = inputId;
    input.checked = Boolean(value);
    input.disabled = !editable;
    input.addEventListener("change", () => {
      commit(input.checked);
    });
  } else if (kind === "int" || kind === "float") {
    input = document.createElement("input");
    input.type = "number";
    input.id = inputId;
    input.step = kind === "int" ? "1" : "any";
    input.value = value === null || value === undefined ? "" : String(value);
    input.disabled = !editable;
    input.addEventListener("input", () => {
      const text = input.value.trim();
      if (text === "") {
        setError("enter a number");
        return;
      }
      const number = Number(text);
      if (!Number.isFinite(number) || (kind === "int" && !Number.isInteger(number))) {
        setError(kind === "int" ? "not an integer" : "not a number");
        return;
      }
      setError(null);
      commit(number);
    });
  } else if (kind === "json") {
    input = document.createElement("textarea");
    input.id = inputId;
    input.spellcheck = false;
    input.rows = 3;
    input.value = JSON.stringify(value ?? null, null, 2);
    input.disabled = !editable;
    input.addEventListener("input", () => {
      try {
        const parsed = JSON.parse(input.value);
        setError(null);
        commit(parsed);
      } catch (parseError) {
        setError(`invalid JSON: ${parseError.message}`);
      }
    });
  } else {
    input = document.createElement("input");
    input.type = "text";
    input.id = inputId;
    input.value = value === null || value === undefined ? "" : String(value);
    input.disabled = !editable;
    input.addEventListener("input", () => {
      commit(input.value);
    });
  }

  if (!editable) {
    input.title = param.note || "read-only";
    row.title = param.note || "read-only";
  }
  row.append(input);

  if (!editable && param.note) {
    const note = document.createElement("div");
    note.className = "muted";
    note.textContent = param.note;
    row.append(note);
  }

  if (editable) {
    error = document.createElement("div");
    error.className = "field-error hidden";
    error.setAttribute("role", "alert");
    row.append(error);
  }

  return row;
}

function renderNodeEditor() {
  ui.nodeEditor.replaceChildren();
  if (!state.plan) {
    ui.selectedNode.textContent = "none";
    ui.nodeEditor.append(message("Select a node in the graph.", "muted"));
    return;
  }
  if (state.selectedId === ROOT_NODE_ID) {
    ui.selectedNode.textContent = state.flowName || "Flow parameters";
    const params = state.plan.parameters || [];
    if (!params.length) {
      ui.nodeEditor.append(message("No flow inputs.", "muted"));
      return;
    }
    for (const param of params) {
      ui.nodeEditor.append(
        buildParam(param, (value) => {
          param.value = value;
          markDirty();
        }),
      );
    }
    return;
  }
  const node = (state.plan.nodes || []).find(
    (candidate) => String(candidate.id) === String(state.selectedId),
  );
  if (!node) {
    ui.selectedNode.textContent = "none";
    ui.nodeEditor.append(message("Select a node in the graph.", "muted"));
    return;
  }

  ui.selectedNode.textContent = `${node.name} #${node.instance}`;
  const duplicates = (state.plan.nodes || []).filter(
    (candidate) => candidate.name === node.name,
  ).length;
  if (duplicates > 1) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = `"${node.name}" has ${duplicates} instances; edits apply to all of them.`;
    ui.nodeEditor.append(note);
  }

  const params = node.params || [];
  if (!params.length) {
    ui.nodeEditor.append(message("No parameters on this node.", "muted"));
  } else {
    for (const param of params) {
      ui.nodeEditor.append(
        buildParam(param, (value) => {
          for (const candidate of state.plan?.nodes || []) {
            if (candidate.name !== node.name) continue;
            for (const other of candidate.params || []) {
              if (other.name === param.name) other.value = value;
            }
          }
          markDirty();
        }),
      );
    }
  }
  ui.nodeEditor.append(buildPolicyEditor(node));
}

function parsePolicyField(text, kind, allowEmpty) {
  if (text.trim() === "") {
    return allowEmpty ? { value: null } : { error: "enter a number" };
  }
  const number = Number(text);
  if (
    !Number.isFinite(number) ||
    number < 0 ||
    (kind === "int" && !Number.isInteger(number))
  ) {
    return { error: kind === "int" ? "not a non-negative integer" : "not a non-negative number" };
  }
  return { value: number };
}

function buildPolicyEditor(node) {
  const box = document.createElement("div");
  box.className = "policy";
  const heading = document.createElement("h3");
  heading.textContent = `Policy — ${node.name}`;
  box.append(heading);

  const grid = document.createElement("div");
  grid.className = "policy-grid";
  const policy = node.policy || {};
  const fields = [
    ["retries", "int", false],
    ["retry_delay_seconds", "float", false],
    ["timeout", "float", true],
  ];

  for (const [key, kind, allowEmpty] of fields) {
    const label = document.createElement("label");
    const inputId = nextId("policy");
    label.htmlFor = inputId;
    label.textContent = key;
    const input = document.createElement("input");
    input.type = "number";
    input.id = inputId;
    input.step = kind === "int" ? "1" : "any";
    input.min = "0";
    input.placeholder = allowEmpty ? "none" : "0";
    input.value =
      policy[key] === null || policy[key] === undefined ? "" : String(policy[key]);

    const error = document.createElement("div");
    error.className = "field-error hidden";
    error.setAttribute("role", "alert");

    input.addEventListener("input", () => {
      const parsed = parsePolicyField(input.value, kind, allowEmpty);
      if (parsed.error) {
        error.textContent = parsed.error;
        error.classList.remove("hidden");
        return;
      }
      error.classList.add("hidden");
      for (const candidate of state.plan?.nodes || []) {
        if (candidate.name !== node.name) continue;
        candidate.policy = { ...(candidate.policy || {}), [key]: parsed.value };
      }
      markDirty();
    });

    const cell = document.createElement("div");
    cell.className = "policy-cell";
    cell.append(input, error);
    grid.append(label, cell);
  }

  box.append(grid);
  return box;
}

// --------------------------------------------------------------- messages ----

function showEvalError(messageText, traceback) {
  ui.evalError.replaceChildren();
  const headline = document.createElement("div");
  headline.textContent = messageText;
  ui.evalError.append(headline);
  if (traceback) {
    const details = document.createElement("details");
    details.className = "details";
    const summary = document.createElement("summary");
    summary.textContent = "traceback";
    const pre = document.createElement("pre");
    pre.textContent = traceback;
    details.append(summary, pre);
    ui.evalError.append(details);
  }
  ui.evalError.classList.remove("hidden");
}

function hideEvalError() {
  ui.evalError.classList.add("hidden");
  ui.evalError.replaceChildren();
}

function renderWarnings(warnings) {
  ui.warnings.replaceChildren();
  const list = Array.isArray(warnings) ? warnings : [];
  if (!list.length) {
    ui.warnings.classList.add("hidden");
    return;
  }
  for (const warning of list) {
    const item = document.createElement("li");
    item.textContent = String(warning);
    ui.warnings.append(item);
  }
  ui.warnings.classList.remove("hidden");
}

// ----------------------------------------------------------------- execute ----

async function execute() {
  if (!state.flowFile) {
    showEvalError("Select a .py flow file first.");
    return;
  }
  if (!state.plan) {
    showEvalError("Evaluate the flow before executing.");
    return;
  }
  hideEvalError();
  ui.execute.disabled = true;
  ui.cancel.disabled = false;
  ui.cancel.classList.remove("hidden");
  ui.resultBanner.classList.add("hidden");
  ui.resultBanner.replaceChildren();
  ui.log.replaceChildren();
  setJobStatus("starting…");
  lockRootForRun();

  try {
    const data = await postJson("/api/execute", buildPayload());
    if (!data?.job_id) throw new Error("response did not include a job_id");
    state.jobId = data.job_id;
    openStream(data.job_id);
  } catch (error) {
    setJobStatus("failed to start");
    showEvalError(`Execute failed: ${error.message}`);
    ui.cancel.classList.add("hidden");
    ui.execute.disabled = !state.plan;
    state.jobId = null;
    unlockRootAfterRun();
  }
}

function openStream(jobId) {
  if (state.source) {
    state.source.close();
    state.source = null;
  }
  const source = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/events`);
  state.source = source;

  source.addEventListener("status", (event) => {
    const data = parseEvent(event);
    setJobStatus(data?.state || "status");
  });
  source.addEventListener("log", (event) => {
    const data = parseEvent(event);
    appendLog(data?.record ?? data);
  });
  source.addEventListener("done", (event) => {
    const data = parseEvent(event);
    source.close();
    if (state.source === source) state.source = null;
    state.jobId = null;
    finishRun(data);
  });
  source.onerror = () => {
    if (state.source === source) setJobStatus("stream disconnected — retrying");
  };
}

function parseEvent(event) {
  try {
    return JSON.parse(event.data);
  } catch {
    return { text: event.data };
  }
}

function finishRun(data) {
  setJobStatus(data?.state || "done");
  showResult(data?.result, data?.state, data?.error);
  if (data?.result && Array.isArray(data.result.warnings)) {
    renderWarnings(data.result.warnings);
  }
  ui.cancel.classList.add("hidden");
  ui.cancel.disabled = false;
  ui.execute.disabled = !state.plan;
  unlockRootAfterRun();
}

function setJobStatus(text) {
  ui.jobStatus.textContent = String(text);
}

function logSummary(record) {
  if (record === null || record === undefined) return "log";
  if (typeof record !== "object") return String(record);
  const node = record.node ?? record.name ?? record.flow ?? "?";
  const status = record.status ?? record.event ?? record.state ?? record.level ?? "log";
  const duration = record.duration_ms ?? record.durationMs ?? record.elapsed_ms;
  const attempt = record.attempt != null ? ` #${record.attempt}` : "";
  const timing =
    duration === null || duration === undefined || Number.isNaN(Number(duration))
      ? ""
      : ` · ${Number(duration)} ms`;
  return `${node}${attempt} · ${status}${timing}`;
}

function appendLog(record) {
  const item = document.createElement("li");
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = logSummary(record);
  const body = document.createElement("pre");
  body.textContent = JSON.stringify(record ?? null, null, 2);
  details.append(summary, body);
  item.append(details);

  const nearBottom = ui.log.scrollHeight - ui.log.scrollTop - ui.log.clientHeight < 48;
  ui.log.append(item);
  if (nearBottom) ui.log.scrollTop = ui.log.scrollHeight;
}

function showResult(result, finalState, topError) {
  const banner = ui.resultBanner;
  banner.replaceChildren();
  banner.classList.remove("hidden", "bad");

  const run = result?.run || null;
  const failed =
    finalState !== "succeeded" ||
    result?.ok === false ||
    Boolean(topError) ||
    Boolean(result?.error);
  if (failed) banner.classList.add("bad");

  const parts = [
    ["status", run?.status ?? finalState ?? "unknown"],
    ["result", run?.result ?? null],
    ["duration", run?.duration_ms != null ? `${run.duration_ms} ms` : result?.duration_ms != null ? `${result.duration_ms} ms` : null],
    ["node", run?.node || null],
    ["attempt", run?.attempt != null ? String(run.attempt) : null],
    ["error", run?.error ?? result?.error ?? topError ?? null],
    [
      "failed nodes",
      Array.isArray(run?.failed_nodes) && run.failed_nodes.length
        ? run.failed_nodes.map((path) => (Array.isArray(path) ? path.join(" › ") : String(path))).join("; ")
        : null,
    ],
    ["log", run?.log || null],
    ["run id", run?.run_id || null],
  ];

  let shown = 0;
  for (const [key, value] of parts) {
    if (value === null || value === undefined || value === "") continue;
    const keyNode = document.createElement("span");
    keyNode.className = "key";
    keyNode.textContent = `${key}:`;
    const valueNode = document.createElement("span");
    valueNode.className = "val";
    const text = typeof value === "object" ? JSON.stringify(value) : String(value);
    valueNode.textContent = text.length > 600 ? `${text.slice(0, 597)}…` : text;
    valueNode.title = text;
    banner.append(keyNode, valueNode);
    shown += 1;
  }
  if (!shown) {
    const plain = document.createElement("span");
    plain.textContent = finalState || "done";
    banner.append(plain);
  }
}

async function cancelRun() {
  if (!state.jobId) return;
  ui.cancel.disabled = true;
  try {
    const status = await api(`/api/jobs/${encodeURIComponent(state.jobId)}/cancel`, {
      method: "POST",
    });
    setJobStatus(status?.state || "cancelling…");
  } catch (error) {
    if (error.status === 404) {
      // The job is gone (server restarted or the record was already dropped).
      if (state.source) {
        state.source.close();
        state.source = null;
      }
      state.jobId = null;
      ui.cancel.classList.add("hidden");
      setJobStatus("job already finished");
      ui.execute.disabled = !state.plan;
      unlockRootAfterRun();
    } else {
      setJobStatus("cancel failed");
      showEvalError(`Cancel failed: ${error.message}`);
    }
  } finally {
    ui.cancel.disabled = false;
  }
}

// ------------------------------------------------------------ run options ----

const OPTION_INPUTS = [
  ui.optMaxWorkers,
  ui.optRetries,
  ui.optRetryDelay,
  ui.optTimeout,
  ui.optSummary,
  ui.optFixedClock,
];

function setOptionsEnabled(enabled) {
  for (const input of OPTION_INPUTS) input.disabled = !enabled;
}

function syncOptions() {
  const options = { ...OPTION_DEFAULTS, ...(state.plan?.options || {}) };
  ui.optMaxWorkers.value = String(options.max_workers);
  ui.optRetries.value = String(options.retries);
  ui.optRetryDelay.value = String(options.retry_delay_seconds);
  ui.optTimeout.value =
    options.timeout === null || options.timeout === undefined ? "" : String(options.timeout);
  ui.optSummary.value = options.summary ? "true" : "false";
  ui.optFixedClock.value = options.fixed_clock ? "true" : "false";
}

function readOptions() {
  if (!state.plan) return;
  if (!state.plan.options) state.plan.options = { ...OPTION_DEFAULTS };
  const options = state.plan.options;
  const number = (input, integer, minimum) => {
    const text = input.value.trim();
    if (text === "") return null;
    const value = Number(text);
    if (!Number.isFinite(value) || value < minimum) return null;
    if (integer && !Number.isInteger(value)) return null;
    return value;
  };
  const maxWorkers = number(ui.optMaxWorkers, true, 1);
  if (maxWorkers !== null) options.max_workers = maxWorkers;
  const retries = number(ui.optRetries, true, 0);
  if (retries !== null) options.retries = retries;
  const retryDelay = number(ui.optRetryDelay, false, 0);
  if (retryDelay !== null) options.retry_delay_seconds = retryDelay;
  if (ui.optTimeout.value.trim() === "") {
    options.timeout = null;
  } else {
    const timeout = number(ui.optTimeout, false, 0);
    if (timeout !== null) options.timeout = timeout;
  }
  options.summary = ui.optSummary.value === "true";
  options.fixed_clock = ui.optFixedClock.value === "true";
  markDirty();
}

// ----------------------------------------------------------------- wiring ----

ui.fileList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-path]");
  if (!button) return;
  const path = button.dataset.path;
  if (button.dataset.kind === "dir") loadTree(path);
  else {
    selectFile(path).catch((error) =>
      showEvalError(`Cannot open ${path}: ${error.message}`),
    );
  }
});

ui.crumbs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-path]");
  if (button) loadTree(button.dataset.path);
});

ui.refreshTree.addEventListener("click", () => loadTree(state.dir));
ui.openRoot.addEventListener("click", switchRoot);
ui.projectRoot.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    switchRoot();
  }
});
ui.evaluate.addEventListener("click", evaluate);
ui.execute.addEventListener("click", execute);
ui.cancel.addEventListener("click", cancelRun);
ui.fitGraph.addEventListener("click", () => fitGraph(ui.graph));
ui.clearLog.addEventListener("click", () => ui.log.replaceChildren());
ui.importPlan.addEventListener("click", () => ui.planFile.click());
ui.exportPlan.addEventListener("click", exportPlan);

ui.planFile.addEventListener("change", () => {
  const file = ui.planFile.files?.[0];
  ui.planFile.value = "";
  if (!file) return;
  file
    .text()
    .then((text) => importPlanText(text, file.name))
    .catch((error) => showEvalError(`Cannot read ${file.name}: ${error.message}`));
});

ui.flowSelect.addEventListener("change", () => {
  state.flowName = ui.flowSelect.value || null;
  markDirty();
});

for (const input of OPTION_INPUTS) {
  input.addEventListener("input", readOptions);
  input.addEventListener("change", readOptions);
}

syncOptions();
setOptionsEnabled(false);

boot().catch((error) => {
  ui.health.textContent = `startup failed: ${error.message}`;
  ui.health.classList.add("bad");
});
