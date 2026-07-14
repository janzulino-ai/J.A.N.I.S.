#!/usr/bin/env bash
# WireGuard server JANIS — genera wg0 + template peer per dispositivi fleet
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PEERS="$ROOT/peers"
WG_DIR="/etc/wireguard"
SUBNET="10.8.0.0/24"
SERVER_IP="10.8.0.1/24"
PORT="${WG_WG_PORT:-51820}"
LAN="${WG_LAN:-192.168.1.0/24}"
IFACE="${WG_INTERFACE:-$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}' || echo eth0)}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Esegui con sudo"
  exit 1
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
  echo "OK peer: $name → ${ip}/32 → $peer_dir/client.conf"
done

sysctl -w net.ipv4.ip_forward=1
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null || echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

systemctl enable wg-quick@wg0 2>/dev/null || true
systemctl restart wg-quick@wg0 2>/dev/null || wg-quick up wg0

echo ""
echo "Server pubkey: $SERVER_PUB"
echo "Peer configs: $PEERS/*/client.conf"
echo "Imposta WG_ENDPOINT=host:51820 prima di distribuire i client."
