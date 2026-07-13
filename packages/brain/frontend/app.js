// JANIS — bootstrap sicuro
(function () {
    "use strict";

    function boot() {
        if (typeof THREE === "undefined") {
            console.error("ERRORE: Three.js non caricato.");
            return;
        }
        if (!window.JanisBrain || !window.JanisPanel) {
            console.error("ERRORE: moduli JANIS mancanti.");
            return;
        }

        const params = new URLSearchParams(location.search);
        let rawMode = params.get("mode") || "browser";
        if (rawMode === "browser") rawMode = "window";
        let displayMode = rawMode;
        let muted = params.get("muted") === "1";
        try {
            if (localStorage.getItem("janis_tts_muted") === "1") muted = true;
            if (localStorage.getItem("janis_tts_muted") === "0") muted = false;
        } catch (_) {}
        let audioUnlocked = false;
        let ttsNeedsUnlock = false;
        let currentState = "IDLE";
        let ws = null;
        let recognition = null;
        let isListening = false;
        let reconnectDelay = 1000;
        let userLevel = 3, janisLevel = 3, targetUserLevel = 3, targetJanisLevel = 3;
        let currentAudio = null, chatBuffer = "";
        let chatStreamingEl = null;
        const TTS_PLAYBACK_RATE = 1.18;
        let lastNodeId = null;
        const activeAgents = new Map();
        const ttsQueue = [];
        let ttsPlaying = false;

        const badge = document.getElementById("status-badge");
        const connDot = document.getElementById("conn-dot");
        const connLabel = document.getElementById("conn-label");
        const knowledgeLegend = document.getElementById("knowledge-legend");
        const fleetNodesEl = document.getElementById("fleet-nodes");
        const fleetSummaryEl = document.getElementById("fleet-summary");
        const cmdInput = document.getElementById("cmd-input");
        const voiceBtn = document.getElementById("voice-btn");
        const micSelect = document.getElementById("mic-select");
        const sendBtn = document.getElementById("send-btn");
        const clearBtn = document.getElementById("clear-btn");
        const stopVoiceBtn = document.getElementById("stop-voice-btn");
        const ttsToggleBtn = document.getElementById("tts-toggle");
        const speakingIndicator = document.getElementById("speaking-indicator");
        const agentSelect = document.getElementById("agent-select");
        const chatAgentLabel = document.getElementById("chat-agent-label");
        const paidToggle = document.getElementById("paid-toggle");
        const paidState = document.getElementById("paid-state");
        const reasoningQuick = document.getElementById("reasoning-quick");
        const cursorModelQuick = document.getElementById("cursor-model-quick");
        const proHint = document.getElementById("pro-hint");

        let runtimeState = {
            paid_mode: false,
            reasoning_provider: "ollama",
            cursor_reasoning_model: "",
            cursor_api_configured: false,
            effective_reasoning: "ollama",
            cursor_models: [],
        };

        const AGENTS = {
            janis: { label: "JANIS", title: "Chat JANIS", panel: null },
            terminal: { label: "Terminal", title: "Agente Terminal", panel: "terminal-main", panel_type: "terminal" },
            cursor: { label: "Cursor Agent", title: "Agente Cursor", panel: "cursor-main", panel_type: "cursor" },
            mac: { label: "Mac Mini", title: "Agente Mac", panel: "mac-main", panel_type: "mac" },
            web: { label: "Browser", title: "Agente Web", panel_type: "web" },
            whatsapp: { label: "WhatsApp", title: "Agente WhatsApp", panel: "whatsapp-main", panel_type: "whatsapp" },
        };
        let selectedAgent = "janis";

        let renderer = null;
        let canvas = null;

        function logDock(text, cls) {
            window.JanisPanel?.logDock?.(text, cls || "");
        }

        function logVerbose(prefix, text, cls) {
            window.JanisPanel?.logVerbose?.(prefix, text, cls || "");
        }

        const REASONING_LABELS = {
            ollama: "Ollama",
            cursor: "Cursor API",
            openrouter: "OpenRouter",
            auto: "Auto PRO",
        };

        function fillCursorModels(models, selected) {
            if (!cursorModelQuick) return;
            const list = models && models.length ? models : ["composer-2.5"];
            cursorModelQuick.innerHTML = list.map((m) =>
                `<option value="${m}"${m === selected ? " selected" : ""}>${m}</option>`
            ).join("");
        }

        function applyRuntimeUI(rt) {
            runtimeState = { ...runtimeState, ...rt };
            const paid = !!runtimeState.paid_mode;
            if (paidToggle) paidToggle.classList.toggle("on", paid);
            if (paidState) paidState.textContent = paid ? "ON" : "OFF";
            if (reasoningQuick) {
                reasoningQuick.disabled = !paid;
                reasoningQuick.value = runtimeState.reasoning_provider || "ollama";
            }
            fillCursorModels(
                runtimeState.cursor_models,
                runtimeState.cursor_reasoning_model || runtimeState.cursor_code_model
            );
            const showCursorModel = paid && (runtimeState.reasoning_provider === "cursor" || runtimeState.reasoning_provider === "auto");
            const cursorModelLabel = document.querySelector('label[for="cursor-model-quick"]');
            if (cursorModelLabel) cursorModelLabel.hidden = !showCursorModel;
            if (cursorModelQuick) {
                cursorModelQuick.disabled = !showCursorModel;
                cursorModelQuick.hidden = !showCursorModel;
            }
            if (proHint) {
                proHint.className = "pro-hint";
                if (!paid) {
                    proHint.textContent = "Attiva PRO per Cursor API e modelli cloud.";
                } else if (runtimeState.reasoning_provider === "cursor" && !runtimeState.cursor_api_configured) {
                    proHint.textContent = "Aggiungi CURSOR_API_KEY in Impostazioni.";
                    proHint.classList.add("warn");
                } else {
                    const eff = REASONING_LABELS[runtimeState.effective_reasoning] || runtimeState.effective_reasoning;
                    proHint.textContent = `Attivo: ${eff}`;
                    proHint.classList.add("ok");
                }
            }
        }

        let runtimeApiAvailable = true;

        async function fetchRuntime() {
            try {
                const res = await fetch(`${wsBase()}/api/runtime`);
                if (res.status === 404) {
                    runtimeApiAvailable = false;
                    const st = await fetch(`${wsBase()}/api/status`).then((r) => r.json()).catch(() => ({}));
                    if (!st.runtime_api) {
                        if (proHint) {
                            proHint.textContent = "Riavvia JANIS per abilitare PRO (backend non aggiornato).";
                            proHint.className = "pro-hint warn";
                        }
                    }
                    return null;
                }
                if (!res.ok) throw new Error("runtime");
                runtimeApiAvailable = true;
                applyRuntimeUI(await res.json());
                return runtimeState;
            } catch (_) {
                if (proHint) proHint.textContent = "Runtime non disponibile — controlla connessione backend.";
                return null;
            }
        }

        async function patchRuntime(body) {
            const res = await fetch(`${wsBase()}/api/runtime`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (res.status === 404) {
                runtimeApiAvailable = false;
                throw new Error("runtime404");
            }
            if (!res.ok) throw new Error("runtime save");
            const data = await res.json();
            applyRuntimeUI(data);
            const eff = REASONING_LABELS[data.effective_reasoning] || data.effective_reasoning;
            logDock(`PRO ${data.paid_mode ? "ON" : "OFF"} · ${eff}`, data.paid_mode ? "ok" : "");
            return data;
        }

        async function togglePaidMode() {
            const nextPaid = !runtimeState.paid_mode;
            try {
                let res = await fetch(`${wsBase()}/api/runtime/toggle-paid`, { method: "POST" });
                if (res.status === 404) {
                    res = await fetch(`${wsBase()}/api/runtime`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ paid_mode: nextPaid }),
                    });
                }
                if (res.status === 404) {
                    runtimeApiAvailable = false;
                    logDock("PRO: riavvia JANIS (backend senza /api/runtime)", "err");
                    if (proHint) {
                        proHint.textContent = "Riavvia JANIS: .\\dev\\stop-janis.ps1 poi .\\dev\\run-debug.ps1";
                        proHint.className = "pro-hint warn";
                    }
                    return;
                }
                if (!res.ok) throw new Error("toggle");
                await fetchRuntime();
                logDock(`PRO ${runtimeState.paid_mode ? "attivato" : "disattivato"}`, runtimeState.paid_mode ? "ok" : "");
            } catch (_) {
                logDock("Errore toggle PRO — riavvia il backend", "err");
            }
        }

        function applyDisplayMode(mode) {
            displayMode = mode || "window";
            document.body.className = `mode-${displayMode} mode-ide interact-mode`;
            window.JanisPanel?.syncDockHeight?.();
            window.JanisPanel?.relayoutAll?.();
            if (renderer) resizeScene();
        }

        document.body.className = `mode-${displayMode} mode-ide interact-mode`;
        window.JanisPanel.syncDockHeight();

        const brainMount = document.getElementById("brain-viewport");
        if (!brainMount) {
            logDock("ERRORE: sidebar cervello mancante", "err");
            return;
        }

        canvas = document.createElement("canvas");
        canvas.id = "janis-scene";
        canvas.className = "panel-brain-canvas";
        brainMount.appendChild(canvas);

        window.JanisPanel.initDefaults();

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
        const BRAIN_BOUNDS = 1.05;
        const BRAIN_LOOK_Y = 0.12;

        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, premultipliedAlpha: false });
        renderer.setClearColor(0x000000, 0);

        function fitBrainCamera(w, h) {
            const aspect = Math.max(0.35, w / Math.max(1, h));
            camera.aspect = aspect;
            const vFovRad = THREE.MathUtils.degToRad(camera.fov);
            const hFovRad = 2 * Math.atan(Math.tan(vFovRad / 2) * aspect);
            const tightFov = Math.min(vFovRad, hFovRad);
            const padding = 1.35;
            const dist = (BRAIN_BOUNDS * padding) / Math.sin(tightFov / 2);
            camera.position.set(0, BRAIN_LOOK_Y * 0.85, Math.max(4.0, dist));
            camera.lookAt(0, BRAIN_LOOK_Y, 0);
            camera.updateProjectionMatrix();
        }

        function resizeScene() {
            if (!canvas || !renderer) return;
            window.JanisPanel.syncDockHeight();
            const rect = canvas.getBoundingClientRect();
            const w = Math.max(1, rect.width);
            const h = Math.max(1, rect.height);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            renderer.setSize(w, h, false);
            fitBrainCamera(w, h);
        }

        window.JanisPanel.setOnPanelResize(resizeScene);

        const characterGroup = new THREE.Group();
        scene.add(characterGroup);
        const neuronCore = (window.JanisBrain?.createSecondBrain || window.JanisNeurons.createNeuronCore)();
        characterGroup.add(neuronCore.group);
        characterGroup.position.set(0, 0.15, 0);
        characterGroup.scale.setScalar(0.88);

        const clock = new THREE.Clock();

        function animate() {
            requestAnimationFrame(animate);
            const dt = clock.getDelta();
            userLevel += (targetUserLevel - userLevel) * 0.04;
            janisLevel += (targetJanisLevel - janisLevel) * 0.04;
            neuronCore.setLevels(userLevel, janisLevel);
            neuronCore.update(dt, currentState);
            characterGroup.rotation.y += dt * 0.2;
            characterGroup.position.y = 0.15 + Math.sin(clock.getElapsedTime() * 0.8) * 0.04;
            updateLegend();
            renderer.render(scene, camera);
        }
        animate();
        resizeScene();
        logDock("Cervello attivo", "ok");

        function updateLegend() {
            if (!knowledgeLegend) return;
            const agents = activeAgents.size;
            const agentHint = agents > 0 ? ` · <span class="k-agents">${agents} agenti</span>` : "";
            knowledgeLegend.innerHTML =
                `<span class="k-user">Tu ${Math.round(userLevel)}</span>`
                + `<span class="k-sep"> · </span>`
                + `<span class="k-janis">JANIS ${Math.round(janisLevel)}</span>`
                + `<span class="k-sep"> · </span>`
                + `<span class="k-nodes">${neuronCore.getNodeCount?.() || 0} nodi</span>`
                + agentHint;
        }

        function updateFleetUI(fleet) {
            if (!fleetSummaryEl || !fleetNodesEl) return;
            const nodes = fleet?.nodes || [];
            const online = fleet?.nodes_online ?? nodes.filter((n) => n.online).length;
            const total = fleet?.nodes_total ?? nodes.length;
            if (total === 0) {
                fleetSummaryEl.textContent = "0 nodi";
                fleetSummaryEl.title = "Nessun nodo Fleet connesso";
                fleetNodesEl.classList.remove("fleet-active");
                return;
            }
            fleetNodesEl.classList.add("fleet-active");
            const labels = nodes.map((n) => {
                const dot = n.online ? "●" : "○";
                return `${dot} ${n.node_id}`;
            }).join(" · ");
            fleetSummaryEl.textContent = online === total
                ? `${online} nodo${online === 1 ? "" : "i"} online`
                : `${online}/${total} online`;
            fleetSummaryEl.title = labels || "Nodi Fleet";
        }

        async function fetchFleetStatus() {
            try {
                const res = await fetch(`${wsBase()}/api/fleet/nodes`);
                if (!res.ok) return;
                updateFleetUI(await res.json());
            } catch (_) { /* backend offline */ }
        }

        function setConn(on) {
            connDot.className = "conn-dot " + (on ? "online" : "offline");
            connLabel.textContent = on ? "ONLINE" : "OFFLINE";
            connLabel.className = "conn-label " + (on ? "online" : "offline");
        }

        function setState(s) {
            currentState = s;
            if (badge) { badge.textContent = s; badge.className = "badge " + s.toLowerCase(); }
            logVerbose("STATE", s);
            const bv = document.getElementById("brain-viewport");
            if (bv) {
                bv.classList.remove("brain-speaking", "brain-thinking", "brain-active");
                if (s === "SPEAKING") bv.classList.add("brain-speaking", "brain-active");
                else if (s === "THINKING" || s === "ACTING") bv.classList.add("brain-thinking", "brain-active");
                else if (s === "LISTENING") bv.classList.add("brain-active");
            }
        }

        function wsBase() {
            return (params.get("backend") || location.origin).replace(/\/$/, "");
        }

        function wsUrl() {
            const u = new URL(wsBase());
            const proto = u.protocol === "https:" ? "wss" : "ws";
            const device = (displayMode === "window" || displayMode === "browser") ? "browser" : "desktop";
            return `${proto}://${u.host}/ws/janis?device_id=${device}`;
        }

        function updateAgentUI() {
            const agent = AGENTS[selectedAgent] || AGENTS.janis;
            if (chatAgentLabel) chatAgentLabel.textContent = agent.title;
            if (cmdInput) {
                cmdInput.placeholder = selectedAgent === "janis"
                    ? "Messaggio per JANIS..."
                    : `Messaggio per ${agent.label}...`;
            }
            if (agentSelect && agentSelect.value !== selectedAgent) {
                agentSelect.value = selectedAgent;
            }
        }

        function openAgentPanel(agentKey) {
            const agent = AGENTS[agentKey];
            if (!agent || agentKey === "janis") return;
            if (agentKey === "web") {
                window.JanisPanel.openWeb("https://duckduckgo.com", "Browser");
            } else if (agentKey === "whatsapp") {
                window.JanisPanel.openWhatsApp();
            } else if (agentKey === "mac") {
                window.JanisPanel.openMac();
            } else if (agent.panel) {
                window.JanisPanel.open({
                    id: agent.panel,
                    panel_type: agent.panel_type,
                    title: agent.label,
                    width: agentKey === "terminal" ? 520 : 480,
                    height: agentKey === "terminal" ? 340 : 360,
                    content: agentKey === "cursor"
                        ? "Output agenti Cursor SDK.\nConfigura CURSOR_API_KEY in .env\n"
                        : agentKey === "terminal"
                            ? "JANIS Terminal — output comandi qui.\n"
                            : undefined,
                    manual: true,
                });
            }
        }

        function setSelectedAgent(key) {
            if (!AGENTS[key]) return;
            selectedAgent = key;
            window.__janisSelectedAgent = key;
            updateAgentUI();
            window.JanisPanel?.syncAgentCards?.(key);
            if (key !== "janis") openAgentPanel(key);
        }

        function sendMessage(text) {
            if (!text.trim()) return;
            unlockAudio();
            logVerbose("CHAT", ">>> " + text.trim());
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                logDock("Non connessa — riconnetto...", "err");
                connect();
                setTimeout(() => sendMessage(text), 1500);
                return;
            }
            window.JanisPanel.appendChat(text.trim(), "user");
            ws.send(JSON.stringify({
                type: "chat_message",
                text: text.trim(),
                agent: selectedAgent,
            }));
        }

        function sanitizeForTts(text) {
            let t = (text || "")
                .replace(/```[\s\S]*?```/g, " ")
                .replace(/`[^`\n]+`/g, " ")
                .replace(/\*\*([^*]+)\*\*/g, "$1")
                .replace(/\*([^*]+)\*/g, "$1")
                .replace(/^#{1,6}\s+/gm, "")
                .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
                .replace(/https?:\/\/\S+/g, "")
                .replace(/[🟢🟡🔴⏸️✓✗▶◆🔧🌐⌨💬🍎＋🔊🔇]/g, " ")
                .replace(/\s+/g, " ")
                .trim();
            // Preferisci le prime frasi conversazionali
            const parts = t.split(/(?<=[.!?…])\s+/).filter((s) => {
                s = s.trim();
                return s.length >= 12 && !/^[\d\-•*]+\s/.test(s) && !/\{[^}]*"tool"/.test(s);
            });
            if (parts.length) {
                t = parts.slice(0, 3).join(" ");
            }
            return t.slice(0, 420);
        }

        function updateTtsToggleUi() {
            if (!ttsToggleBtn) return;
            ttsToggleBtn.classList.toggle("on", !muted);
            ttsToggleBtn.classList.toggle("off", muted);
            ttsToggleBtn.title = muted ? "Voce JANIS disattivata — clicca per attivare" : "Voce JANIS attiva";
            ttsToggleBtn.textContent = muted ? "🔇" : "🔊";
        }

        async function unlockAudio() {
            if (audioUnlocked) return true;
            try {
                if (window.AudioContext) {
                    const ctx = new AudioContext();
                    if (ctx.state === "suspended") await ctx.resume();
                    await ctx.close();
                }
                const probe = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAA==");
                probe.volume = 0.01;
                await probe.play();
                audioUnlocked = true;
                ttsNeedsUnlock = false;
                logVerbose("TTS", "Audio sbloccato", "ok");
                return true;
            } catch (e) {
                logVerbose("TTS", "Sblocco audio: " + (e.message || e), "err");
                return false;
            }
        }

        async function playNextTts() {
            if (ttsPlaying || !ttsQueue.length || muted) return;
            if (!audioUnlocked) {
                const ok = await unlockAudio();
                if (!ok) {
                    ttsNeedsUnlock = true;
                    return;
                }
            }
            ttsPlaying = true;
            const raw = ttsQueue.shift();
            const text = sanitizeForTts(raw);
            if (!text) {
                ttsPlaying = false;
                if (ttsQueue.length) playNextTts();
                return;
            }
            try {
                const res = await fetch(`${wsBase()}/api/tts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text }),
                });
                if (!res.ok) {
                    const errBody = await res.text().catch(() => "");
                    throw new Error("tts " + res.status + " " + errBody.slice(0, 80));
                }
                const blob = await res.blob();
                if (!blob.size) throw new Error("audio vuoto");
                const url = URL.createObjectURL(blob);
                if (currentAudio) { currentAudio.pause(); currentAudio = null; }
                currentAudio = new Audio(url);
                currentAudio.volume = 1;
                currentAudio.playbackRate = TTS_PLAYBACK_RATE;
                setState("SPEAKING");
                if (speakingIndicator) speakingIndicator.hidden = false;
                if (stopVoiceBtn) stopVoiceBtn.hidden = false;
                currentAudio.onended = () => {
                    URL.revokeObjectURL(url);
                    currentAudio = null;
                    ttsPlaying = false;
                    if (ttsQueue.length) playNextTts();
                    else {
                        setState("IDLE");
                        if (speakingIndicator) speakingIndicator.hidden = true;
                        if (stopVoiceBtn) stopVoiceBtn.hidden = true;
                    }
                };
                await currentAudio.play();
            } catch (e) {
                const msg = e && e.message ? e.message : String(e);
                logVerbose("TTS", "Errore riproduzione: " + msg, "err");
                if (e && (e.name === "NotAllowedError" || msg.includes("play"))) {
                    ttsQueue.unshift(raw);
                    ttsNeedsUnlock = true;
                    audioUnlocked = false;
                    logVerbose("TTS", "Clicca 🔊 o Invia per sbloccare l'audio del browser", "err");
                }
                ttsPlaying = false;
                setState("IDLE");
                if (speakingIndicator) speakingIndicator.hidden = true;
                if (stopVoiceBtn) stopVoiceBtn.hidden = true;
                if (ttsQueue.length && audioUnlocked) playNextTts();
            }
        }

        function speak(text) {
            const clean = sanitizeForTts(text);
            if (!clean || muted) return;
            ttsQueue.push(clean);
            playNextTts();
        }

        function stopSpeaking() {
            ttsQueue.length = 0;
            ttsPlaying = false;
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }
            setState("IDLE");
            if (speakingIndicator) speakingIndicator.hidden = true;
            if (stopVoiceBtn) stopVoiceBtn.hidden = true;
        }
        if (stopVoiceBtn) stopVoiceBtn.addEventListener("click", stopSpeaking);

        if (ttsToggleBtn) {
            ttsToggleBtn.addEventListener("click", async () => {
                await unlockAudio();
                muted = !muted;
                try { localStorage.setItem("janis_tts_muted", muted ? "1" : "0"); } catch (_) {}
                updateTtsToggleUi();
                if (muted) stopSpeaking();
                else if (ttsNeedsUnlock || ttsQueue.length) playNextTts();
                else speak("Voce JANIS attiva.");
            });
        }
        updateTtsToggleUi();
        if (muted) logVerbose("TTS", "Voce disattivata (muted) — clicca 🔇 per riattivare", "err");

        ["click", "keydown"].forEach((ev) => {
            document.addEventListener(ev, () => {
                unlockAudio().then((ok) => {
                    if (ok && ttsNeedsUnlock && ttsQueue.length && !muted) playNextTts();
                });
            }, { passive: true, capture: true });
        });

        function getChatLogEl() {
            return document.getElementById("chat-messages");
        }

        function ensureChatStreamingLine() {
            const log = getChatLogEl();
            if (!log) return null;
            if (!chatStreamingEl) {
                chatStreamingEl = document.createElement("div");
                chatStreamingEl.className = "chat-line chat-janis chat-streaming";
                chatStreamingEl.textContent = "JANIS: ";
                log.appendChild(chatStreamingEl);
            }
            return chatStreamingEl;
        }

        function finalizeChatStream() {
            if (chatStreamingEl) {
                chatStreamingEl.classList.remove("chat-streaming");
                chatStreamingEl = null;
            }
        }

        function connect() {
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
            const url = wsUrl();
            logDock("Connessione " + url);
            ws = new WebSocket(url);

            ws.onopen = () => {
                setConn(true);
                reconnectDelay = 1000;
                logDock("Connessa!", "ok");
                fetchRuntime();
                fetchFleetStatus();
                fetch(`${wsBase()}/api/status`).then(r => r.json()).then(d => {
                    if (d.fleet) updateFleetUI(d.fleet);
                    if (d.mac_node?.online) logDock("Mac Mini online (SSH)", "ok");
                    else if (d.mac_node?.enabled) logDock("Mac Mini offline", "err");
                }).catch(() => {});
                fetch(`${wsBase()}/api/knowledge`).then(r => r.json()).then(d => {
                    if (d.user_level) targetUserLevel = d.user_level;
                    if (d.janis_level) targetJanisLevel = d.janis_level;
                }).catch(() => {});
                fetch(`${wsBase()}/api/knowledge/graph`).then(r => r.json()).then(g => {
                    if (g?.nodes?.length) neuronCore.loadGraph(g);
                }).catch(() => {});
            };

            ws.onmessage = (ev) => {
                let data;
                try { data = JSON.parse(ev.data); } catch { return; }
                switch (data.type) {
                    case "state": setState(data.state); break;
                    case "chat_chunk": {
                        const fmt = window.JanisPanel?.formatChatDisplay || ((t) => t);
                        chatBuffer += data.text || "";
                        const line = ensureChatStreamingLine();
                        if (line) {
                            line.textContent = "JANIS: " + fmt(chatBuffer);
                            const log = getChatLogEl();
                            if (log) log.scrollTop = log.scrollHeight;
                        }
                        break;
                    }
                    case "chat_end": {
                        const hadStream = !!chatStreamingEl;
                        finalizeChatStream();
                        if (chatBuffer.trim()) {
                            if (!hadStream) {
                                window.JanisPanel.appendChat(chatBuffer.trim(), "janis");
                            }
                            logVerbose("CHAT", "<<< " + chatBuffer.trim().slice(0, 200));
                            const toSpeak = (data.tts_text || "").trim() || chatBuffer.trim();
                            speak(toSpeak);
                            if (data.tts_text && data.tts_text.trim() !== chatBuffer.trim().slice(0, 420)) {
                                logVerbose("TTS", "voce: " + data.tts_text.trim().slice(0, 120), "ok");
                            }
                        }
                        chatBuffer = "";
                        break;
                    }
                    case "knowledge_update":
                        if (data.user_level) targetUserLevel = data.user_level;
                        if (data.janis_level) targetJanisLevel = data.janis_level;
                        break;
                    case "brain_node":
                        if (data.node) neuronCore.addNode(data.node, lastNodeId);
                        if (data.node?.id) lastNodeId = data.node.id;
                        break;
                    case "brain_agent":
                        if (data.action === "spawn") {
                            neuronCore.spawnAgent(data.id, data.label || data.tool);
                            activeAgents.set(data.id, data.label || data.tool);
                        } else if (data.action === "dismiss") {
                            neuronCore.dismissAgent(data.id);
                            activeAgents.delete(data.id);
                        }
                        window.JanisPages?.setActiveAgents?.(activeAgents);
                        break;
                    case "knowledge_grow":
                        fetch(`${wsBase()}/api/knowledge/graph`).then(r => r.json()).then(g => {
                            if (g?.nodes?.length) neuronCore.loadGraph(g);
                        }).catch(() => {});
                        break;
                    case "tool_start":
                        logVerbose("TOOL", "▶ " + data.tool + (data.reason ? " — " + data.reason : ""), "tool");
                        window.JanisPages?.recordToolStart?.(data.tool, data.reason);
                        break;
                    case "tool_end":
                        logVerbose("TOOL", "✓ " + data.tool + (data.result ? ": " + String(data.result).slice(0, 160) : ""), "ok");
                        window.JanisPages?.recordToolEnd?.(data.tool);
                        break;
                    case "cursor_stream":
                        window.JanisPanel.appendCursorStream?.(data.id || "cursor-main", data.chunk, data.done);
                        break;
                    case "autodev": {
                        const done = data.done;
                        const ok = data.result?.ok;
                        const cls = done ? (ok ? "ok" : (data.result || /Errore|✗/.test(data.message || "") ? "err" : "ok")) : "tool";
                        logVerbose("AUTODEV", data.message || "", cls);
                        if (done) {
                            logDock(ok ? "Auto-codice completato ✓" : (data.message || "Auto-codice terminato"), ok ? "ok" : "err");
                            const v = data.result?.validated ? "validato" : "non validato";
                            if (data.result) logVerbose("AUTODEV", `risultato: ${v}${data.result.restarted ? ", backend riavviato" : ""}`, ok ? "ok" : "err");
                        }
                        break;
                    }
                    case "analyze": {
                        const done = data.done;
                        const cls = done ? ( /Errore|✗/.test(data.message || "") ? "err" : "ok") : "tool";
                        logVerbose("ANALYZE", data.message || "", cls);
                        if (done) {
                            logDock(/Errore|✗/.test(data.message || "") ? (data.message || "Analisi terminata") : "Analisi completata ✓", cls);
                        }
                        break;
                    }
                    case "panel": window.JanisPanel.handleEvent(data); break;
                    case "error": logDock("Errore: " + data.message, "err"); break;
                    case "system":
                        logVerbose("WS", "system · brain v" + (data.brain_version || "?") + " · session " + (data.session_id || "").slice(-8));
                        if (data.ollama && !data.ollama.online) logDock("Ollama offline!", "err");
                        if (data.knowledge?.memories > 0) {
                            logDock(`Memoria: ${data.knowledge.memories} voci`, "ok");
                        }
                        if (!data.brain_version || data.brain_version < 5) {
                            logDock("Backend vecchio — premi Shift+F5 poi F5 in Cursor", "err");
                            window.JanisPanel.appendChat(
                                "Backend non aggiornato. Riavvia debug (Shift+F5, poi F5) per abilitare la memoria persistente.",
                                "janis",
                            );
                        }
                        break;
                    case "session_cleared":
                        chatBuffer = "";
                        finalizeChatStream();
                        logDock("Sessione reset", "ok");
                        break;
                }
            };

            ws.onerror = () => { setConn(false); logDock("Errore WS", "err"); };
            ws.onclose = () => {
                setConn(false);
                logDock("Riconnessione...", "err");
                setTimeout(connect, reconnectDelay);
                reconnectDelay = Math.min(reconnectDelay * 2, 12000);
            };
        }

        connect();
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
        }, 20000);
        setInterval(fetchFleetStatus, 15000);

        function submit() {
            const t = cmdInput.value.trim();
            if (!t) return;
            cmdInput.value = "";
            sendMessage(t);
        }
        sendBtn.addEventListener("click", submit);
        cmdInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.altKey) {
                e.preventDefault();
                submit();
            }
        });
        clearBtn.addEventListener("click", () => {
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "clear_session" }));
        });

        document.querySelectorAll(".mod-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const kind = btn.dataset.panel;
                if (kind === "web") {
                    setSelectedAgent("web");
                } else if (kind === "terminal") {
                    setSelectedAgent("terminal");
                } else if (kind === "cursor") {
                    setSelectedAgent("cursor");
                } else if (kind === "mac") {
                    setSelectedAgent("mac");
                } else if (kind === "whatsapp") {
                    setSelectedAgent("whatsapp");
                } else if (kind === "chat") {
                    setSelectedAgent("janis");
                    cmdInput?.focus();
                } else {
                    window.JanisPanel.open({ id: "app-" + Date.now(), panel_type: "app", title: "Modulo", width: 400, height: 280, content: "Nuovo modulo agente" });
                }
            });
        });

        const autodevBtn = document.getElementById("autodev-btn");
        if (autodevBtn) {
            autodevBtn.addEventListener("click", () => {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    logDock("Non connesso — impossibile avviare auto-codice", "err");
                    return;
                }
                setSelectedAgent("cursor");
                logVerbose("AUTODEV", "richiesta ciclo auto-codice (verifica Cursor → fix → valida → riavvia)", "tool");
                logDock("Auto-codice avviato — guarda il terminale", "ok");
                autodevBtn.classList.add("is-busy");
                ws.send(JSON.stringify({ type: "autodev_run", restart: true }));
                setTimeout(() => autodevBtn.classList.remove("is-busy"), 4000);
            });
        }

        const analyzeBtn = document.getElementById("analyze-btn");
        if (analyzeBtn) {
            analyzeBtn.addEventListener("click", () => {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    logDock("Non connesso — impossibile avviare analisi", "err");
                    return;
                }
                setSelectedAgent("janis");
                logVerbose("ANALYZE", "roadmap feature (analisi + fleet + reflect)", "tool");
                logDock("Analisi roadmap avviata", "ok");
                analyzeBtn.classList.add("is-busy");
                ws.send(JSON.stringify({ type: "analyze_run", action: "roadmap" }));
                setTimeout(() => analyzeBtn.classList.remove("is-busy"), 5000);
            });
        }

        if (agentSelect) {
            agentSelect.addEventListener("change", () => {
                setSelectedAgent(agentSelect.value);
            });
        }
        window.__janisSelectedAgent = selectedAgent;
        updateAgentUI();
        window.JanisPanel?.syncAgentCards?.(selectedAgent);

        if (paidToggle) paidToggle.addEventListener("click", togglePaidMode);
        if (reasoningQuick) {
            reasoningQuick.addEventListener("change", () => {
                patchRuntime({ reasoning_provider: reasoningQuick.value }).catch(() => logDock("Errore provider", "err"));
            });
        }
        if (cursorModelQuick) {
            cursorModelQuick.addEventListener("change", () => {
                patchRuntime({ cursor_reasoning_model: cursorModelQuick.value }).catch(() => logDock("Errore modello", "err"));
            });
        }
        fetchRuntime();

        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        let wantMicListening = false;
        let micInputMode = "auto"; // auto | webspeech | backend
        let srFailCount = 0;
        let backendListening = false;
        let levelPollTimer = null;
        let zeroLevelTicks = 0;
        let sttBackendReady = false;

        function isBadSpeechEnv() {
            const ua = navigator.userAgent || "";
            if (/Electron/i.test(ua)) return true;
            if (/Cursor/i.test(ua)) return true;
            if (location.protocol === "vscode-webview:") return true;
            if (location.hostname === "127.0.0.1" && location.port && location.port !== "8010" && location.port !== "8001") return false;
            return false;
        }

        async function refreshMicDevices() {
            if (!micSelect || !window.JanisMic?.listAudioDevices) return;
            const saved = window.JanisMic.getPreferredDeviceId?.() || "";
            let devices = [];
            try {
                devices = await window.JanisMic.listAudioDevices();
            } catch (e) {
                logVerbose("MIC", "Enumerazione dispositivi fallita: " + e.message, "err");
            }
            const opts = ['<option value="">🎤 Mic predefinito</option>'];
            devices.forEach((d) => {
                const sel = d.deviceId === saved ? " selected" : "";
                opts.push(`<option value="${d.deviceId.replace(/"/g, "&quot;")}"${sel}>${d.label.replace(/</g, "&lt;")}</option>`);
            });
            micSelect.innerHTML = opts.join("");
        }

        async function logMicBootDiagnostics() {
            const srOk = !!SR;
            const badEnv = isBadSpeechEnv();
            let devices = [];
            let perm = { ok: false };
            let sttDiag = {};
            try {
                if (window.JanisMic?.listAudioDevices) devices = await window.JanisMic.listAudioDevices();
            } catch (_) {}
            try {
                if (window.JanisMic?.checkMicPermission) perm = await window.JanisMic.checkMicPermission();
            } catch (e) {
                perm = { ok: false, error: e.message };
            }
            try {
                if (window.JanisMic?.fetchDiagnostic) sttDiag = await window.JanisMic.fetchDiagnostic();
            } catch (_) {}
            sttBackendReady = !!sttDiag.ready;
            logVerbose("MIC", `Diagnostica: SR=${srOk ? "sì" : "no"} · dispositivi=${devices.length} · permesso=${perm.ok ? "ok" : "no"} · STT backend=${sttBackendReady ? "ok" : "no"} · porta=${location.port || "80"}`, perm.ok ? "ok" : "err");
            if (badEnv) logVerbose("MIC", "Browser embedded — uso STT backend (Whisper locale), non Web Speech", "ok");
            if (!perm.ok && perm.error) logVerbose("MIC", "Permesso: " + perm.error, "err");
            if (!sttBackendReady) {
                logVerbose("MIC", "STT non disponibile su questa porta — apri http://127.0.0.1:8010 oppure riavvia backend", "err");
                if (sttDiag.install_hint) logVerbose("MIC", "STT: " + sttDiag.install_hint, "err");
            } else {
                micInputMode = "backend";
            }
            if (perm.ok && window.JanisMic?.getStreamInfo) {
                const info = window.JanisMic.getStreamInfo();
                if (info?.label) logVerbose("MIC", "Dispositivo attivo: " + info.label, "ok");
            }
            await refreshMicDevices();
            if (voiceBtn) {
                if (!SR && !sttBackendReady) {
                    voiceBtn.title = "Microfono: installa faster-whisper sul backend";
                } else {
                    voiceBtn.title = "Clicca per ascoltare (clicca di nuovo per stop/invia)";
                }
            }
        }

        function clearLevelPoll() {
            if (levelPollTimer) {
                clearInterval(levelPollTimer);
                levelPollTimer = null;
            }
            zeroLevelTicks = 0;
        }

        function startLevelPoll() {
            clearLevelPoll();
            levelPollTimer = setInterval(() => {
                const lvl = window.JanisMic?.getAudioLevel?.() ?? 0;
                logVerbose("MIC", `Livello audio: ${lvl}%`, lvl > 0 ? "ok" : "");
                if (lvl <= 0) {
                    zeroLevelTicks += 1;
                    if (zeroLevelTicks >= 6) {
                        logVerbose("MIC", "Segnale audio zero — seleziona microfono Bluetooth in Impostazioni JANIS o Windows", "err");
                        zeroLevelTicks = 0;
                    }
                } else {
                    zeroLevelTicks = 0;
                }
            }, 500);
        }

        function shouldUseBackendMode() {
            if (micInputMode === "backend") return true;
            if (micInputMode === "webspeech") return false;
            if (sttBackendReady) return true;
            if (!SR || isBadSpeechEnv()) return false;
            if (srFailCount >= 2) return false;
            return false;
        }

        let backendBlobPromise = null;

        async function startBackendListening() {
            if (!window.JanisMic?.startRecording || !sttBackendReady) {
                logVerbose("MIC", "STT backend non disponibile — pip install faster-whisper sul server", "err");
                wantMicListening = false;
                voiceBtn?.classList.remove("listening");
                setState("IDLE");
                return;
            }
            try {
                const devId = window.JanisMic.getPreferredDeviceId?.();
                await window.JanisMic.ensureStream(devId || undefined);
            } catch (e) {
                wantMicListening = false;
                logVerbose("MIC", "Permesso microfono negato: " + (e.message || e), "err");
                voiceBtn?.classList.remove("listening");
                setState("IDLE");
                return;
            }
            backendListening = true;
            isListening = true;
            voiceBtn?.classList.add("listening");
            setState("LISTENING");
            const info = window.JanisMic.getStreamInfo?.();
            if (info?.label) logVerbose("MIC", "Registro da: " + info.label, "ok");
            logVerbose("MIC", "Modalità backend — parla, poi clicca 🎙 di nuovo per inviare", "ok");
            startLevelPoll();
            try {
                backendBlobPromise = window.JanisMic.startRecording();
            } catch (e) {
                backendListening = false;
                wantMicListening = false;
                clearLevelPoll();
                logVerbose("MIC", "Registrazione fallita: " + e.message, "err");
                voiceBtn?.classList.remove("listening");
                setState("IDLE");
            }
        }

        async function stopBackendListening() {
            clearLevelPoll();
            backendListening = false;
            isListening = false;
            voiceBtn?.classList.remove("listening");
            if (!window.JanisMic?.isRecording?.()) {
                setState("IDLE");
                return;
            }
            setState("THINKING");
            logVerbose("MIC", "Trascrizione in corso…", "ok");
            try {
                window.JanisMic.stopRecording();
                const blob = await backendBlobPromise;
                backendBlobPromise = null;
                if (!blob || blob.size < 32) {
                    logVerbose("MIC", "Audio troppo breve o vuoto", "err");
                    setState("IDLE");
                    return;
                }
                const result = await window.JanisMic.transcribeBackend(blob);
                const text = (result.text || "").trim();
                if (text) {
                    if (cmdInput) cmdInput.value = text;
                    logVerbose("MIC", "Trascritto: " + text.slice(0, 120), "ok");
                    sendMessage(text);
                } else {
                    logVerbose("MIC", "Nessun testo riconosciuto — riprova parlando più forte", "err");
                }
            } catch (e) {
                logVerbose("MIC", "STT fallito: " + e.message, "err");
            }
            if (!wantMicListening) setState("IDLE");
        }

        async function startMicListening() {
            if (shouldUseBackendMode()) {
                micInputMode = "backend";
                await startBackendListening();
                return;
            }
            if (!recognition) {
                if (sttBackendReady) {
                    micInputMode = "backend";
                    await startBackendListening();
                    return;
                }
                logVerbose("MIC", "Riconoscimento vocale non supportato — usa Chrome/Edge o scrivi in chat", "err");
                window.JanisPanel?.appendChat?.(
                    "Il microfono non è supportato in questo browser. Apri JANIS in Chrome/Edge esterno, oppure scrivi in chat.",
                    "janis",
                );
                wantMicListening = false;
                return;
            }
            try {
                const devId = window.JanisMic?.getPreferredDeviceId?.();
                if (window.JanisMic?.ensureStream) {
                    await window.JanisMic.ensureStream(devId || undefined);
                }
            } catch (e) {
                wantMicListening = false;
                const msg = e.message || String(e);
                logVerbose("MIC", "Permesso microfono negato: " + msg, "err");
                window.JanisPanel?.appendChat?.(
                    "Microfono non accessibile. In Windows: Impostazioni → Privacy → Microfono → consenti al browser.",
                    "janis",
                );
                voiceBtn?.classList.remove("listening");
                setState("IDLE");
                return;
            }
            startLevelPoll();
            try {
                recognition.start();
            } catch (e) {
                if (e.name === "InvalidStateError") {
                    try { recognition.stop(); } catch (_) {}
                    setTimeout(() => {
                        try { recognition.start(); } catch (e2) {
                            logVerbose("MIC", "Avvio fallito: " + e2.message, "err");
                            srFailCount += 1;
                            maybeSwitchToBackend();
                        }
                    }, 250);
                } else {
                    logVerbose("MIC", "Avvio fallito: " + e.message, "err");
                    srFailCount += 1;
                    wantMicListening = false;
                    maybeSwitchToBackend();
                }
            }
        }

        function maybeSwitchToBackend() {
            if (!wantMicListening || !sttBackendReady) return;
            clearLevelPoll();
            try { recognition?.stop(); } catch (_) {}
            logVerbose("MIC", "Web Speech fallito — passo a STT backend locale", "ok");
            srFailCount = 3;
            micInputMode = "backend";
            startBackendListening();
        }

        function stopMicListening() {
            wantMicListening = false;
            clearLevelPoll();
            if (backendListening) {
                stopBackendListening();
                return;
            }
            if (recognition) {
                try { recognition.stop(); } catch (_) {}
            }
            isListening = false;
            voiceBtn?.classList.remove("listening");
            setState("IDLE");
        }

        if (SR) {
            recognition = new SR();
            recognition.lang = "it-IT";
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            recognition.onstart = () => {
                recognition._janisStartTs = Date.now();
                isListening = true;
                voiceBtn?.classList.add("listening");
                setState("LISTENING");
                logVerbose("MIC", "Ascolto Web Speech — parla ora", "ok");
            };

            recognition.onend = () => {
                isListening = false;
                if (backendListening) return;
                voiceBtn?.classList.remove("listening");
                if (wantMicListening && !shouldUseBackendMode()) {
                    const elapsed = Date.now() - (recognition._janisStartTs || 0);
                    if (elapsed < 1500 && wantMicListening) {
                        srFailCount += 1;
                        logVerbose("MIC", "Ascolto terminato troppo presto (" + Math.round(elapsed) + " ms)", "err");
                        if (srFailCount >= 2) {
                            maybeSwitchToBackend();
                            return;
                        }
                    }
                    logVerbose("MIC", "Riconnessione ascolto…", "ok");
                    setTimeout(() => {
                        if (wantMicListening && !shouldUseBackendMode()) startMicListening();
                    }, 350);
                } else if (!wantMicListening) {
                    clearLevelPoll();
                    setState("IDLE");
                }
            };

            recognition.onerror = (ev) => {
                const err = ev.error || "unknown";
                logVerbose("MIC", "Errore Web Speech: " + err, "err");
                if (err === "not-allowed" || err === "service-not-allowed") {
                    wantMicListening = false;
                    window.JanisPanel?.appendChat?.(
                        "Microfono bloccato dal browser. Clicca il lucchetto nella barra indirizzi e consenti il microfono.",
                        "janis",
                    );
                } else if (err === "audio-capture") {
                    srFailCount += 1;
                    if (sttBackendReady) {
                        maybeSwitchToBackend();
                    } else {
                        wantMicListening = false;
                        window.JanisPanel?.appendChat?.(
                            "Nessun microfono rilevato. Collega un mic o seleziona il dispositivo nel menu 🎤.",
                            "janis",
                        );
                    }
                } else if (err === "network") {
                    srFailCount += 1;
                    logVerbose("MIC", "Speech API richiede rete — passo a STT backend se possibile", "err");
                    maybeSwitchToBackend();
                } else if (err === "no-speech" && srFailCount < 1) {
                    /* silenzio normale */
                } else if (["aborted", "no-speech"].includes(err)) {
                    srFailCount += 1;
                }
            };

            recognition.onresult = (ev) => {
                srFailCount = 0;
                let interim = "";
                let final = "";
                for (let i = ev.resultIndex; i < ev.results.length; i++) {
                    const t = ev.results[i][0].transcript;
                    if (ev.results[i].isFinal) final += t;
                    else interim += t;
                }
                if (interim && cmdInput) cmdInput.value = interim.trim();
                if (final.trim()) {
                    if (cmdInput) cmdInput.value = final.trim();
                    logVerbose("MIC", "Sentito: " + final.trim().slice(0, 120), "ok");
                    sendMessage(final.trim());
                }
            };
        }

        if (voiceBtn) {
            voiceBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (backendListening) {
                    await stopBackendListening();
                    wantMicListening = false;
                    logVerbose("MIC", "Registrazione inviata", "ok");
                    return;
                }
                if (wantMicListening) {
                    stopMicListening();
                    logVerbose("MIC", "Ascolto disattivato", "ok");
                } else {
                    wantMicListening = true;
                    srFailCount = 0;
                    await startMicListening();
                }
            });
        }

        if (micSelect) {
            micSelect.addEventListener("change", async () => {
                const id = micSelect.value || "";
                window.JanisMic?.setPreferredDeviceId?.(id || null);
                window.JanisMic?.stop?.();
                logVerbose("MIC", id ? "Microfono selezionato" : "Microfono predefinito di sistema", "ok");
                try {
                    await window.JanisMic?.ensureStream?.(id || undefined);
                    const info = window.JanisMic?.getStreamInfo?.();
                    if (info?.label) logVerbose("MIC", "Connesso: " + info.label, "ok");
                } catch (err) {
                    logVerbose("MIC", "Cambio microfono fallito: " + err.message, "err");
                }
            });
        }

        if (navigator.mediaDevices?.addEventListener) {
            navigator.mediaDevices.addEventListener("devicechange", () => {
                refreshMicDevices().catch(() => {});
            });
        }

        logMicBootDiagnostics();

        canvas.addEventListener("click", (e) => {
            const rect = canvas.getBoundingClientRect();
            const ndcX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            const ndcY = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
            const nodeId = neuronCore.pickNode?.(ndcX, ndcY, camera);
            if (nodeId && !nodeId.startsWith("seed-")) {
                window.JanisPages?.openMemory?.(nodeId);
            }
        });

        window.addEventListener("resize", () => {
            resizeScene();
            window.JanisPanel.relayoutAllDebounced?.() || window.JanisPanel.relayoutAll();
        });

        function setInteractMode(on) {
            document.body.classList.toggle("interact-mode", !!on);
        }

        function setMuted(v) {
            muted = !!v;
        }

        function setDisplayMode(mode) {
            applyDisplayMode(mode === "browser" ? "window" : (mode || "window"));
        }

        setInteractMode(true);
        window.JanisPages?.init?.({ wsBase });
        window.JanisPanel.appendChat("Sistema JANIS online. Come posso aiutarti?", "janis");
        window.JANIS = { sendMessage, connect, setInteractMode, setMuted, setDisplayMode, resizeScene, fetchRuntime, patchRuntime };
        logDock("JANIS IDE pronta", "ok");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
