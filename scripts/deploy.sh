#!/usr/bin/env bash
#
# Ship the current branch to Home Assistant in one command.
#
# Pushes the current branch to origin, then has HA check it out, pull,
# rsync pyscript/ into place, and reload pyscript — the same steps as the
# manual web-terminal flow, run over SSH as `assen` with sudo.
#
# Requires the `ha` SSH host alias (see scripts/README or ~/.ssh/config).
set -euo pipefail

branch=$(git rev-parse --abbrev-ref HEAD)

echo "⬆️  Pushing $branch to origin…"
git push origin "$branch"

echo "🚀 Deploying on HA (fetch + checkout $branch + update_ha.sh)…"
ssh ha "cd /homeassistant/ha && sudo git fetch origin $branch && sudo git checkout -B $branch origin/$branch && sudo ./update_ha.sh"

echo "✅ Deployed $branch."
