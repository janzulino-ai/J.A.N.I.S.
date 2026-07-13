/**
 * JANIS Mic — getUserMedia, VU meter, MediaRecorder + backend STT fallback.
 */
(function (global) {
    const DEVICE_KEY = "janis.mic.deviceId";

    let mediaStream = null;
    let muted = false;
    let audioContext = null;
    let analyser = null;
    let analyserSource = null;
    let activeRecorder = null;

    function getPreferredDeviceId() {
        try {
            return localStorage.getItem(DEVICE_KEY) || undefined;
        } catch (_) {
            return undefined;
        }
    }

    function setPreferredDeviceId(id) {
        try {
            if (id) localStorage.setItem(DEVICE_KEY, id);
            else localStorage.removeItem(DEVICE_KEY);
        } catch (_) {}
    }

    function _currentDeviceId() {
        const track = mediaStream?.getAudioTracks?.()[0];
        return track?.getSettings?.().deviceId || null;
    }

    function setupAnalyser(stream) {
        try {
            const Ctx = global.AudioContext || global.webkitAudioContext;
            if (!Ctx) return;
            if (!audioContext) audioContext = new Ctx();
            if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
            if (analyserSource) {
                try { analyserSource.disconnect(); } catch (_) {}
            }
            analyserSource = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.65;
            analyserSource.connect(analyser);
        } catch (_) {
            analyser = null;
        }
    }

    async function ensureStream(deviceId) {
        const wantId = deviceId !== undefined ? deviceId : getPreferredDeviceId();
        if (mediaStream) {
            const cur = _currentDeviceId();
            if (!wantId || cur === wantId) {
                setupAnalyser(mediaStream);
                return mediaStream;
            }
            stop();
        }
        if (!navigator.mediaDevices?.getUserMedia) {
            throw new Error("getUserMedia non disponibile");
        }
        // Bluetooth: ideal (non exact) + processing off spesso evita segnale zero
        const audio = {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            channelCount: { ideal: 1 },
        };
        if (wantId) audio.deviceId = { ideal: wantId };

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio, video: false });
        } catch (e) {
            if (wantId) {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false,
                    },
                    video: false,
                });
            } else {
                throw e;
            }
        }
        setupAnalyser(mediaStream);
        _logTrackInfo(mediaStream);
        if (muted) setMuted(true);
        return mediaStream;
    }

    async function listAudioDevices() {
        if (!navigator.mediaDevices?.enumerateDevices) return [];
        try {
            await ensureStream(getPreferredDeviceId());
        } catch (_) {}
        const all = await navigator.mediaDevices.enumerateDevices();
        return all
            .filter((d) => d.kind === "audioinput")
            .map((d, i) => ({
                deviceId: d.deviceId,
                label: d.label || `Microfono ${i + 1}`,
                groupId: d.groupId,
            }));
    }

    function _logTrackInfo(stream) {
        const track = stream?.getAudioTracks?.()[0];
        if (!track) return null;
        const s = track.getSettings?.() || {};
        return {
            label: track.label,
            deviceId: s.deviceId,
            sampleRate: s.sampleRate,
            channelCount: s.channelCount,
            muted: track.muted,
            enabled: track.enabled,
            readyState: track.readyState,
        };
    }

    function getStreamInfo() {
        if (!mediaStream) return null;
        return _logTrackInfo(mediaStream);
    }

    function getAudioLevel() {
        if (!analyser) return 0;
        const buf = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (let i = 0; i < buf.length; i++) {
            const v = Math.abs(buf[i] - 128);
            if (v > peak) peak = v;
        }
        return Math.min(100, Math.round((peak / 128) * 100));
    }

    function _pickMimeType() {
        const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
        for (const m of candidates) {
            if (global.MediaRecorder?.isTypeSupported?.(m)) return m;
        }
        return "";
    }

    async function startRecording() {
        if (activeRecorder && activeRecorder.state === "recording") {
            throw new Error("Registrazione già attiva");
        }
        const stream = await ensureStream(getPreferredDeviceId());
        const mimeType = _pickMimeType();
        const opts = mimeType ? { mimeType } : undefined;
        const rec = new MediaRecorder(stream, opts);
        const chunks = [];
        activeRecorder = rec;

        const blobPromise = new Promise((resolve, reject) => {
            rec.ondataavailable = (ev) => {
                if (ev.data && ev.data.size > 0) chunks.push(ev.data);
            };
            rec.onstop = () => {
                activeRecorder = null;
                const type = mimeType ? mimeType.split(";")[0] : "audio/webm";
                resolve(new Blob(chunks, { type }));
            };
            rec.onerror = (ev) => {
                activeRecorder = null;
                reject(ev.error || new Error("MediaRecorder error"));
            };
            rec.start(250);
        });
        return blobPromise;
    }

    function stopRecording() {
        if (activeRecorder && activeRecorder.state === "recording") {
            activeRecorder.stop();
            return true;
        }
        return false;
    }

    function isRecording() {
        return !!(activeRecorder && activeRecorder.state === "recording");
    }

    async function recordBlob(maxSeconds) {
        const blobPromise = startRecording();
        if (maxSeconds > 0) {
            setTimeout(() => stopRecording(), maxSeconds * 1000);
        }
        return blobPromise;
    }

    async function transcribeBackend(blob) {
        const fd = new FormData();
        fd.append("file", blob, "audio.webm");
        fd.append("language", "it");
        const res = await fetch(`${location.origin}/api/stt`, { method: "POST", body: fd });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = { detail: res.statusText };
        }
        if (!res.ok) {
            const detail = data.detail;
            const msg = typeof detail === "object"
                ? (detail.error || detail.install || JSON.stringify(detail))
                : (detail || res.statusText);
            throw new Error(msg);
        }
        return data;
    }

    async function fetchDiagnostic() {
        try {
            const res = await fetch(`${location.origin}/api/stt/diagnostic`, { method: "GET" });
            if (!res.ok) {
                return { ready: false, error: `HTTP ${res.status}`, install_hint: "Riavvia backend JANIS (STT non caricato)" };
            }
            return await res.json();
        } catch (e) {
            return { ready: false, error: e.message, install_hint: "Backend offline o porta sbagliata — prova :8010" };
        }
    }

    async function checkMicPermission() {
        try {
            await ensureStream();
            return { ok: true, source: "webrtc", level: getAudioLevel() };
        } catch (e) {
            await reportGap(`Microfono non accessibile: ${e.message}`);
            return { ok: false, error: e.message };
        }
    }

    async function reportGap(message) {
        try {
            await fetch(`${location.origin}/api/gaps`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    description: message,
                    tool: "microphone",
                    severity: "medium",
                    proposed_fix: "Verificare permessi microfono Windows e dispositivo predefinito",
                }),
            });
        } catch (_) {}
    }

    function setMuted(value) {
        muted = !!value;
        if (mediaStream) {
            mediaStream.getAudioTracks().forEach((t) => {
                t.enabled = !muted;
            });
        }
    }

    function stop() {
        stopRecording();
        if (mediaStream) {
            mediaStream.getTracks().forEach((t) => t.stop());
            mediaStream = null;
        }
        if (analyserSource) {
            try { analyserSource.disconnect(); } catch (_) {}
            analyserSource = null;
        }
        analyser = null;
    }

    global.JanisMic = {
        ensureStream,
        listAudioDevices,
        getPreferredDeviceId,
        setPreferredDeviceId,
        getAudioLevel,
        getStreamInfo,
        startRecording,
        stopRecording,
        isRecording,
        recordBlob,
        transcribeBackend,
        fetchDiagnostic,
        checkMicPermission,
        reportGap,
        setMuted,
        stop,
        isMuted: () => muted,
    };
})(window);
