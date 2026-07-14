(function () {
  const panel = document.getElementById("hud-terminal");
  const log = document.getElementById("hud-term-log");
  const form = document.getElementById("hud-term-form");
  const input = document.getElementById("hud-term-input");
  const toggle = document.getElementById("term-toggle");
  const closeBtn = document.getElementById("term-close");
  const shellSel = document.getElementById("hud-term-shell");
  if (!panel || !log || !form || !input) return;

  const history = [];
  let histIdx = -1;

  function promptForShell() {
    return (shellSel && shellSel.value) || "wsl";
  }

  function appendBlock(text, cls) {
    const pre = document.createElement("pre");
    pre.className = "term-block " + (cls || "out");
    pre.textContent = text;
    log.appendChild(pre);
    log.scrollTop = log.scrollHeight;
  }

  function appendPrompt(cmd) {
    const p = document.createElement("div");
    p.className = "term-prompt";
    const shell = promptForShell().toUpperCase();
    p.textContent = `[${shell}] $ ${cmd}`;
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
  }

  async function runCommand(cmd) {
    appendPrompt(cmd);
    history.push(cmd);
    histIdx = history.length;

    const shell = promptForShell();
    appendBlock("… esecuzione …", "pending");

    try {
      const r = await fetch("/api/hud/terminal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd, shell }),
      });
      const data = await r.json();
      const pending = log.querySelector(".term-block.pending");
      if (pending) pending.remove();

      if (!data.ok) {
        appendBlock(data.error || "Errore sconosciuto", "err");
        return;
      }
      appendBlock(data.output || "(nessun output)", "out");
    } catch (e) {
      const pending = log.querySelector(".term-block.pending");
      if (pending) pending.remove();
      appendBlock("Errore rete: " + (e.message || "fetch fallita"), "err");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const cmd = input.value.trim();
    if (!cmd) return;
    input.value = "";
    runCommand(cmd);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!history.length) return;
      histIdx = Math.max(0, histIdx - 1);
      input.value = history[histIdx] || "";
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!history.length) return;
      histIdx = Math.min(history.length, histIdx + 1);
      input.value = histIdx >= history.length ? "" : history[histIdx];
    }
  });

  if (toggle) {
    toggle.addEventListener("click", () => {
      panel.classList.toggle("hidden");
      if (!panel.classList.contains("hidden")) {
        input.focus();
        if (!log.childElementCount) {
          appendBlock(
            "Terminale HUD — comandi sul brain (WSL) o Windows (PowerShell).\n" +
              "Esempi: ls -la | pwd | curl -s http://127.0.0.1:8001/api/status",
            "hint"
          );
        }
      }
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", () => panel.classList.add("hidden"));
  }
})();
