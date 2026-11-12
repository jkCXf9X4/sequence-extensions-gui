// Browser UI for the sequence_extensions flow engine. Vanilla ES module.
// All engine-provided text is inserted with textContent; there is no innerHTML.

import { fitGraph, renderGraph, selectGraphNode } from "./graph.js";

const $ = (id) => document.getElementById(id);

const ui = {
  health: $("health"),
  crumbs: $("crumbs"),
  fileList: $("file-list"),
  refreshTree: $("refresh-tree"),
  flowFile: $("flow-file"),
  flowSelect: $("flow-select"),
  configFile: $("config-file"),
  toml: $("toml-editor"),
  save: $("save-config"),
  saveStatus: $("save-status"),
  evaluate: $("evaluate"),
  evalError: $("eval-error"),
  warnings: $("warnings"),
  graph: $("graph"),
  graphEmpty: $("graph-empty"),
  fitGraph: $("fit-graph"),
  execute: $("execute"),
  cancel: $("cancel"),
  dirtyHint: $("dirty-hint"),
  rootNode: $("root-node"),
  rootEditor: $("root-editor"),
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

const state = {
  projectRoot: "",
  dir: "",
  entries: [],
  flowFile: null,
  configFile: null,
  configText: "",
  flowName: null,
  plan: null,
  selectedId: null,
  overrides: emptyOverrides(),
  dirty: false,
  jobId: null,
  source: null,
};

let widgetSeq = 0;

function emptyOverrides() {
  return { root: {}, nodes: {}, policy: {}, node_defaults: null, options: null };
}

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

function flowDir(path) {
  if (!path) return null;
  const index = path.lastIndexOf("/");
  return index >= 0 ? path.slice(0, index) : null;
}

// ---------------------------------------------------------------- startup ----

async function boot() {
  try {
    const health = await api("/api/health");
    state.projectRoot = health.project_root || "";
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
    ui.fileList.append(message("No .py or .toml files here.", "empty"));
    return;
  }
  for (const entry of entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "file-entry";
    button.dataset.path = entry.path;
    button.dataset.kind = entry.kind;
    button.setAttribute("role", "option");
    const selected = entry.path === state.flowFile || entry.path === state.configFile;
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
      resetPlan({ keepOverrides: false });
    }
    renderFiles(state.entries);
    return;
  }
  if (lower.endsWith(".toml")) {
    try {
      const data = await api(`/api/file?path=${encodeURIComponent(path)}`);
      state.configFile = path;
      state.configText = data?.content ?? "";
      ui.configFile.textContent = path;
      ui.toml.value = state.configText;
      ui.save.disabled = false;
      ui.saveStatus.textContent = "";
      markDirty();
      renderFiles(state.entries);
    } catch (error) {
      showEvalError(`Cannot load ${path}: ${error.message}`);
    }
  }
}

function resetPlan({ keepOverrides }) {
  state.plan = null;
  state.selectedId = null;
  state.dirty = false;
  if (!keepOverrides) state.overrides = emptyOverrides();
  ui.execute.disabled = true;
  ui.dirtyHint.classList.add("hidden");
  ui.graphEmpty.classList.remove("hidden");
  ui.graphEmpty.textContent = "Evaluate a flow to see its graph";
  ui.rootNode.textContent = "";
  ui.selectedNode.textContent = "none";
  ui.rootEditor.replaceChildren(message("No plan loaded.", "muted"));
  ui.nodeEditor.replaceChildren(message("Select a node in the graph.", "muted"));
  renderGraph(ui.graph, null);
  readOptions();
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

function buildPayload() {
  reconcileOverrides();
  // The config's directory drives TOML-relative paths; "." means the project root.
  const cwd = state.configFile
    ? (flowDir(state.configFile) ?? ".")
    : flowDir(state.flowFile);
  return {
    flow_file: state.flowFile,
    config_file: state.configFile || null,
    config_text: state.configFile ? state.configText : null,
    flow_name: state.flowName || null,
    cwd,
    overrides: JSON.parse(JSON.stringify(state.overrides)),
  };
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
    resetPlan({ keepOverrides: true });
    return;
  }
  if (Array.isArray(result.available_flows)) populateFlowSelect(result.available_flows);
  renderWarnings(result.warnings);

  if (!result.ok) {
    showEvalError(result.error || "Evaluate failed.", result.traceback);
    resetPlan({ keepOverrides: true });
    return;
  }
  if (!result.plan) {
    showEvalError("Evaluate succeeded but returned no plan.");
    resetPlan({ keepOverrides: true });
    return;
  }

  hideEvalError();
  state.plan = result.plan;
  state.selectedId = null;
  state.dirty = false;
  reconcileOverrides();
  ui.dirtyHint.classList.add("hidden");
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
  ui.graphEmpty.classList.add("hidden");
  ui.rootNode.textContent = state.plan.root || "";
  ui.execute.disabled = false;
  renderGraph(ui.graph, state.plan, {
    onSelect: selectNode,
    selectedId: null,
    emptyText: "Root flow — no child nodes.",
  });
  renderRootEditor();
  renderNodeEditor();
}

