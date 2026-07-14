"""API VPN — stato hub WireGuard (Mode A, nessun segreto)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_HUB_LAN_IP = os.environ.get("JANIS_HUB_LAN_IP", "192.168.1.73")
_TUNNEL_SUBNET = "10.8.0.0/24"
_SERVER_TUNNEL = "10.8.0.1"
_LISTEN_PORT = int(os.environ.get("WG_WG_PORT", "51820"))
_LAN_ROUTE = os.environ.get("WG_LAN", "192.168.1.0/24")
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _wg_active() -> bool:
    try:
        proc = subprocess.run(
            ["wg", "show", "wg0"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _peer_hints() -> list[dict]:
    peers_dir = _REPO_ROOT / "infra" / "vpn" / "peers"
    out: list[dict] = []
    mapping = {
        "iphone-15-pro-max": "10.8.0.10",
        "iphone-14-pro": "10.8.0.11",
        "ipad-pro-2020": "10.8.0.12",
        "zenbook": "10.8.0.20",
    }
    for node_id, tunnel_ip in mapping.items():
        conf = peers_dir / node_id / "client.conf"
        out.append({
            "node_id": node_id,
            "tunnel_ip": tunnel_ip,
            "config_ready": conf.is_file(),
            "example": f"infra/vpn/peers/{node_id}/client.conf.example",
        })
    return out


@router.get("/api/vpn/status")
async def vpn_status():
    brain_url = f"http://{_HUB_LAN_IP}:8001"
    return {
        "mode": "A",
        "hub_node_id": "windows-pc",
        "hub_lan_ip": _HUB_LAN_IP,
        "brain_url": brain_url,
        "wireguard": {
            "server_tunnel_ip": _SERVER_TUNNEL,
            "subnet": _TUNNEL_SUBNET,
            "listen_port_udp": _LISTEN_PORT,
            "lan_route": _LAN_ROUTE,
            "active": _wg_active(),
        },
        "peers": _peer_hints(),
        "setup_hints": [
            "WSL: sudo bash infra/wsl/setup-wireguard.sh",
            "Windows: powershell -ExecutionPolicy Bypass -File infra/windows/setup-wireguard-forward.ps1",
            "Router: forward UDP 51820 to hub LAN IP (192.168.1.73)",
            "Set WG_ENDPOINT=<public_ip_or_ddns>:51820 before distributing client.conf",
            "After VPN: Pocket uses same brain URL http://192.168.1.73:8001",
        ],
        "docs": [
            "infra/vpn/README.md",
            "apps/pocket/docs/WIREGUARD-VPN-SETUP.md",
            "docs/MOBILE-OPS.md",
        ],
    }
