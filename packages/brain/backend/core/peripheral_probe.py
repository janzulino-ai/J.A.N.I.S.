"""Probe periferiche Linux — USB, audio, video, input, display, bluetooth."""
from __future__ import annotations

import glob
import re
from pathlib import Path


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def probe_peripherals() -> dict:
    usb = _probe_usb()
    audio = _probe_audio()
    video = _probe_video()
    displays = _probe_displays()
    bluetooth = _probe_bluetooth()
    inputs = _probe_input_devices()

    missing = []
    if not audio.get("devices"):
        missing.append("audio")
    if not video.get("devices"):
        missing.append("camera")
    if usb.get("count", 0) == 0:
        missing.append("usb")

    return {
        "usb": usb,
        "audio": audio,
        "video": video,
        "displays": displays,
        "bluetooth": bluetooth,
        "input": inputs,
        "missing": missing,
        "summary": _peripheral_summary(usb, audio, video, displays, bluetooth, inputs),
    }


def _probe_usb() -> dict:
    import subprocess
    try:
        out = subprocess.check_output(["lsusb"], stderr=subprocess.DEVNULL, text=True, timeout=5)
    except Exception:
        return {"count": 0, "devices": []}
    devices = []
    for line in out.splitlines():
        m = re.match(r"Bus (\d+) Device (\d+): ID ([0-9a-f:]+)\s*(.*)", line, re.I)
        if m:
            devices.append({
                "bus": m.group(1),
                "device": m.group(2),
                "id": m.group(3),
                "name": m.group(4).strip() or "USB device",
            })
    return {"count": len(devices), "devices": devices[:24]}


def _probe_audio() -> dict:
    devices = []
    cards = _read_text("/proc/asound/cards")
    for line in cards.splitlines():
        m = re.match(r"\s*(\d+)\s+\[([^\]]+)\]", line)
        if m:
            devices.append({"card": m.group(1), "name": m.group(2).strip()})
    capture = []
    import subprocess
    try:
        out = subprocess.check_output(["arecord", "-l"], stderr=subprocess.DEVNULL, text=True, timeout=3)
        for line in out.splitlines():
            if line.strip().startswith("card "):
                capture.append(line.strip())
    except Exception:
        pass
    return {
        "cards": len(devices),
        "devices": devices,
        "capture_lines": capture[:6],
        "ready": bool(devices),
    }


def _probe_video() -> dict:
    devices = []
    for path in sorted(glob.glob("/dev/video*")):
        devices.append({"node": path, "name": path})
    import subprocess
    try:
        out = subprocess.check_output(
            ["v4l2-ctl", "--list-devices"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=4,
        )
        parsed = []
        current = ""
        for line in out.splitlines():
            if not line.startswith("\t") and line.strip():
                current = line.strip().rstrip(":")
            elif line.startswith("\t") and current:
                parsed.append({"name": current, "node": line.strip()})
        if parsed:
            devices = parsed
    except Exception:
        pass
    return {"count": len(devices), "devices": devices[:12], "ready": bool(devices)}


def _probe_displays() -> dict:
    outputs = []
    for card in glob.glob("/sys/class/drm/card*-*/status"):
        name = Path(card).parent.name
        status = _read_text(card).strip()
        outputs.append({"connector": name, "status": status or "unknown"})
    import subprocess
    try:
        out = subprocess.check_output(
            ["xrandr", "--current"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            env={"DISPLAY": ":0"},
        )
        for line in out.splitlines():
            if " connected" in line:
                parts = line.split()
                outputs.append({
                    "connector": parts[0],
                    "status": "connected",
                    "mode": parts[2] if len(parts) > 2 else "",
                })
    except Exception:
        pass
    return {"count": len(outputs), "outputs": outputs[:8]}


def _probe_bluetooth() -> dict:
    import subprocess
    adapters = []
    try:
        out = subprocess.check_output(["hciconfig"], stderr=subprocess.DEVNULL, text=True, timeout=3)
        for block in out.split("\n\n"):
            first = block.splitlines()[0] if block.splitlines() else ""
            if first:
                adapters.append(first.strip())
    except Exception:
        pass
    return {"adapters": len(adapters), "lines": adapters[:4]}


def _probe_input_devices() -> dict:
    devices = []
    for path in sorted(glob.glob("/dev/input/by-id/*"))[:16]:
        devices.append(Path(path).name)
    return {"count": len(devices), "by_id": devices}


def _peripheral_summary(usb, audio, video, displays, bluetooth, inputs) -> str:
    parts = [
        f"USB {usb.get('count', 0)}",
        f"Audio {audio.get('cards', 0)}",
        f"Video {video.get('count', 0)}",
        f"Display {displays.get('count', 0)}",
        f"BT {bluetooth.get('adapters', 0)}",
        f"Input {inputs.get('count', 0)}",
    ]
    return " · ".join(parts)
