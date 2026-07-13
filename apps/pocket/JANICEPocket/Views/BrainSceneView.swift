import SceneKit
import SwiftUI
import UIKit

/// Brain 3D SceneKit — IDLE calmo, THINKING pulse, ACTING particelle; nodi crescono con knowledge.
struct BrainSceneView: UIViewRepresentable {
    var mode: BrainAnimationMode = .idle
    var nodeCount: Int = 4
    var knowledgeLevel: Double = 0

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> SCNView {
        let view = SCNView()
        view.backgroundColor = .clear
        view.antialiasingMode = .multisampling4X
        view.allowsCameraControl = false
        view.autoenablesDefaultLighting = false
        view.scene = context.coordinator.buildScene()
        context.coordinator.sceneView = view
        context.coordinator.startDisplayLink()
        return view
    }

    func updateUIView(_ uiView: SCNView, context: Context) {
        context.coordinator.sync(mode: mode, nodeCount: nodeCount, knowledgeLevel: knowledgeLevel)
    }

    static func dismantleUIView(_ uiView: SCNView, coordinator: Coordinator) {
        coordinator.stopDisplayLink()
    }

    final class Coordinator: NSObject {
        weak var sceneView: SCNView?
        private var coreNode: SCNNode?
        private var orbitNode: SCNNode?
        private var satelliteNodes: [SCNNode] = []
        private var particleNode: SCNNode?
        private var displayLink: CADisplayLink?
        private var pulsePhase: CGFloat = 0
        private var currentMode: BrainAnimationMode = .idle
        private var targetNodeCount = 4
        private var knowledgeLevel: Double = 0

        func buildScene() -> SCNScene {
            let scene = SCNScene()

            let camera = SCNNode()
            camera.camera = SCNCamera()
            camera.position = SCNVector3(0, 0, 4.2)
            scene.rootNode.addChildNode(camera)

            let ambient = SCNNode()
            ambient.light = SCNLight()
            ambient.light?.type = .ambient
            ambient.light?.color = UIColor(white: 0.15, alpha: 1)
            scene.rootNode.addChildNode(ambient)

            let key = SCNNode()
            key.light = SCNLight()
            key.light?.type = .omni
            key.light?.color = JaniceColors.uiAccent.withAlphaComponent(0.9)
            key.position = SCNVector3(1.5, 2, 3)
            scene.rootNode.addChildNode(key)

            let core = SCNNode(geometry: SCNSphere(radius: 0.38))
            core.geometry?.firstMaterial?.diffuse.contents = JaniceColors.uiAccent
            core.geometry?.firstMaterial?.emission.contents = JaniceColors.uiAccent.withAlphaComponent(0.55)
            core.name = "core"
            scene.rootNode.addChildNode(core)
            coreNode = core

            let orbit = SCNNode()
            scene.rootNode.addChildNode(orbit)
            orbitNode = orbit

            rebuildSatellites(count: 4)

            let particles = SCNNode()
            let system = SCNParticleSystem()
            system.birthRate = 0
            system.particleLifeSpan = 0.8
            system.particleSize = 0.04
            system.particleColor = JaniceColors.uiAccent
            system.emissionDuration = 0
            system.spreadingAngle = 180
            system.particleVelocity = 1.2
            system.particleVelocityVariation = 0.6
            system.blendMode = .additive
            particles.addParticleSystem(system)
            scene.rootNode.addChildNode(particles)
            particleNode = particles

            return scene
        }

        func sync(mode: BrainAnimationMode, nodeCount: Int, knowledgeLevel: Double) {
            currentMode = mode
            self.knowledgeLevel = knowledgeLevel
            if nodeCount != targetNodeCount {
                targetNodeCount = nodeCount
                rebuildSatellites(count: targetNodeCount)
            }
            updateParticles()
        }

        func startDisplayLink() {
            stopDisplayLink()
            let link = CADisplayLink(target: self, selector: #selector(tick))
            link.add(to: .main, forMode: .common)
            displayLink = link
        }

        func stopDisplayLink() {
            displayLink?.invalidate()
            displayLink = nil
        }

        @objc private func tick() {
            pulsePhase += 0.04
            guard let core = coreNode, let orbit = orbitNode else { return }

            let baseScale: CGFloat = 1.0 + CGFloat(knowledgeLevel) * 0.25
            switch currentMode {
            case .idle:
                let breathe = 1.0 + 0.04 * sin(pulsePhase * 0.8)
                core.scale = SCNVector3(breathe * baseScale, breathe * baseScale, breathe * baseScale)
                orbit.eulerAngles.y += 0.003
            case .thinking:
                let pulse = 1.0 + 0.14 * sin(pulsePhase * 3.5)
                core.scale = SCNVector3(pulse * baseScale, pulse * baseScale, pulse * baseScale)
                orbit.eulerAngles.y += 0.012
            case .acting:
                let jitter = 1.0 + 0.08 * sin(pulsePhase * 6)
                core.scale = SCNVector3(jitter * baseScale, jitter * baseScale, jitter * baseScale)
                orbit.eulerAngles.y += 0.02
            }
        }

        private func rebuildSatellites(count: Int) {
            satelliteNodes.forEach { $0.removeFromParentNode() }
            satelliteNodes.removeAll()
            guard let orbit = orbitNode else { return }

            let n = max(3, count)
            for i in 0..<n {
                let angle = Float(i) / Float(n) * Float.pi * 2
                let radius: Float = 0.85 + Float(knowledgeLevel) * 0.25
                let size = CGFloat(0.07 + knowledgeLevel * 0.05)
                let node = SCNNode(geometry: SCNSphere(radius: size))
                node.geometry?.firstMaterial?.diffuse.contents = i.isMultiple(of: 2)
                    ? JaniceColors.uiGold
                    : JaniceColors.uiAccent.withAlphaComponent(0.85)
                node.position = SCNVector3(cos(angle) * radius, sin(angle * 0.6) * 0.35, sin(angle) * radius)
                orbit.addChildNode(node)
                satelliteNodes.append(node)
            }
        }

        private func updateParticles() {
            guard let particles = particleNode?.particleSystems?.first else { return }
            particles.birthRate = currentMode == .acting ? 90 : 0
        }
    }
}
