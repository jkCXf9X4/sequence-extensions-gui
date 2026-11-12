#!/usr/bin/env bash
# Create the venv and install the requirements. Idempotent: safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3.11
VENV=.venv

if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
fi

"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r requirements-dev.txt

"$VENV/bin/python" -c "import seq_ext_gui, sequence_extensions"  # smoke check

echo
echo "Venv ready: $VENV"
echo "  source $VENV/bin/activate"
echo "  seq-ext-gui --project-root ../sequence_extensions/examples/flow_runner"
