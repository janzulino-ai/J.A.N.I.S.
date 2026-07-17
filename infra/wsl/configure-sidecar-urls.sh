#!/usr/bin/env bash
# Imposta COMFYUI_URL / SEARXNG_URL nel .env brain verso servizi su Windows host.
set -euo pipefail

JANIS="${JANIS:-$HOME/projects/J.A.N.I.S.}"
BRAIN="${BRAIN:-$JANIS/packages/brain}"
ENV_FILE="$BRAIN/.env"

if [ ! -f "$ENV_FILE" ]; then
  cp "$BRAIN/.env.example" "$ENV_FILE"
fi

# Preferisci default route (WSL2 → Windows), poi nameserver resolv.conf
HOST_IP="$(ip route show default 2>/dev/null | awk '{print $3}' | head -1 || true)"
if [ -z "${HOST_IP:-}" ]; then
  HOST_IP="$(grep -m1 nameserver /etc/resolv.conf 2>/dev/null | awk '{print $2}' || true)"
fi
if [ -z "${HOST_IP:-}" ]; then
  echo "Impossibile rilevare IP host Windows"
  exit 1
fi

echo "Host Windows (gateway): $HOST_IP"

pick_base() {
  local port="$1"
  local path="${2:-/}"
  for base in "http://127.0.0.1:${port}" "http://${HOST_IP}:${port}"; do
    if curl -sf -m 2 "${base}${path}" >/dev/null 2>&1; then
      echo "$base"
      return 0
    fi
  done
  # default: assume Windows host
  echo "http://${HOST_IP}:${port}"
  return 0
}

COMFY="$(pick_base 8188 /system_stats)"
SEARX="$(pick_base 8080 /)"

upsert() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

upsert COMFYUI_URL "$COMFY"
upsert SEARXNG_URL "$SEARX"
upsert MCP_ENABLED true
upsert HEARTBEAT_ENABLED true
upsert DOCTOR_HEAL_ENABLED true

echo "Aggiornato $ENV_FILE"
echo "  COMFYUI_URL=$COMFY"
echo "  SEARXNG_URL=$SEARX"
echo "Riavvia il brain per applicare."
