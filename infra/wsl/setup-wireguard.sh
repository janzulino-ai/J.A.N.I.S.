#!/usr/bin/env bash
# WireGuard server JANIS — Mode A hub (Windows PC / WSL brain)
# Tunnel 10.8.0.1 · UDP 51820 · route LAN 192.168.1.0/24 → brain http://192.168.1.73:8001
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PEERS="$REPO_ROOT/infra/vpn/peers"
WG_DIR="/etc/wireguard"
SUBNET="10.8.0.0/24"
SERVER_IP="10.8.0.1/24"
PORT="${WG_WG_PORT:-51820}"
LAN="${WG_LAN:-192.168.1.0/24}"
HUB_LAN_IP="${JANIS_HUB_LAN_IP:-192.168.1.73}"
IFACE="${WG_INTERFACE:-$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}' || echo eth0)}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con: sudo bash infra/wsl/setup-wireguard.sh"
  exit 1
fi

if ! command -v wg >/dev/null 2>&1; then
  echo "Installazione WireGuard..."
  apt-get update -qq
  apt-get install -y wireguard wireguard-tools iptables
fi

mkdir -p "$PEERS" "$WG_DIR"
chmod 700 "$PEERS"

genkey() { wg genkey; }
pubkey() { wg pubkey; }

if [ ! -f "$WG_DIR/server.key" ]; then
  genkey | tee "$WG_DIR/server.key" | pubkey > "$WG_DIR/server.pub"
  chmod 600 "$WG_DIR/server.key"
fi

SERVER_PRIV="$(cat "$WG_DIR/server.key")"
SERVER_PUB="$(cat "$WG_DIR/server.pub")"

declare -A PEER_MAP=(
  [iphone-15-pro-max]=10.8.0.10
  [iphone-14-pro]=10.8.0.11
  [ipad-pro-2020]=10.8.0.12
  [zenbook]=10.8.0.20
)

cat > "$WG_DIR/wg0.conf" <<EOF
[Interface]
Address = $SERVER_IP
ListenPort = $PORT
PrivateKey = $SERVER_PRIV
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o $IFACE -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o $IFACE -j MASQUERADE
EOF

for name in "${!PEER_MAP[@]}"; do
  ip="${PEER_MAP[$name]}"
  peer_dir="$PEERS/$name"
  mkdir -p "$peer_dir"
  if [ ! -f "$peer_dir/private.key" ]; then
    genkey | tee "$peer_dir/private.key" | pubkey > "$peer_dir/public.key"
    chmod 600 "$peer_dir/private.key"
  fi
  peer_priv="$(cat "$peer_dir/private.key")"
  peer_pub="$(cat "$peer_dir/public.key")"
  cat >> "$WG_DIR/wg0.conf" <<EOF

[Peer]
# $name
PublicKey = $peer_pub
AllowedIPs = ${ip}/32
EOF
  ENDPOINT="${WG_ENDPOINT:-YOUR_PUBLIC_IP_OR_DDNS}:${PORT}"
  cat > "$peer_dir/client.conf" <<EOF
[Interface]
PrivateKey = $peer_priv
Address = ${ip}/32
DNS = 192.168.1.1

[Peer]
PublicKey = $SERVER_PUB
Endpoint = $ENDPOINT
AllowedIPs = $LAN
PersistentKeepalive = 25
EOF
  cat > "$peer_dir/client.conf.example" <<EOF
[Interface]
PrivateKey = <PEER_PRIVATE_KEY>
Address = ${ip}/32
DNS = 192.168.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <YOUR_PUBLIC_IP_OR_DDNS>:${PORT}
AllowedIPs = ${LAN}
PersistentKeepalive = 25
EOF
  echo "OK peer: $name → ${ip}/32 → $peer_dir/client.conf"
done

sysctl -w net.ipv4.ip_forward=1
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

if systemctl is-enabled wg-quick@wg0 >/dev/null 2>&1; then
  systemctl restart wg-quick@wg0
elif command -v wg-quick >/dev/null 2>&1; then
  wg-quick down wg0 2>/dev/null || true
  wg-quick up wg0
else
  echo "WARN: wg-quick non disponibile — avvia manualmente: sudo wg-quick up wg0"
fi

echo ""
echo "=== WireGuard WSL (Mode A) ==="
echo "Hub LAN IP:    $HUB_LAN_IP"
echo "Brain URL:     http://${HUB_LAN_IP}:8001"
echo "Server pubkey: $SERVER_PUB"
echo "Peer configs:  $PEERS/*/client.conf"
echo ""
echo "Prossimi passi (Windows host):"
echo "  powershell -ExecutionPolicy Bypass -File infra/windows/setup-wireguard-forward.ps1"
echo "  Router: forward UDP ${PORT} → ${HUB_LAN_IP}"
echo "  Imposta WG_ENDPOINT=<DDNS_o_IP_pubblico>:${PORT} e rigenera client se serve."
