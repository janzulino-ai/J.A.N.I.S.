(function () {
  const panel = document.getElementById("hud-chat");
  const log = document.getElementById("hud-chat-log");
  const form = document.getElementById("hud-chat-form");
  const input = document.getElementById("hud-chat-input");
  const toggle = document.getElementById("chat-toggle");
  const closeBtn = document.getElementById("chat-close");
  const wsStatus = document.getElementById("chat-ws-status");
  if (!panel || !log) return;

  let ws = null;
  let streamBuf = "";
  let streamEl = null;

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

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/janis?device_id=kiosk-tty1`);
    ws.onopen = () => setWs(true);
    ws.onclose = () => { setWs(false); setTimeout(connect, 3000); };
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
        }
        if (msg.type === "state") {
          line("sys", msg.state || "");
        }
        if (msg.type === "tool_start") {
          line("tool", `▸ ${msg.tool}: ${(msg.reason || "").slice(0, 60)}`);
        }
      } catch (_) { /* ignore */ }
    };
  }

  async function sendHttp(text) {
    line("user", text);
    streamBuf = "";
    streamEl = line("assistant", "…");
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
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
    } catch (e) {
      streamEl.textContent = "Errore: " + (e.message || "chat fallita");
    }
    streamEl = null;
  }

  function send(text) {
    if (!text.trim()) return;
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

  toggle.addEventListener("click", () => panel.classList.toggle("hidden"));
  closeBtn.addEventListener("click", () => panel.classList.add("hidden"));

  connect();
})();