function selectNode(id) {
  state.selectedId = id;
  selectGraphNode(ui.graph, id);
  renderNodeEditor();
}

// -------------------------------------------------------- parameter editor ----

function sameValue(left, right) {
  if (left === right) return true;
  if (left === null || right === null || left === undefined || right === undefined) return false;
  if (typeof left === "object" && typeof right === "object") {
    try {
      return JSON.stringify(left) === JSON.stringify(right);
    } catch {
      return false;
    }
  }
  return false;
}

function hasOverride(origin, owner, name) {
  if (origin === "root") {
    return Object.prototype.hasOwnProperty.call(state.overrides.root, name);
  }
  const bag = state.overrides.nodes[owner];
  return Boolean(bag && Object.prototype.hasOwnProperty.call(bag, name));
}

function currentOverride(origin, owner, name) {
  if (origin === "root") return state.overrides.root[name];
  return state.overrides.nodes[owner]?.[name];
}

function deleteOverride(origin, owner, name) {
  if (origin === "root") {
    delete state.overrides.root[name];
    return;
  }
  const bag = state.overrides.nodes[owner];
  if (!bag) return;
  delete bag[name];
  if (!Object.keys(bag).length) delete state.overrides.nodes[owner];
}

// Drop overrides the current plan would not accept: read-only params and nodes
// that no longer exist must never be sent back to the engine.
function reconcileOverrides() {
  const plan = state.plan;
  if (!plan) return;
  const rootParams = Array.isArray(plan.parameters) ? plan.parameters : [];
  const editableRoot = new Set(
    rootParams.filter((param) => param && param.editable !== false).map((param) => param.name),
  );
  for (const name of Object.keys(state.overrides.root)) {
    if (!editableRoot.has(name)) delete state.overrides.root[name];
  }

  const editableByNode = new Map();
  for (const node of Array.isArray(plan.nodes) ? plan.nodes : []) {
    if (!node || typeof node.name !== "string") continue;
    let names = editableByNode.get(node.name);
    if (!names) {
      names = new Set();
      editableByNode.set(node.name, names);
    }
    for (const param of Array.isArray(node.params) ? node.params : []) {
      if (param && param.editable !== false) names.add(param.name);
    }
  }

  for (const owner of Object.keys(state.overrides.nodes)) {
    const bag = state.overrides.nodes[owner];
    const allowed = editableByNode.get(owner);
    if (!bag || !allowed) {
      delete state.overrides.nodes[owner];
      continue;
    }
    for (const name of Object.keys(bag)) {
      if (!allowed.has(name)) delete bag[name];
    }
    if (!Object.keys(bag).length) delete state.overrides.nodes[owner];
  }

  for (const owner of Object.keys(state.overrides.policy)) {
    if (!editableByNode.has(owner)) delete state.overrides.policy[owner];
  }
}

function setOverride(origin, owner, name, value, original) {
  if (sameValue(value, original)) {
    if (hasOverride(origin, owner, name)) deleteOverride(origin, owner, name);
    markDirty();
    return;
  }
  if (origin === "root") {
    state.overrides.root[name] = value;
  } else {
    const bag = state.overrides.nodes[owner] || {};
    bag[name] = value;
    state.overrides.nodes[owner] = bag;
  }
  markDirty();
}

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

