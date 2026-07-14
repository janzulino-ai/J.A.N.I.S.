/** HUD visualizations — grafici, neuroni, pipeline animata (no Three.js) */
(function (global) {
  const W = 100;
  const H = 48;

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  function pathFromSeries(values, maxH) {
    if (!values.length) return "";
    const max = Math.max(...values, 1);
    const step = W / Math.max(values.length - 1, 1);
    return values.map((v, i) => {
      const x = i * step;
      const y = maxH - (v / max) * (maxH - 4) - 2;
      return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }

  function areaFromSeries(values, maxH) {
    const line = pathFromSeries(values, maxH);
    if (!line) return "";
    const lastX = ((values.length - 1) * W) / Math.max(values.length - 1, 1);
    return `${line} L${lastX},${maxH} L0,${maxH} Z`;
  }

  function sparkline(values, tone) {
    const v = values.length ? values : [0];
    const stroke = tone || "var(--term-cyan)";
    return `<svg class="viz-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <path class="viz-area tone-${tone || "cyan"}" d="${areaFromSeries(v, H)}"/>
      <path class="viz-line tone-${tone || "cyan"}" d="${pathFromSeries(v, H)}" fill="none" stroke="${stroke}"/>
    </svg>`;
  }

  function dualArea(cpu, ram) {
    const c = cpu.length ? cpu : [0];
    const r = ram.length ? ram : [0];
    return `<svg class="viz-dual" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <path class="viz-area tone-magenta" d="${areaFromSeries(r, H)}" opacity="0.35"/>
      <path class="viz-area tone-cyan" d="${areaFromSeries(c, H)}" opacity="0.45"/>
      <path class="viz-line tone-magenta" d="${pathFromSeries(r, H)}" fill="none"/>
      <path class="viz-line tone-cyan" d="${pathFromSeries(c, H)}" fill="none"/>
    </svg>`;
  }

  function arcGauge(pct, label, tone) {
    const p = clamp(Number(pct) || 0, 0, 100);
    const r = 36;
    const c = 2 * Math.PI * r;
    const off = c * (1 - p / 100);
    return `<div class="viz-arc tone-${tone || "cyan"}">
      <svg viewBox="0 0 96 56" aria-hidden="true">
        <circle class="arc-bg" cx="48" cy="48" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="0"/>
        <circle class="arc-fill" cx="48" cy="48" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${off}"/>
      </svg>
      <span class="arc-val">${Math.round(p)}%</span>
      <label>${label || ""}</label>
    </div>`;
  }

  function waveform(seed, tone) {
    const pts = [];
    const t = (seed || 0) * 0.01;
    for (let i = 0; i <= 40; i++) {
      const x = (i / 40) * W;
      const y = H / 2 + Math.sin(i * 0.35 + t) * 12 + Math.sin(i * 0.9 + t * 1.3) * 6;
      pts.push(`${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return `<svg class="viz-wave tone-${tone || "lime"}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <path class="wave-path" d="${pts.join(" ")}" fill="none"/>
      <path class="wave-path wave-echo" d="${pts.join(" ")}" fill="none"/>
    </svg>`;
  }

  function neuronOrb(count, tone, label, side) {
    const n = clamp(Number(count) || 0, 0, 999);
    const strands = Math.min(24, Math.max(8, Math.round(6 + n / 8)));
    let paths = "";
    for (let i = 0; i < strands; i++) {
      const a = (i / strands) * Math.PI * 2;
      const r0 = 18 + (i % 5);
      const x1 = 50 + Math.cos(a) * r0;
      const y1 = 50 + Math.sin(a) * r0 * 0.85;
      const x2 = 50 + Math.cos(a + 0.4) * (r0 + 14);
      const y2 = 50 + Math.sin(a + 0.4) * (r0 + 14) * 0.85;
      paths += `<line class="neuron-strand s${i % 4}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
    }
    const nodes = Math.min(12, Math.max(3, Math.round(n / 10) + 3));
    let dots = "";
    for (let i = 0; i < nodes; i++) {
      const a = (i / nodes) * Math.PI * 2 + 0.2;
      const r = 12 + (i % 4) * 5;
      dots += `<circle class="neuron-node n${i % 3}" cx="${50 + Math.cos(a) * r}" cy="${50 + Math.sin(a) * r * 0.9}" r="2.2"/>`;
    }
    return `<div class="viz-neuron-orb tone-${tone || "cyan"} side-${side || "left"}">
      <svg class="neuron-svg" viewBox="0 0 100 100" aria-hidden="true">
        <circle class="neuron-core" cx="50" cy="50" r="10"/>
        ${paths}
        ${dots}
      </svg>
      <div class="neuron-meta">
        <span class="neuron-count">${n}</span>
        <span class="neuron-lbl">${label || "NODI"}</span>
      </div>
    </div>`;
  }

  function pipelineAnim(steps, liveIdx, provider) {
    const list = steps || ["INPUT", "THINK", "TOOLS", "AGENTS", "OUT"];
    const live = liveIdx ?? 0;
    const nodes = list.map((s, i) => {
      const cls = i === live ? "live" : i < live ? "done" : "";
      return `<span class="pipe-node anim ${cls}" style="--i:${i}">${s}</span>`;
    }).join('<span class="pipe-connector anim"></span>');
    return `<div class="viz-pipeline">
      <div class="pipeline synapse-flow">${nodes}</div>
      <div class="pipe-provider">${provider || "OLLAMA"}</div>
    </div>`;
  }

  function dualBrainBridge(userN, janisN, liveStep) {
    return `<div class="viz-dual-brain">
      ${neuronOrb(janisN, "magenta", "JANIS BRAIN", "left")}
      <div class="brain-bridge">
        ${pipelineAnim(["IN", "THINK", "TOOL", "OUT"], liveStep, "")}
        <svg class="synapse-bridge" viewBox="0 0 60 40" aria-hidden="true">
          <path class="synapse-path" d="M4,20 C20,4 40,36 56,20"/>
          <path class="synapse-path delay" d="M4,24 C22,38 38,6 56,24"/>
          <circle class="synapse-pulse" cx="30" cy="20" r="3"/>
        </svg>
      </div>
      ${neuronOrb(userN, "gold", "USER BRAIN", "right")}
    </div>`;
  }

  function miniCells(items) {
    return `<div class="viz-minis">${items.map((it) =>
      `<div class="viz-mini tone-${it.tone || "cyan"}">
        <span class="vm-lbl">${it.label}</span>
        <span class="vm-val">${it.val}</span>
      </div>`
    ).join("")}</div>`;
  }

  global.HudViz = {
    sparkline,
    dualArea,
    arcGauge,
    waveform,
    neuronOrb,
    pipelineAnim,
    dualBrainBridge,
    miniCells,
  };
})(window);
