/**
 * JANIS Neuron Core — sfera energetica filamenti blu/giallo
 */
(function (global) {
    function createNeuronCore() {
        const THREE = global.THREE;
        if (!THREE) {
            console.error("THREE.js non caricato");
            return { group: new (global.Group || function(){})(), setLevels(){}, update(){}, getScale: () => 1 };
        }

        const BLUE = new THREE.Color(0x0088ff);
        const YELLOW = new THREE.Color(0xffcc00);

        function lerpColor(t, a, b) {
            return a.clone().lerp(b, t);
        }

        function colorAt(x) {
            const t = Math.max(0, Math.min(1, (x / 0.35 + 1) * 0.5));
            if (t < 0.35) return BLUE.clone();
            if (t > 0.65) return YELLOW.clone();
            return lerpColor((t - 0.35) / 0.3, BLUE, YELLOW);
        }

        function rand(seed) {
            const x = Math.sin(seed * 127.1 + seed * 311.7) * 43758.5453;
            return x - Math.floor(x);
        }

        function onSphere(r, u, v) {
            const theta = u * Math.PI * 2;
            const phi = Math.acos(2 * v - 1);
            return new THREE.Vector3(
                r * Math.sin(phi) * Math.cos(theta),
                r * Math.sin(phi) * Math.sin(theta),
                r * Math.cos(phi),
            );
        }

        function jaggedPath(a, b, segments, seed, chaos) {
            const pts = [a.clone()];
            for (let i = 1; i < segments; i++) {
                const t = i / segments;
                const p = a.clone().lerp(b, t);
                const wobble = chaos * (1 - Math.abs(t - 0.5) * 1.2);
                p.x += (rand(seed + i * 17.3) - 0.5) * wobble;
                p.y += (rand(seed + i * 41.9) - 0.5) * wobble;
                p.z += (rand(seed + i * 73.1) - 0.5) * wobble;
                pts.push(p);
            }
            pts.push(b.clone());
            return pts;
        }

        function pushLineStrip(positions, colors, pts) {
            for (let i = 0; i < pts.length - 1; i++) {
                const p0 = pts[i];
                const p1 = pts[i + 1];
                const c0 = colorAt(p0.x);
                const c1 = colorAt(p1.x);
                positions.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
                colors.push(c0.r, c0.g, c0.b, c1.r, c1.g, c1.b);
            }
        }

        const group = new THREE.Group();
        const inner = new THREE.Group();
        group.add(inner);

        let userLevel = 3;
        let janisLevel = 3;
        let builtKey = "";
        let strandLines = null;
        let ringLines = null;
        let pulsePhase = 0;

        function radiusForLevels(u, j) {
            return 0.48 + Math.max(0, Math.min(1, (u + j - 6) / 120)) * 0.38;
        }

        function strandCount(u, j) {
            return Math.min(160, Math.max(48, Math.round(40 + (u + j))));
        }

        function disposeChildren() {
            inner.traverse((obj) => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
                    else obj.material.dispose();
                }
            });
            inner.clear();
        }

        function rebuild(force = false) {
            const key = `${Math.round(userLevel)}|${Math.round(janisLevel)}`;
            if (!force && key === builtKey) return;
            builtKey = key;
            disposeChildren();

            const R = radiusForLevels(userLevel, janisLevel);
            const nStrands = strandCount(userLevel, janisLevel);
            const positions = [];
            const colors = [];

            for (let i = 0; i < nStrands; i++) {
                const a = onSphere(R * (0.7 + rand(i) * 0.3), rand(i * 3.1), rand(i * 7.3));
                const b = onSphere(R * (0.7 + rand(i + 50) * 0.3), rand(i * 11.7), rand(i * 19.1));
                pushLineStrip(positions, colors, jaggedPath(a, b, 10, i * 3.1, 0.2));
            }

            for (let i = 0; i < nStrands * 0.6; i++) {
                const mid = onSphere(R * rand(i + 80) * 0.4, rand(i), rand(i + 1));
                const outer = onSphere(R, rand(i + 2), rand(i + 3));
                pushLineStrip(positions, colors, jaggedPath(outer, mid, 8, i * 1.7, 0.15));
            }

            const geo = new THREE.BufferGeometry();
            geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
            geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
            strandLines = new THREE.LineSegments(
                geo,
                new THREE.LineBasicMaterial({
                    vertexColors: true,
                    transparent: true,
                    opacity: 1,
                    blending: THREE.NormalBlending,
                    depthWrite: false,
                    linewidth: 2,
                }),
            );
            inner.add(strandLines);

            // Anello
            const ringPos = [];
            const ringCol = [];
            for (let i = 0; i <= 64; i++) {
                const ang = (i / 64) * Math.PI * 2;
                const p0 = new THREE.Vector3(Math.cos(ang) * R * 1.1, 0, Math.sin(ang) * R * 1.1);
                const ang2 = ((i + 1) / 64) * Math.PI * 2;
                const p1 = new THREE.Vector3(Math.cos(ang2) * R * 1.1, 0, Math.sin(ang2) * R * 1.1);
                const c = colorAt(p0.x);
                ringPos.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
                ringCol.push(c.r, c.g, c.b, c.r, c.g, c.b);
            }
            const ringGeo = new THREE.BufferGeometry();
            ringGeo.setAttribute("position", new THREE.Float32BufferAttribute(ringPos, 3));
            ringGeo.setAttribute("color", new THREE.Float32BufferAttribute(ringCol, 3));
            ringLines = new THREE.LineSegments(
                ringGeo,
                new THREE.LineBasicMaterial({
                    vertexColors: true,
                    transparent: true,
                    opacity: 0.9,
                    blending: THREE.NormalBlending,
                    depthWrite: false,
                }),
            );
            inner.add(ringLines);
        }

        function setLevels(u, j) {
            if (u !== undefined) userLevel = Math.max(3, Math.min(100, u));
            if (j !== undefined) janisLevel = Math.max(3, Math.min(100, j));
            rebuild();
        }

        function update(dt, visualState = "IDLE") {
            pulsePhase += dt;
            const breathe = 1 + Math.sin(pulsePhase * 1.2) * 0.04;
            let extra = visualState === "SPEAKING" ? 0.08 : visualState === "THINKING" ? 0.05 : 0;
            inner.scale.setScalar(breathe + extra);
            inner.rotation.y += dt * 0.25;
            inner.rotation.x = Math.sin(pulsePhase * 0.35) * 0.1;
            if (strandLines) strandLines.material.opacity = 0.85 + Math.sin(pulsePhase * 2) * 0.1;
        }

        rebuild(true);
        return { group, setLevels, update, getScale: () => radiusForLevels(userLevel, janisLevel) };
    }

    global.JanisNeurons = { createNeuronCore };
})(window);
