#!/usr/bin/env bash
# Create the shared venv one level above the GUI and engine repos, then install.
# The venv is outside both repositories so neither tracks or deletes it.
# Idempotent: safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3.11
VENV=../.venv

if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
fi

"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r requirements-dev.txt

"$VENV/bin/python" -c "import seq_ext_gui, sequence_extensions"  # smoke check

echo
echo "Venv ready: $(cd "$VENV" && pwd)"
echo "  source ../.venv/bin/activate"
echo "  seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner"
