#!/usr/bin/env sh
# Add-on entrypoint: read options from the HA add-on config into env, then serve.
set -e

OPTS=/data/options.json
export HA_URL=$(python3 -c "import json;print(json.load(open('$OPTS')).get('ha_url',''))")
export HA_TOKEN=$(python3 -c "import json;print(json.load(open('$OPTS')).get('ha_token',''))")
export VM_URL=$(python3 -c "import json;print(json.load(open('$OPTS')).get('vm_url',''))")
export DASHBOARD_TOKEN=$(python3 -c "import json;print(json.load(open('$OPTS')).get('dashboard_token',''))")

if [ -z "$HA_TOKEN" ]; then
  echo "ERROR: ha_token is empty — set it in the add-on Configuration tab." >&2
  exit 1
fi

cd /app/backend
exec uvicorn app:app --host 0.0.0.0 --port 8099
