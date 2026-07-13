(function () {
    const params = new URLSearchParams(location.search);
    const deviceId = (params.get("device_id") || "desktop").toLowerCase();
    const compact = params.get("compact") === "1" || deviceId.startsWith("pocket");
    const canvas = document.getElementById("brain-canvas");
    const root = document.getElementById("brain-root");
    const body = document.body;
    const base = location.origin;

    if (compact) body.classList.add("brain-compact");
    else if (deviceId === "desktop") body.classList.add("brain-desktop-orb");
    else body.classList.add("brain-desktop-orb");

    let currentState = "IDLE";
    let isActive = false;
    let neuronCore = null;
    let renderer = null;
    let scene = null;
    let camera = null;
    let lastFrame = performance.now();
    let ttsQueue = [];
    let ttsPlaying = false;
    let currentAudio = null;
    let ws = null;

    function applyMinimalChrome() {
        const s = orbSize();
        const px = s + "px";
        document.documentElement.style.width = px;
        document.documentElement.style.height = px;
        document.documentElement.style.overflow = "hidden";
        document.documentElement.style.background = "transparent";
        body.style.width = px;
        body.style.height = px;
        body.style.minWidth = "0";
        body.style.minHeight = "0";
        body.style.background = "transparent";
        root.style.width = px;
        root.style.height = px;
    }

    function orbSize() {
        if (compact) return 72;
        if (deviceId === "desktop") return 120;
        return 112;
    }

    applyMinimalChrome();

    function setState(s) {
        currentState = s || "IDLE";
        root.classList.toggle("speaking", currentState === "SPEAKING");
        if (neuronCore) neuronCore.update(0.016, currentState);
    }

    function setActive(active) {
        isActive = active;
        root.classList.toggle("active", active);
        root.classList.toggle("dormant", !active);
    }

    function sanitizeForTts(text) {
        return (text || "").replace(/\s+/g, " ").trim().slice(0, 420);
    }

    async function unlockAudio() {
        try {
            const a = new Audio();
            a.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
            await a.play();
            return true;
        } catch (_) {
            return false;
        }
    }

    async function playNextTts() {
        if (ttsPlaying || !ttsQueue.length || !isActive) return;
        await unlockAudio();
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
            if (!res.ok) throw new Error("tts");
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
        if (!isActive) return;
        const clean = sanitizeForTts(text);
        if (!clean) return;
        ttsQueue.push(clean);
        playNextTts();
    }

    function resizeRenderer() {
        if (!renderer || !canvas) return;
        const s = orbSize();
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.style.width = s + "px";
        canvas.style.height = s + "px";
        renderer.setPixelRatio(dpr);
        renderer.setSize(Math.round(s * dpr), Math.round(s * dpr), false);
    }

    function initBrain3d() {
        if (!canvas || !window.THREE || !window.JanisBrain) return;
        const THREE = window.THREE;
        renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, premultipliedAlpha: true });
        renderer.setClearColor(0x000000, 0);
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(42, 1, 0.1, 20);
        camera.position.z = 2.4;
        neuronCore = window.JanisBrain.createSecondBrain({ luminous: true, compact: compact });
        scene.add(neuronCore.group);
        resizeRenderer();
        function tick(now) {
            const dt = Math.min(0.05, (now - lastFrame) / 1000);
            lastFrame = now;
            if (neuronCore) neuronCore.update(dt, currentState);
            renderer.render(scene, camera);
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        window.addEventListener("resize", resizeRenderer);
    }

    async function refreshPresence() {
        try {
            const r = await fetch(base + "/api/presence");
            const p = await r.json();
            setActive((p.device_id || "").toLowerCase() === deviceId);
        } catch (_) {
            setActive(false);
        }
    }

    function handlePresenceMsg(msg) {
        if (msg.type !== "presence_changed") return;
        const active = (msg.device_id || "").toLowerCase() === deviceId;
        setActive(active);
        if (active && msg.speak_text) speak(msg.speak_text);
    }

    function connectWs() {
        const url = base.replace(/^http/, "ws") + "/ws/janis?device_id=" + encodeURIComponent(deviceId);
        ws = new WebSocket(url);
        ws.onopen = () => refreshPresence();
        ws.onclose = () => setTimeout(connectWs, 3000);
        ws.onmessage = (ev) => {
            let msg;
            try { msg = JSON.parse(ev.data); } catch { return; }
            handlePresenceMsg(msg);
            if (msg.type === "state" && isActive) setState(msg.state);
            if (msg.type === "chat_end" && isActive && msg.tts_text) speak(msg.tts_text);
        };
    }

    fetch(base + "/api/presence/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            device_id: deviceId,
            surface: deviceId.startsWith("pocket") ? "mobile" : "widget",
            follow_user: true,
        }),
    }).catch(() => {});

    initBrain3d();
    refreshPresence();
    setInterval(refreshPresence, 2000);
    connectWs();
})();
