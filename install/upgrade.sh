#!/usr/bin/env bash
# AstroFiler Upgrade Script (Linux)
# Runs upgrade steps in a terminal.

set -euo pipefail

# Prefer green text (terminal theme controls background)
if command -v tput >/dev/null 2>&1; then
  tput setaf 2 || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

printf "========================================\n"
printf "AstroFiler Upgrade\n"
printf "========================================\n\n"

echo "Working directory: $REPO_ROOT"
echo

echo "Running: git pull"
git pull

echo

PYTHON=""
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "Python not found. Please install Python 3 and/or run install script first." >&2
  exit 1
fi

echo "Using Python: $PYTHON"
echo

echo "Upgrading pip..."
"$PYTHON" -m pip install --upgrade pip

echo

echo "Installing requirements.txt..."
"$PYTHON" -m pip install -r "$REPO_ROOT/requirements.txt"

echo

echo "Upgrade complete."

echo "AstroFiler has been upgraded please run again"

# Best-effort GUI dialog
if command -v zenity >/dev/null 2>&1; then
  zenity --info --title="AstroFiler" --text="Astrofiler has been upgraded please run again" || true
fi

echo
read -r -p "Press Enter to close..." _
