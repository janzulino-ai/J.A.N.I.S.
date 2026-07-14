(function () {
  /* Griglia 3×3 modulare — ogni blocco: col, row, colSpan, rowSpan (1–3) */
  const BLOCKS = [
    { id: "hardware", col: 1, row: 1, colSpan: 1, rowSpan: 1, title: "HARDWARE", accent: "cyan" },
    { id: "providers", col: 2, row: 1, colSpan: 2, rowSpan: 1, title: "ROUTING · COSTI", accent: "gold" },
    { id: "processes", col: 1, row: 2, colSpan: 1, rowSpan: 2, title: "PROCESSI · SERVIZI", accent: "lime" },
    { id: "focus", col: 2, row: 2, colSpan: 2, rowSpan: 2, title: "NEURAL CORE", accent: "magenta", carousel: true },
  ];

  const FOCUS_VIEWS = [
    { id: "runtime", label: "RUNTIME", sub: "CPU · RAM · GPU · TEMP" },
    { id: "reasoning", label: "RAGIONAMENTO", sub: "PIPELINE · TOOL LOOP" },
    { id: "fleet", label: "SATELLITI", sub: "MAC · WIN-VM · POCKET" },
    { id: "memory", label: "MEMORIA", sub: "KNOWLEDGE · SESSION" },
    { id: "peripherals", label: "PERIFERICHE", sub: "API · CANALI · I/O" },
  ];

  const PAUSE_MS = 10 * 60 * 1000;
  const ARC_R = 46;
  const ARC_C = 2 * Math.PI * ARC_R;

  let focusIdx = 0;
  let fullscreenId = null;
  let paused = false;
  let pauseUntil = 0;
  let timer = null;
  let metrics = {};
  let status = {};
  let hardware = {};
  let knowledge = {};
  let wavePhase = 0;

  const gridEl = document.getElementById("hud-grid");
  const dotsEl = document.getElementById("sheet-dots");
  const pauseBadge = document.getElementById("pause-badge");
  const footMeta = document.getElementById("foot-meta");
  const stage = document.getElementById("server-stage");
  const clockEl = document.getElementById("hud-clock");

  function esc(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatUptime(sec) {
    if (!sec) return "—";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}H ${m}M`;
  }

  function arcGauge(label, value, unit, max, accent) {
    const pct = value != null && !isNaN(value) ? Math.min(100, Math.max(0, value)) : null;
    const dash = pct != null ? (pct / max) * ARC_C : 0;
    const display = pct != null ? `${Math.round(pct)}${unit}` : "—";
    return `<div class="arc-gauge accent-${accent}">
      <svg viewBox="0 0 110 110">
        <circle class="arc-bg" cx="55" cy="55" r="${ARC_R}"/>
        <circle class="arc-fill" cx="55" cy="55" r="${ARC_R}"
          stroke-dasharray="${ARC_C}" stroke-dashoffset="${ARC_C - dash}"/>
      </svg>
      <span class="arc-val">${display}</span>
      <label>${label}</label>
    </div>`;
  }

  function statRow(label, value, tone) {
    return `<div class="stat-row tone-${tone || "cyan"}">
      <span class="stat-lbl">${label}</span>
      <span class="stat-val">${esc(value)}</span>
    </div>`;
  }

  function badge(text, on, extra) {
    const cls = on ? "on" : (extra || "off");
    return `<span class="proc-badge ${cls}">${text}</span>`;
  }

  function processList() {
    const orch = status.orchestrator || {};
    const items = [
      { label: "OLLAMA", on: !!status.ollama?.online, load: status.ollama?.online ? 88 : 4, tag: status.ollama?.online ? "ON" : "OFF" },
      { label: "JANIS.API", on: true, load: 92, tag: "ON" },
      { label: "STT", on: !!status.stt?.ready, load: status.stt?.ready ? 55 : 12, tag: status.stt?.ready ? "ON" : "DEG" },
      { label: "FLEET_HUB", on: (status.fleet?.nodes_online || 0) > 0, load: Math.round(((status.fleet?.nodes_online || 0) / (status.fleet?.nodes_total || 3)) * 100), tag: `${status.fleet?.nodes_online || 0}/${status.fleet?.nodes_total || 3}` },
      { label: "COST_ROUTER", on: !status.orchestrator?.cloud_blocked, load: orch.active ? 75 : 35, tag: (orch.cloud_blocked ? "BLOCK" : (orch.mode || orch.default_tier || "LOCAL")).toUpperCase() },
      { label: "TELEGRAM", on: !!status.channels?.telegram, load: status.channels?.telegram ? 40 : 0, tag: status.channels?.telegram ? "ON" : "OFF" },
      { label: "SCHEDULER", on: status.scheduler !== false, load: 30, tag: "ON" },
      { label: "CURSOR_SDK", on: !!status.paid_mode || !!status.cursor_ready, load: status.paid_mode ? 60 : 8, tag: status.paid_mode ? "PRO" : "FREE" },
    ];
    return items.map((p) => `<div class="proc-row">
      <span class="proc-name">${p.label}</span>
      ${badge(p.tag, p.on, p.on ? "on" : "exe")}
      <div class="proc-bar-wrap"><span class="proc-bar tone-lime" style="width:${p.load}%"></span></div>
    </div>`).join("");
  }

  function renderHardware() {
    const cpu = metrics.cpu || {};
    const gpu = metrics.gpu || {};
    const mem = metrics.memory || {};
    const hw = hardware || {};
    return `<div class="block-body">
      <div class="big-metrics">
        <div class="big-metric tone-cyan"><span class="bm-val">${Math.round(cpu.usage_pct || 0)}%</span><span class="bm-lbl">CPU</span></div>
        <div class="big-metric tone-magenta"><span class="bm-val">${Math.round(mem.usage_pct || 0)}%</span><span class="bm-lbl">RAM</span></div>
        <div class="big-metric tone-gold"><span class="bm-val">${Math.round(gpu.usage_pct || 0)}%</span><span class="bm-lbl">GPU</span></div>
      </div>
      ${statRow("HOST", (metrics.hostname || "—").toUpperCase())}
      ${statRow("PLATFORM", metrics.platform || "LINUX")}
      ${statRow("ARCH", hw.cpu?.arch || "—", "lime")}
      ${statRow("RAM TOT", hw.ram_gb ? `${hw.ram_gb} GB` : "—", "gold")}
      ${statRow("TEMP", cpu.temp_c != null ? `${Math.round(cpu.temp_c)}°C` : "—", cpu.temp_c > 75 ? "warn" : "cyan")}
      ${statRow("UPTIME", formatUptime(metrics.uptime_sec), "lime")}
      ${metrics.disk?.[0] ? statRow("DISCO", `${metrics.disk[0].mount} ${metrics.disk[0].used_pct}%`, "gold") : ""}
      ${metrics.glances ? statRow("GLANCES", "LINK", "lime") : statRow("GLANCES", "OFF", "warn")}
    </div>`;
  }

  let scout = {};

  function renderProviders() {
    const orch = status.orchestrator || {};
    const usage = status.llm_usage || {};
    const prov = (status.reasoning_provider || "ollama").toUpperCase();
    const paid = status.paid_mode ? "PRO · A PAGAMENTO" : "FREE · LOCALE";
    const budget = orch.daily_budget_usd ?? 2;
    const spent = usage.spent_today_usd ?? orch.spent_today_usd ?? 0;
    const rem = orch.remaining_usd ?? budget;
    const pct = budget ? Math.min(100, (spent / budget) * 100) : 0;
    const cloudBlocked = orch.cloud_blocked ? `<div class="warning-strip">CLOUD BLOCCATO · BUDGET</div>` : "";
    const lat = usage.avg_latency_ms ? `${Math.round(usage.avg_latency_ms)}ms` : "—";
    const scoutLines = (scout.recent || []).slice(0, 3).map((c) =>
      `<span class="tier-pill tone-cyan">${esc(c.name)} · ${esc(c.status)} · ${esc(c.deployment || "local")}</span>`
    ).join(" ");
    return `<div class="block-body">
      ${cloudBlocked}
      <div class="provider-hero tone-gold">
        <span class="ph-main">${prov}</span>
        <span class="ph-sub">${paid}</span>
      </div>
      <div class="tier-row">
        <span class="tier-pill tone-lime active">LOCALE</span>
        <span class="tier-pill tone-cyan ${prov.includes("OPEN") ? "active" : ""}">OPENROUTER</span>
        <span class="tier-pill tone-magenta ${status.paid_mode ? "active" : ""}">CURSOR PRO</span>
      </div>
      <div class="budget-bar"><span class="budget-fill" style="width:${pct}%"></span></div>
      <div class="budget-labels">
        <span>SPESO $${Number(spent).toFixed(2)} · ${usage.calls_today ?? 0} call</span>
        <span>RESTO $${Number(rem).toFixed(2)} / $${budget}</span>
      </div>
      ${statRow("LATENZA LLM", lat, "lime")}
      ${statRow("LITELLM", status.llm_provider?.litellm_online ? "ON" : "OFF", "cyan")}
      ${statRow("MODELLO", status.ollama?.model || status.ollama?.models?.[0] || "gemma4", "cyan")}
      ${statRow("SESSIONI", status.session_messages ?? 0, "magenta")}
      ${scoutLines ? `<div class="tier-row scout-row">${scoutLines}</div>` : ""}
      ${statRow("TECH SCOUT", scout.total != null ? `${scout.total} candidati` : "—", "gold")}
    </div>`;
  }

  function renderProcesses() {
    const warnings = [];
    if (!status.ollama?.online) warnings.push("OLLAMA OFFLINE");
    if ((status.fleet?.nodes_online || 0) < (status.fleet?.nodes_total || 3)) warnings.push("FLEET GAP");
    if ((metrics.cpu?.temp_c || 0) > 75) warnings.push("THERMAL");
    const warn = warnings.length
      ? `<div class="warning-strip">${warnings.join(" · ")}</div>`
      : "";
    return `<div class="block-body scroll-y">
      ${warn}
      <div class="process-list">${processList()}</div>
      <div class="tracer-block">
        <span class="tracer-label">LOAD TRACE</span>
        <div class="tracer-bar"><span class="tracer-fill tone-cyan" style="width:${Math.min(100, metrics.cpu?.usage_pct || 0)}%"></span></div>
      </div>
      <div class="tracer-block">
        <span class="tracer-label">MEM TRACE</span>
        <div class="tracer-bar"><span class="tracer-fill tone-magenta" style="width:${metrics.memory?.usage_pct || 0}%"></span></div>
      </div>
    </div>`;
  }

  function livePipeIndex() {
    if ((status.connected_clients || []).length > 0) return 4;
    if ((metrics.gpu?.usage_pct || 0) > 20) return 2;
    if (status.ollama?.online) return 1;
    return 0;
  }

  function fleetNodes() {
    const nodes = status.fleet?.nodes || [];
    if (nodes.length) return nodes;
    return [
      { node_id: "mac-node", online: !!status.mac_node?.ok, info: status.mac_node?.detail || "SSH" },
      { node_id: "win-vm", online: true, info: "KVM · VNC" },
      { node_id: "pocket-iphone", online: !!(status.presence?.devices?.length), info: "iOS body" },
    ];
  }

  function fleetCard(name, online, info) {
    return `<div class="fleet-card ${online ? "online" : "offline"}">
      <span class="fleet-icon">${online ? "◉" : "◎"}</span>
      <div><div class="fleet-name">${esc(name)}</div><div class="fleet-info">${esc(info)}</div></div>
      <span class="fleet-status">${online ? "LINK" : "GAP"}</span>
    </div>`;
  }

  function renderFocusRuntime() {
    return `<div class="gauge-grid">
      ${arcGauge("CPU", metrics.cpu?.usage_pct, "%", 100, "cyan")}
      ${arcGauge("RAM", metrics.memory?.usage_pct, "%", 100, "magenta")}
      ${arcGauge("GPU", metrics.gpu?.usage_pct, "%", 100, "gold")}
      ${arcGauge("TEMP", metrics.cpu?.temp_c, "°C", 100, "warn")}
    </div>`;
  }

  function renderFocusReasoning() {
    const nodes = ["INPUT", "THINK", "TOOLS", "AGENTS", "OUT"];
    const live = livePipeIndex();
    const parts = nodes.map((n, i) => {
      const conn = i > 0 ? '<span class="pipe-connector"></span>' : "";
      return `${conn}<span class="pipe-node ${i === live ? "live" : ""}">${n}</span>`;
    }).join("");
    const orch = status.orchestrator || {};
    return `<div class="pipeline-wrap"><div class="pipeline">${parts}</div></div>
      <div class="focus-meta">
        ${statRow("PROVIDER", (status.reasoning_provider || "local").toUpperCase(), "gold")}
        ${statRow("TIER", (orch.default_tier || "LOCAL").toUpperCase(), "lime")}
        ${statRow("TOOL LOOP", "max 8 iter", "cyan")}
      </div>`;
  }

  function renderFocusFleet() {
    return `<div class="fleet-grid">${fleetNodes().map((n) =>
      fleetCard(n.node_id || n.id, n.online, n.info || n.status || "")
    ).join("")}</div>`;
  }

  function renderFocusMemory() {
    const k = knowledge || {};
    return `<div class="mem-grid">
      <div class="mem-cell tone-cyan"><label>VERSION</label><span class="val">${esc(status.version)}</span></div>
      <div class="mem-cell tone-magenta"><label>BRAIN</label><span class="val">v${status.brain_version || "?"}</span></div>
      <div class="mem-cell tone-lime"><label>MSG</label><span class="val">${status.session_messages ?? "—"}</span></div>
      <div class="mem-cell tone-gold"><label>MEMORIES</label><span class="val">${k.total_memories ?? k.count ?? "—"}</span></div>
      <div class="mem-cell tone-cyan"><label>FOLDERS</label><span class="val">${k.knowledge_folders ?? "—"}</span></div>
      <div class="mem-cell tone-warn"><label>GAPS</label><span class="val">${k.open_gaps ?? "—"}</span></div>
    </div>`;
  }

  function renderFocusPeripherals() {
    const pocket = status.pocket_api || {};
    const apis = Object.entries(pocket).slice(0, 6);
    const mac = status.mac_node || {};
    const pres = status.presence || {};
    return `<div class="periph-grid">
      <div class="periph-col">
        <span class="periph-head tone-orange">POCKET API</span>
        ${apis.map(([k, v]) => statRow(k.toUpperCase(), v, "cyan")).join("")}
      </div>
      <div class="periph-col">
        <span class="periph-head tone-blue">NODI</span>
        ${statRow("MAC SSH", mac.ok ? "ONLINE" : "OFFLINE", mac.ok ? "lime" : "warn")}
        ${statRow("PRESENCE", (pres.devices || []).length || 0, "magenta")}
        ${statRow("STT", status.stt?.engine || "—", "gold")}
        ${statRow("ACTIVE", status.active_client || "—", "cyan")}
      </div>
      <div class="waveform-row compact">
        <div class="wave-block"><span class="wave-label">SIGNAL</span><svg class="wave-svg" id="wave-focus" viewBox="0 0 120 32"></svg></div>
      </div>
    </div>`;
  }

  function renderFocusBody(viewId) {
    switch (viewId) {
      case "runtime": return renderFocusRuntime();
      case "reasoning": return renderFocusReasoning();
      case "fleet": return renderFocusFleet();
      case "memory": return renderFocusMemory();
      case "peripherals": return renderFocusPeripherals();
      default: return "";
    }
  }

  function renderFocus() {
    const v = FOCUS_VIEWS[focusIdx];
    return `<div class="focus-inner">
      <div class="focus-head">
        <span class="focus-title">[-${v.label}-]</span>
        <span class="focus-sub">${v.sub}</span>
      </div>
      <div class="focus-body">${renderFocusBody(v.id)}</div>
      <div class="reactor-mini" aria-hidden="true">
        <svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="36" class="rx-ring"/>
          <circle cx="40" cy="40" r="24" class="rx-ring" style="animation-direction:reverse"/>
          <circle cx="40" cy="40" r="4" class="rx-core"/></svg>
      </div>
    </div>`;
  }

  const RENDERERS = {
    hardware: renderHardware,
    providers: renderProviders,
    processes: renderProcesses,
    focus: renderFocus,
  };

  function blockStyle(b) {
    if (!fullscreenId) {
      return `grid-column:${b.col} / span ${b.colSpan};grid-row:${b.row} / span ${b.rowSpan}`;
    }
    if (fullscreenId === b.id) {
      return "grid-column:2;grid-row:2";
    }
    const rims = BLOCKS.filter((x) => x.id !== fullscreenId);
    const idx = rims.findIndex((x) => x.id === b.id);
    const slots = [
      "grid-column:2;grid-row:1",
      "grid-column:1;grid-row:2",
      "grid-column:3;grid-row:2",
    ];
    return slots[idx] || "grid-column:2;grid-row:3";
  }

  function buildGrid() {
    gridEl.innerHTML = BLOCKS.map((b) => {
      const body = (RENDERERS[b.id] || (() => ""))();
      const isFs = fullscreenId === b.id;
      const isRim = fullscreenId && fullscreenId !== b.id;
      return `<article class="hud-block accent-${b.accent} ${isFs ? "is-focus" : ""} ${isRim ? "is-rim" : ""}"
        data-id="${b.id}" style="${blockStyle(b)}" tabindex="0">
        <div class="block-frame">
          <span class="frame-corner tl"></span><span class="frame-corner tr"></span>
          <span class="frame-corner bl"></span><span class="frame-corner br"></span>
          <header class="block-head"><span class="block-title">${b.title}</span>
            <span class="block-expand">${isFs ? "◈ FULL" : "⊞"}</span>
          </header>
          ${body}
        </div>
      </article>`;
    }).join("");

    gridEl.querySelectorAll(".hud-block").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFullscreen(el.dataset.id);
      });
    });
  }

  function toggleFullscreen(id) {
    if (fullscreenId === id) {
      fullscreenId = null;
      stage.classList.remove("grid-fullscreen");
    } else {
      fullscreenId = id;
      stage.classList.add("grid-fullscreen");
      paused = true;
      pauseUntil = Date.now() + PAUSE_MS;
      pauseBadge.classList.remove("hidden");
      footMeta.textContent = `FULLSCREEN · ${id.toUpperCase()} · CLICK = ESCI`;
      clearTimeout(timer);
      timer = setTimeout(exitFullscreenPause, PAUSE_MS);
    }
    buildGrid();
    renderWaveforms();
  }

  function exitFullscreenPause() {
    if (Date.now() >= pauseUntil) {
      paused = false;
      fullscreenId = null;
      stage.classList.remove("grid-fullscreen");
      pauseBadge.classList.add("hidden");
      footMeta.textContent = "GRID 3×3 · CLICK BLOCCO = FULLSCREEN";
      buildGrid();
      scheduleCarousel();
    }
  }

  function renderDots() {
    dotsEl.innerHTML = FOCUS_VIEWS.map((v, i) =>
      `<span class="dot ${i === focusIdx ? "on" : ""}" data-i="${i}" title="${v.label}"></span>`
    ).join("");
    dotsEl.querySelectorAll(".dot").forEach((d) => {
      d.addEventListener("click", (e) => {
        e.stopPropagation();
        focusIdx = parseInt(d.dataset.i, 10);
        paused = true;
        pauseUntil = Date.now() + PAUSE_MS;
        pauseBadge.classList.remove("hidden");
        buildGrid();
        clearTimeout(timer);
        timer = setTimeout(() => {
          paused = false;
          pauseBadge.classList.add("hidden");
          scheduleCarousel();
        }, PAUSE_MS);
      });
    });
  }

  function carouselMs() {
    const v = FOCUS_VIEWS[focusIdx];
    let base = 35000;
    if (v.id === "runtime" && (metrics.gpu?.usage_pct || 0) > 30) base = 50000;
    if (v.id === "fleet" && (status.fleet?.nodes_online || 0) > 0) base = 25000;
    return base;
  }

  function scheduleCarousel() {
    clearTimeout(timer);
    if (paused && Date.now() < pauseUntil) return;
    if (fullscreenId) return;
    timer = setTimeout(() => {
      focusIdx = (focusIdx + 1) % FOCUS_VIEWS.length;
      buildGrid();
      renderDots();
      scheduleCarousel();
    }, carouselMs());
  }

  function wavePath(phase, amp, freq) {
    const pts = [];
    for (let x = 0; x <= 120; x += 2) {
      const y = 16 + Math.sin((x + phase) * freq * 0.08) * amp;
      pts.push(`${x === 0 ? "M" : "L"}${x},${y.toFixed(1)}`);
    }
    return pts.join(" ");
  }

  function renderWaveforms() {
    wavePhase += 4;
    const amp = 3 + (metrics.cpu?.usage_pct || 0) * 0.1;
    const svg = document.getElementById("wave-focus");
    if (svg) {
      svg.innerHTML = `<path class="wave-path tone-cyan" d="${wavePath(wavePhase, amp, 1.1)}"/>
        <path class="wave-path tone-magenta" d="${wavePath(wavePhase + 30, amp * 0.6, 1.9)}" style="opacity:0.4"/>`;
    }
  }

  function updateSysStatus() {
    const el = document.getElementById("sys-status");
    if (!el) return;
    el.textContent = status.ollama?.online ? "ONLINE" : "DEGRADED";
  }

  function refresh() {
    buildGrid();
    renderDots();
    renderWaveforms();
    updateSysStatus();
    clockEl.textContent = new Date().toLocaleTimeString("it-IT", { hour12: false });
  }

  async function poll() {
    try {
      const [m, s, h, k, sc] = await Promise.all([
        fetch("/api/host/metrics").then((r) => r.json()),
        fetch("/api/status").then((r) => r.json()),
        fetch("/api/host/hardware").then((r) => r.json()).catch(() => ({})),
        fetch("/api/knowledge").then((r) => r.json()).catch(() => ({})),
        fetch("/api/scout/status").then((r) => r.json()).catch(() => ({})),
      ]);
      metrics = m;
      status = s;
      hardware = h;
      knowledge = k;
      scout = sc;
    } catch (_) { /* preview / offline */ }
    refresh();
  }

  stage.addEventListener("click", () => {
    if (fullscreenId) toggleFullscreen(fullscreenId);
  });

  refresh();
  poll();
  scheduleCarousel();
  setInterval(poll, 5000);
  setInterval(renderWaveforms, 250);
})();
