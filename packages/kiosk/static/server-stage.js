(function () {
  let perception = {};
  let peripherals = {};
  let llmModels = {};
  let evolve = {};
  let hudPage = 0;

  const BLOCKS = [
    { id: "hardware", page: 0, col: 1, row: 1, colSpan: 1, rowSpan: 1, title: "HARDWARE LIVE", accent: "cyan" },
    { id: "inventory", page: 0, col: 2, row: 1, colSpan: 1, rowSpan: 1, title: "INVENTARIO", accent: "gold" },
    { id: "network", page: 0, col: 3, row: 1, colSpan: 1, rowSpan: 1, title: "RETE · LOAD", accent: "lime" },
    { id: "disks", page: 0, col: 1, row: 2, colSpan: 1, rowSpan: 1, title: "DISCHI · BLOCK", accent: "gold" },
    { id: "sidecars", page: 0, col: 2, row: 2, colSpan: 1, rowSpan: 1, title: "SIDECAR · STACK", accent: "lime" },
    { id: "providers", page: 0, col: 3, row: 2, colSpan: 1, rowSpan: 1, title: "ROUTING · COSTI", accent: "gold" },
    { id: "services", page: 0, col: 1, row: 3, colSpan: 1, rowSpan: 1, title: "SERVIZI · CANALI", accent: "lime" },
    { id: "fleet", page: 0, col: 2, row: 3, colSpan: 1, rowSpan: 1, title: "FLOTTA · I/O", accent: "magenta" },
    { id: "brain", page: 0, col: 3, row: 3, colSpan: 1, rowSpan: 1, title: "CERVELLO · TOOL", accent: "magenta" },
    { id: "peripherals", page: 1, col: 1, row: 1, colSpan: 1, rowSpan: 2, title: "PERIFERICHE", accent: "magenta" },
    { id: "perception", page: 1, col: 2, row: 1, colSpan: 1, rowSpan: 2, title: "VEDERE · SENTIRE", accent: "cyan" },
    { id: "llm", page: 1, col: 3, row: 1, colSpan: 1, rowSpan: 1, title: "MODELLI LLM", accent: "gold" },
    { id: "evolve", page: 1, col: 3, row: 2, colSpan: 1, rowSpan: 1, title: "AUTO-EVOLVE", accent: "lime" },
  ];

  const PAUSE_MS = 10 * 60 * 1000;
  let fullscreenId = null;
  let pauseUntil = 0;
  let timer = null;
  let pollOk = false;
  let pollErr = "";
  let pollCount = 0;

  let dash = {};
  let metrics = {};
  let status = {};
  let inventory = {};
  let knowledge = {};
  let scout = {};
  let gaps = {};
  let winVm = {};
  let tools = [];
  let mcp = {};
  let reasoning = {};

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
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d) return `${d}D ${h}H`;
    return `${h}H ${m}M`;
  }

  function formatBytes(n) {
    if (n == null || isNaN(n)) return "—";
    const u = ["B", "KB", "MB", "GB", "TB"];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(i > 1 ? 1 : 0)} ${u[i]}`;
  }

  function statRow(label, value, tone) {
    return `<div class="stat-row tone-${tone || "cyan"}">
      <span class="stat-lbl">${label}</span>
      <span class="stat-val">${esc(value)}</span>
    </div>`;
  }

  function badge(text, on, extra) {
    return `<span class="proc-badge ${on ? "on" : (extra || "off")}">${text}</span>`;
  }

  function sidecarRow(name, on, detail) {
    return `<div class="proc-row">
      <span class="proc-name">${name}</span>
      ${badge(on ? "ON" : "OFF", on)}
      ${detail ? `<span class="proc-detail">${esc(detail)}</span>` : ""}
    </div>`;
  }

  function physicalDisks(list) {
    return (list || []).filter((d) => {
      const m = d.mount || "";
      return !m.startsWith("/snap") && d.fstype !== "squashfs";
    });
  }

  function applyDashboard(d) {
    dash = d || {};
    metrics = d.metrics || {};
    status = d.status || {};
    inventory = d.inventory || {};
    knowledge = d.knowledge || {};
    scout = d.scout || {};
    gaps = d.gaps || {};
    winVm = d.win_vm || {};
    tools = d.tools || [];
    mcp = d.mcp || {};
    reasoning = d.reasoning || {};
    perception = d.perception || {};
    peripherals = d.peripherals || inventory.peripherals || {};
    llmModels = d.llm_models || {};
    evolve = d.evolve || {};
  }

  function renderHardware() {
    const cpu = metrics.cpu || {};
    const gpu = metrics.gpu || {};
    const mem = metrics.memory || {};
    return `<div class="block-body scroll-y">
      <div class="big-metrics compact">
        <div class="big-metric tone-cyan"><span class="bm-val">${Math.round(cpu.usage_pct || 0)}%</span><span class="bm-lbl">CPU</span></div>
        <div class="big-metric tone-magenta"><span class="bm-val">${Math.round(mem.usage_pct || 0)}%</span><span class="bm-lbl">RAM</span></div>
        <div class="big-metric tone-gold"><span class="bm-val">${Math.round(gpu.usage_pct || 0)}%</span><span class="bm-lbl">GPU</span></div>
      </div>
      ${statRow("HOST", (metrics.hostname || inventory.hostname || "—").toUpperCase())}
      ${statRow("PLATFORM", `${metrics.platform || inventory.platform || "—"} ${inventory.release || ""}`.trim())}
      ${statRow("CPU", inventory.cpu?.model || "—", "cyan")}
      ${statRow("CORES", inventory.cpu?.cores_logical || "—", "lime")}
      ${statRow("RAM TOT", inventory.memory_gb ? `${inventory.memory_gb} GB` : "—", "gold")}
      ${statRow("TEMP CPU", cpu.temp_c != null ? `${Math.round(cpu.temp_c)}°C` : "—", (cpu.temp_c || 0) > 75 ? "warn" : "cyan")}
      ${gpu.name ? statRow("GPU", gpu.name, "gold") : statRow("GPU", "non rilevata", "warn")}
      ${statRow("UPTIME", formatUptime(metrics.uptime_sec), "lime")}
      ${statRow("BRAIN UP", formatUptime(metrics.process_uptime_sec), "muted")}
    </div>`;
  }

  function renderInventory() {
    const gpus = inventory.gpu || [];
    const probed = inventory.probed_at ? new Date(inventory.probed_at).toLocaleString("it-IT") : "—";
    return `<div class="block-body scroll-y">
      ${statRow("HOSTNAME", inventory.hostname || "—")}
      ${statRow("KERNEL", inventory.release || "—", "lime")}
      ${statRow("ARCH", inventory.arch || "—", "cyan")}
      ${statRow("USB DEV", inventory.usb_devices ?? "—", "magenta")}
      ${statRow("PROBED", probed, "muted")}
      ${gpus.length ? gpus.map((g) => statRow("GPU", `${g.name || "?"} · ${g.vram || ""} ${g.driver || ""}`.trim(), "gold")).join("") : statRow("GPU", "nessuna", "warn")}
      <div class="mini-head">BLOCK DEV</div>
      ${(inventory.block_devices || []).slice(0, 8).map((b) =>
        statRow(b.name || "dev", `${b.size || "?"} · ${b.type || ""} ${b.model || ""}`.trim(), "cyan")
      ).join("") || statRow("BLOCK", "—", "warn")}
    </div>`;
  }

  function renderNetwork() {
    const nics = inventory.network || [];
    const net = metrics.network || {};
    const la = metrics.cpu?.load_avg || {};
    return `<div class="block-body scroll-y">
      ${statRow("RX", formatBytes(net.rx_bytes), "cyan")}
      ${statRow("TX", formatBytes(net.tx_bytes), "lime")}
      ${la["1m"] != null ? statRow("LOAD 1M", Number(la["1m"]).toFixed(2), "gold") : ""}
      ${la["5m"] != null ? statRow("LOAD 5M", Number(la["5m"]).toFixed(2), "gold") : ""}
      ${la["15m"] != null ? statRow("LOAD 15M", Number(la["15m"]).toFixed(2), "gold") : ""}
      ${statRow("GLANCES", metrics.glances ? "ON :61208" : "OFF", metrics.glances ? "lime" : "warn")}
      <div class="mini-head">NIC</div>
      ${nics.length ? nics.map((n) =>
        statRow(n.name, (n.addresses || []).join(" · ") || "down", "cyan")
      ).join("") : statRow("NIC", "nessuna", "warn")}
    </div>`;
  }

  function renderDisks() {
    const disks = physicalDisks(inventory.disks || metrics.disk || []);
    if (!disks.length) return `<div class="block-body scroll-y">${statRow("DISCHI", "nessuno", "warn")}</div>`;
    return `<div class="block-body scroll-y">${disks.map((d) => {
      const label = d.device || d.mount || "?";
      return `<div class="disk-row">
        <div class="disk-head"><span>${esc(label)}</span><span>${d.used_pct ?? 0}%</span></div>
        <div class="proc-bar-wrap"><span class="proc-bar tone-gold" style="width:${d.used_pct || 0}%"></span></div>
        <div class="disk-sub">${esc(d.mount || "")} ${esc(d.fstype || "")} · ${d.total_gb ?? "?"} GB · free ${d.free_gb ?? "?"} GB</div>
      </div>`;
    }).join("")}</div>`;
  }

  function renderSidecars() {
    const sc = metrics.sidecars || {};
    const oll = status.ollama || {};
    const lp = status.llm_provider || {};
    const sched = status.scheduler || {};
    return `<div class="block-body scroll-y">
      <div class="process-list">
        ${sidecarRow("JANIS BRAIN", sc.brain !== false, `v${status.brain_version || "?"}`)}
        ${sidecarRow("OLLAMA", !!(sc.ollama || oll.online), (oll.models || []).slice(0, 2).join(", ") || "off")}
        ${sidecarRow("GLANCES", !!sc.glances, sc.glances ? ":61208" : "off")}
        ${sidecarRow("LITELLM", !!(sc.litellm || lp.litellm_online), lp.active || "proxy")}
        ${sidecarRow("QDRANT", !!sc.qdrant, sc.qdrant ? ":6333" : "off")}
        ${sidecarRow("STT", !!status.stt?.ready, status.stt?.engine || "—")}
        ${sidecarRow("SCHEDULER", !!sched.running, `${sched.enabled_jobs || 0}/${sched.job_count || 0} job`)}
        ${sidecarRow("AUTONOMY", !!sched.autonomy_running, sched.autonomy_enabled ? "loop" : "off")}
      </div>
    </div>`;
  }

  function renderProviders() {
    const orch = status.orchestrator || {};
    const usage = status.llm_usage || {};
    const lp = status.llm_provider || {};
    const byTier = (lp.ollama_probe || {}).by_tier || {};
    const prov = (reasoning.provider || lp.active || status.reasoning_provider || "ollama").toUpperCase();
    const budget = orch.daily_budget_usd ?? 2;
    const spent = usage.spent_today_usd ?? orch.spent_today_usd ?? 0;
    const rem = orch.remaining_usd ?? budget;
    const pct = budget ? Math.min(100, (spent / budget) * 100) : 0;
    return `<div class="block-body scroll-y">
      ${orch.cloud_blocked ? `<div class="warning-strip">CLOUD BLOCCATO</div>` : ""}
      <div class="provider-hero tone-gold">
        <span class="ph-main">${prov}</span>
        <span class="ph-sub">${status.paid_mode ? "PRO" : "FREE"} · ${lp.configured || "local"}</span>
      </div>
      <div class="budget-bar"><span class="budget-fill" style="width:${pct}%"></span></div>
      <div class="budget-labels">
        <span>$${Number(spent).toFixed(2)} · ${usage.calls_today ?? 0} call</span>
        <span>$${Number(rem).toFixed(2)} / $${budget}</span>
      </div>
      ${statRow("MODELLO", lp.ollama_model || ollamaModel(), "cyan")}
      ${byTier.fast ? statRow("FAST", byTier.fast, "lime") : ""}
      ${byTier.balanced ? statRow("BALANCED", byTier.balanced, "gold") : ""}
      ${byTier.capable ? statRow("CAPABLE", byTier.capable, "magenta") : ""}
      ${statRow("FALLBACK", (lp.fallback_chain || []).join(" → ") || "—", "lime")}
      ${statRow("LATENZA", usage.avg_latency_ms ? `${Math.round(usage.avg_latency_ms)}ms` : "—", "gold")}
      ${statRow("TIER", reasoning.tier || (orch.default_tier || "local").toUpperCase(), "lime")}
      ${statRow("MODE", reasoning.mode || (orch.mode || "—").toUpperCase(), "magenta")}
      ${(status.paid_capabilities || []).map((c) =>
        statRow(c.name.toUpperCase(), c.key_present ? `${c.tier} · KEY OK` : `${c.tier} · NO KEY`, c.key_present ? "lime" : "warn")
      ).join("")}
    </div>`;
  }

  function ollamaModel() {
    const o = status.ollama || {};
    return o.models?.[0] || "—";
  }

  function renderServices() {
    const skills = status.channel_skills?.skills || [];
    const sched = status.scheduler || {};
    const core = [
      { label: "JANIS.API", on: pollOk, tag: pollOk ? "LIVE" : "ERR" },
      { label: "OLLAMA", on: !!status.ollama?.online, tag: status.ollama?.online ? "ON" : "OFF" },
      { label: "STT", on: !!status.stt?.ready, tag: status.stt?.engine || "OFF" },
      { label: "COST_ROUTER", on: !status.orchestrator?.cloud_blocked, tag: (status.orchestrator?.mode || "LOCAL").toUpperCase() },
      { label: "CURSOR", on: !!status.paid_mode, tag: status.paid_mode ? "PRO" : "FREE" },
      { label: "WS CLIENTS", on: (status.connected_clients || []).length > 0, tag: `${(status.connected_clients || []).length}` },
    ];
    const coreHtml = core.map((p) => `<div class="proc-row"><span class="proc-name">${p.label}</span>${badge(p.tag, p.on)}</div>`).join("");
    const skillHtml = skills.map((s) => {
      const caps = (s.capabilities || []).join(",");
      const why = !s.ready && s.requires ? `manca ${s.requires.join(",")}` : (s.ready ? caps : "not ready");
      return `<div class="proc-row"><span class="proc-name">${(s.channel || s.id).toUpperCase()}</span>${badge(s.ready ? "READY" : "WAIT", s.ready, s.ready ? "on" : "exe")}<span class="proc-detail">${esc(why)}</span></div>`;
    }).join("");
    const jobHtml = (sched.jobs || []).map((j) =>
      `<div class="proc-row"><span class="proc-name">${(j.id || "?").toUpperCase()}</span>${badge(j.enabled ? "ON" : "OFF", j.enabled)}<span class="proc-detail">${j.action} @ ${j.hour}:${String(j.minute).padStart(2, "0")}</span></div>`
    ).join("");
    return `<div class="block-body scroll-y">
      <div class="mini-head">CORE · ${pollOk ? "API OK" : "API ERR"}</div>
      <div class="process-list">${coreHtml}</div>
      <div class="mini-head">CANALI · ${status.channel_skills?.ready_count ?? 0} ready</div>
      <div class="process-list">${skillHtml || statRow("CANALI", "—", "warn")}</div>
      <div class="mini-head">SCHEDULER</div>
      <div class="process-list">${jobHtml || statRow("JOBS", "—", "warn")}</div>
    </div>`;
  }

  function renderFleet() {
    const nodes = status.fleet?.nodes || [];
    const mac = status.mac_node || {};
    const pres = status.presence || {};
    const pocket = status.pocket_api || {};
    const vm = winVm || {};
    return `<div class="block-body scroll-y">
      <div class="mini-head">NODI · ${status.fleet?.nodes_online || 0}/${status.fleet?.nodes_total || 0}</div>
      ${nodes.map((n) =>
        `<div class="fleet-card ${n.online ? "online" : "offline"} compact">
          <span class="fleet-icon">${n.online ? "◉" : "◎"}</span>
          <div><div class="fleet-name">${esc(n.node_id || n.hostname)}</div>
          <div class="fleet-info">${esc(n.os || "")} · hb ${n.last_heartbeat_sec_ago != null ? `${Math.round(n.last_heartbeat_sec_ago)}s` : "—"}</div></div>
          <span class="fleet-status">${n.online ? "LINK" : "GAP"}</span>
        </div>`
      ).join("") || statRow("FLEET", "vuota", "warn")}
      ${statRow("MAC SSH", mac.online ? "ONLINE" : "OFFLINE", mac.online ? "lime" : "warn")}
      ${mac.info ? statRow("MAC ERR", String(mac.info).slice(0, 48), "warn") : ""}
      ${statRow("WIN-VM", vm.available ? (vm.state || "?").toUpperCase() : "N/D", vm.state === "running" ? "lime" : "warn")}
      ${vm.disk ? statRow("VM DISK", vm.disk, "muted") : ""}
      ${statRow("VNC", vm.vnc ? `${vm.vnc.host}:${vm.vnc.port}` : "—", "cyan")}
      ${statRow("PRESENCE", `${pres.surface || "—"} · ${pres.power_state || "—"}`, "magenta")}
      ${statRow("ACTIVE WS", status.active_client || "—", "gold")}
      <div class="mini-head">POCKET API</div>
      ${Object.entries(pocket).map(([k, v]) => statRow(k.toUpperCase(), v, "cyan")).join("")}
    </div>`;
  }

  function renderBrain() {
    const nodes = reasoning.pipeline || ["INPUT", "THINK", "TOOLS", "AGENTS", "OUT"];
    const live = reasoning.live_step ?? 0;
    const pipe = nodes.map((n, i) => {
      const conn = i > 0 ? '<span class="pipe-connector"></span>' : "";
      return `${conn}<span class="pipe-node ${i === live ? "live" : ""}">${n}</span>`;
    }).join("");
    const open = gaps.open || [];
    const gs = gaps.stats || {};
    return `<div class="block-body scroll-y">
      <div class="mini-head">PIPELINE · ${reasoning.provider || "—"}</div>
      <div class="pipeline-wrap compact"><div class="pipeline">${pipe}</div></div>
      ${statRow("TOOLS", `${tools.length} registrati`, "lime")}
      ${statRow("MCP", `${(mcp.mcp_servers || []).length} server`, "cyan")}
      <div class="mini-head">TOOL REGISTRY</div>
      ${tools.slice(0, 12).map((t) => statRow(t, "OK", "cyan")).join("")}
      ${tools.length > 12 ? statRow("…", `+${tools.length - 12}`, "muted") : ""}
      <div class="mini-head">MEMORIA · L${knowledge.level ?? "—"}</div>
      ${statRow("MEM TOTAL", knowledge.memories ?? knowledge.count ?? 0, "gold")}
      ${statRow("USER / JANIS", `${knowledge.user_memories ?? 0} / ${knowledge.janis_memories ?? 0}`, "magenta")}
      ${statRow("SESSION MSG", status.session_messages ?? 0, "cyan")}
      ${statRow("GAP APERTI", gs.open ?? open.length, gs.open ? "warn" : "lime")}
      ${open.slice(0, 3).map((g) => statRow("GAP", String(g.description || g.id).slice(0, 36), "warn")).join("")}
      ${statRow("SCOUT", scout.total ?? 0, "gold")}
      ${(scout.recent || []).slice(0, 3).map((c) => statRow(c.name, `${c.status} · ${c.deployment || "local"}`, "cyan")).join("")}
    </div>`;
  }

  function renderPeripherals() {
    const p = peripherals || {};
    const usb = p.usb || {};
    const aud = p.audio || {};
    const vid = p.video || {};
    const disp = p.displays || {};
    const bt = p.bluetooth || {};
    const inp = p.input || {};
    const missing = p.missing || [];
    return `<div class="block-body scroll-y">
      ${statRow("RIEPILOGO", p.summary || "—", "cyan")}
      ${missing.length ? `<div class="warning-strip">MANCA: ${missing.join(", ")}</div>` : ""}
      <div class="mini-head">USB · ${usb.count || 0}</div>
      ${(usb.devices || []).slice(0, 8).map((u) => statRow(u.id || "?", (u.name || "").slice(0, 32), "gold")).join("") || statRow("USB", "nessuno", "warn")}
      <div class="mini-head">AUDIO · ${aud.cards || 0} schede</div>
      ${(aud.devices || []).map((a) => statRow(`CARD ${a.card}`, a.name, aud.ready ? "lime" : "warn")).join("") || statRow("AUDIO", "non rilevato", "warn")}
      ${(aud.capture_lines || []).slice(0, 3).map((l) => statRow("CAP", l.slice(0, 40), "muted")).join("")}
      <div class="mini-head">VIDEO · ${vid.count || 0}</div>
      ${(vid.devices || []).map((v) => statRow(v.name || v.node, v.node || "", vid.ready ? "lime" : "warn")).join("") || statRow("CAMERA", "non rilevata", "warn")}
      <div class="mini-head">DISPLAY · ${disp.count || 0}</div>
      ${(disp.outputs || []).slice(0, 4).map((o) => statRow(o.connector, o.status + (o.mode ? ` ${o.mode}` : ""), "cyan")).join("")}
      ${statRow("BLUETOOTH", bt.adapters || 0, bt.adapters ? "lime" : "muted")}
      ${statRow("INPUT", inp.count || 0, "magenta")}
      ${(inp.by_id || []).slice(0, 4).map((n) => statRow("DEV", n.slice(0, 36), "muted")).join("")}
    </div>`;
  }

  function renderPerception() {
    const stt = perception.stt || status.stt || {};
    const vis = perception.vision || {};
    const hw = perception.hardware_needed || [];
    return `<div class="block-body scroll-y">
      ${statRow("LOCAL FIRST", perception.local_first ? "SI" : "NO", perception.local_first ? "lime" : "warn")}
      ${statRow("CLOUD", perception.cloud_llm_allowed ? "ALLOW" : "BLOCK", perception.cloud_llm_allowed ? "warn" : "lime")}
      <div class="mini-head">ASCOLTO (STT)</div>
      ${statRow("ENGINE", stt.engine || "—", stt.ready ? "lime" : "warn")}
      ${statRow("READY", stt.ready ? "SI" : "NO", stt.ready ? "lime" : "warn")}
      ${statRow("API", stt.endpoint || "/api/stt", "cyan")}
      <div class="mini-head">VISIONE</div>
      ${statRow("MODELLI", (vis.ollama_vision_models || []).join(", ") || "nessuno", vis.vision_ready ? "lime" : "warn")}
      ${statRow("FRAME POCKET", vis.recent_frames ?? 0, "gold")}
      ${statRow("ULTIMO", vis.last_frame || "—", "muted")}
      ${statRow("API", vis.pocket_endpoint || "/api/pocket/vision", "cyan")}
      ${hw.length ? `<div class="warning-strip">${hw.join(" · ")}</div>` : statRow("PERCEZIONE", "OK", "lime")}
      ${statRow("WIN-VM", (perception.win_vm || {}).state || "—", "cyan")}
    </div>`;
  }

  function renderLlm() {
    const by = llmModels.by_tier || {};
    const results = llmModels.results || [];
    return `<div class="block-body scroll-y">
      ${statRow("ATTIVI", (llmModels.working || []).join(", ") || "—", "lime")}
      ${statRow("FAST", by.fast || "—", "lime")}
      ${statRow("BALANCED", by.balanced || "—", "gold")}
      ${statRow("CAPABLE", by.capable || "—", "magenta")}
      <div class="mini-head">PROBE LATENZA</div>
      ${results.map((r) => statRow(r.model, r.ok ? `${Math.round(r.latency_ms)}ms` : "FAIL", r.ok ? "cyan" : "warn")).join("") || statRow("PROBE", "—", "warn")}
    </div>`;
  }

  function renderEvolve() {
    const au = evolve.autonomy || {};
    const sched = evolve.scheduler || status.scheduler || {};
    const props = evolve.proposals || [];
    const lab = evolve.lab || {};
    const labRun = lab.active_run || lab.latest_run || {};
    const labStatus = lab.active_run ? (labRun.stage || "RUN") : (lab.ready_train ? "READY" : "IDLE");
    const labTone = lab.active_run ? "cyan" : lab.ready_train ? "lime" : "muted";
    return `<div class="block-body scroll-y">
      ${statRow("GAP APERTI", evolve.gaps_open ?? 0, evolve.gaps_open ? "warn" : "lime")}
      ${statRow("PROPOSTE", evolve.proposals_open ?? 0, "gold")}
      ${statRow("SCOUT", evolve.scout_total ?? 0, "cyan")}
      ${statRow("LLM LAB", labStatus, labTone)}
      ${statRow("DATASET", lab.curated_examples ?? 0, (lab.curated_examples || 0) >= (lab.min_dataset_size || 30) ? "lime" : "warn")}
      ${statRow("GPU LAB", lab.gpu && lab.gpu.available ? "OK" : "NO", lab.gpu && lab.gpu.available ? "lime" : "warn")}
      ${statRow("AUTONOMY", au.enabled ? "ON" : "OFF", au.enabled ? "lime" : "warn")}
      ${statRow("REFLECT", au.reflect ? "ON" : "OFF", "lime")}
      ${statRow("AUTODEV", au.autodev ? "ON" : "OFF", au.autodev ? "lime" : "muted")}
      ${statRow("SCHEDULER", sched.running ? "RUN" : "STOP", sched.running ? "lime" : "warn")}
      ${props.slice(0, 2).map((p) => statRow("PROP", String(p.title || p.id || "?").slice(0, 30), "gold")).join("")}
      ${(scout.recent || []).slice(0, 1).map((c) => statRow("SCOUT", c.name, "cyan")).join("")}
    </div>`;
  }

  const RENDERERS = {
    hardware: renderHardware,
    inventory: renderInventory,
    network: renderNetwork,
    disks: renderDisks,
    sidecars: renderSidecars,
    providers: renderProviders,
    services: renderServices,
    fleet: renderFleet,
    brain: renderBrain,
    peripherals: renderPeripherals,
    perception: renderPerception,
    llm: renderLlm,
    evolve: renderEvolve,
  };

  function visibleBlocks() {
    return BLOCKS.filter((b) => b.page === hudPage);
  }

  function blockStyle(b) {
    if (b.page !== hudPage && !fullscreenId) return "display:none";
    if (!fullscreenId) return `grid-column:${b.col} / span ${b.colSpan};grid-row:${b.row} / span ${b.rowSpan}`;
    if (fullscreenId === b.id) return "grid-column:1 / span 3;grid-row:1 / span 3";
    return "display:none";
  }

  function buildGrid() {
    gridEl.innerHTML = visibleBlocks().map((b) => {
      const isFs = fullscreenId === b.id;
      return `<article class="hud-block accent-${b.accent} ${isFs ? "is-focus" : ""}" data-id="${b.id}" style="${blockStyle(b)}" tabindex="0">
        <div class="block-frame">
          <div class="block-scan"></div>
          <span class="block-id">${b.id.slice(0, 3).toUpperCase()}</span>
          <header class="block-head"><span class="block-title">${b.title}</span><span class="block-expand">${isFs ? "◈ EXP" : "⊞"}</span></header>
          ${(RENDERERS[b.id] || (() => ""))()}
        </div>
      </article>`;
    }).join("");
    gridEl.querySelectorAll(".hud-block").forEach((el) => {
      el.addEventListener("click", (e) => { e.stopPropagation(); toggleFullscreen(el.dataset.id); });
    });
  }

  function toggleFullscreen(id) {
    if (fullscreenId === id) {
      fullscreenId = null;
      stage.classList.remove("grid-fullscreen");
      pauseBadge.classList.add("hidden");
      footMeta.textContent = pollOk ? `PAG ${hudPage + 1}/2 · POLL 5S` : `ERR: ${pollErr}`;
    } else {
      fullscreenId = id;
      stage.classList.add("grid-fullscreen");
      pauseUntil = Date.now() + PAUSE_MS;
      pauseBadge.classList.remove("hidden");
      footMeta.textContent = `FULL · ${id.toUpperCase()}`;
      clearTimeout(timer);
      timer = setTimeout(() => {
        fullscreenId = null;
        stage.classList.remove("grid-fullscreen");
        pauseBadge.classList.add("hidden");
        buildGrid();
      }, PAUSE_MS);
    }
    buildGrid();
  }

  function renderDots() {
    const pages = ["OPS", "I/O · PERCEZIONE"];
    dotsEl.innerHTML = pages.map((label, i) =>
      `<span class="dot ${i === hudPage ? "on" : ""}" data-page="${i}" title="${label}"></span>`
    ).join("");
    dotsEl.querySelectorAll(".dot").forEach((d) => {
      d.addEventListener("click", (e) => {
        e.stopPropagation();
        hudPage = parseInt(d.dataset.page, 10);
        fullscreenId = null;
        stage.classList.remove("grid-fullscreen");
        buildGrid();
        renderDots();
        footMeta.textContent = pollOk
          ? `PAG ${hudPage + 1}/2 · ${pages[hudPage]} · POLL 5S`
          : `API ERR · ${pollErr}`;
      });
    });
  }

  function updateSysStatus() {
    const el = document.getElementById("sys-status");
    if (!el) return;
    if (!pollOk) { el.textContent = "NO DATA"; return; }
    const ok = status.ollama?.online && metrics.sidecars?.brain !== false;
    el.textContent = ok ? "ONLINE" : "DEGRADED";
  }

  function refresh() {
    buildGrid();
    renderDots();
    updateSysStatus();
    if (clockEl) clockEl.textContent = new Date().toLocaleTimeString("it-IT", { hour12: false });
    if (!fullscreenId) {
      footMeta.textContent = pollOk
        ? `PAG ${hudPage + 1}/2 · LIVE · POLL 5S`
        : `API ERR · ${pollErr}`;
    }
  }

  async function poll() {
    pollCount += 1;
    const refreshInv = pollCount % 12 === 1;
    try {
      const r = await fetch(`/api/hud/dashboard${refreshInv ? "?refresh_inventory=true" : ""}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (!d.ok) throw new Error("dashboard not ok");
      applyDashboard(d);
      pollOk = true;
      pollErr = "";
    } catch (e) {
      pollOk = false;
      pollErr = e.message || "fetch failed";
    }
    refresh();
  }

  stage.addEventListener("click", () => { if (fullscreenId) toggleFullscreen(fullscreenId); });
  refresh();
  poll();
  setInterval(poll, 5000);
})();