function buildParam(param, origin, owner) {
  const editable = param.editable !== false;
  const kind = widgetKind(param.type);
  const value = hasOverride(origin, owner, param.name)
    ? currentOverride(origin, owner, param.name)
    : param.value;

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
      setOverride(origin, owner, param.name, input.checked, param.value);
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
      setOverride(origin, owner, param.name, number, param.value);
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
        setOverride(origin, owner, param.name, parsed, param.value);
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
      setOverride(origin, owner, param.name, input.value, param.value);
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

function renderRootEditor() {
  ui.rootEditor.replaceChildren();
  const params = state.plan?.parameters || [];
  if (!params.length) {
    ui.rootEditor.append(message("No flow inputs.", "muted"));
    return;
  }
  const rootName = state.plan.root || "root";
  for (const param of params) ui.rootEditor.append(buildParam(param, "root", rootName));
}

function renderNodeEditor() {
  ui.nodeEditor.replaceChildren();
  if (!state.plan) {
    ui.selectedNode.textContent = "none";
    ui.nodeEditor.append(message("Select a node in the graph.", "muted"));
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
    for (const param of params) ui.nodeEditor.append(buildParam(param, "node", node.name));
  }
  ui.nodeEditor.append(buildPolicyEditor(node));
}

function parsePolicyField(text, kind) {
  if (text.trim() === "") return { empty: true };
  const number = Number(text);
  if (!Number.isFinite(number) || (kind === "int" && !Number.isInteger(number))) {
    return { error: kind === "int" ? "not an integer" : "not a number" };
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
  const policy = state.overrides.policy[node.name] || {};
  const fields = [
    ["retries", node.policy?.retries ?? 0, "int"],
    ["retry_delay_seconds", node.policy?.retry_delay_seconds ?? 0, "float"],
    ["timeout", node.policy?.timeout ?? null, "float"],
  ];

  for (const [key, original, kind] of fields) {
    const label = document.createElement("label");
    const inputId = nextId("policy");
    label.htmlFor = inputId;
    label.textContent = key;
    const input = document.createElement("input");
    input.type = "number";
    input.id = inputId;
    input.step = kind === "int" ? "1" : "any";
    input.min = "0";
    input.placeholder = key === "timeout" ? "inherit" : String(original ?? "");
    const current = Object.prototype.hasOwnProperty.call(policy, key) ? policy[key] : original;
    input.value = current === null || current === undefined ? "" : String(current);

    const error = document.createElement("div");
    error.className = "field-error hidden";
    error.setAttribute("role", "alert");

    input.addEventListener("input", () => {
      const parsed = parsePolicyField(input.value, kind);
      const bag = state.overrides.policy[node.name] || {};
      if (parsed.error) {
        error.textContent = parsed.error;
        error.classList.remove("hidden");
        return;
      }
      error.classList.add("hidden");
      const existed = Object.prototype.hasOwnProperty.call(bag, key);
      if (parsed.empty) {
        delete bag[key];
      } else if (existed || !sameValue(parsed.value, original)) {
        bag[key] = parsed.value;
      }
      if (Object.keys(bag).length) state.overrides.policy[node.name] = bag;
      else delete state.overrides.policy[node.name];
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
    } else {
      setJobStatus("cancel failed");
      showEvalError(`Cancel failed: ${error.message}`);
    }
  } finally {
    ui.cancel.disabled = false;
  }
}

// ------------------------------------------------------------ run options ----

function readOptions() {
  const options = {};
  const number = (input, integer) => {
    const text = input.value.trim();
    if (text === "") return null;
    const value = Number(text);
    if (!Number.isFinite(value) || (integer && !Number.isInteger(value))) return null;
    return value;
  };
  const maxWorkers = number(ui.optMaxWorkers, true);
  const retries = number(ui.optRetries, true);
  const retryDelay = number(ui.optRetryDelay, false);
  const timeout = number(ui.optTimeout, false);
  if (maxWorkers !== null) options.max_workers = maxWorkers;
  if (retries !== null) options.retries = retries;
  if (retryDelay !== null) options.retry_delay_seconds = retryDelay;
  if (timeout !== null) options.timeout = timeout;
  if (ui.optSummary.value !== "") options.summary = ui.optSummary.value === "true";
  if (ui.optFixedClock.value !== "") options.fixed_clock = ui.optFixedClock.value === "true";
  state.overrides.options = Object.keys(options).length ? options : null;
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
ui.save.addEventListener("click", saveConfig);
ui.evaluate.addEventListener("click", evaluate);
ui.execute.addEventListener("click", execute);
ui.cancel.addEventListener("click", cancelRun);
ui.fitGraph.addEventListener("click", () => fitGraph(ui.graph));
ui.clearLog.addEventListener("click", () => ui.log.replaceChildren());

ui.flowSelect.addEventListener("change", () => {
  state.flowName = ui.flowSelect.value || null;
  markDirty();
});

ui.toml.addEventListener("input", () => {
  state.configText = ui.toml.value;
  markDirty();
});

ui.toml.addEventListener("keydown", (event) => {
  if (event.key !== "Tab" || event.shiftKey) return;
  event.preventDefault();
  const start = ui.toml.selectionStart;
  const end = ui.toml.selectionEnd;
  const text = ui.toml.value;
  ui.toml.value = `${text.slice(0, start)}  ${text.slice(end)}`;
  ui.toml.selectionStart = start + 2;
  ui.toml.selectionEnd = start + 2;
  state.configText = ui.toml.value;
  markDirty();
});

async function saveConfig() {
  if (!state.configFile) return;
  ui.save.disabled = true;
  ui.saveStatus.textContent = "saving…";
  try {
    await api(`/api/file?path=${encodeURIComponent(state.configFile)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: state.configText }),
    });
    ui.saveStatus.textContent = "saved";
  } catch (error) {
    ui.saveStatus.textContent = "save failed";
    showEvalError(`Save failed: ${error.message}`);
  } finally {
    ui.save.disabled = false;
  }
}

for (const input of [
  ui.optMaxWorkers,
  ui.optRetries,
  ui.optRetryDelay,
  ui.optTimeout,
  ui.optSummary,
  ui.optFixedClock,
]) {
  input.addEventListener("input", readOptions);
  input.addEventListener("change", readOptions);
}

boot().catch((error) => {
  ui.health.textContent = `startup failed: ${error.message}`;
  ui.health.classList.add("bad");
});
