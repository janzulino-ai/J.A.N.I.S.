/**
 * JANIS Window Manager — finestre modulari spostabili nello spazio di lavoro
 */
(function (global) {
    const panels = new Map();
    let zIndex = 100;
    let layerEl = null;
    let snapPreviewEl = null;
    let chatPanelId = "chat-main";
    const CHAT_FLOAT_ID = "chat-floating";
    const CHAT_DOCK_KEY = "janis_chat_docked";
    const CHAT_W_KEY = "janis_chat_w";
    const CHAT_FLOAT_RECT_KEY = "janis_chat_float_rect";
    const FLOAT_LAYOUT_KEY = "janis_float_layout";
    const CONTROLS_ID = "controls-main";
    const BRAIN_FLOAT_ID = "brain-float-main";
    const NAV_ID = "nav-main";
    const brainPanelId = "brain-main";
    let onPanelResize = null;
    let onPanelChange = null;
    let focusedPanelId = null;

    const SNAP_THRESHOLD = 14;
    /** Snap ai bordi solo con Shift premuto durante il trascinamento */
    const SNAP_REQUIRES_SHIFT = true;
    const MIN_PANEL_W = 260;
    const MIN_PANEL_H = 140;
    const RESIZE_DIRS = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];

    const ICONS = { chat: "💬", "chat-ui": "💬", terminal: "⌨", web: "🌐", app: "◆", log: "📋", brain: "🧠", cursor: "◆", whatsapp: "📱", mac: "🍎" };
    const STORAGE_KEY = "janis_panel_layout_v2";
    let saveTimer = null;

    function ensureDom() {
        if (!layerEl) layerEl = document.getElementById("panel-layer");
    }

    function ensureTerminal() {
        if (panels.has("terminal-main")) return panels.get("terminal-main");
        open({
            id: "terminal-main",
            panel_type: "terminal",
            title: "Terminal VERBOSE",
            width: 900,
            height: 260,
            content: "=== JANIS TERMINAL VERBOSE ===\nTutti gli eventi di sistema, tool e chat compaiono qui.\n\n",
            manual: true,
        });
        return panels.get("terminal-main");
    }

    function appendTerminal(text, cls = "", prefix = "SYS") {
        ensureTerminal();
        const pre = panels.get("terminal-main")?.body?.querySelector(".panel-terminal");
        if (!pre) return;
        const ts = new Date().toLocaleTimeString("it-IT", { hour12: false });
        pre.textContent += `[${ts}] [${prefix}] ${text}\n`;
        pre.scrollTop = pre.scrollHeight;
    }

    function logVerbose(prefix, text, cls = "") {
        appendTerminal(text, cls, String(prefix || "SYS").toUpperCase());
    }

    function logDock(text, cls = "") {
        const prefix = cls === "tool" ? "TOOL" : cls === "err" ? "ERR" : cls === "ok" ? "OK" : "SYS";
        appendTerminal(text, cls, prefix);
    }

    function syncDockHeight() {
        const agentZone = document.getElementById("agent-zone");
        if (document.body.classList.contains("mode-ide")) {
            document.documentElement.style.setProperty("--dock-height", "0px");
            return 0;
        }
        const dock = document.getElementById("control-dock");
        const dockH = dock ? dock.offsetHeight : 150;
        document.documentElement.style.setProperty("--dock-height", dockH + "px");
        return dockH;
    }

    function isFloatLayout() {
        return document.body.classList.contains("layout-float");
    }

    function enableFloatLayout() {
        document.body.classList.add("layout-float");
        try { localStorage.setItem(FLOAT_LAYOUT_KEY, "1"); } catch (_) {}
        if (!isChatDetached()) detachChat();
        updateFloatLayoutButton();
        relayoutAll();
        notifyPanelChange();
    }

    function disableFloatLayout() {
        document.body.classList.remove("layout-float");
        try { localStorage.setItem(FLOAT_LAYOUT_KEY, "0"); } catch (_) {}
        if (isChatDetached()) attachChat();
        updateFloatLayoutButton();
        relayoutAll();
        notifyPanelChange();
    }

    function toggleFloatLayout() {
        if (isFloatLayout()) disableFloatLayout();
        else enableFloatLayout();
    }

    function getWorkspace() {
        syncDockHeight();
        const pad = 8;

        if (document.body.classList.contains("layout-float") || document.body.classList.contains("chat-detached")
            || document.body.classList.contains("shell-float")) {
            if (document.body.classList.contains("shell-float")) {
                const pad = 8;
                const right = window.innerWidth - pad;
                const bottom = window.innerHeight - pad;
                return {
                    top: pad,
                    left: pad,
                    right,
                    bottom,
                    width: Math.max(320, right - pad),
                    height: Math.max(160, bottom - pad),
                };
            }
            const sidebar = document.getElementById("sidebar");
            const sbRight = sidebar ? sidebar.getBoundingClientRect().right : 260;
            const left = sbRight + pad;
            const right = window.innerWidth - pad;
            const top = pad;
            const bottom = window.innerHeight - pad;
            return {
                top,
                left,
                right,
                bottom,
                width: Math.max(320, right - left),
                height: Math.max(160, bottom - top),
            };
        }

        const zone = document.getElementById("agent-zone");
        if (zone && document.body.classList.contains("mode-ide")) {
            const r = zone.getBoundingClientRect();
            const top = r.top + pad;
            const left = r.left + pad;
            const right = r.right - pad;
            const bottom = r.bottom - pad;
            return {
                top,
                left,
                right,
                bottom,
                width: right - left,
                height: Math.max(120, bottom - top),
            };
        }
        const dockH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dock-height")) || 150;
        const left = pad;
        const right = window.innerWidth - pad;
        const bottom = window.innerHeight - dockH - pad;
        const top = pad;
        return {
            top,
            left,
            right,
            bottom,
            width: right - left,
            height: Math.max(120, bottom - top),
        };
    }

    function setPanelGeometry(el, x, y, w, h) {
        el.style.position = "fixed";
        el.style.left = x + "px";
        el.style.top = y + "px";
        el.style.width = w + "px";
        el.style.height = h + "px";
        el.style.right = "auto";
        el.style.bottom = "auto";
        el.style.flex = "none";
        el.style.maxWidth = "none";
    }

    function getSnapRect(snap, ws) {
        const halfW = Math.floor(ws.width / 2);
        const halfH = Math.floor(ws.height / 2);
        switch (snap) {
            case "left":
                return { x: ws.left, y: ws.top, w: halfW, h: ws.height };
            case "right":
                return { x: ws.left + halfW, y: ws.top, w: ws.width - halfW, h: ws.height };
            case "max":
                return { x: ws.left, y: ws.top, w: ws.width, h: ws.height };
            case "top-left":
                return { x: ws.left, y: ws.top, w: halfW, h: halfH };
            case "top-right":
                return { x: ws.left + halfW, y: ws.top, w: ws.width - halfW, h: halfH };
            case "bottom-left":
                return { x: ws.left, y: ws.top + halfH, w: halfW, h: ws.height - halfH };
            case "bottom-right":
                return { x: ws.left + halfW, y: ws.top + halfH, w: ws.width - halfW, h: ws.height - halfH };
            default:
                return null;
        }
    }

    function updateSnapClass(entry) {
        entry.el.classList.toggle("snapped-max", entry.snapped === "max");
        entry.el.dataset.snapped = entry.snapped || "";
    }

    function applySnapGeometry(entry, snap) {
        const ws = getWorkspace();
        const rect = getSnapRect(snap, ws);
        if (!rect) return;
        setPanelGeometry(entry.el, rect.x, rect.y, rect.w, rect.h);
        entry.snapped = snap;
        entry.manual = true;
        updateSnapClass(entry);
        notifyPanelResize(entry.el.dataset.id);
    }

    function detectSnapZone(left, top, w, h, ws) {
        const right = left + w;
        const bottom = top + h;
        const nearLeft = left - ws.left <= SNAP_THRESHOLD;
        const nearRight = ws.right - right <= SNAP_THRESHOLD;
        const nearTop = top - ws.top <= SNAP_THRESHOLD;
        const nearBottom = ws.bottom - bottom <= SNAP_THRESHOLD;

        if (nearTop && nearLeft) return "top-left";
        if (nearTop && nearRight) return "top-right";
        if (nearBottom && nearLeft) return "bottom-left";
        if (nearBottom && nearRight) return "bottom-right";
        /* max solo doppio click header — non snap automatico in alto */
        if (nearLeft && !nearTop && !nearBottom) return "left";
        if (nearRight && !nearTop && !nearBottom) return "right";
        return null;
    }

    function ensureSnapPreview() {
        ensureDom();
        if (!snapPreviewEl && layerEl) {
            snapPreviewEl = document.createElement("div");
            snapPreviewEl.className = "panel-snap-preview";
            snapPreviewEl.style.display = "none";
            layerEl.appendChild(snapPreviewEl);
        }
        return snapPreviewEl;
    }

    function showSnapPreview(snap) {
        const preview = ensureSnapPreview();
        if (!preview) return;
        if (!snap) {
            preview.style.display = "none";
            return;
        }
        const ws = getWorkspace();
        const rect = getSnapRect(snap, ws);
        if (!rect) {
            preview.style.display = "none";
            return;
        }
        preview.style.display = "block";
        preview.dataset.snap = snap;
        setPanelGeometry(preview, rect.x, rect.y, rect.w, rect.h);
    }

    function hideSnapPreview() {
        if (snapPreviewEl) snapPreviewEl.style.display = "none";
    }

    function saveRect(entry) {
        const r = entry.el.getBoundingClientRect();
        entry.savedRect = { left: r.left, top: r.top, width: r.width, height: r.height };
    }

    function restoreSavedRect(entry) {
        if (!entry.savedRect) return;
        const r = entry.savedRect;
        setPanelGeometry(entry.el, r.left, r.top, r.width, r.height);
        entry.snapped = null;
        entry.savedRect = null;
        updateSnapClass(entry);
        clampPanel(entry.el);
        notifyPanelResize(entry.el.dataset.id);
    }

    function toggleMaximize(entry) {
        if (entry.snapped === "max") {
            restoreSavedRect(entry);
        } else {
            saveRect(entry);
            applySnapGeometry(entry, "max");
        }
    }

    function clampPanel(el) {
        const ws = getWorkspace();
        const rect = el.getBoundingClientRect();
        let w = rect.width;
        let h = rect.height;
        let x = rect.left;
        let y = rect.top;
        w = Math.min(w, ws.width);
        h = Math.min(h, ws.height);
        w = Math.max(MIN_PANEL_W, w);
        h = Math.max(MIN_PANEL_H, h);
        x = Math.max(ws.left, Math.min(x, ws.right - w));
        y = Math.max(ws.top, Math.min(y, ws.bottom - h));
        setPanelGeometry(el, x, y, w, h);
    }

    const AGENT_PANEL_IDS = {
        terminal: "terminal-main",
        cursor: "cursor-main",
        mac: "mac-main",
        whatsapp: "whatsapp-main",
    };

    function syncAgentCards(selectedAgent) {
        const sel = selectedAgent || window.__janisSelectedAgent || "janis";
        document.querySelectorAll(".sidebar-agents .agent-card[data-panel]").forEach((card) => {
            const kind = card.dataset.panel;
            let on = false;
            if (kind === "web") {
                on = sel === "web";
            } else if (kind === "app") {
                on = false;
            } else if (AGENT_PANEL_IDS[kind]) {
                on = panels.has(AGENT_PANEL_IDS[kind]);
            }
            card.classList.toggle("active", on);
        });
    }

    function notifyPanelChange() {
        syncAgentTabs();
        syncAgentCards();
        if (typeof onPanelChange === "function") onPanelChange(list());
    }

    function syncAgentTabs() {
        const container = document.getElementById("agent-open-tabs");
        if (!container) return;
        container.innerHTML = "";
        const MAIN_AGENT_PANELS = new Set(Object.values(AGENT_PANEL_IDS));
        const items = list().filter(
            (p) => p.id !== chatPanelId && p.id !== brainPanelId && !MAIN_AGENT_PANELS.has(p.id),
        );
        items.forEach((p) => {
            const tab = document.createElement("button");
            tab.type = "button";
            tab.className = "agent-card agent-tab" + (p.id === focusedPanelId ? " active" : "");
            tab.dataset.panelId = p.id;
            const icon = ICONS[p.type] || "◆";
            tab.innerHTML =
                `<span class="tab-icon">${icon}</span>`
                + `<span class="tab-text">${p.title || p.id}</span>`
                + `<span class="tab-close" role="button" title="Chiudi">✕</span>`;
            tab.addEventListener("click", (e) => {
                if (e.target.closest(".tab-close")) {
                    e.stopPropagation();
                    close(p.id);
                    return;
                }
                focus(p.id);
            });
            container.appendChild(tab);
        });
    }

    function setOnPanelChange(fn) {
        onPanelChange = fn;
    }

    function notifyPanelResize(id) {
        if ((id === brainPanelId || id === BRAIN_FLOAT_ID) && typeof onPanelResize === "function") {
            onPanelResize();
        }
    }

    function normalizeUrl(url) {
        const u = (url || "").trim();
        if (!u) return "about:blank";
        if (/^https?:\/\//i.test(u)) return u;
        return "https://" + u;
    }

    function proxyUrl(url) {
        const n = normalizeUrl(url);
        if (n === "about:blank") return n;
        return `/api/web/proxy?url=${encodeURIComponent(n)}`;
    }

    const EXTERNAL_HOSTS = /(^|\.)(youtube\.com|youtu\.be|netflix\.com|twitch\.tv|spotify\.com|facebook\.com|instagram\.com|twitter\.com|x\.com|tiktok\.com)$/i;

    function isExternalOnlySite(url) {
        try {
            const host = new URL(normalizeUrl(url)).hostname.toLowerCase();
            return EXTERNAL_HOSTS.test(host);
        } catch (_) {
            return false;
        }
    }

    function externalNoticeHtml(url, reason) {
        const safe = url.replace(/"/g, "&quot;");
        return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
            body{margin:0;font-family:Segoe UI,sans-serif;background:#050a12;color:#c8e8ff;
            display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;padding:24px}
            .box{max-width:420px}h2{color:#00d4ff;font-size:18px;margin:0 0 12px}
            p{font-size:13px;line-height:1.55;color:rgba(200,232,255,.85)}
            code{color:#ffcc00;font-size:12px;word-break:break-all}
        </style></head><body><div class="box">
            <h2>Aperto nel browser di sistema</h2>
            <p>${reason || "Questo sito non può essere visualizzato nel pannello interno."}</p>
            <p><code>${safe}</code></p>
            <p>Se non si è aperto, usa il pulsante ↗ nella barra indirizzi.</p>
        </div></body></html>`;
    }

    async function openExternal(url) {
        const n = normalizeUrl(url);
        if (n === "about:blank") return false;

        try {
            if (window.pywebview?.api?.open_url) {
                const r = await window.pywebview.api.open_url(n);
                if (r?.ok) {
                    logDock(`Browser: ${n}`, "ok");
                    return true;
                }
            }
        } catch (_) {}

        try {
            const res = await fetch("/api/desktop/open-url", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: n }),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                logDock(`Browser: ${n}`, "ok");
                return true;
            }
            logDock(data.error || `Errore apertura browser (${res.status})`, "err");
        } catch (e) {
            logDock("Browser non raggiungibile — riavvia JANIS", "err");
        }
        return false;
    }

    function openSystemBrowser(url, title) {
        const n = normalizeUrl(url || "https://duckduckgo.com");
        openExternal(n);
        if (title) logDock(`Apro ${title}`, "ok");
        return n;
    }

    function createWebToolbar(body, spec, entry) {
        const bar = document.createElement("div");
        bar.className = "panel-web-toolbar";
        bar.innerHTML = `
            <button type="button" class="panel-nav-btn" data-nav="back" title="Indietro">←</button>
            <button type="button" class="panel-nav-btn" data-nav="refresh" title="Ricarica">↻</button>
            <input class="panel-url-input" type="text" placeholder="https://..." spellcheck="false" />
            <button type="button" class="panel-nav-btn panel-nav-go" data-nav="go" title="Vai">→</button>
            <button type="button" class="panel-nav-btn panel-nav-ext" data-nav="external" title="Apri nel browser">↗</button>
        `;
        const input = bar.querySelector(".panel-url-input");
        input.value = spec.url && spec.url !== "about:blank" ? spec.url : "";

        const iframe = document.createElement("iframe");
        iframe.className = "panel-iframe";
        iframe.setAttribute(
            "sandbox",
            "allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-top-navigation",
        );

        const status = document.createElement("div");
        status.className = "panel-web-status";

        function navigate(url, opts = {}) {
            const n = normalizeUrl(url);
            input.value = n === "about:blank" ? "" : n;
            entry.spec.url = n;
            status.textContent = "";
            status.className = "panel-web-status";
            const titleEl = entry.el.querySelector(".panel-title");
            try {
                const host = new URL(n).hostname;
                if (host && titleEl) titleEl.textContent = host.replace(/^www\./, "");
            } catch (_) {}

            if (n === "about:blank") {
                iframe.removeAttribute("srcdoc");
                iframe.src = "about:blank";
                return;
            }

            const forceExternal = opts.externalOnly || entry.spec.external_only || isExternalOnlySite(n);

            if (forceExternal) {
                openExternal(n);
                iframe.removeAttribute("src");
                iframe.srcdoc = externalNoticeHtml(
                    n,
                    "YouTube, streaming e app web pesanti si aprono nel browser predefinito di Windows.",
                );
                status.textContent = "Aperto nel browser di sistema ↗";
                status.classList.add("ok");
                logDock(`Browser esterno: ${n}`, "ok");
                return;
            }

            const proxy = proxyUrl(n);
            fetch(proxy, { method: "GET", cache: "no-store" })
                .then(async (res) => {
                    const ct = (res.headers.get("content-type") || "").toLowerCase();
                    if (!res.ok) {
                        if (res.status === 404) {
                            status.textContent = "Proxy web non attivo — riavvia JANIS (stop + play), poi ↻";
                            status.classList.add("err");
                            logDock("Proxy /api/web/proxy non trovato — riavvia backend", "err");
                        } else {
                            status.textContent = `Errore ${res.status} — prova ↗ Apri nel browser`;
                            status.classList.add("err");
                        }
                        iframe.removeAttribute("srcdoc");
                        iframe.src = n;
                        return;
                    }
                    if (ct.includes("application/json")) {
                        const body = await res.text();
                        if (body.includes('"detail"')) {
                            status.textContent = "Sito non caricabile nel pannello — usa ↗";
                            status.classList.add("err");
                            iframe.removeAttribute("srcdoc");
                            iframe.src = n;
                            return;
                        }
                    }
                    iframe.removeAttribute("srcdoc");
                    iframe.src = proxy;
                })
                .catch(() => {
                    status.textContent = "Proxy non raggiungibile — caricamento diretto…";
                    iframe.removeAttribute("srcdoc");
                    iframe.src = n;
                });
        }

        bar.querySelector('[data-nav="go"]').addEventListener("click", () => navigate(input.value));
        bar.querySelector('[data-nav="refresh"]').addEventListener("click", () => { iframe.src = iframe.src; });
        bar.querySelector('[data-nav="external"]').addEventListener("click", () => openExternal(input.value || spec.url));
        bar.querySelector('[data-nav="back"]').addEventListener("click", () => {
            try { iframe.contentWindow.history.back(); } catch (_) {}
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") navigate(input.value);
        });

        iframe.addEventListener("load", () => {
            if (!iframe.src || iframe.src === "about:blank") return;
            status.textContent = "";
        });
        iframe.addEventListener("error", () => {
            status.textContent = "Errore caricamento — prova ↗ Apri nel browser";
        });

        body.appendChild(bar);
        body.appendChild(status);
        body.appendChild(iframe);
        entry.navigate = navigate;
        navigate(spec.url || "about:blank", {
            externalOnly: spec.external_only || spec.externalOnly,
        });
    }

    function renderBody(body, spec, entry) {
        body.innerHTML = "";
        const t = spec.panel_type || spec.type || "app";

        if (t === "brain") {
            const host = document.createElement("div");
            host.className = "panel-brain-host";
            host.id = `brain-host-${spec.id}`;
            body.appendChild(host);
            if (spec.canvas) {
                host.appendChild(spec.canvas);
                notifyPanelResize(spec.id);
            }
        } else if (t === "web") {
            createWebToolbar(body, spec, entry);
        } else if (t === "terminal") {
            const pre = document.createElement("pre");
            pre.className = "panel-terminal";
            pre.textContent = spec.content || "JANIS Terminal — pronto.\n";
            body.appendChild(pre);
        } else if (t === "chat") {
            const log = document.createElement("div");
            log.className = "panel-chat-log";
            log.id = `chat-log-${spec.id}`;
            if (spec.content) log.textContent = spec.content;
            body.appendChild(log);
        } else if (t === "chat-ui") {
            body.classList.add("chat-panel-body");
        } else if (t === "controls" || t === "nav" || t === "page") {
            body.classList.add("panel-mount", `panel-${t}-body`);
        } else if (t === "cursor") {
            const pre = document.createElement("pre");
            pre.className = "panel-cursor";
            pre.textContent = spec.content || "Cursor Agent — in attesa…\n";
            body.appendChild(pre);
            entry.cursorEl = pre;
        } else if (t === "mac") {
            const pre = document.createElement("pre");
            pre.className = "panel-mac";
            pre.textContent = spec.content || "Mac Mini — SSH janzu@mac-mini-di-janzu.local\n";
            body.appendChild(pre);
            entry.macEl = pre;
        } else if (t === "whatsapp") {
            body.innerHTML = `
                <div class="panel-whatsapp">
                    <div class="wa-qr">QR WhatsApp<br><span>(API futura)</span></div>
                    <div class="wa-status">Non connesso</div>
                    <ul class="wa-msgs"><li class="page-muted">Nessun messaggio</li></ul>
                </div>`;
        } else {
            const pre = document.createElement("pre");
            pre.className = "panel-content";
            pre.textContent = spec.content || "";
            body.appendChild(pre);
        }
    }

    function startDrag(el, entry, e) {
        entry.manual = true;
        entry.snapped = null;
        updateSnapClass(entry);
        el.classList.add("dragging");
        const rect = el.getBoundingClientRect();
        const ox = e.clientX - rect.left;
        const oy = e.clientY - rect.top;
        setPanelGeometry(el, rect.left, rect.top, rect.width, rect.height);

        let pendingSnap = null;

        function move(ev) {
            const ws = getWorkspace();
            const w = el.offsetWidth;
            const h = el.offsetHeight;
            let x = ev.clientX - ox;
            let y = ev.clientY - oy;
            x = Math.max(ws.left, Math.min(x, ws.right - w));
            y = Math.max(ws.top, Math.min(y, ws.bottom - h));
            setPanelGeometry(el, x, y, w, h);

            pendingSnap = null;
            if (!SNAP_REQUIRES_SHIFT || ev.shiftKey) {
                pendingSnap = detectSnapZone(x, y, w, h, ws);
            }
            if (pendingSnap) {
                showSnapPreview(pendingSnap);
                el.classList.add("snap-hint");
            } else {
                hideSnapPreview();
                el.classList.remove("snap-hint");
            }
            notifyPanelResize(el.dataset.id);
        }

        function up(ev) {
            el.classList.remove("dragging", "snap-hint");
            hideSnapPreview();
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);

            const allowSnap = pendingSnap && (!SNAP_REQUIRES_SHIFT || ev?.shiftKey);
            if (allowSnap) {
                applySnapGeometry(entry, pendingSnap);
            } else {
                entry.snapped = null;
                updateSnapClass(entry);
                clampPanel(el);
                notifyPanelResize(el.dataset.id);
            }
            entry.manual = true;
            scheduleSave();
        }

        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
        focus(el.dataset.id);
    }

    function startResize(el, entry, dir, e) {
        e.preventDefault();
        e.stopPropagation();
        entry.manual = true;
        entry.snapped = null;
        updateSnapClass(entry);
        el.classList.add("resizing");

        const rect = el.getBoundingClientRect();
        const startX = e.clientX;
        const startY = e.clientY;
        const startLeft = rect.left;
        const startTop = rect.top;
        const startW = rect.width;
        const startH = rect.height;

        function move(ev) {
            const ws = getWorkspace();
            let left = startLeft;
            let top = startTop;
            let w = startW;
            let h = startH;
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;

            if (dir.includes("e")) w = startW + dx;
            if (dir.includes("w")) {
                w = startW - dx;
                left = startLeft + dx;
            }
            if (dir.includes("s")) h = startH + dy;
            if (dir.includes("n")) {
                h = startH - dy;
                top = startTop + dy;
            }

            w = Math.max(MIN_PANEL_W, w);
            h = Math.max(MIN_PANEL_H, h);

            if (left < ws.left) {
                if (dir.includes("w")) w -= ws.left - left;
                left = ws.left;
            }
            if (top < ws.top) {
                if (dir.includes("n")) h -= ws.top - top;
                top = ws.top;
            }
            if (left + w > ws.right) {
                if (dir.includes("e")) w = ws.right - left;
                else left = ws.right - w;
            }
            if (top + h > ws.bottom) {
                if (dir.includes("s")) h = ws.bottom - top;
                else top = ws.bottom - h;
            }

            w = Math.max(MIN_PANEL_W, Math.min(w, ws.right - left));
            h = Math.max(MIN_PANEL_H, Math.min(h, ws.bottom - top));
            left = Math.max(ws.left, Math.min(left, ws.right - w));
            top = Math.max(ws.top, Math.min(top, ws.bottom - h));

            setPanelGeometry(el, left, top, w, h);
            notifyPanelResize(el.dataset.id);
        }

        function up() {
            el.classList.remove("resizing");
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            entry.manual = true;
            entry.snapped = null;
            updateSnapClass(entry);
            clampPanel(el);
            notifyPanelResize(el.dataset.id);
            if (el.dataset.id === CHAT_FLOAT_ID) saveChatFloatRect(entry);
            scheduleSave();
        }

        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
        focus(el.dataset.id);
    }

    function createPanelEl(spec) {
        const el = document.createElement("div");
        el.className = `panel panel-${spec.panel_type || spec.type || "app"}`;
        el.dataset.id = spec.id;
        el.style.zIndex = ++zIndex;
        el.style.width = (spec.width || 480) + "px";
        el.style.height = (spec.height || 340) + "px";

        const header = document.createElement("div");
        header.className = "panel-header";
        header.title = "Trascina per spostare · Shift+bordo = aggancia · Doppio click = ingrandisci";
        header.innerHTML = `
            <span class="panel-icon">${ICONS[spec.panel_type || spec.type] || "◆"}</span>
            <span class="panel-title">${spec.title || spec.id}</span>
            <button type="button" class="panel-btn panel-focus" title="Porta avanti">▣</button>
            <button type="button" class="panel-btn panel-close" title="Chiudi">✕</button>
        `;

        const body = document.createElement("div");
        body.className = "panel-body";
        const entry = {
            el,
            body,
            spec: { ...spec },
            manual: !!spec.manual,
            snapped: null,
            savedRect: null,
        };

        if (spec.id !== brainPanelId && spec.id !== CHAT_FLOAT_ID) {
            header.querySelector(".panel-close").addEventListener("click", () => close(spec.id));
        } else if (spec.id === CHAT_FLOAT_ID) {
            const btn = header.querySelector(".panel-close");
            btn.textContent = "⬇";
            btn.title = "Aggancia chat alla colonna";
            btn.addEventListener("click", () => attachChat());
        } else {
            header.querySelector(".panel-close").style.visibility = "hidden";
        }
        header.querySelector(".panel-focus").addEventListener("click", () => focus(spec.id));
        header.addEventListener("mousedown", (e) => {
            if (e.target.closest(".panel-btn")) return;
            startDrag(el, entry, e);
        });
        header.addEventListener("dblclick", (e) => {
            if (e.target.closest(".panel-btn")) return;
            e.preventDefault();
            toggleMaximize(entry);
        });

        renderBody(body, spec, entry);
        el.appendChild(header);
        el.appendChild(body);

        RESIZE_DIRS.forEach((dir) => {
            const handle = document.createElement("div");
            handle.className = "panel-resize-handle " + dir;
            handle.title = "Ridimensiona";
            handle.addEventListener("mousedown", (ev) => startResize(el, entry, dir, ev));
            el.appendChild(handle);
        });

        return entry;
    }

    function cascadePosition(index, w, h, ws, bias = "center") {
        const col = index % 3;
        const row = Math.floor(index / 3);
        const offsetX = col * 34;
        const offsetY = row * 34;
        let x;
        if (bias === "right") {
            x = ws.right - w - 24 - offsetX;
        } else if (bias === "left") {
            x = ws.left + 16 + offsetX;
        } else {
            x = ws.left + Math.max(16, (ws.width - w) / 2) + (col - 1) * 40;
        }
        const y = ws.top + 36 + offsetY;
        return {
            x: Math.max(ws.left, Math.min(x, ws.right - w)),
            y: Math.max(ws.top, Math.min(y, ws.bottom - h)),
        };
    }

    function saveChatFloatRect(entry) {
        if (!entry || entry.el.dataset.id !== CHAT_FLOAT_ID) return;
        const r = entry.el.getBoundingClientRect();
        try {
            localStorage.setItem(
                CHAT_FLOAT_RECT_KEY,
                JSON.stringify({ left: r.left, top: r.top, width: r.width, height: r.height }),
            );
        } catch (_) {}
    }

    function restoreChatFloatRect(entry) {
        if (!entry || entry.el.dataset.id !== CHAT_FLOAT_ID) return false;
        try {
            const raw = localStorage.getItem(CHAT_FLOAT_RECT_KEY);
            if (!raw) return false;
            const s = JSON.parse(raw);
            if (!s.width || !s.height || s.width < 200 || s.height < 200) return false;
            setPanelGeometry(entry.el, s.left, s.top, s.width, s.height);
            clampPanel(entry.el);
            entry.manual = true;
            const r = entry.el.getBoundingClientRect();
            const ws = getWorkspace();
            if (r.width < 200 || r.height < 200) return false;
            if (r.right < ws.left + 40 || r.bottom < ws.top + 40) return false;
            return true;
        } catch (_) {
            return false;
        }
    }

    function positionDefault(el, index, spec) {
        const ws = getWorkspace();
        const id = el.dataset.id || "";
        const floatMode = isFloatLayout() || isChatDetached();

        el.style.position = "fixed";
        el.style.flex = "none";
        el.style.maxWidth = "none";
        el.style.right = "auto";
        el.style.bottom = "auto";

        if (id === brainPanelId) {
            const w = spec?.width || 480;
            const h = spec?.height || 360;
            const pos = cascadePosition(0, w, h, ws, "center");
            setPanelGeometry(el, pos.x, pos.y, w, h);
        } else if (id === CHAT_FLOAT_ID) {
            const w = Math.min(spec?.width || 560, ws.width - 40);
            const h = Math.min(spec?.height || 640, ws.height - 40);
            const entry = panels.get(CHAT_FLOAT_ID);
            if (entry && restoreChatFloatRect(entry)) return;
            const pos = cascadePosition(0, w, h, ws, floatMode ? "right" : "left");
            setPanelGeometry(el, pos.x, pos.y, w, h);
        } else if (id === "terminal-main") {
            const w = Math.min(spec?.width || 520, ws.width - 40);
            const h = Math.min(spec?.height || 340, ws.height - 40);
            const pos = cascadePosition(floatMode ? 1 : index, w, h, ws, floatMode ? "center" : "left");
            setPanelGeometry(el, pos.x, pos.y, w, h);
        } else if (id === "cursor-main") {
            const w = Math.min(spec?.width || 480, ws.width - 40);
            const h = Math.min(spec?.height || 360, ws.height - 40);
            const pos = cascadePosition(floatMode ? 2 : index + 1, w, h, ws, floatMode ? "center" : "left");
            setPanelGeometry(el, pos.x, pos.y, w, h);
        } else if (id === chatPanelId) {
            /* chat legacy — colonna IDE */
        } else {
            const w = Math.min(spec?.width || el.offsetWidth || 520, ws.width - 40);
            const h = Math.min(spec?.height || el.offsetHeight || 360, ws.height - 40);
            const pos = cascadePosition(index, w, h, ws, floatMode ? "center" : "left");
            setPanelGeometry(el, pos.x, pos.y, w, h);
        }
    }

    function saveLayout() {
        const data = {};
        panels.forEach((entry, id) => {
            if (id === chatPanelId || id === brainPanelId) return;
            const r = entry.el.getBoundingClientRect();
            data[id] = { left: r.left, top: r.top, width: r.width, height: r.height, manual: entry.manual };
            if (id === CHAT_FLOAT_ID) saveChatFloatRect(entry);
        });
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch (_) {}
    }

    function scheduleSave() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveLayout, 400);
    }

    function restoreLayout() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const data = JSON.parse(raw);
            panels.forEach((entry, id) => {
                if (id === CHAT_FLOAT_ID && restoreChatFloatRect(entry)) {
                    entry.manual = true;
                    return;
                }
                const s = data[id];
                if (!s) return;
                setPanelGeometry(entry.el, s.left, s.top, s.width, s.height);
                entry.manual = true;
                entry.snapped = null;
                updateSnapClass(entry);
            });
        } catch (_) {}
    }

    let relayoutTimer = null;
    function relayoutAllDebounced() {
        clearTimeout(relayoutTimer);
        relayoutTimer = setTimeout(() => { relayoutAll(); scheduleSave(); }, 120);
    }

    function appendCursorStream(id, chunk, done) {
        let p = panels.get(id);
        if (!p) {
            open({ id, panel_type: "cursor", title: "Cursor Agent", width: 520, height: 360, content: "" });
            p = panels.get(id);
        }
        const pre = p?.body?.querySelector(".panel-cursor");
        if (pre) {
            pre.textContent += chunk || "";
            pre.scrollTop = pre.scrollHeight;
        }
        if (done) logDock("Cursor Agent completato", "ok");
    }

    function openMac() {
        return open({
            id: "mac-main",
            panel_type: "mac",
            title: "Mac Mini",
            width: 520,
            height: 360,
            content: "Mac Mini M4 — SSH remoto.\nChiedi a JANIS comandi per macOS.\n",
            manual: true,
        });
    }

    function openWhatsApp() {
        return open({
            id: "whatsapp-main",
            panel_type: "whatsapp",
            title: "WhatsApp",
            width: 380,
            height: 480,
            manual: true,
        });
    }
    function adjustFloatShell() {
        const ws = getWorkspace();
        const termH = Math.min(280, Math.max(200, Math.floor(ws.height * 0.28)));
        const entry = panels.get("terminal-main");
        if (entry) {
            setPanelGeometry(entry.el, ws.left, ws.bottom - termH, ws.width, termH);
        }
    }

    function relayoutAll() {
        if (document.body.classList.contains("shell-float")) {
            adjustFloatShell();
            return;
        }
        let i = 0;
        panels.forEach((entry) => {
            if (entry.snapped) {
                applySnapGeometry(entry, entry.snapped);
            } else if (entry.manual) {
                clampPanel(entry.el);
            } else {
                positionDefault(entry.el, i, entry.spec);
            }
            notifyPanelResize(entry.el.dataset.id);
            i++;
        });
    }

    function open(spec) {
        ensureDom();
        if (!layerEl) return;
        const id = spec.id;
        if (panels.has(id)) {
            update({ ...spec, id, action: "update" });
            focus(id);
            return id;
        }
        const entry = createPanelEl(spec);
        panels.set(id, entry);
        layerEl.appendChild(entry.el);
        positionDefault(entry.el, panels.size - 1, spec);
        entry.manual = spec.manual !== false;
        entry.snapped = null;
        updateSnapClass(entry);
        focus(id);
        logDock(`Finestra: ${spec.title || id}`, "ok");
        notifyPanelResize(id);
        return id;
    }

    function getBrainMount() {
        const fixed = document.getElementById("brain-viewport");
        if (fixed) return fixed;
        const entry = panels.get(brainPanelId);
        if (!entry) return null;
        return entry.body.querySelector(".panel-brain-host");
    }

    function openBrain(canvas, title) {
        if (panels.has(brainPanelId)) {
            focus(brainPanelId);
            if (canvas) {
                const host = getBrainMount();
                if (host && !host.contains(canvas)) {
                    host.appendChild(canvas);
                    notifyPanelResize(brainPanelId);
                }
            }
            return brainPanelId;
        }
        return open({
            id: brainPanelId,
            panel_type: "brain",
            title: title || "Cervello",
            width: 480,
            height: 360,
            canvas,
        });
    }

    function openWeb(url, title) {
        openSystemBrowser(url || "https://duckduckgo.com", title || "Browser");
        return null;
    }

    function close(id) {
        if (id === CHAT_FLOAT_ID) {
            attachChat();
            return;
        }
        if (id === brainPanelId) {
            logDock("Il cervello resta sempre attivo", "err");
            focus(brainPanelId);
            return;
        }
        const p = panels.get(id);
        if (!p) return;
        p.el.remove();
        panels.delete(id);
        if (focusedPanelId === id) focusedPanelId = null;
        logDock(`Chiusa: ${id}`);
        notifyPanelChange();
    }

    function update(spec) {
        const p = panels.get(spec.id);
        if (!p) {
            open(spec);
            return;
        }
        if (spec.title) {
            p.spec.title = spec.title;
            p.el.querySelector(".panel-title").textContent = spec.title;
        }
        const ptype = spec.panel_type || spec.type;
        if (spec.url && (p.spec.panel_type === "web" || ptype === "web")) {
            p.spec.url = spec.url;
            if (p.navigate) p.navigate(spec.url);
            else renderBody(p.body, { ...p.spec, url: spec.url }, p);
        } else if (spec.content !== undefined) {
            p.spec.content = spec.content;
            renderBody(p.body, p.spec, p);
        }
        if (spec.width) {
            p.spec.width = spec.width;
            p.el.style.width = spec.width + "px";
        }
        if (spec.height) {
            p.spec.height = spec.height;
            p.el.style.height = spec.height + "px";
        }
        if (p.snapped) {
            applySnapGeometry(p, p.snapped);
        } else {
            clampPanel(p.el);
        }
        notifyPanelResize(spec.id);
    }

    function append(spec) {
        let p = panels.get(spec.id);
        if (!p) {
            open({
                id: spec.id,
                panel_type: spec.panel_type || "log",
                title: spec.title || spec.id,
                content: spec.content || "",
            });
            return;
        }
        const t = p.spec.panel_type || "log";
        if (t === "terminal") {
            const pre = p.body.querySelector(".panel-terminal");
            if (pre) pre.textContent += spec.content || "";
        } else if (t === "mac") {
            const pre = p.body.querySelector(".panel-mac");
            if (pre) pre.textContent += spec.content || "";
        } else if (t === "cursor") {
            const pre = p.body.querySelector(".panel-cursor");
            if (pre) pre.textContent += spec.content || "";
        } else if (t === "chat") {
            const log = p.body.querySelector(".panel-chat-log");
            if (log) log.textContent += spec.content || "";
        } else {
            const pre = p.body.querySelector(".panel-content");
            if (pre) pre.textContent += spec.content || "";
        }
        p.body.scrollTop = p.body.scrollHeight;
    }

    function focus(id) {
        const p = panels.get(id);
        if (!p) return;
        p.el.style.zIndex = ++zIndex;
        focusedPanelId = id;
        notifyPanelChange();
    }

    function list() {
        return Array.from(panels.values()).map((p) => ({
            id: p.spec.id,
            type: p.spec.panel_type || p.spec.type,
            title: p.spec.title,
        }));
    }

    function isChatDetached() {
        return document.body.classList.contains("chat-detached");
    }

    function updateChatDockButton() {
        const btn = document.getElementById("chat-dock-toggle");
        if (!btn) return;
        if (isChatDetached()) {
            btn.textContent = "⬇";
            btn.title = "Aggancia chat alla colonna";
        } else {
            btn.textContent = "⧉";
            btn.title = "Sgancia chat (finestra flottante)";
        }
    }

    function getChatBlocks() {
        const col = document.getElementById("chat-column");
        if (!col) return [];
        return [
            col.querySelector(".chat-header"),
            document.getElementById("chat-messages"),
            col.querySelector(".chat-composer"),
        ].filter(Boolean);
    }

    function detachChat() {
        if (panels.has(CHAT_FLOAT_ID)) {
            focus(CHAT_FLOAT_ID);
            return;
        }
        ensureDom();
        const blocks = getChatBlocks();
        if (!blocks.length) {
            logVerbose("ERR", "Chat: blocchi DOM non trovati in #chat-column", "err");
            return;
        }

        open({
            id: CHAT_FLOAT_ID,
            panel_type: "chat-ui",
            title: "Chat JANIS",
            width: 560,
            height: Math.min(window.innerHeight - 60, 720),
            manual: true,
        });

        const entry = panels.get(CHAT_FLOAT_ID);
        if (!entry) return;
        entry.el.classList.add("panel-chat-ui");
        entry.body.innerHTML = "";
        entry.body.classList.add("chat-panel-body");
        blocks.forEach((node) => entry.body.appendChild(node));

        document.body.classList.add("chat-detached");
        try { localStorage.setItem(CHAT_DOCK_KEY, "0"); } catch (_) {}
        updateChatDockButton();
        updateFloatLayoutButton();
        focus(CHAT_FLOAT_ID);
        const entryAfter = panels.get(CHAT_FLOAT_ID);
        if (entryAfter) {
            if (!restoreChatFloatRect(entryAfter)) {
                positionDefault(entryAfter.el, 0, entryAfter.spec);
            }
            entryAfter.manual = true;
            entryAfter.el.style.display = "";
            entryAfter.el.style.visibility = "visible";
            clampPanel(entryAfter.el);
        }
        if (!document.body.classList.contains("shell-float")) {
            relayoutAll();
        }
    }

    function attachChat() {
        const col = document.getElementById("chat-column");
        const entry = panels.get(CHAT_FLOAT_ID);
        if (!col || !entry) {
            document.body.classList.remove("chat-detached");
            updateChatDockButton();
            return;
        }

        const blocks = [
            entry.body.querySelector(".chat-header"),
            entry.body.querySelector("#chat-messages"),
            entry.body.querySelector(".chat-composer"),
        ].filter(Boolean);

        blocks.forEach((node) => col.appendChild(node));

        entry.el.remove();
        panels.delete(CHAT_FLOAT_ID);
        if (focusedPanelId === CHAT_FLOAT_ID) focusedPanelId = null;
        document.body.classList.remove("chat-detached");
        try { localStorage.setItem(CHAT_DOCK_KEY, "1"); } catch (_) {}
        updateChatDockButton();
        updateFloatLayoutButton();
        relayoutAll();
    }

    function toggleChatDock() {
        if (isChatDetached()) attachChat();
        else detachChat();
    }

    function initChatColumnResize() {
        const resizer = document.getElementById("chat-column-resizer");
        if (!resizer) return;

        try {
            const saved = localStorage.getItem(CHAT_W_KEY);
            if (saved) {
                const w = Math.max(320, Math.min(780, parseInt(saved, 10)));
                if (!Number.isNaN(w)) {
                    document.documentElement.style.setProperty("--chat-w", w + "px");
                }
            }
        } catch (_) {}

        resizer.addEventListener("mousedown", (e) => {
            if (isChatDetached()) return;
            e.preventDefault();
            const startX = e.clientX;
            const root = document.documentElement;
            const startW = parseInt(getComputedStyle(root).getPropertyValue("--chat-w"), 10) || 480;

            function move(ev) {
                const dw = ev.clientX - startX;
                const next = Math.max(320, Math.min(780, startW + dw));
                root.style.setProperty("--chat-w", next + "px");
            }

            function up() {
                document.removeEventListener("mousemove", move);
                document.removeEventListener("mouseup", up);
                const w = parseInt(getComputedStyle(root).getPropertyValue("--chat-w"), 10);
                try { localStorage.setItem(CHAT_W_KEY, String(w)); } catch (_) {}
            }

            document.addEventListener("mousemove", move);
            document.addEventListener("mouseup", up);
        });
    }

    function restoreChatDockState() {
        try {
            if (document.body.classList.contains("shell-float")) {
                if (!panels.has(CHAT_FLOAT_ID)) detachChat();
                else focus(CHAT_FLOAT_ID);
                layoutFloatShell();
                updateChatDockButton();
                return;
            }
            if (localStorage.getItem(CHAT_DOCK_KEY) === "0") {
                detachChat();
            }
        } catch (_) {}
        updateChatDockButton();
    }

    function updateFloatLayoutButton() {
        const btn = document.getElementById("float-layout-toggle");
        if (!btn) return;
        if (isFloatLayout()) {
            btn.classList.add("active");
            btn.title = "Layout colonne (chat agganciata)";
        } else {
            btn.classList.remove("active");
            btn.title = "Layout finestre flottanti";
        }
    }

    function restoreFloatLayoutState() {
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.get("float") === "1" || localStorage.getItem(FLOAT_LAYOUT_KEY) === "1") {
                enableFloatLayout();
                return;
            }
        } catch (_) {}
        updateFloatLayoutButton();
    }

    function initChatDockUi() {
        initChatColumnResize();
        const toggle = document.getElementById("chat-dock-toggle");
        if (toggle) toggle.addEventListener("click", toggleChatDock);
        const floatBtn = document.getElementById("float-layout-toggle");
        if (floatBtn) floatBtn.addEventListener("click", toggleFloatLayout);
        restoreFloatLayoutState();
        restoreChatDockState();
    }

    function formatChatDisplay(text) {
        if (!text) return "";
        let s = String(text).replace(/\r\n/g, "\n");
        s = s.replace(/([^\n])\s+(\d+\.\s)/g, "$1\n$2");
        s = s.replace(/([^\n•])\s*(•\s)/g, "$1\n$2");
        return s;
    }

    function appendChat(text, who = "janis") {
        const log = document.getElementById("chat-messages");
        const display = formatChatDisplay(text);
        if (log) {
            const line = document.createElement("div");
            line.className = "chat-line chat-" + who;
            line.textContent = (who === "user" ? "Tu: " : "JANIS: ") + display;
            log.appendChild(line);
            log.scrollTop = log.scrollHeight;
            return;
        }
        let p = panels.get(chatPanelId);
        if (!p) {
            open({ id: chatPanelId, panel_type: "chat", title: "Chat JANIS", width: 440, height: 360 });
            p = panels.get(chatPanelId);
        }
        const panelLog = p?.body.querySelector(".panel-chat-log");
        if (panelLog) {
            const line = document.createElement("div");
            line.className = "chat-line chat-" + who;
            line.textContent = (who === "user" ? "Tu: " : "JANIS: ") + display;
            panelLog.appendChild(line);
            panelLog.scrollTop = panelLog.scrollHeight;
        }
    }

    function handleEvent(ev) {
        const action = ev.action || "open";
        switch (action) {
            case "browser_opened":
                openSystemBrowser(ev.url, ev.title);
                break;
            case "open":
                if ((ev.panel_type || ev.type) === "brain") {
                    focus(brainPanelId);
                    break;
                }
                if ((ev.panel_type || ev.type) === "web") {
                    openSystemBrowser(ev.url, ev.title);
                    break;
                }
                open({
                    id: ev.id,
                    panel_type: ev.panel_type || ev.type || "app",
                    title: ev.title,
                    url: ev.url,
                    content: ev.content,
                    width: ev.width,
                    height: ev.height,
                    external_only: ev.external_only || ev.externalOnly,
                    manual: ev.manual !== false && (ev.panel_type === "web" || ev.type === "web"),
                });
                break;
            case "close":
                close(ev.id);
                break;
            case "update":
                update(ev);
                break;
            case "append":
                append(ev);
                break;
            case "focus":
                focus(ev.id);
                break;
            case "list":
                logDock("Finestre aperte: " + list().map((x) => x.title).join(", ") || "(nessuna)");
                break;
            default:
                break;
        }
    }

    function moveIntoPanel(panelId, selector, createSpec) {
        let entry = panels.get(panelId);
        if (!entry && createSpec) {
            open(createSpec);
            entry = panels.get(panelId);
        }
        if (!entry) return;
        const mount = entry.body.querySelector(".panel-mount") || entry.body;
        document.querySelectorAll(selector).forEach((node) => {
            if (node && node.parentElement !== mount) mount.appendChild(node);
        });
    }

    function layoutFloatShell() {
        const ws = getWorkspace();
        const place = (id, x, y, w, h) => {
            const entry = panels.get(id);
            if (!entry) return;
            setPanelGeometry(entry.el, x, y, w, h);
            entry.manual = true;
            entry.el.style.display = "";
        };

        const termH = Math.min(280, Math.max(200, Math.floor(ws.height * 0.28)));
        place("terminal-main", ws.left, ws.bottom - termH, ws.width, termH);

        const ctrlW = 300;
        const ctrlH = Math.min(440, ws.height - termH - 180);
        place(CONTROLS_ID, ws.left + 8, ws.top + 8, ctrlW, ctrlH);

        place(NAV_ID, ws.left + 8, ws.top + ctrlH + 16, 200, 132);

        const brainW = 300;
        const brainH = 250;
        place(BRAIN_FLOAT_ID, ws.right - brainW - 8, ws.top + 8, brainW, brainH);
        notifyPanelResize(BRAIN_FLOAT_ID);

        const chatW = Math.min(460, Math.max(360, Math.floor(ws.width * 0.34)));
        const chatH = Math.min(560, ws.height - termH - 72);
        const chatEntry = panels.get(CHAT_FLOAT_ID);
        if (chatEntry) {
            if (!restoreChatFloatRect(chatEntry)) {
                place(CHAT_FLOAT_ID, ws.left + Math.floor(ws.width * 0.36), ws.top + 48, chatW, chatH);
            }
            chatEntry.el.style.display = "";
            chatEntry.el.style.visibility = "visible";
            clampPanel(chatEntry.el);
            focus(CHAT_FLOAT_ID);
        }

        ["jobs", "projects", "settings"].forEach((page, i) => {
            const id = `page-float-${page}`;
            const entry = panels.get(id);
            if (!entry) return;
            if (!entry.manual) {
                place(id, ws.left + ctrlW + 24 + i * 28, ws.top + 48 + i * 24, 400, 360);
            }
            entry.el.style.display = entry.el.dataset.pageVisible === "1" ? "" : "none";
        });
    }

    function openNavPage(nav) {
        document.querySelectorAll(".nav-item").forEach((b) => {
            b.classList.toggle("active", b.dataset.nav === nav);
        });
        ["jobs", "projects", "settings"].forEach((page) => {
            const entry = panels.get(`page-float-${page}`);
            if (entry) {
                entry.el.style.display = "none";
                entry.el.dataset.pageVisible = "0";
            }
        });
        if (nav === "chat") {
            if (!isChatDetached()) detachChat();
            focus(CHAT_FLOAT_ID);
            return;
        }
        const id = `page-float-${nav}`;
        const entry = panels.get(id);
        if (entry) {
            entry.el.style.display = "";
            entry.el.dataset.pageVisible = "1";
            focus(id);
        }
    }

    function initFloatShell() {
        ensureDom();
        document.body.classList.add("layout-float", "shell-float");
        try {
            localStorage.setItem(FLOAT_LAYOUT_KEY, "1");
            localStorage.setItem(CHAT_DOCK_KEY, "0");
        } catch (_) {}

        ensureTerminal();

        open({
            id: CONTROLS_ID,
            panel_type: "controls",
            title: "Agenti · PRO · Stato",
            width: 300,
            height: 420,
            manual: true,
        });
        open({
            id: BRAIN_FLOAT_ID,
            panel_type: "page",
            title: "JANIS Brain",
            width: 300,
            height: 250,
            manual: true,
        });
        open({
            id: NAV_ID,
            panel_type: "nav",
            title: "Navigazione",
            width: 200,
            height: 132,
            manual: true,
        });

        ["jobs", "projects", "settings"].forEach((page) => {
            const titles = { jobs: "Lavori", projects: "Progetti", settings: "Impostazioni" };
            open({
                id: `page-float-${page}`,
                panel_type: "page",
                title: titles[page] || page,
                width: 400,
                height: 360,
                manual: false,
            });
            const entry = panels.get(`page-float-${page}`);
            if (entry) {
                entry.body.classList.add("page-float-body");
                entry.el.style.display = "none";
                entry.el.dataset.pageVisible = "0";
            }
        });

        moveIntoPanel(CONTROLS_ID, "#knowledge-legend", null);
        moveIntoPanel(CONTROLS_ID, ".sidebar-agents", null);
        moveIntoPanel(CONTROLS_ID, "#sidebar-pro", null);
        moveIntoPanel(CONTROLS_ID, ".sidebar-footer", null);
        moveIntoPanel(BRAIN_FLOAT_ID, "#brain-viewport", null);
        moveIntoPanel(NAV_ID, ".sidebar-nav", null);
        ["jobs", "projects", "settings"].forEach((page) => {
            moveIntoPanel(`page-float-${page}`, `#page-${page}`, null);
        });

        const controlsBody = panels.get(CONTROLS_ID)?.body;
        if (controlsBody) controlsBody.classList.add("controls-panel-body");

        detachChat();
        restoreLayout();
        layoutFloatShell();
        if (panels.has(CHAT_FLOAT_ID)) {
            focus(CHAT_FLOAT_ID);
            panels.get(CHAT_FLOAT_ID).el.style.zIndex = ++zIndex + 50;
        } else {
            logVerbose("ERR", "Finestra chat non creata — ricarica la pagina", "err");
        }
        updateFloatLayoutButton();
        logVerbose("SYS", "Shell a finestre flottanti attiva", "ok");
        logVerbose("SYS", "Terminal VERBOSE — log di avvio, WS, tool, chat", "ok");
        notifyPanelChange();
    }

    function initDefaults(canvas) {
        if (document.body.classList.contains("mode-ide")) {
            initFloatShell();
            initChatDockUi();
            return;
        }
        openBrain(canvas, "Cervello");
        open({
            id: chatPanelId,
            panel_type: "chat",
            title: "Chat JANIS",
            width: 400,
            height: 320,
        });
        open({
            id: "terminal-main",
            panel_type: "terminal",
            title: "Terminal",
            width: 440,
            height: 300,
            content: "JANIS Terminal — output comandi qui.\n",
            manual: true,
        });
        relayoutAll();
    }

    function setOnPanelResize(fn) {
        onPanelResize = fn;
    }

    function setOnBrainResize(fn) {
        onPanelResize = fn;
    }

    function setBrainResizeHandler(fn) {
        onPanelResize = fn;
    }

    global.JanisPanel = {
        open, openBrain, openWeb, openSystemBrowser, openWhatsApp, openMac, close, update, append, focus, list, handleEvent,
        formatChatDisplay, appendChat, appendCursorStream, logDock, logVerbose, appendTerminal, initDefaults, initFloatShell, initChatDockUi,
        relayoutAll, relayoutAllDebounced, openNavPage, layoutFloatShell,
        detachChat, attachChat, toggleChatDock, enableFloatLayout, disableFloatLayout, toggleFloatLayout, isFloatLayout,
        syncDockHeight, scheduleSave, syncAgentTabs, syncAgentCards,
        setOnPanelResize, setOnBrainResize, setBrainResizeHandler, setOnPanelChange,
        getBrainMount,
        getChatPanelId: () => chatPanelId,
        getBrainPanelId: () => brainPanelId,
    };
})(window);
