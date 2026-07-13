(function () {
    const chat = document.getElementById("widget-chat");
    const input = document.getElementById("widget-input");
    const sendBtn = document.getElementById("widget-send");
    const statusEl = document.getElementById("widget-status");
    const presenceEl = document.getElementById("widget-presence");
    const brainCanvas = document.getElementById("widget-brain");
    const hud = document.querySelector(".widget-hud");

    const base = location.origin;
    let ws = null;
    let buffer = "";
    let currentState = "IDLE";
    let ttsQueue = [];
    let ttsPlaying = false;
    let currentAudio = null;
    let audioUnlocked = false;

    let neuronCore = null;
    let renderer = null;
    let scene = null;
    let camera = null;
    let lastFrame = performance.now();

    function appendMsg(role, text) {
        const div = document.createElement("div");
        div.className = "widget-msg " + role;
        div.textContent = text;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    function setStatus(on) {
        statusEl.textContent = on ? "ONLINE" : "OFFLINE";
        statusEl.className = "widget-status " + (on ? "online" : "offline");
    }

    function setState(s) {
        currentState = s || "IDLE";
        if (hud) hud.classList.toggle("brain-speaking", currentState === "SPEAKING");
        if (neuronCore) neuronCore.update(0.016, currentState);
    }

    function sanitizeForTts(text) {
        return (text || "").replace(/\s+/g, " ").trim().slice(0, 420);
    }

    async function unlockAudio() {
        try {
            const a = new Audio();
            a.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
            await a.play();
            audioUnlocked = true;
            return true;
        } catch (_) {
            return false;
        }
    }

    async function playNextTts() {
        if (ttsPlaying || !ttsQueue.length) return;
        if (!audioUnlocked) {
            const ok = await unlockAudio();
            if (!ok) return;
        }
        ttsPlaying = true;
        const text = sanitizeForTts(ttsQueue.shift());
        if (!text) {
            ttsPlaying = false;
            if (ttsQueue.length) playNextTts();
            return;
        }
        try {
            const res = await fetch(base + "/api/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });
            if (!res.ok) throw new Error("tts " + res.status);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            if (currentAudio) currentAudio.pause();
            currentAudio = new Audio(url);
            setState("SPEAKING");
            currentAudio.onended = () => {
                URL.revokeObjectURL(url);
                currentAudio = null;
                ttsPlaying = false;
                if (ttsQueue.length) playNextTts();
                else setState("IDLE");
            };
            await currentAudio.play();
        } catch (_) {
            ttsPlaying = false;
            setState("IDLE");
            if (ttsQueue.length) playNextTts();
        }
    }

    function speak(text) {
        const clean = sanitizeForTts(text);
        if (!clean) return;
        ttsQueue.push(clean);
        playNextTts();
    }

    function initBrain() {
        if (!brainCanvas || !window.THREE || !window.JanisBrain) return;
        const THREE = window.THREE;
        renderer = new THREE.WebGLRenderer({ canvas: brainCanvas, alpha: true, antialias: true });
        renderer.setSize(64, 64, false);
        renderer.setClearColor(0x000000, 0);
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(42, 1, 0.1, 20);
        camera.position.z = 2.2;
        neuronCore = window.JanisBrain.createSecondBrain();
        scene.add(neuronCore.group);
        function tick(now) {
            const dt = Math.min(0.05, (now - lastFrame) / 1000);
            lastFrame = now;
            if (neuronCore) neuronCore.update(dt, currentState);
            renderer.render(scene, camera);
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    async function refreshPresence() {
        try {
            const r = await fetch(base + "/api/presence");
            const p = await r.json();
            if (presenceEl) {
                presenceEl.textContent = (p.device_id || "?") + " @ " + (p.surface || "?");
            }
        } catch (_) {}
    }

    function connect() {
        const url = base.replace(/^http/, "ws") + "/ws/janis?device_id=widget";
        ws = new WebSocket(url);
        ws.onopen = () => {
            setStatus(true);
            fetch(base + "/api/presence/claim", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ device_id: "widget", surface: "widget", follow_user: true }),
            }).catch(() => {});
            refreshPresence();
        };
        ws.onclose = () => {
            setStatus(false);
            setTimeout(connect, 3000);
        };
        ws.onmessage = (ev) => {
            let msg;
            try { msg = JSON.parse(ev.data); } catch { return; }
            if (msg.type === "chat_chunk" && msg.text) {
                buffer += msg.text;
                setState(msg.state || "THINKING");
            }
            if (msg.type === "chat_end") {
                if (buffer.trim()) {
                    appendMsg("assistant", buffer.trim());
                    speak(msg.tts_text || buffer.trim());
                }
                buffer = "";
            }
            if (msg.type === "state" && msg.state) {
                setState(msg.state);
            }
            if (msg.type === "error" && msg.message) {
                appendMsg("system", msg.message);
            }
        };
    }

    async function send() {
        const text = (input.value || "").trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
        await unlockAudio();
        appendMsg("user", text);
        input.value = "";
        setState("LISTENING");
        ws.send(JSON.stringify({ type: "chat_message", text }));
    }

    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    });

    initBrain();
    connect();
    setInterval(refreshPresence, 5000);
})();
