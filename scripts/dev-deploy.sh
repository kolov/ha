#!/usr/bin/env bash
#
# Fast iteration deploy — NO git round-trip.
#
# rsyncs your local pyscript/ (including uncommitted changes) straight to HA
# and reloads pyscript. Use while tweaking; commit + run deploy.sh when happy.
#
# Note: what's running on HA can drift from git when you use this. It's a
# dev-loop tool, not the source of truth.
#
# Requires the `ha` SSH host alias (see scripts/README or ~/.ssh/config).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "📤 Syncing local pyscript/ → HA…"
# --rsync-path runs the remote rsync under sudo so it can write the
# root-owned /homeassistant/pyscript directory.
rsync -av --delete --rsync-path="sudo rsync" pyscript/ ha:/homeassistant/pyscript/

echo "♻️  Reloading pyscript…"
ssh ha 'sudo /homeassistant/reload-python.sh'

echo "✅ Dev-deployed (working tree)."
