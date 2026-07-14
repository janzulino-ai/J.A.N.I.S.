"""Esecuzione CLI/API a pagamento con gate budget."""
from __future__ import annotations

import asyncio
import shlex

from backend.core.paid_capabilities import check_allowed, list_capabilities, record_paid_usage
from backend.core.tools.registry import register

ALLOWED_CLI = frozenset({"gh", "cursor", "git"})


@register("paid_cli_exec")
async def paid_cli_exec(args: dict) -> str:
    capability = (args.get("capability") or args.get("name") or "").strip()
    command = (args.get("command") or "").strip()
    if not capability:
        return "capability obbligatoria (es. gh_cli, cursor_agent)"
    if not command:
        return "command obbligatorio"

    gate = check_allowed(capability)
    if not gate.get("ok"):
        return f"Bloccato: {gate.get('error')}"

    parts = shlex.split(command)
    if not parts:
        return "Comando vuoto"
    bin_name = parts[0].split("/")[-1]
    if bin_name not in ALLOWED_CLI:
        return f"CLI non in allowlist: {bin_name}. Consentiti: {', '.join(sorted(ALLOWED_CLI))}"

    try:
        proc = await asyncio.create_subprocess_exec(
            *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        est = gate.get("estimate_usd") or 0.0
        if est > 0:
            record_paid_usage(capability, est, tool="paid_cli_exec")
        stdout = out.decode(errors="replace")[:4000]
        stderr = err.decode(errors="replace")[:1000]
        if proc.returncode != 0:
            return f"Exit {proc.returncode}\n{stderr or stdout}"
        return stdout or "(ok, no output)"
    except asyncio.TimeoutError:
        return "Timeout 120s"
    except FileNotFoundError:
        return f"Comando non trovato: {parts[0]}"


@register("paid_capabilities_list")
async def paid_capabilities_list(_args: dict) -> str:
    caps = list_capabilities()
    lines = ["Catalogo paid/local capabilities:"]
    for c in caps:
        key = "✓" if c.get("key_present") else "✗"
        lines.append(f"- {c['name']} [{c['tier']}] key={key} ~${c['estimate_usd']}")
    return "\n".join(lines)
