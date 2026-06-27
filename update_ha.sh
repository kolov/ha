#! /bin/bash
set -e
git pull

# pyscript automations
rsync -av --delete pyscript/ /homeassistant/pyscript/
/homeassistant/reload-python.sh

# ventilation limit helpers (input_number) + reload so YAML edits take effect.
# NOTE: one-time setup still required — configuration.yaml must contain
#   input_number: !include ventilation_limits.yaml
rsync -av ha-config/ventilation_limits.yaml /homeassistant/ventilation_limits.yaml
TOKEN=$(grep -oE 'Bearer [A-Za-z0-9._-]+' /homeassistant/reload-python.sh | head -1 | awk '{print $2}')
curl -s -X POST http://localhost:8123/api/services/input_number/reload \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" >/dev/null
