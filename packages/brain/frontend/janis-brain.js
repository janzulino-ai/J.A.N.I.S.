/**
 * JANIS Second Brain — grafo conoscenza (Obsidian-like) + agenti effimeri
 */
(function (global) {
    const COL = {
        user: new (global.THREE?.Color || function(){})() || null,
        janis: null,
        agent: null,
        edge: null,
        agentEdge: null,
    };

    function initColors(THREE, luminous) {
        COL.user = new THREE.Color(luminous ? 0x33bbff : 0x0088ff);
        COL.janis = new THREE.Color(luminous ? 0xffdd44 : 0xffcc00);
        COL.agent = new THREE.Color(0xff8844);
        COL.edge = new THREE.Color(luminous ? 0x44ccff : 0x2266aa);
        COL.agentEdge = new THREE.Color(0xffaa55);
    }

    function createSecondBrain(opts) {
        opts = opts || {};
        const luminous = !!opts.luminous;
        const compact = !!opts.compact;
        const THREE = global.THREE;
        if (!THREE) {
            return { group: { add(){} }, setLevels(){}, update(){}, loadGraph(){}, spawnAgent(){}, dismissAgent(){}, addNode(){} };
        }
        initColors(THREE, luminous);

        const group = new THREE.Group();
        const knowledgeGroup = new THREE.Group();
        const agentGroup = new THREE.Group();
        group.add(knowledgeGroup);
        group.add(agentGroup);

        let userLevel = 3, janisLevel = 3;
        let pulsePhase = 0;
        let visualState = "IDLE";
        const nodeMap = new Map();
        const agentMap = new Map();
        let edgeLines = null;
        let coreMesh = null;
        let lastNodeId = null;

        function scaleForLevels() {
            return 0.62 + Math.max(0, Math.min(1, (userLevel + janisLevel - 6) / 120)) * 0.42;
        }

        function disposeObj(obj) {
            if (!obj) return;
            obj.traverse((o) => {
                if (o.geometry) o.geometry.dispose();
                if (o.material) {
                    if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
                    else o.material.dispose();
                }
            });
        }

        function makeCore() {
            if (coreMesh) {
                knowledgeGroup.remove(coreMesh);
                disposeObj(coreMesh);
            }
            const geo = new THREE.SphereGeometry(0.08, 16, 16);
            const mat = new THREE.MeshBasicMaterial({
                color: luminous ? 0x55eeff : 0x00d4ff,
                transparent: true,
                opacity: luminous ? 1.0 : 0.85,
            });
            coreMesh = new THREE.Mesh(geo, mat);
            knowledgeGroup.add(coreMesh);
        }

        function nodeColor(source) {
            return source === "janis" ? COL.janis : COL.user;
        }

        function rebuildEdges(extraEdges) {
            if (edgeLines) {
                knowledgeGroup.remove(edgeLines);
                disposeObj(edgeLines);
                edgeLines = null;
            }
            const positions = [];
            const colors = [];
            const allEdges = extraEdges || [];

            nodeMap.forEach((n) => {
                n.links.forEach((targetId) => {
                    const t = nodeMap.get(targetId);
                    if (!t) return;
                    positions.push(n.x, n.y, n.z, t.x, t.y, t.z);
                    const c = nodeColor(n.source);
                    colors.push(c.r, c.g, c.b, c.r * 0.7, c.g * 0.7, c.b * 0.7);
                });
            });

            allEdges.forEach((e) => {
                const a = nodeMap.get(e.from);
                const b = nodeMap.get(e.to);
                if (!a || !b) return;
                positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
                colors.push(COL.edge.r, COL.edge.g, COL.edge.b, COL.edge.r, COL.edge.g, COL.edge.b);
            });

            if (positions.length < 6) return;
            const geo = new THREE.BufferGeometry();
            geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
            geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
            edgeLines = new THREE.LineSegments(
                geo,
                new THREE.LineBasicMaterial({
                    vertexColors: true,
                    transparent: true,
                    opacity: luminous ? 0.92 : 0.55,
                    depthWrite: false,
                }),
            );
            knowledgeGroup.add(edgeLines);
        }

        function addNodeMesh(node, animateIn) {
            if (nodeMap.has(node.id)) return;
            const col = nodeColor(node.source);
            const r = (compact ? 0.018 : 0.025) + (node.size || 1) * (compact ? 0.009 : 0.012);
            const geo = new THREE.SphereGeometry(r, 8, 8);
            const mat = new THREE.MeshBasicMaterial({
                color: col,
                transparent: true,
                opacity: animateIn ? 0 : (luminous ? 1.0 : 0.9),
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(node.x, node.y, node.z);
            knowledgeGroup.add(mesh);

            const entry = {
                id: node.id,
                source: node.source,
                x: node.x,
                y: node.y,
                z: node.z,
                mesh,
                mat,
                links: new Set(),
                born: animateIn ? 0 : 1,
            };
            nodeMap.set(node.id, entry);
            if (animateIn && lastNodeId && nodeMap.has(lastNodeId)) {
                entry.links.add(lastNodeId);
                nodeMap.get(lastNodeId).links.add(node.id);
            }
            lastNodeId = node.id;
            rebuildEdges();
        }

        function loadGraph(data) {
            knowledgeGroup.children.slice().forEach((c) => {
                if (c !== coreMesh) {
                    knowledgeGroup.remove(c);
                    disposeObj(c);
                }
            });
            nodeMap.clear();
            edgeLines = null;
            lastNodeId = null;
            makeCore();

            const nodes = data?.nodes || [];
            const edges = data?.edges || [];
            nodes.forEach((n) => addNodeMesh(n, false));
            edges.forEach((e) => {
                const a = nodeMap.get(e.from);
                const b = nodeMap.get(e.to);
                if (a && b) {
                    a.links.add(e.to);
                    b.links.add(e.from);
                }
            });
            if (nodes.length) lastNodeId = nodes[nodes.length - 1].id;
            rebuildEdges();
        }

        function addNode(node, connectTo) {
            if (!node) return;
            if (connectTo && nodeMap.has(connectTo)) {
                lastNodeId = connectTo;
            }
            addNodeMesh(node, true);
        }

        function agentOrbitPos(id, t) {
            const h = id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
            const ang = t * 1.8 + h * 0.17;
            const r = 0.82 + (h % 7) * 0.025;
            return new THREE.Vector3(Math.cos(ang) * r, Math.sin(ang * 0.7) * 0.35, Math.sin(ang) * r);
        }

        function spawnAgent(id, label) {
            if (agentMap.has(id)) return;
            const geo = new THREE.OctahedronGeometry(0.06, 0);
            const mat = new THREE.MeshBasicMaterial({
                color: COL.agent,
                transparent: true,
                opacity: 0.95,
                wireframe: true,
            });
            const mesh = new THREE.Mesh(geo, mat);
            agentGroup.add(mesh);

            const lineGeo = new THREE.BufferGeometry();
            const lineMat = new THREE.LineBasicMaterial({
                color: COL.agentEdge,
                transparent: true,
                opacity: 0.7,
            });
            const line = new THREE.Line(lineGeo, lineMat);
            agentGroup.add(line);

            agentMap.set(id, {
                id,
                label: label || id,
                mesh,
                mat,
                line,
                lineGeo,
                life: 0,
                pulse: 0,
            });
        }

        function dismissAgent(id) {
            const a = agentMap.get(id);
            if (!a) return;
            a.dying = true;
        }

        function setLevels(u, j) {
            if (u !== undefined) userLevel = Math.max(3, Math.min(100, u));
            if (j !== undefined) janisLevel = Math.max(3, Math.min(100, j));
        }

        function update(dt, state) {
            visualState = state || visualState;
            pulsePhase += dt;
            const scale = scaleForLevels();
            const breathe = 1 + Math.sin(pulsePhase * 1.1) * 0.035;
            let extra = visualState === "SPEAKING" ? 0.06 : visualState === "THINKING" ? 0.05 : visualState === "ACTING" ? 0.04 : 0;
            group.scale.setScalar(scale * (breathe + extra));
            group.rotation.y += dt * 0.18;

            if (coreMesh) {
                const cm = coreMesh.material;
                cm.opacity = luminous
                    ? 0.92 + Math.sin(pulsePhase * 2.5) * 0.08
                    : 0.7 + Math.sin(pulsePhase * 2.5) * 0.2;
                coreMesh.scale.setScalar(1 + Math.sin(pulsePhase * 1.8) * (luminous ? 0.22 : 0.15));
            }

            nodeMap.forEach((n) => {
                if (n.born < 1) {
                    n.born = Math.min(1, n.born + dt * 2);
                    n.mat.opacity = n.born * (luminous ? 1.0 : 0.9);
                    n.mesh.scale.setScalar(0.3 + n.born * 0.7);
                }
                n.mesh.position.y = n.y + Math.sin(pulsePhase * 2 + n.x * 3) * 0.008;
            });

            if (edgeLines) {
                edgeLines.material.opacity = luminous
                    ? 0.75 + Math.sin(pulsePhase) * 0.2
                    : 0.45 + Math.sin(pulsePhase) * 0.12;
            }

            const toRemove = [];
            agentMap.forEach((a, id) => {
                a.life += dt;
                a.pulse += dt * 4;
                const pos = agentOrbitPos(id, a.life);
                a.mesh.position.copy(pos);
                a.mesh.rotation.x += dt * 2;
                a.mesh.rotation.y += dt * 3;
                const pulse = 1 + Math.sin(a.pulse) * 0.35;
                a.mesh.scale.setScalar(pulse);

                const core = new THREE.Vector3(0, 0, 0);
                a.lineGeo.setAttribute(
                    "position",
                    new THREE.Float32BufferAttribute(
                        [core.x, core.y, core.z, pos.x, pos.y, pos.z], 3,
                    ),
                );
                a.lineGeo.attributes.position.needsUpdate = true;
                a.lineMat.opacity = 0.5 + Math.sin(a.pulse * 2) * 0.35;

                if (a.dying) {
                    a.mat.opacity = Math.max(0, a.mat.opacity - dt * 1.2);
                    a.lineMat.opacity = Math.max(0, a.lineMat.opacity - dt * 1.2);
                    if (a.mat.opacity <= 0) toRemove.push(id);
                }
            });
            toRemove.forEach((id) => {
                const a = agentMap.get(id);
                if (a) {
                    agentGroup.remove(a.mesh);
                    agentGroup.remove(a.line);
                    disposeObj(a.mesh);
                    disposeObj(a.line);
                    agentMap.delete(id);
                }
            });
        }

        makeCore();
        // nodi seed iniziali se grafo vuoto
        [
            { id: "seed-user", source: "user", x: -0.35, y: 0.2, z: 0.15, size: 1 },
            { id: "seed-janis", source: "janis", x: 0.35, y: -0.15, z: 0.1, size: 1 },
        ].forEach((n) => addNodeMesh(n, false));
        nodeMap.get("seed-user").links.add("seed-janis");
        nodeMap.get("seed-janis").links.add("seed-user");
        rebuildEdges();

        return {
            group,
            setLevels,
            update,
            loadGraph,
            addNode,
            spawnAgent,
            dismissAgent,
            getScale: scaleForLevels,
            getNodeCount: () => nodeMap.size,
            getAgentCount: () => agentMap.size,
            pickNode: (ndcX, ndcY, camera) => {
                if (!global.THREE) return null;
                const raycaster = new THREE.Raycaster();
                const mouse = new THREE.Vector2(ndcX, ndcY);
                raycaster.setFromCamera(mouse, camera);
                const meshes = [];
                nodeMap.forEach((n) => { if (n.mesh) meshes.push(n.mesh); });
                const hits = raycaster.intersectObjects(meshes, false);
                if (!hits.length) return null;
                const hit = hits[0].object;
                for (const [id, n] of nodeMap) {
                    if (n.mesh === hit) {
                        nodeMap.forEach((x) => {
                            if (x.mat) { x.mat.opacity = 0.9; x.mesh.scale.setScalar(1); }
                        });
                        n.mat.opacity = 1;
                        n.mesh.scale.setScalar(1.4);
                        if (typeof pickCallback === "function") pickCallback(id);
                        return id;
                    }
                }
                return null;
            },
            setOnNodeSelect: (fn) => { pickCallback = fn; },
        };
    }

    let pickCallback = null;

    global.JanisBrain = { createSecondBrain };
    global.JanisNeurons = { createNeuronCore: createSecondBrain };
})(window);
