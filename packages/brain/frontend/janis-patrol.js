/**
 * JANIS Patrol — percorso verticale sui bordi schermo (overlay/screensaver).
 */
(function (global) {
    const EDGES = ["left", "right"];

    function createPatrol(options = {}) {
        const state = {
            active: false,
            edge: options.edge || "right",
            yNorm: 0.5,
            direction: 1,
            speed: options.speed || 0.08,
            bobPhase: 0,
            lowPower: false,
        };

        function setActive(on) {
            state.active = !!on;
        }

        function setLowPower(on) {
            state.lowPower = !!on;
            state.speed = on ? 0.04 : (options.speed || 0.08);
        }

        function flipEdge() {
            state.edge = state.edge === "right" ? "left" : "right";
        }

        function update(dt, characterGroup, camera) {
            if (!state.active || !characterGroup) return;

            const speed = state.speed * (state.lowPower ? 0.5 : 1);
            state.yNorm += state.direction * speed * dt;
            if (state.yNorm >= 0.92) {
                state.yNorm = 0.92;
                state.direction = -1;
            } else if (state.yNorm <= 0.08) {
                state.yNorm = 0.08;
                state.direction = 1;
            }

            state.bobPhase += dt * (state.lowPower ? 2 : 4);
            const walkBob = Math.sin(state.bobPhase) * 0.025;
            const lean = state.direction * 0.04;

            const aspect = window.innerWidth / window.innerHeight;
            const xWorld = state.edge === "right" ? 1.15 * aspect : -1.15 * aspect;
            const yWorld = (0.5 - state.yNorm) * 2.2;

            characterGroup.position.set(xWorld, yWorld + walkBob, 0);
            characterGroup.rotation.y = state.edge === "right" ? -Math.PI / 2 : Math.PI / 2;
            characterGroup.rotation.z = lean;

            if (camera) {
                camera.position.lerp(
                    { x: 0, y: 0.1, z: 3.5 },
                    state.lowPower ? 0.02 : 0.08
                );
            }
        }

        return {
            state,
            setActive,
            setLowPower,
            flipEdge,
            update,
            EDGES,
        };
    }

    global.JanisPatrol = { createPatrol };
})(window);
