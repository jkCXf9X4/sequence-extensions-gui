// Self-contained SVG layered DAG renderer. No dependencies, no innerHTML.
//
// Orientation: an edge is `from` -> `to`, where `from` depends on `to`
// (dependent -> dependency). A node's layer is the longest path from that node
// to a sink while following those edges, so a node with no dependencies is at
// layer 0 and dependents get larger layers. Layers are drawn top-to-bottom in
// reverse: dependents above, dependencies below. Arrowheads therefore point
// downward "depends on".

const NS = "http://www.w3.org/2000/svg";
const NODE_W = 212;
const NODE_H = 96;
const COL_GAP = 36;
const ROW_GAP = 58;
const stateBySvg = new WeakMap();
let markerSeq = 0;

function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== null) node.setAttribute(key, String(value));
  }
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function short(value, limit) {
  let text;
  if (value === null || value === undefined) {
    text = String(value);
  } else if (typeof value === "object") {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  } else {
    text = String(value);
  }
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

function edgeEnds(edge) {
  return { from: edge.from ?? edge.source, to: edge.to ?? edge.target };
}

function clip(value, limit) {
  const text = String(value ?? "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

export function renderGraph(svg, plan, options = {}) {
  const previous = stateBySvg.get(svg);
  if (previous?.dispose) previous.dispose();
  clear(svg);
  svg.classList.remove("panning");

  const nodes = Array.isArray(plan?.nodes) ? plan.nodes : [];
  const edges = Array.isArray(plan?.edges) ? plan.edges : [];
  const state = { transform: null, width: 0, height: 0, dispose: null, justDragged: false, fit: null };
  stateBySvg.set(svg, state);

  if (nodes.length === 0) {
    const note = el("text", { class: "graph-note", x: 28, y: 46 });
    note.textContent = options.emptyText || "No nodes — this flow has a plain root.";
    svg.append(note);
    return;
  }

  const byId = new Map();
  for (const node of nodes) byId.set(String(node.id), node);

  const deps = new Map();
  for (const node of nodes) deps.set(String(node.id), []);
  for (const edge of edges) {
    const { from, to } = edgeEnds(edge);
    if (from === undefined || to === undefined) continue;
    const source = String(from);
    const target = String(to);
    if (!byId.has(source) || !byId.has(target)) continue;
    deps.get(source).push(target);
  }

  const memo = new Map();
  const visiting = new Set();
  function rank(id) {
    if (memo.has(id)) return memo.get(id);
    if (visiting.has(id)) return 0; // defensive: plans should be acyclic
    visiting.add(id);
    let best = 0;
    for (const dep of deps.get(id) || []) best = Math.max(best, 1 + rank(dep));
    visiting.delete(id);
    memo.set(id, best);
    return best;
  }

  const ranks = new Map();
  let maxRank = 0;
  for (const node of nodes) {
    const value = rank(String(node.id));
    ranks.set(String(node.id), value);
    maxRank = Math.max(maxRank, value);
  }

  const rows = new Map();
  for (const node of nodes) {
    const value = ranks.get(String(node.id));
    if (!rows.has(value)) rows.set(value, []);
    rows.get(value).push(node);
  }
  for (const row of rows.values()) {
    row.sort((a, b) => String(a.id).localeCompare(String(b.id), undefined, { numeric: true }));
  }

  const widest = Math.max(...[...rows.values()].map((row) => row.length));
  const width = widest * NODE_W + (widest - 1) * COL_GAP;
  const height = (maxRank + 1) * NODE_H + maxRank * ROW_GAP;
  state.width = width;
  state.height = height;

  const positions = new Map();
  for (const [layer, row] of rows) {
    const rowWidth = row.length * NODE_W + (row.length - 1) * COL_GAP;
    const startX = (width - rowWidth) / 2;
    const y = (maxRank - layer) * (NODE_H + ROW_GAP);
    row.forEach((node, index) => {
      positions.set(String(node.id), { x: startX + index * (NODE_W + COL_GAP), y });
    });
  }

  markerSeq += 1;
  const markerId = `graph-arrow-${markerSeq}`;
  const defs = el("defs");
  const marker = el("marker", {
    id: markerId,
    markerWidth: 8,
    markerHeight: 8,
    refX: 7,
    refY: 3,
    orient: "auto",
  });
  marker.append(el("path", { class: "edge-arrow", d: "M0,0 L7,3 L0,6 Z" }));
  defs.append(marker);
  svg.append(defs);

  const viewport = el("g", { class: "viewport" });
  svg.append(viewport);
  const transform = { k: 1, x: 0, y: 0 };
  state.transform = transform;

  function applyTransform() {
    viewport.setAttribute(
      "transform",
      `translate(${transform.x} ${transform.y}) scale(${transform.k})`,
    );
  }

  for (const edge of edges) {
    const { from, to } = edgeEnds(edge);
    if (from === undefined || to === undefined) continue;
    const source = positions.get(String(from));
    const target = positions.get(String(to));
    if (!source || !target) continue;
    const x1 = source.x + NODE_W / 2;
    const y1 = source.y + NODE_H;
    const x2 = target.x + NODE_W / 2;
    const y2 = target.y - 2;
    const midY = (y1 + y2) / 2;
    const path = el("path", {
      class: "edge",
      d: `M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}`,
      "marker-end": `url(#${markerId})`,
    });
    viewport.append(path);
  }

  const selected = options.selectedId === undefined || options.selectedId === null
    ? null
    : String(options.selectedId);

  for (const node of nodes) {
    const pos = positions.get(String(node.id));
    if (!pos) continue;
    const nodeId = String(node.id);
    const name = String(node.name ?? nodeId);
    const kind = String(node.kind ?? "node");
    const instance = node.instance ?? 1;
    const params = (node.params || []).map((param) => {
      return `${param.name}=${short(param.value ?? param.default, 14)}`;
    });
    const paramText = params.length ? clip(params.join(", "), 34) : "no parameters";
    const fullParams = params.length ? params.join(", ") : "no parameters";

    const group = el("g", {
      class: `graph-node${nodeId === selected ? " selected" : ""}`,
      transform: `translate(${pos.x} ${pos.y})`,
      "data-node-id": nodeId,
      tabindex: "0",
      role: "button",
      "aria-label": `${name}, instance ${instance}, ${kind}. Select to edit parameters.`,
    });
    group.append(el("rect", { class: "node-box", width: NODE_W, height: NODE_H, rx: 8, ry: 8 }));

    const nameText = el("text", { class: "node-name", x: 12, y: 24 });
    nameText.textContent = clip(name, 24);
    group.append(nameText);

    const meta = el("text", { class: "node-meta", x: 12, y: 42 });
    meta.textContent = `#${instance} · ${kind}`;
    group.append(meta);

    const paramLine = el("text", { class: "node-params", x: 12, y: 62 });
    paramLine.textContent = paramText;
    group.append(paramLine);

    const policy = node.policy || {};
    const policyLine = el("text", { class: "node-params", x: 12, y: 78 });
    policyLine.textContent = clip(
      `retries=${policy.retries ?? 0} timeout=${policy.timeout ?? "—"}`,
      34,
    );
    group.append(policyLine);

    const title = el("title");
    title.textContent = `${name} (#${instance}, ${kind})\n${fullParams}`;
    group.append(title);

    group.addEventListener("click", (event) => {
      if (state.justDragged) return;
      event.stopPropagation();
      if (typeof options.onSelect === "function") options.onSelect(node.id);
    });
    group.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      if (typeof options.onSelect === "function") options.onSelect(node.id);
    });

    viewport.append(group);
  }

  function fit() {
    const box = svg.getBoundingClientRect();
    const cw = box.width || svg.clientWidth || 900;
    const ch = box.height || svg.clientHeight || 600;
    const pad = 32;
    const scale = Math.min(
      1.25,
      Math.max(0.12, Math.min((cw - pad * 2) / width, (ch - pad * 2) / height)),
    );
    transform.k = scale;
    transform.x = (cw - width * scale) / 2;
    transform.y = (ch - height * scale) / 2;
    applyTransform();
  }
  state.fit = fit;
  fit();

  let drag = null;
  const onPointerDown = (event) => {
    if (event.button !== 0) return;
    drag = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      startX: transform.x,
      startY: transform.y,
      moved: false,
    };
    try {
      svg.setPointerCapture(event.pointerId);
    } catch {
      /* pointer capture is best-effort */
    }
  };
  const onPointerMove = (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    transform.x = drag.startX + dx;
    transform.y = drag.startY + dy;
    applyTransform();
  };
  const onPointerUp = (event) => {
    if (!drag) return;
    try {
      svg.releasePointerCapture(drag.pointerId);
    } catch {
      /* pointer capture is best-effort */
    }
    state.justDragged = drag.moved;
    window.setTimeout(() => {
      state.justDragged = false;
    }, 0);
    drag = null;
    svg.classList.remove("panning");
  };
  const onPointerCancel = () => {
    drag = null;
    svg.classList.remove("panning");
  };
  const onWheel = (event) => {
    event.preventDefault();
    const box = svg.getBoundingClientRect();
    const px = event.clientX - box.left;
    const py = event.clientY - box.top;
    const next = Math.min(3, Math.max(0.12, transform.k * Math.exp(-event.deltaY * 0.0015)));
    transform.x = px - ((px - transform.x) * next) / transform.k;
    transform.y = py - ((py - transform.y) * next) / transform.k;
    transform.k = next;
    applyTransform();
  };

  svg.addEventListener("pointerdown", onPointerDown);
  svg.addEventListener("pointermove", onPointerMove);
  svg.addEventListener("pointerup", onPointerUp);
  svg.addEventListener("pointercancel", onPointerCancel);
  svg.addEventListener("wheel", onWheel, { passive: false });

  state.dispose = () => {
    svg.removeEventListener("pointerdown", onPointerDown);
    svg.removeEventListener("pointermove", onPointerMove);
    svg.removeEventListener("pointerup", onPointerUp);
    svg.removeEventListener("pointercancel", onPointerCancel);
    svg.removeEventListener("wheel", onWheel);
  };
}

export function fitGraph(svg) {
  const state = stateBySvg.get(svg);
  if (state?.fit) state.fit();
}

export function selectGraphNode(svg, id) {
  const wanted = id === undefined || id === null ? null : String(id);
  for (const group of svg.querySelectorAll(".graph-node")) {
    group.classList.toggle("selected", group.getAttribute("data-node-id") === wanted);
  }
}
