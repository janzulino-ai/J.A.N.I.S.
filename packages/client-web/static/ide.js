(function () {
  const root = document.getElementById("janis-ide");
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const messages = document.getElementById("chat-messages");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const liveContent = document.getElementById("live-content");
  const chatTitle = document.querySelector(".chat-title");
  const tabs = document.querySelectorAll(".tab");
  let ws = null;
  let wsOk = false;
  let activeTab = "agents";
  const liveBuffers = { agents: [], tools: [], fleet: [], logs: [] };

  toggle.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
    root.classList.toggle("sidebar-collapsed");
  });

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      activeTab = t.dataset.tab;
      renderLive();
    });
  });

  function setConn(ok, label) {
    wsOk = ok;
    if (chatTitle) chatTitle.textContent = ok ? "J.A.N.I.S. · LIVE" : `J.A.N.I.S. · ${label || "OFFLINE"}`;
    sendBtn.disabled = false;
  }

  function appendMsg(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function pushLive(kind, line) {
    const bucket = kind.startsWith("tool") ? "tools" : kind.startsWith("brain") ? "agents" : kind.includes("fleet") ? "fleet" : "logs";
    liveBuffers[bucket].unshift(line);
    liveBuffers[bucket] = liveBuffers[bucket].slice(0, 80);
    if (activeTab === bucket) renderLive();
  }

  function renderLive() {
    liveContent.innerHTML = (liveBuffers[activeTab] || [])
      .map((l) => `<div class="live-event">${l}</div>`)
      .join("") || "<div class='live-event'>—</div>";
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws/janis?device_id=client-web`;
    ws = new WebSocket(url);
    ws.onopen = () => setConn(true);
    ws.onclose = () => { setConn(false, "WS reconnect…"); setTimeout(connect, 3000); };
    ws.onerror = () => setConn(false, "WS err");
    let buf = "";
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        const t = msg.type || "";
        pushLive(t, `${new Date().toLocaleTimeString()} ${t} ${JSON.stringify(msg).slice(0, 120)}`);
        if (t === "chat_chunk") {
          buf += msg.text || msg.content || msg.delta || "";
          const last = messages.querySelector(".msg.assistant.streaming");
          if (last) last.textContent = buf;
          else {
            const div = document.createElement("div");
            div.className = "msg assistant streaming";
            div.textContent = buf;
            messages.appendChild(div);
          }
        }
        if (t === "chat_end") {
          const last = messages.querySelector(".msg.assistant.streaming");
          if (last) last.classList.remove("streaming");
          buf = "";
        }
      } catch (_) {}
    };
  }

  async function sendHttp(text) {
    appendMsg("user", text);
    const el = appendMsg("assistant", "…");
    el.classList.add("streaming");
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let acc = "";
      let out = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        for (const m of acc.matchAll(/"text"\s*:\s*"((?:\\.|[^"\\])*)"/g)) {
          try { out = JSON.parse('"' + m[1].replace(/\\/g, "\\\\") + '"'); } catch (_) { out = m[1]; }
        }
        if (out) el.textContent = out;
      }
    } catch (e) {
      el.textContent = "Errore chat: " + (e.message || "?");
    }
    el.classList.remove("streaming");
  }

  function sendChat() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    if (ws && ws.readyState === 1) {
      appendMsg("user", text);
      ws.send(JSON.stringify({ type: "chat", text, device_id: "client-web" }));
    } else {
      sendHttp(text);
    }
  }

  sendBtn.addEventListener("click", sendChat);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  connect();
  renderLive();
})();
