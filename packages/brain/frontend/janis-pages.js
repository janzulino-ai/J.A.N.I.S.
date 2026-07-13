/**
 * JANIS — pagine sidebar (Lavori, Progetti, Impostazioni)
 */
(function (global) {
    "use strict";

    let wsBaseFn = () => location.origin;
    let toolRuns = [];
    let activeAgents = new Map();
    let folderBrowser = { currentPath: "", scanRoots: [] };

    function parseScanRoots(raw) {
        return (raw || "")
            .split(",")
            .map((p) => p.trim())
            .filter(Boolean);
    }

    function joinScanRoots(roots) {
        return [...new Set(roots.map((p) => p.trim()).filter(Boolean))].join(",");
    }

    function syncFolderHiddenInputs() {
        const rootsEl = document.getElementById("janis-scan-roots");
        if (rootsEl) rootsEl.value = joinScanRoots(folderBrowser.scanRoots);
        renderScanRootsList();
    }

    function renderScanRootsList() {
        const el = document.getElementById("scan-roots-list");
        if (!el) return;
        if (!folderBrowser.scanRoots.length) {
            el.innerHTML = '<li class="page-muted">Nessuna cartella autorizzata — aggiungine una dal browser sotto.</li>';
            return;
        }
        el.innerHTML = folderBrowser.scanRoots.map((p) =>
            `<li><code>${escapeHtml(p)}</code>
                <button type="button" class="btn-icon remove-root" data-path="${escapeAttr(p)}" title="Rimuovi">✕</button></li>`
        ).join("");
        el.querySelectorAll(".remove-root").forEach((btn) => {
            btn.addEventListener("click", () => {
                const path = btn.getAttribute("data-path");
                folderBrowser.scanRoots = folderBrowser.scanRoots.filter((x) => x !== path);
                syncFolderHiddenInputs();
            });
        });
    }

    function escapeHtml(s) {
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
    }

    function escapeAttr(s) {
        return escapeHtml(s);
    }

    async function loadDrives() {
        const box = document.getElementById("fs-drives");
        if (!box) return;
        try {
            const res = await fetch(`${wsBaseFn()}/api/fs/drives`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || res.statusText);
            box.innerHTML = (data.drives || []).map((d) => {
                const type = d.type === "removable" ? "USB" : d.type === "network" ? "Rete" : "Disco";
                const label = d.label ? `${d.label}` : d.path;
                return `<button type="button" class="drive-btn" data-path="${escapeAttr(d.path)}" title="${escapeAttr(type)}">${escapeHtml(d.letter ? d.letter + ":" : label)}</button>`;
            }).join("");
            box.querySelectorAll(".drive-btn").forEach((btn) => {
                btn.addEventListener("click", () => browseFolder(btn.getAttribute("data-path")));
            });
            if (data.drives?.length && !folderBrowser.currentPath) {
                await browseFolder(data.drives[0].path);
            }
        } catch (e) {
            box.innerHTML = `<span class="page-err">${escapeHtml(e.message)}</span>`;
        }
    }

    async function browseFolder(path) {
        const list = document.getElementById("fs-folder-list");
        const crumb = document.getElementById("fs-breadcrumb");
        if (!list) return;
        list.innerHTML = "<li class='page-muted'>Caricamento…</li>";
        try {
            const q = path ? `?path=${encodeURIComponent(path)}` : "";
            const res = await fetch(`${wsBaseFn()}/api/fs/browse${q}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || res.statusText);
            folderBrowser.currentPath = data.path;
            if (crumb) crumb.textContent = data.path;
            let html = "";
            if (data.parent) {
                html += `<li><button type="button" class="folder-row parent" data-path="${escapeAttr(data.parent)}">⬆ Cartella superiore</button></li>`;
            }
            html += (data.entries || []).map((e) =>
                `<li><button type="button" class="folder-row" data-path="${escapeAttr(e.path)}">📁 ${escapeHtml(e.name)}</button></li>`
            ).join("");
            if (!html) html = "<li class='page-muted'>Nessuna sottocartella.</li>";
            list.innerHTML = html;
            list.querySelectorAll(".folder-row").forEach((btn) => {
                btn.addEventListener("click", () => browseFolder(btn.getAttribute("data-path")));
            });
        } catch (e) {
            list.innerHTML = `<li class="page-err">${escapeHtml(e.message)}</li>`;
        }
    }

    function addCurrentToScanRoots() {
        const p = folderBrowser.currentPath;
        if (!p) return;
        if (!folderBrowser.scanRoots.includes(p)) {
            folderBrowser.scanRoots.push(p);
        }
        syncFolderHiddenInputs();
    }

    async function saveKnowledgeFolders() {
        const status = document.getElementById("knowledge-status");
        if (status) status.textContent = "Salvo cartelle…";
        const body = {
            janis_scan_roots: joinScanRoots(folderBrowser.scanRoots) || undefined,
        };
        const res = await fetch(`${wsBaseFn()}/api/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || res.statusText);
        }
        if (status) status.textContent = "JANIS sta imparando con Ollama… (neuroni in crescita)";
        pollKnowledgeStatus();
    }

    async function pollKnowledgeStatus(attempts = 30) {
        const status = document.getElementById("knowledge-status");
        for (let i = 0; i < attempts; i++) {
            await new Promise((r) => setTimeout(r, 4000));
            try {
                const res = await fetch(`${wsBaseFn()}/api/knowledge/status`);
                const data = await res.json();
                const when = data.last_enriched ? data.last_enriched.slice(0, 19).replace("T", " ") : null;
                if (when && status) {
                    status.textContent = `${data.folder_count} cartelle · ${data.clusters} cluster · aggiornato ${when}`;
                    window.JANIS?.connect?.();
                    renderSettings();
                    return;
                }
            } catch (_) { /* retry */ }
        }
        if (status) status.textContent = "Apprendimento in corso — i neuroni si aggiornano in background.";
    }

    function setWsBase(fn) {
        wsBaseFn = fn;
    }

    function recordToolStart(tool, reason) {
        toolRuns.unshift({
            tool,
            reason: reason || "",
            time: new Date().toLocaleTimeString(),
            status: "running",
        });
        if (toolRuns.length > 30) toolRuns.pop();
        renderJobs();
    }

    function recordToolEnd(tool) {
        const run = toolRuns.find((r) => r.tool === tool && r.status === "running");
        if (run) run.status = "done";
        renderJobs();
    }

    function setActiveAgents(map) {
        activeAgents = map;
        renderJobs();
    }

    function switchNav(nav) {
        document.querySelectorAll(".nav-item").forEach((b) => {
            b.classList.toggle("active", b.dataset.nav === nav);
        });
        if (document.body.classList.contains("shell-float")) {
            global.JanisPanel?.openNavPage?.(nav);
            if (nav === "jobs") renderJobs();
            if (nav === "projects") renderProjects();
            if (nav === "settings") renderSettings();
            return;
        }
        const isChat = nav === "chat";
        document.getElementById("chat-column")?.classList.toggle("nav-hidden", !isChat);
        document.getElementById("page-views")?.classList.toggle("visible", !isChat);
        document.querySelectorAll(".page-view").forEach((p) => {
            p.classList.toggle("active", p.dataset.page === nav);
        });
        if (nav === "jobs") renderJobs();
        if (nav === "projects") renderProjects();
        if (nav === "settings") renderSettings();
    }

    function renderJobs() {
        const el = document.getElementById("page-jobs");
        if (!el) return;
        const agents = Array.from(activeAgents.entries());
        let html = "<h3>Agenti attivi</h3>";
        if (!agents.length) {
            html += '<p class="page-muted">Nessun agente in esecuzione.</p>';
        } else {
            html += "<ul class='page-list'>" + agents.map(([id, label]) =>
                `<li><span class="dot running"></span> ${label} <code>${id}</code></li>`
            ).join("") + "</ul>";
        }
        html += "<h3>Tool recenti</h3>";
        if (!toolRuns.length) {
            html += '<p class="page-muted">Nessun tool eseguito in questa sessione.</p>';
        } else {
            html += "<ul class='page-list'>" + toolRuns.map((r) =>
                `<li><span class="dot ${r.status}"></span> ${r.time} — <strong>${r.tool}</strong> ${r.reason ? `<em>${r.reason}</em>` : ""}</li>`
            ).join("") + "</ul>";
        }
        el.innerHTML = html;
    }

    async function renderProjects() {
        const el = document.getElementById("page-projects");
        if (!el) return;
        el.innerHTML = "<p class='page-muted'>Caricamento…</p>";
        try {
            const res = await fetch(`${wsBaseFn()}/api/projects`);
            const data = await res.json();
            let html = `<h3>Workspace: ${data.root}</h3><ul class="page-list">`;
            (data.projects || []).forEach((p) => {
                html += `<li class="${p.is_current ? "current" : ""}">📁 <strong>${p.name}</strong><br><code>${p.path}</code></li>`;
            });
            html += "</ul>";
            el.innerHTML = html;
        } catch (e) {
            el.innerHTML = `<p class="page-err">Errore: ${e.message}</p>`;
        }
    }

    async function populateSettingsMicSelect() {
        const sel = document.getElementById("settings-mic-select");
        if (!sel || !global.JanisMic?.listAudioDevices) return;
        const saved = global.JanisMic.getPreferredDeviceId?.() || "";
        let devices = [];
        try {
            devices = await global.JanisMic.listAudioDevices();
        } catch (_) {}
        sel.innerHTML = '<option value="">Mic predefinito di sistema</option>' +
            devices.map((d) =>
                `<option value="${escapeAttr(d.deviceId)}"${d.deviceId === saved ? " selected" : ""}>${escapeHtml(d.label)}</option>`
            ).join("");
    }

    async function renderSettings() {
        const el = document.getElementById("page-settings");
        if (!el) return;
        try {
            const [resSettings, resRuntime] = await Promise.all([
                fetch(`${wsBaseFn()}/api/settings`),
                fetch(`${wsBaseFn()}/api/runtime`),
            ]);
            const s = await resSettings.json();
            const rt = await resRuntime.json();
            const knowledge = s.knowledge || {};
            const enrichDate = knowledge.last_enriched
                ? knowledge.last_enriched.slice(0, 19).replace("T", " ")
                : "—";
            const scanRoots = parseScanRoots(s.janis_scan_roots);
            folderBrowser.scanRoots = scanRoots;
            folderBrowser.currentPath = scanRoots[0] || "";
            const providers = (s.reasoning_providers || rt.reasoning_providers || ["ollama", "cursor", "openrouter", "auto"]);
            const cursorModels = s.cursor_models || rt.cursor_models || [];
            el.innerHTML = `
                <h3>Impostazioni</h3>
                <form id="settings-form" class="settings-form">
                    <fieldset class="settings-folder-index">
                        <legend>Cartelle da conoscere</legend>
                        <p class="page-muted">Seleziona cartelle su qualsiasi disco. JANIS le legge con Ollama e arricchisce i neuroni del second brain — come un vault Obsidian.</p>
                        <input type="hidden" id="janis-scan-roots" name="janis_scan_roots" value="${escapeAttr(joinScanRoots(folderBrowser.scanRoots))}" />
                        <p class="page-muted"><strong>Cervello:</strong> ${knowledge.folder_count || scanRoots.length} cartelle · ${knowledge.clusters || 0} cluster · ${enrichDate}</p>
                        <p class="page-muted">Cartelle selezionate:</p>
                        <ul id="scan-roots-list" class="page-list scan-roots-list"></ul>
                        <div class="fs-browser">
                            <p class="page-muted">Unità disponibili</p>
                            <div id="fs-drives" class="fs-drives"></div>
                            <p class="page-muted">Sfoglia e seleziona</p>
                            <div id="fs-breadcrumb" class="fs-breadcrumb">${escapeHtml(folderBrowser.currentPath || "—")}</div>
                            <ul id="fs-folder-list" class="fs-folder-list page-list"></ul>
                            <div class="fs-browser-actions">
                                <button type="button" id="add-scan-root-btn" class="btn-save secondary">Aggiungi questa cartella</button>
                                <button type="button" id="save-paths-btn" class="btn-save">Salva e impara</button>
                            </div>
                            <label class="fs-path-manual">Oppure incolla percorso
                                <input type="text" id="manual-folder-path" placeholder="D:\\Film  oppure  C:\\Users\\...\\Videos" />
                            </label>
                            <button type="button" id="add-manual-path-btn" class="btn-save secondary">Aggiungi percorso</button>
                        </div>
                        <span id="knowledge-status" class="page-muted"></span>
                    </fieldset>
                    <fieldset class="settings-pro">
                        <legend>Modalità PRO (API a pagamento)</legend>
                        <p class="page-muted">Attiva anche il pulsante PRO nella sidebar. Con PRO puoi usare Cursor API per il ragionamento e l'agente codice.</p>
                        <label class="checkbox-row">
                            <input type="checkbox" name="paid_mode" ${rt.paid_mode ? "checked" : ""} />
                            PRO attivo
                        </label>
                        <label>Ragionamento (con PRO)
                            <select name="reasoning_provider">
                                ${providers.map((p) =>
                                    `<option value="${p}" ${rt.reasoning_provider === p ? "selected" : ""}>${p}</option>`
                                ).join("")}
                            </select>
                        </label>
                        <label>Modello Cursor (ragionamento)
                            <select name="cursor_reasoning_model">
                                ${cursorModels.map((m) =>
                                    `<option value="${m}" ${(rt.cursor_reasoning_model || s.cursor_model) === m ? "selected" : ""}>${m}</option>`
                                ).join("")}
                            </select>
                        </label>
                        <label class="checkbox-row">
                            <input type="checkbox" name="cursor_code_enabled" ${rt.cursor_code_enabled !== false ? "checked" : ""} />
                            Agente Cursor (codice) abilitato
                        </label>
                        <label class="checkbox-row">
                            <input type="checkbox" name="openrouter_when_paid" ${rt.openrouter_when_paid !== false ? "checked" : ""} />
                            OpenRouter nel fallback Auto PRO
                        </label>
                        <label>Cursor API key
                            <input name="cursor_api_key" type="password" placeholder="${s.cursor_api_key_hint || "sk-…"}" autocomplete="off" />
                        </label>
                        <label>Modello Cursor default (.env)
                            <select name="cursor_model">
                                ${cursorModels.map((m) =>
                                    `<option value="${m}" ${s.cursor_model === m ? "selected" : ""}>${m}</option>`
                                ).join("")}
                            </select>
                        </label>
                        <p class="page-muted">Cursor: ${s.cursor_configured ? "configurato" : "non configurato"} · Attivo ora: ${rt.effective_reasoning || s.llm_active}</p>
                    </fieldset>
                    <h4>Locale e voce</h4>
                    <label>Provider LLM (senza PRO)
                        <select name="llm_provider">
                            <option value="ollama" ${s.llm_provider === "ollama" ? "selected" : ""}>Ollama (locale)</option>
                            <option value="auto" ${s.llm_provider === "auto" ? "selected" : ""}>Auto (fallback)</option>
                            <option value="openrouter" ${s.llm_provider === "openrouter" ? "selected" : ""}>OpenRouter</option>
                        </select>
                    </label>
                    <label>Modello Ollama
                        <input name="ollama_model" value="${s.ollama_model || ""}" list="ollama-models" />
                        <datalist id="ollama-models">${(s.ollama_models || []).map((m) => `<option value="${m}">`).join("")}</datalist>
                    </label>
                    <label>Voce TTS
                        <input name="tts_voice" value="${s.tts_voice || ""}" />
                    </label>
                    <fieldset class="settings-folder-index">
                        <legend>Microfono</legend>
                        <p class="page-muted">Seleziona il microfono (utile con cuffie Bluetooth). Puoi cambiarlo anche dal menu 🎤 accanto al pulsante vocale in chat.</p>
                        <label>Dispositivo input
                            <select id="settings-mic-select">
                                <option value="">Mic predefinito di sistema</option>
                            </select>
                        </label>
                        <button type="button" id="refresh-mic-btn" class="btn-save secondary">Aggiorna elenco microfoni</button>
                    </fieldset>
                    <label>Rate TTS <input name="tts_rate" value="${s.tts_rate || ""}" /></label>
                    <label>Pitch TTS <input name="tts_pitch" value="${s.tts_pitch || ""}" /></label>
                    <label>Workspace <input name="janis_workspace" value="${s.janis_workspace || ""}" /></label>
                    <p class="page-muted">Ollama: ${s.ollama_online ? "online" : "offline"} · OpenRouter: ${s.openrouter_configured ? "ok" : "—"}</p>
                    <button type="submit" class="btn-save">Salva</button>
                    <button type="button" id="test-tts-btn" class="btn-save secondary">Test voce</button>
                </form>`;
            document.getElementById("settings-form").addEventListener("submit", saveSettings);
            document.getElementById("test-tts-btn").addEventListener("click", testTts);
            document.getElementById("add-scan-root-btn")?.addEventListener("click", addCurrentToScanRoots);
            document.getElementById("add-manual-path-btn")?.addEventListener("click", () => {
                const input = document.getElementById("manual-folder-path");
                const p = input?.value?.trim();
                if (!p) return;
                if (!folderBrowser.scanRoots.includes(p)) folderBrowser.scanRoots.push(p);
                folderBrowser.currentPath = p;
                syncFolderHiddenInputs();
                const crumb = document.getElementById("fs-breadcrumb");
                if (crumb) crumb.textContent = p;
                if (input) input.value = "";
            });
            document.getElementById("save-paths-btn")?.addEventListener("click", async () => {
                try {
                    await saveKnowledgeFolders();
                } catch (e) {
                    const st = document.getElementById("knowledge-status");
                    if (st) st.textContent = `Errore: ${e.message}`;
                }
            });
            renderScanRootsList();
            loadDrives();
            populateSettingsMicSelect();
            document.getElementById("refresh-mic-btn")?.addEventListener("click", populateSettingsMicSelect);
            document.getElementById("settings-mic-select")?.addEventListener("change", (ev) => {
                const id = ev.target.value || "";
                global.JanisMic?.setPreferredDeviceId?.(id || null);
                global.JanisMic?.stop?.();
                const mainSel = document.getElementById("mic-select");
                if (mainSel) mainSel.value = id;
            });
        } catch (e) {
            el.innerHTML = `<p class="page-err">${e.message}</p>`;
        }
    }

    async function saveSettings(ev) {
        ev.preventDefault();
        const fd = new FormData(ev.target);
        const body = Object.fromEntries(fd.entries());
        const runtimeBody = {
            paid_mode: !!ev.target.querySelector('[name="paid_mode"]')?.checked,
            reasoning_provider: body.reasoning_provider,
            cursor_reasoning_model: body.cursor_reasoning_model,
            cursor_code_enabled: !!ev.target.querySelector('[name="cursor_code_enabled"]')?.checked,
            openrouter_when_paid: !!ev.target.querySelector('[name="openrouter_when_paid"]')?.checked,
        };
        delete body.paid_mode;
        delete body.reasoning_provider;
        delete body.cursor_reasoning_model;
        delete body.cursor_code_enabled;
        delete body.openrouter_when_paid;
        if (!body.cursor_api_key) delete body.cursor_api_key;
        if (!body.janis_scan_roots) delete body.janis_scan_roots;
        delete body.janis_movies_path;
        await Promise.all([
            fetch(`${wsBaseFn()}/api/settings`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            }),
            fetch(`${wsBaseFn()}/api/runtime`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(runtimeBody),
            }),
        ]);
        window.JANIS?.fetchRuntime?.();
        renderSettings();
    }

    async function testTts() {
        const voice = document.querySelector('[name="tts_voice"]')?.value;
        const res = await fetch(`${wsBaseFn()}/api/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: "Ciao, sono JANIS. Voce configurata correttamente.", voice }),
        });
        if (res.ok) {
            const url = URL.createObjectURL(await res.blob());
            new Audio(url).play();
        }
    }

    function bindNav() {
        document.querySelectorAll(".nav-item[data-nav]").forEach((btn) => {
            btn.addEventListener("click", () => switchNav(btn.dataset.nav));
        });
    }

    async function checkSetup() {
        if (localStorage.getItem("janis_setup_done") === "1") return;
        try {
            const res = await fetch(`${wsBaseFn()}/api/setup/status`);
            const s = await res.json();
            if (!s.ready) showSetupModal(s);
        } catch (_) {
            showSetupModal({ ready: false });
        }
    }

    function showSetupModal(status) {
        if (document.getElementById("setup-modal")) return;
        const modal = document.createElement("div");
        modal.id = "setup-modal";
        modal.className = "setup-modal";
        modal.innerHTML = `
            <div class="setup-card">
                <h2>Benvenuto in JANIS</h2>
                <ol>
                    <li class="${status.env_exists ? "ok" : ""}">File .env ${status.env_exists ? "✓" : "— copia .env.example"}</li>
                    <li class="${status.ollama_online ? "ok" : ""}">Ollama ${status.ollama_online ? "✓ online" : "✗ offline — avvia Ollama"}</li>
                    <li>Modelli: ${(status.ollama_models || []).slice(0, 3).join(", ") || "nessuno"}</li>
                </ol>
                <button type="button" id="setup-dismiss">Inizia</button>
            </div>`;
        document.body.appendChild(modal);
        document.getElementById("setup-dismiss").addEventListener("click", () => {
            localStorage.setItem("janis_setup_done", "1");
            modal.remove();
        });
    }

    function showMemoryDetail(entry) {
        let drawer = document.getElementById("memory-drawer");
        if (!drawer) {
            drawer = document.createElement("aside");
            drawer.id = "memory-drawer";
            drawer.className = "memory-drawer";
            document.getElementById("janis-shell").appendChild(drawer);
        }
        drawer.innerHTML = `
            <button type="button" class="drawer-close">✕</button>
            <h4>Memoria</h4>
            <p class="mem-text">${entry.text || ""}</p>
            <p class="mem-meta">${entry.source || "user"} · ${(entry.timestamp || "").slice(0, 19)}</p>
            <p class="mem-tags">${(entry.tags || []).map((t) => `<span class="tag">${t}</span>`).join("")}</p>`;
        drawer.classList.add("open");
        drawer.querySelector(".drawer-close").addEventListener("click", () => drawer.classList.remove("open"));
    }

    async function openMemory(id) {
        try {
            const res = await fetch(`${wsBaseFn()}/api/memory/${encodeURIComponent(id)}`);
            if (res.ok) showMemoryDetail(await res.json());
        } catch (_) {}
    }

    function init(options) {
        if (options?.wsBase) setWsBase(options.wsBase);
        bindNav();
        checkSetup();
    }

    global.JanisPages = {
        init, switchNav, recordToolStart, recordToolEnd, setActiveAgents, openMemory,
    };
})(window);
