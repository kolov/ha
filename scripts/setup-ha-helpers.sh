#!/usr/bin/env bash
#
# One-time bootstrap for the ventilation limit helpers on HA.
#
# Idempotent. Run once (re-running re-seeds defaults, overwriting tuned values):
#   - copies ha-config/ventilation_limits.yaml to /homeassistant
#   - adds the `input_number: !include ventilation_limits.yaml` include to
#     configuration.yaml (backed up + validated, reverts on failure)
#   - reloads input_number
#   - seeds each helper to its default (fresh HA inits YAML helpers to their
#     min; after seeding, restore_state keeps later edits across restarts)
#
# Ongoing deploys use update_ha.sh, which syncs + reloads but does NOT re-seed.
set -euo pipefail
cd "$(dirname "$0")/.."

# helper -> default (must match LIMIT_DEFAULTS in pyscript/bathroom.py)
DEFAULTS="dehumidifier_off_humidity=50 humidity_medium_fan=55 humidity_high_fan=65 \
humidity_max_fan=75 humidity_diff_ok=6 max_fan_run_time_min=60 fan_cooldown_min=5 \
presence_off_delay_sec=180 night_start_hour=23 night_end_hour=8"

echo "📤 copying helper YAML to HA"
rsync -av --rsync-path="sudo rsync" ha-config/ventilation_limits.yaml ha:/homeassistant/ventilation_limits.yaml

echo "🔧 configuring + seeding on HA"
ssh ha "sudo DEFAULTS='$DEFAULTS' bash -s" <<'REMOTE'
set -e
CFG=/homeassistant/configuration.yaml
TOKEN=$(grep -oE 'Bearer [A-Za-z0-9._-]+' /homeassistant/reload-python.sh | head -1 | awk '{print $2}')
[ -n "$TOKEN" ] || { echo "no token in reload-python.sh"; exit 2; }

if grep -qF "ventilation_limits.yaml" "$CFG"; then
  echo "ventilation include already present"
elif grep -qE "^input_number:" "$CFG"; then
  echo "ERROR: configuration.yaml already has an input_number: section." >&2
  echo "  YAML can't have two input_number: keys — merge the helpers from" >&2
  echo "  ha-config/ventilation_limits.yaml into that section manually, then re-run." >&2
  exit 1
else
  cp "$CFG" "$CFG.pre-ventilation.bak"
  printf '\n# Ventilation/dehumidifier tunable limits\ninput_number: !include ventilation_limits.yaml\n' >> "$CFG"
  RESP=$(curl -s -X POST http://localhost:8123/api/config/core/check_config \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
  if ! echo "$RESP" | grep -qE '"result":\s*"valid"'; then
    echo "config invalid, reverting: $RESP"; cp "$CFG.pre-ventilation.bak" "$CFG"; exit 1
  fi
  echo "include added + config valid"
fi

curl -s -X POST http://localhost:8123/api/services/input_number/reload \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" >/dev/null
echo "input_number reloaded"

for pair in $DEFAULTS; do
  name=${pair%%=*}; value=${pair#*=}
  curl -s -X POST http://localhost:8123/api/services/input_number/set_value \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"entity_id\":\"input_number.$name\",\"value\":$value}" >/dev/null
  echo "  seeded $name = $value"
done
REMOTE

echo "✅ helpers configured and seeded."
