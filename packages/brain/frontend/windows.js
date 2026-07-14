import RFB from "/static/vendor/novnc-esm/core/rfb.js";

const screen = document.getElementById("screen");
const stateEl = document.getElementById("vm-state");
const statusEl = document.getElementById("status-line");

let rfb = null;
let reconnectTimer = null;

async function refreshStatus() {
  try {
    const r = await fetch("/api/win-vm/status");
    const d = await r.json();
    stateEl.textContent = d.state || d.error || "?";
    stateEl.className = "badge " + (d.state === "running" ? "on" : "off");
    if (d.state !== "running" && rfb) {
      disconnectVnc("VM non running");
    }
    if (d.state === "running" && !rfb) {
      scheduleConnect(500);
    }
  } catch (_) {
    stateEl.textContent = "err";
  }
}

function disconnectVnc(reason) {
  if (rfb) {
    try { rfb.disconnect(); } catch (_) { /* ignore */ }
    rfb = null;
  }
  if (reason) statusEl.textContent = reason;
}

function wakeDisplay() {
  if (!rfb) return;
  try {
    rfb.sendPointerEvent(400, 300, 0);
    rfb.sendKey(0xff0d, "Enter", false);
  } catch (_) { /* ignore */ }
}

function connectVnc() {
  if (rfb) return;
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${location.host}/ws/vnc`;
  statusEl.textContent = "Connessione VNC…";
  try {
    screen.innerHTML = "";
    rfb = new RFB(screen, url, {
      shared: true,
    });
    rfb.viewOnly = false;
    rfb.scaleViewport = true;
    rfb.resizeSession = true;
    rfb.clipViewport = false;
    rfb.showDotCursor = true;
    rfb.qualityLevel = 6;
    rfb.compressionLevel = 2;

    rfb.addEventListener("connect", () => {
      statusEl.textContent = "VNC connesso — Windows attivo";
      fetch("/api/win-vm/wake", { method: "POST" }).catch(() => {});
      setTimeout(wakeDisplay, 400);
      setTimeout(wakeDisplay, 2000);
    });
    rfb.addEventListener("desktopname", (e) => {
      if (e.detail?.name) statusEl.textContent = "Desktop: " + e.detail.name;
    });
    rfb.addEventListener("securityfailure", (e) => {
      statusEl.textContent = "VNC auth fallita: " + (e.detail?.reason || "?");
      rfb = null;
      scheduleConnect(5000);
    });
    rfb.addEventListener("disconnect", (e) => {
      rfb = null;
      statusEl.textContent = e.detail?.clean ? "Disconnesso" : "VNC offline";
      scheduleConnect(3000);
    });
  } catch (err) {
    rfb = null;
    statusEl.textContent = "VNC errore: " + (err?.message || err);
    scheduleConnect(4000);
  }
}

function scheduleConnect(ms) {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectVnc, ms);
}

async function vmAction(path) {
  statusEl.textContent = path + "…";
  await fetch(path, { method: "POST" });
  await refreshStatus();
  if (path.includes("start") || path.includes("reboot")) {
    scheduleConnect(8000);
  }
}

document.getElementById("btn-start").onclick = () => vmAction("/api/win-vm/start");
document.getElementById("btn-stop").onclick = () => vmAction("/api/win-vm/stop");
document.getElementById("btn-reboot").onclick = () => vmAction("/api/win-vm/reboot");
document.getElementById("btn-wake").onclick = async () => {
  statusEl.textContent = "Sveglia display…";
  await fetch("/api/win-vm/wake", { method: "POST" });
  wakeDisplay();
};

async function ensureRunning() {
  try {
    const r = await fetch("/api/win-vm/status");
    const d = await r.json();
    if (d.state !== "running") {
      statusEl.textContent = "Avvio VM…";
      await fetch("/api/win-vm/start", { method: "POST" });
      scheduleConnect(12000);
    }
  } catch (_) { /* ignore */ }
}

screen.addEventListener("click", () => {
  if (rfb) wakeDisplay();
});

refreshStatus();
ensureRunning();
setInterval(refreshStatus, 15000);
scheduleConnect(300);
