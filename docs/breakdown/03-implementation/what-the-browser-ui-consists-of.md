---
id: INFO-016
type: info
title: What the browser UI consists of
summary: Four static files, TOML textarea, SVG graph, no build step
date: 2026-11-12
status: current
---

# What the browser UI consists of

The UI is four static files of vanilla JavaScript and CSS, loaded directly with no build or network step.

- **Files:** `index.html`, `app.js`, `graph.js`, `styles.css`; `app.js` imports `graph.js` as an ES module.
- **Editor:** a monospace textarea loads `.toml`, tracks dirtiness, and saves through `PUT /api/file` (`INFO-013`).
- **Graph:** `graph.js` renders the SVG DAG and reports selection through `data-node-id`.
- **Parameters:** type-driven widgets — checkbox, number, text, JSON textarea; read-only ones are disabled with a note.
- **Stream:** an `EventSource` appends `log` records and shows `status` and `done`.
- **Safety:** engine text reaches the DOM through `textContent`; no `innerHTML`, no CDN.
