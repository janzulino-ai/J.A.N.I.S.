"""Test diagnostica connettività Fleet."""
from backend.core.autofix import _classify_issue
from backend.core.fleet_connectivity import (
    _listening_on_all_interfaces,
    looks_like_fleet_connection_issue,
)


def test_detect_fleet_connection_issue():
    user = "WinError 10061 sulla porta WebSocket 8001 per Fleet Mac"
    assert looks_like_fleet_connection_issue(user, "")


def test_detect_fleet_env_blame():
    bad = "Il blocco è nell'ambiente operativo, controlla il firewall."
    user = "connessione Fleet bridge Mac Mini porta 8001"
    assert looks_like_fleet_connection_issue(bad, user)


def test_classify_fleet_connection():
    issue = _classify_issue(
        "diagnostica WinError 10061 ws fleet-node 8001",
        None,
        None,
        "problema di rete firewall",
    )
    assert issue == "fleet_connection"


def test_listening_on_all_interfaces():
    lines = ["TCP    0.0.0.0:8001           0.0.0.0:0              LISTENING       1234"]
    assert _listening_on_all_interfaces(8001, lines) is True

    local = ["TCP    127.0.0.1:8001         0.0.0.0:0              LISTENING       5678"]
    assert _listening_on_all_interfaces(8001, local) is False
