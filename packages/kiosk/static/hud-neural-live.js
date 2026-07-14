/** Rete neurale HUD — animazione canvas reattiva a eventi brain (WS) */
(function (global) {
  const STATE_COLORS = {
    IDLE: { a: "#2ec4ff", b: "#c86bff", speed: 0.4, glow: 0.15 },
    THINKING: { a: "#6ee7ff", b: "#2ec4ff", speed: 1.2, glow: 0.45 },
    ACTING: { a: "#ff8c42", b: "#c86bff", speed: 2.0, glow: 0.65 },
    SPEAKING: { a: "#3dff9a", b: "#2ec4ff", speed: 0.7, glow: 0.35 },
  };

  let canvas = null;
  let ctx = null;
  let nodes = [];
  let edges = [];
  let particles = [];
  let phase = 0;
  let state = "IDLE";
  let toolFlash = 0;
  let toolLabel = "";
  let raf = 0;
  let w = 0;
  let h = 0;

  function rand(seed) {
    const x = Math.sin(seed * 127.1) * 43758.5453;
    return x - Math.floor(x);
  }

  function buildGraph(cw, ch) {
    nodes = [];
    edges = [];
    const mkCluster = (cx, cy, r, count, side) => {
      for (let i = 0; i < count; i++) {
        const u = rand(i + side * 17);
        const v = rand(i + side * 31);
        const ang = u * Math.PI * 2;
        const rad = r * (0.35 + v * 0.65);
        nodes.push({
          x: cx + Math.cos(ang) * rad,
          y: cy + Math.sin(ang) * rad * 0.82,
          side,
          r: 2 + rand(i) * 2.5,
          pulse: rand(i * 5) * Math.PI * 2,
        });
      }
    };
    mkCluster(cw * 0.28, ch * 0.5, Math.min(cw, ch) * 0.22, 18, 0);
    mkCluster(cw * 0.72, ch * 0.5, Math.min(cw, ch) * 0.22, 18, 1);
    nodes.push({ x: cw * 0.5, y: ch * 0.5, side: 2, r: 5, pulse: 0, hub: true });
    const left = nodes.filter((n) => n.side === 0);
    const right = nodes.filter((n) => n.side === 1);
    const hub = nodes[nodes.length - 1];
    left.forEach((a, i) => {
      const b = left[(i + 3) % left.length];
      edges.push({ a, b, side: 0 });
      if (i % 4 === 0) edges.push({ a, b: hub, side: 2 });
    });
    right.forEach((a, i) => {
      const b = right[(i + 5) % right.length];
      edges.push({ a, b, side: 1 });
      if (i % 4 === 0) edges.push({ a, b: hub, side: 2 });
    });
    edges.push({ a: left[0], b: right[0], side: 2 });
    edges.push({ a: left[Math.floor(left.length / 2)], b: right[Math.floor(right.length / 2)], side: 2 });
  }

  function spawnParticles(speed) {
    if (edges.length === 0) return;
    const n = state === "ACTING" ? 4 : state === "THINKING" ? 2 : 1;
    for (let i = 0; i < n; i++) {
      const e = edges[Math.floor(Math.random() * edges.length)];
      particles.push({ e, t: 0, speed: 0.008 + Math.random() * 0.015 * speed });
    }
    if (particles.length > 120) particles.splice(0, particles.length - 120);
  }

  function resize() {
    if (!canvas || !canvas.parentElement) return;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = Math.max(320, rect.width);
    h = Math.max(200, rect.height);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildGraph(w, h);
  }

  function draw() {
    if (!ctx) return;
    const pal = STATE_COLORS[state] || STATE_COLORS.IDLE;
    phase += 0.016 * pal.speed;
    if (toolFlash > 0) toolFlash -= 0.02;

    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = `rgba(46, 196, 255, ${0.06 + pal.glow * 0.08})`;
    ctx.lineWidth = 1;
    const step = 32;
    for (let x = 0; x < w; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    edges.forEach((e) => {
      const col = e.side === 0 ? pal.a : e.side === 1 ? "#ffc44d" : pal.b;
      const alpha = 0.12 + pal.glow * 0.25 + (state === "ACTING" ? 0.15 : 0);
      ctx.strokeStyle = col.replace(")", `, ${alpha})`).replace("rgb", "rgba").replace("#", "");
      if (col.startsWith("#")) {
        const r = parseInt(col.slice(1, 3), 16);
        const g = parseInt(col.slice(3, 5), 16);
        const b = parseInt(col.slice(5, 7), 16);
        ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
      }
      ctx.lineWidth = e.side === 2 ? 1.2 : 0.7;
      ctx.beginPath();
      ctx.moveTo(e.a.x, e.a.y);
      ctx.lineTo(e.b.x, e.b.y);
      ctx.stroke();
    });

    spawnParticles(pal.speed);

    particles.forEach((p) => {
      p.t += p.speed * pal.speed;
      if (p.t >= 1) p.t = 0;
      const x = p.e.a.x + (p.e.b.x - p.e.a.x) * p.t;
      const y = p.e.a.y + (p.e.b.y - p.e.a.y) * p.t;
      ctx.fillStyle = state === "ACTING" ? "rgba(255,140,66,0.9)" : "rgba(110,231,255,0.85)";
      ctx.beginPath();
      ctx.arc(x, y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    });

    nodes.forEach((n) => {
      const pulse = 0.6 + Math.sin(phase * 2 + n.pulse) * 0.4;
      const base = n.side === 0 ? pal.a : n.side === 1 ? "#ffc44d" : pal.b;
      if (base.startsWith("#")) {
        const r = parseInt(base.slice(1, 3), 16);
        const g = parseInt(base.slice(3, 5), 16);
        const b = parseInt(base.slice(5, 7), 16);
        ctx.fillStyle = `rgba(${r},${g},${b},${0.35 + pulse * 0.45})`;
      }
      const rad = n.r * (n.hub ? 1.8 + pulse * 0.5 : 1 + pulse * 0.35);
      ctx.beginPath();
      ctx.arc(n.x, n.y, rad, 0, Math.PI * 2);
      ctx.fill();
      if (n.hub) {
        ctx.strokeStyle = `rgba(110,231,255,${0.4 + pal.glow})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(n.x, n.y, rad + 6 + Math.sin(phase * 3) * 3, 0, Math.PI * 2);
        ctx.stroke();
      }
    });

    if (toolFlash > 0 && toolLabel) {
      ctx.font = '600 11px "JetBrains Mono", monospace';
      ctx.fillStyle = `rgba(255,140,66,${Math.min(1, toolFlash)})`;
      ctx.fillText("▸ " + toolLabel.slice(0, 48), 12, h - 14);
    }

    raf = requestAnimationFrame(draw);
  }

  function setState(next) {
    let s = String(next || "IDLE").toUpperCase();
    if (s === "WORKING") s = "THINKING";
    if (["THINKING", "ACTING", "SPEAKING", "IDLE"].includes(s)) state = s;
    const ribbon = document.getElementById("hud-live-state");
    if (ribbon) {
      ribbon.textContent = state === "IDLE" ? "● LIVE" : "● " + state;
      ribbon.dataset.state = state.toLowerCase();
    }
    document.body.dataset.brainState = state.toLowerCase();
    if (global.JanisHudStage && global.JanisHudStage.setLiveStep) {
      const map = { IDLE: 0, THINKING: 1, ACTING: 2, SPEAKING: 4 };
      global.JanisHudStage.setLiveStep(map[state] ?? 0);
    }
  }

  function pulseTool(name) {
    toolLabel = name || "";
    toolFlash = 1.2;
    spawnParticles(2.5);
    spawnParticles(2.5);
  }

  function onBrainEvent(msg) {
    if (!msg || !msg.type) return;
    if (msg.type === "state") setState(msg.state);
    if (msg.type === "tool_start") {
      setState("ACTING");
      pulseTool(msg.tool || "");
    }
    if (msg.type === "chat_end") setState("IDLE");
    if (msg.type === "state" && msg.state === "IDLE") setState("IDLE");
  }

  function mount() {
    const wrap = document.querySelector(".hud-grid-wrap");
    if (!wrap || canvas) return;
    canvas = document.createElement("canvas");
    canvas.id = "hud-neural-canvas";
    canvas.setAttribute("aria-hidden", "true");
    wrap.insertBefore(canvas, wrap.firstChild);
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", resize);
    global.addEventListener("janis:brain", (ev) => onBrainEvent(ev.detail));
    draw();
  }

  global.JanisNeuralLive = { mount, setState, pulseTool, onBrainEvent };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})(window);
