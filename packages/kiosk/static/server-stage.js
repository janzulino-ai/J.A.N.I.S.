(function () {
  const SHEETS = [
    { id: "runtime", title: "Runtime", baseMs: 45000, activeKey: "gpu" },
    { id: "reasoning", title: "Reasoning", baseMs: 60000, activeKey: "ws" },
    { id: "fleet", title: "Fleet", baseMs: 30000, activeKey: "jobs" },
    { id: "memory", title: "Memory", baseMs: 40000, activeKey: null },
    { id: "thermal", title: "Thermal", baseMs: 25000, activeKey: "temp" },
  ];

  const PAUSE_MS = 10 * 60 * 1000;
  let idx = 0;
  let paused = false;
  let pauseUntil = 0;
  let timer = null;
  let metrics = {};
  let status = {};

  const container = document.getElementById("sheet-container");
  const dotsEl = document.getElementById("sheet-dots");
  const pauseBadge = document.getElementById("pause-badge");
  const stage = document.getElementById("server-stage");
  const clockEl = document.getElementById("hud-clock");

  function renderDots() {
    dotsEl.innerHTML = SHEETS.map((s, i) =>
      `<span class="dot ${i === idx ? "on" : ""}" data-i="${i}"></span>`
    ).join("");
    dotsEl.querySelectorAll(".dot").forEach((d) => {
      d.addEventListener("click", () => focusSheet(parseInt(d.dataset.i, 10)));
    });
  }

  function sheetDuration(s) {
    let mult = 1;
    if (s.activeKey === "gpu" && (metrics.gpu?.usage_pct || 0) > 30) mult = 1.5;
    if (s.activeKey === "ws" && (status.connected_clients || []).length > 0) mult = 1.5;
    if (s.activeKey === "jobs" && (status.fleet?.nodes_online || 0) > 0) mult = 1.5;
    if (s.activeKey === "temp" && (metrics.cpu?.temp_c || 0) > 70) mult = 1.5;
    return Math.round(s.baseMs * mult);
  }

  function renderSheet() {
    const s = SHEETS[idx];
    let html = `<section class="sheet active"><h2>${s.title}</h2>`;
    if (s.id === "runtime") {
      html += `<div class="metric-grid">
        <div class="metric"><label>CPU</label><span class="val">${(metrics.cpu?.usage_pct ?? "—")}%</span></div>
        <div class="metric"><label>RAM</label><span class="val">${(metrics.memory?.usage_pct ?? "—")}%</span></div>
        <div class="metric"><label>GPU</label><span class="val">${(metrics.gpu?.usage_pct ?? "—")}%</span></div>
        <div class="metric"><label>Uptime</label><span class="val">${formatUptime(metrics.uptime_sec)}</span></div>
        <div class="metric"><label>Host</label><span class="val">${metrics.hostname || "—"}</span></div>
        <div class="metric"><label>Temp</label><span class="val">${metrics.cpu?.temp_c != null ? metrics.cpu.temp_c + "°C" : "—"}</span></div>
      </div>`;
    } else if (s.id === "reasoning") {
      const nodes = ["INPUT", "THINKING", "TOOLS", "AGENTS", "RESPONSE"];
      html += `<div class="pipeline">${nodes.map((n, i) =>
        `<span class="pipe-node ${i === 2 ? "live" : ""}">${n}</span>`
      ).join('<span>→</span>')}</div>`;
    } else if (s.id === "fleet") {
      const nodes = status.fleet?.nodes || [];
      if (!nodes.length) {
        html += `<p class="fleet-row">mac-node · win-vm · pocket</p>`;
      } else {
        html += nodes.map((n) =>
          `<p class="fleet-row ${n.online ? "online" : "offline"}"><span class="status">${n.online ? "●" : "○"}</span> ${n.node_id || n.id} — ${n.info || n.status || ""}</p>`
        ).join("");
      }
    } else if (s.id === "memory") {
      html += `<div class="metric-grid">
        <div class="metric"><label>Service</label><span class="val">${status.service || "JANIS"}</span></div>
        <div class="metric"><label>Version</label><span class="val">${status.version || "—"}</span></div>
        <div class="metric"><label>Sessions</label><span class="val">${status.session_messages ?? "—"}</span></div>
      </div>`;
    } else {
      html += `<div class="metric-grid">
        <div class="metric"><label>CPU temp</label><span class="val">${metrics.cpu?.temp_c != null ? metrics.cpu.temp_c + "°C" : "—"}</span></div>
        <div class="metric"><label>GPU util</label><span class="val">${metrics.gpu?.usage_pct ?? "—"}%</span></div>
        <div class="metric"><label>Platform</label><span class="val">${metrics.platform || "Linux"}</span></div>
      </div>`;
    }
    html += "</section>";
    container.innerHTML = html;
    renderDots();
  }

  function formatUptime(sec) {
    if (!sec) return "—";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function scheduleNext() {
    clearTimeout(timer);
    if (paused && Date.now() < pauseUntil) return;
    if (paused && Date.now() >= pauseUntil) {
      paused = false;
      stage.classList.remove("focused");
      pauseBadge.classList.add("hidden");
    }
    timer = setTimeout(() => {
      idx = (idx + 1) % SHEETS.length;
      renderSheet();
      scheduleNext();
    }, sheetDuration(SHEETS[idx]));
  }

  function focusSheet(i) {
    idx = i;
    paused = true;
    pauseUntil = Date.now() + PAUSE_MS;
    stage.classList.add("focused");
    pauseBadge.classList.remove("hidden");
    renderSheet();
    clearTimeout(timer);
    timer = setTimeout(() => {
      paused = false;
      stage.classList.remove("focused");
      pauseBadge.classList.add("hidden");
      scheduleNext();
    }, PAUSE_MS);
  }

  async function poll() {
    try {
      const [m, s] = await Promise.all([
        fetch("/api/host/metrics").then((r) => r.json()),
        fetch("/api/status").then((r) => r.json()),
      ]);
      metrics = m;
      status = s;
    } catch (_) {}
    clockEl.textContent = new Date().toLocaleTimeString("it-IT");
  }

  stage.addEventListener("click", (e) => {
    if (e.target.closest(".dot")) return;
    focusSheet(idx);
  });

  renderSheet();
  scheduleNext();
  poll();
  setInterval(poll, 5000);
})();
