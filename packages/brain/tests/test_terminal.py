"""Test stabilità tool terminal."""
from backend.core.tools.terminal import run_terminal


async def test_terminal_empty_cwd():
    result = await run_terminal({"command": "echo janis", "cwd": ""})
    assert "Errore" not in result.split("\n")[0]
    assert "janis" in result.lower()
