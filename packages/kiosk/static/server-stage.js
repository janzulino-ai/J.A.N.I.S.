(function () {
  const SHEETS = [
    { id: "runtime", title: "Runtime", sub: "SYS · METRICS", baseMs: 45000, activeKey: "gpu" },
    { id: "reasoning", title: "Reasoning", sub: "NEURAL · PIPELINE", baseMs: 60000, activeKey: "ws" },
    { id: "fleet", title: "Fleet", sub: "NODES · MESH", baseMs: 30000, activeKey: "jobs" },
    { id: "memory", title: "Memory", sub: "KNOWLEDGE · STATE", baseMs: 40000, activeKey: null },
    { id: "thermal", title: "Thermal", sub: "SENSORS · ALERT", baseMs: 25000, activeKey: "temp" },
  ];

  const PAUSE_MS = 10 * 60 * 1000;
  const ARC_R = 52;
  const ARC_C = 2 * Math.PI * ARC_R;

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

  function arcGauge(label, value, unit, max) {
    const pct = value != null && !isNaN(value) ? Math.min(100, Math.max(0, value)) : null;
    const dash = pct != null ? (pct / max) * ARC_C : 0;
    const display = pct != null ? `${Math.round(pct)}${unit}` : "—";
    return `<div class="arc-gauge">
      <svg viewBox="0 0 120 120">
        <circle class="arc-bg" cx="60" cy="60" r="${ARC_R}"/>
        <circle class="arc-fill" cx="60" cy="60" r="${ARC_R}"
          stroke-dasharray="${ARC_C}" stroke-dashoffset="${ARC_C - dash}"/>
      </svg>
      <span class="arc-val">${display}</span>
      <label>${label}</label>
    </div>`;
  }

  function textGauge(label, value) {
    return `<div class="arc-gauge">
      <svg viewBox="0 0 120 120">
        <circle class="arc-bg" cx="60" cy="60" r="${ARC_R}"/>
        <circle class="arc-fill" cx="60" cy="60" r="${ARC_R}"
          stroke-dasharray="${ARC_C}" stroke-dashoffset="${ARC_C * 0.25}"/>
      </svg>
      <span class="arc-val" style="font-size:0.75em">${value}</span>
      <label>${label}</label>
    </div>`;
  }

  function sheetHeader(s) {
    return `<div class="sheet-head"><h2>${s.title}</h2><span class="sheet-sub">${s.sub}</span></div>`;
  }

  function renderDots() {
    dotsEl.innerHTML = SHEETS.map((s, i) =>
      `<span class="dot ${i === idx ? "on" : ""}" data-i="${i}" title="${s.title}"></span>`
    ).join("");
    dotsEl.querySelectorAll(".dot").forEach((d) => {
      d.addEventListener("click", (e) => {
        e.stopPropagation();
        focusSheet(parseInt(d.dataset.i, 10));
      });
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

  function livePipeIndex() {
    const clients = status.connected_clients || [];
    if (clients.length > 0) return 2;
    if ((metrics.gpu?.usage_pct || 0) > 20) return 1;
    return 0;
  }

  function renderSheet() {
    const s = SHEETS[idx];
    let body = "";

    if (s.id === "runtime") {
      body = `<div class="gauge-grid">
        ${arcGauge("CPU", metrics.cpu?.usage_pct, "%", 100)}
        ${arcGauge("RAM", metrics.memory?.usage_pct, "%", 100)}
        ${arcGauge("GPU", metrics.gpu?.usage_pct, "%", 100)}
        ${textGauge("UPTIME", formatUptime(metrics.uptime_sec))}
        ${textGauge("HOST", (metrics.hostname || "—").toUpperCase())}
        ${arcGauge("TEMP", metrics.cpu?.temp_c, "°C", 100)}
      </div>`;
    } else if (s.id === "reasoning") {
      const nodes = ["INPUT", "THINKING", "TOOLS", "AGENTS", "RESPONSE"];
      const live = livePipeIndex();
      const parts = [];
      nodes.forEach((n, i) => {
        if (i > 0) parts.push('<span class="pipe-connector"></span>');
        parts.push(`<span class="pipe-node ${i === live ? "live" : ""}">${n}</span>`);
      });
      body = `<div class="pipeline-wrap"><div class="pipeline">${parts.join("")}</div></div>`;
    } else if (s.id === "fleet") {
      const nodes = status.fleet?.nodes || [];
      if (!nodes.length) {
        body = `<div class="fleet-grid">
          ${fleetCard("mac-node", false, "SSH standby")}
          ${fleetCard("win-vm", true, "VM · HDMI RTX")}
          ${fleetCard("pocket", true, "iOS body")}
        </div>`;
      } else {
        body = `<div class="fleet-grid">${nodes.map((n) =>
          fleetCard(n.node_id || n.id, n.online, n.info || n.status || "")
        ).join("")}</div>`;
      }
    } else if (s.id === "memory") {
      body = `<div class="mem-grid">
        <div class="mem-cell"><label>SERVICE</label><span class="val">${status.service || "JANIS"}</span></div>
        <div class="mem-cell"><label>VERSION</label><span class="val">${status.version || "—"}</span></div>
        <div class="mem-cell"><label>SESSIONS</label><span class="val">${status.session_messages ?? "—"}</span></div>
      </div>`;
    } else {
      body = `<div class="gauge-grid">
        ${arcGauge("CPU TEMP", metrics.cpu?.temp_c, "°C", 100)}
        ${arcGauge("GPU LOAD", metrics.gpu?.usage_pct, "%", 100)}
        ${textGauge("PLATFORM", (metrics.platform || "LINUX").toUpperCase())}
      </div>`;
    }

    container.innerHTML = `<section class="sheet active">${sheetHeader(s)}${body}</section>`;
    renderDots();
  }

  function fleetCard(name, online, info) {
    const st = online ? "ONLINE" : "OFFLINE";
    return `<div class="fleet-card ${online ? "online" : "offline"}">
      <span class="fleet-icon">${online ? "◉" : "◎"}</span>
      <div>
        <div class="fleet-name">${name}</div>
        <div class="fleet-info">${info}</div>
      </div>
      <span class="fleet-status">${st}</span>
    </div>`;
  }

  function formatUptime(sec) {
    if (!sec) return "—";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}H ${m}M`;
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
      renderSheet();
    } catch (_) {}
    clockEl.textContent = new Date().toLocaleTimeString("it-IT", { hour12: false });
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
