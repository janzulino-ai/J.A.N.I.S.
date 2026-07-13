(function () {
  const root = document.getElementById("janis-ide");
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const messages = document.getElementById("chat-messages");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const liveContent = document.getElementById("live-content");
  const tabs = document.querySelectorAll(".tab");
  let ws = null;
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

  function appendMsg(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
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
    ws.onclose = () => setTimeout(connect, 3000);
  }

  function sendChat() {
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== 1) return;
    appendMsg("user", text);
    ws.send(JSON.stringify({ type: "chat", text, device_id: "client-web" }));
    input.value = "";
  }

  sendBtn.addEventListener("click", sendChat);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  connect();
  renderLive();
})();
