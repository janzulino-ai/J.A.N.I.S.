(function () {
  const panel = document.getElementById("hud-chat");
  const log = document.getElementById("hud-chat-log");
  const form = document.getElementById("hud-chat-form");
  const input = document.getElementById("hud-chat-input");
  const toggle = document.getElementById("chat-toggle");
  const closeBtn = document.getElementById("chat-close");
  const wsStatus = document.getElementById("chat-ws-status");
  if (!panel || !log || !form || !input) return;

  let ws = null;
  let streamBuf = "";
  let streamEl = null;
  let reconnectTimer = null;

  function line(role, text) {
    const d = document.createElement("div");
    d.className = "chat-line " + role;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  function setWs(on) {
    if (!wsStatus) return;
    wsStatus.className = "chat-ws " + (on ? "on" : "off");
    wsStatus.textContent = on ? "WS OK" : "HTTP";
  }

  function emitBrain(msg) {
    window.dispatchEvent(new CustomEvent("janis:brain", { detail: msg }));
    if (window.JanisNeuralLive && window.JanisNeuralLive.onBrainEvent) {
      window.JanisNeuralLive.onBrainEvent(msg);
    }
    if (msg.type === "tool_start") {
      const el = document.getElementById("hud-live-tool");
      if (el) el.textContent = msg.tool ? "▸ " + msg.tool : "";
    }
    if (msg.type === "chat_end" || (msg.type === "state" && msg.state === "IDLE")) {
      const el = document.getElementById("hud-live-tool");
      if (el) el.textContent = "";
    }
  }

  function connect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/janis?device_id=kiosk-tty1`);
    ws.onopen = () => setWs(true);
    ws.onclose = () => {
      setWs(false);
      reconnectTimer = setTimeout(connect, 3000);
    };
    ws.onerror = () => setWs(false);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "chat_chunk") {
          streamBuf += msg.text || "";
          if (!streamEl) streamEl = line("assistant", "");
          streamEl.textContent = streamBuf;
          log.scrollTop = log.scrollHeight;
        }
        if (msg.type === "chat_end") {
          if (!streamEl && streamBuf) line("assistant", streamBuf);
          streamBuf = "";
          streamEl = null;
          emitBrain(msg);
        }
        if (msg.type === "state") {
          line("sys", msg.state || "");
          emitBrain(msg);
        }
        if (msg.type === "tool_start") {
          line("tool", `▸ ${msg.tool}: ${(msg.reason || "").slice(0, 60)}`);
          emitBrain(msg);
        }
        if (msg.type === "error") {
          line("sys", "ERR: " + (msg.message || "errore"));
        }
      } catch (_) { /* ignore */ }
    };
  }

  async function sendHttp(text) {
    line("user", text);
    streamBuf = "";
    streamEl = line("assistant", "…");
    emitBrain({ type: "state", state: "THINKING" });
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let acc = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        const m = acc.match(/"text"\s*:\s*"((?:\\.|[^"\\])*)"/);
        if (m) {
          try {
            const t = JSON.parse('"' + m[1].replace(/\\/g, "\\\\") + '"');
            streamEl.textContent = t;
          } catch (_) {
            streamEl.textContent = m[1];
          }
        }
      }
      emitBrain({ type: "chat_end" });
    } catch (e) {
      streamEl.textContent = "Errore: " + (e.message || "chat fallita");
    }
    streamEl = null;
    emitBrain({ type: "state", state: "IDLE" });
  }

  function send(text) {
    if (!text.trim()) return;
    emitBrain({ type: "state", state: "THINKING" });
    if (ws && ws.readyState === 1) {
      line("user", text);
      streamBuf = "";
      streamEl = null;
      ws.send(JSON.stringify({ type: "chat", text, device_id: "kiosk-tty1" }));
    } else {
      sendHttp(text);
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = input.value.trim();
    if (!t) return;
    input.value = "";
    send(t);
  });

  if (toggle) {
    toggle.addEventListener("click", () => panel.classList.toggle("hidden"));
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", () => panel.classList.add("hidden"));
  }

  connect();
})();
