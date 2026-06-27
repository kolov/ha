#!/usr/bin/env bash
#
# Assemble the local HA add-on at /addons/ventilation_dashboard on the HA box.
# After running, install it from Settings -> Add-ons -> Local add-ons.
set -euo pipefail
cd "$(dirname "$0")/.."   # dashboard/

DEST=ha:/addons/ventilation_dashboard

echo "📦 add-on metadata + app source -> $DEST"
rsync -av --rsync-path="sudo rsync" addon/config.yaml addon/Dockerfile addon/run.sh "$DEST/"
rsync -av --delete --rsync-path="sudo rsync" \
  --exclude '.env' --exclude '.venv' --exclude '__pycache__' \
  backend/ "$DEST/backend/"
rsync -av --delete --rsync-path="sudo rsync" frontend/ "$DEST/frontend/"

echo "✅ Deployed. In HA: Settings → Add-ons → Add-on Store → ⋮ → Reload,"
echo "   then open 'Ventilation Dashboard' under Local add-ons → Install → set ha_token → Start."
