import RFB from "https://cdn.jsdelivr.net/npm/@novnc/novnc@1.5.0/core/rfb.js";

const screen = document.getElementById("screen");
const stateEl = document.getElementById("vm-state");
const statusEl = document.getElementById("status-line");

async function refreshStatus() {
  try {
    const r = await fetch("/api/win-vm/status");
    const d = await r.json();
    stateEl.textContent = d.state || d.error || "?";
    stateEl.className = "badge " + (d.state === "running" ? "on" : "off");
  } catch (_) {
    stateEl.textContent = "err";
  }
}

function connectVnc() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${proto}//${location.host}/ws/vnc`;
  fetch("/api/win-vm/vnc-config")
    .then((r) => r.json())
    .then((cfg) => {
      const rfb = new RFB(screen, url, { shared: true });
      rfb.scaleViewport = true;
      rfb.resizeSession = true;
      if (cfg.password) rfb.credentials = { password: cfg.password };
      rfb.addEventListener("connect", () => {
        statusEl.textContent = "VNC connesso";
      });
      rfb.addEventListener("disconnect", (e) => {
        statusEl.textContent = e.detail.clean ? "Disconnesso" : "VNC offline — avvia win-vm";
        setTimeout(connectVnc, 4000);
      });
      return rfb;
    })
    .catch(() => {
      statusEl.textContent = "Errore config VNC";
      setTimeout(connectVnc, 4000);
    });
}

async function vmAction(path) {
  statusEl.textContent = path + "…";
  await fetch(path, { method: "POST" });
  await refreshStatus();
}

document.getElementById("btn-start").onclick = () => vmAction("/api/win-vm/start");
document.getElementById("btn-stop").onclick = () => vmAction("/api/win-vm/stop");
document.getElementById("btn-reboot").onclick = () => vmAction("/api/win-vm/reboot");

refreshStatus();
setInterval(refreshStatus, 15000);
connectVnc();
