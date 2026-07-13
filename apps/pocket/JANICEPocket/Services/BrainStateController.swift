import Foundation

enum BrainAnimationMode: String, Equatable {
    case idle = "IDLE"
    case thinking = "THINKING"
    case acting = "ACTING"

    static func from(_ raw: String?) -> BrainAnimationMode {
        guard let raw else { return .idle }
        let upper = raw.uppercased()
        if upper.contains("ACT") || upper.contains("TOOL") || upper.contains("RUN") {
            return .acting
        }
        if upper.contains("THINK") || upper.contains("PLAN") || upper.contains("PROCESS") {
            return .thinking
        }
        return .idle
    }
}

/// Stato condiviso del brain 3D — aggiornato da eventi WebSocket.
@MainActor
final class BrainStateController: ObservableObject {
    static let shared = BrainStateController()

    @Published private(set) var mode: BrainAnimationMode = .idle
    @Published private(set) var nodeCount: Int = 4
    @Published private(set) var knowledgeLevel: Double = 0
    @Published private(set) var lastEventLabel = ""
    @Published private(set) var fleetJobStatus = ""

    private init() {}

    func handleChatEvent(_ event: JaniceChatEvent) {
        switch event.type {
        case "state":
            let raw = event.payload["state"] as? String ?? event.payload["status"] as? String
            mode = BrainAnimationMode.from(raw)
            lastEventLabel = raw ?? "state"
        case "knowledge_update":
            applyKnowledge(event.payload)
            lastEventLabel = "knowledge"
        case "brain_node":
            if let count = event.payload["count"] as? Int {
                nodeCount = max(3, min(count, 24))
            } else {
                nodeCount = min(nodeCount + 1, 24)
            }
            knowledgeLevel = min(knowledgeLevel + 0.08, 1.0)
            lastEventLabel = "nodo +1"
        case "brain_agent":
            mode = BrainAnimationMode.from(event.payload["status"] as? String ?? "THINKING")
            lastEventLabel = event.payload["agent"] as? String ?? "agent"
        default:
            if event.type.hasPrefix("tool_") {
                mode = .acting
                lastEventLabel = event.payload["name"] as? String ?? event.type
            } else if event.type.hasPrefix("brain_") {
                mode = BrainAnimationMode.from(event.type)
                lastEventLabel = event.type.replacingOccurrences(of: "_", with: " ")
            } else if event.type.hasPrefix("job_") {
                fleetJobStatus = event.text
                    ?? event.payload["status"] as? String
                    ?? event.payload["job_id"] as? String
                    ?? event.type
                lastEventLabel = fleetJobStatus
            }
        }
        JaniceLiveActivityService.shared.sync(from: self)
    }

    func resetToIdle() {
        if mode != .acting { mode = .idle }
        JaniceLiveActivityService.shared.sync(from: self)
    }

    private func applyKnowledge(_ payload: [String: Any]) {
        if let level = payload["level"] as? Double {
            knowledgeLevel = min(max(level, 0), 1)
        } else if let count = payload["count"] as? Int {
            knowledgeLevel = min(Double(count) / 20.0, 1.0)
            nodeCount = max(3, min(count + 3, 24))
        } else {
            knowledgeLevel = min(knowledgeLevel + 0.05, 1.0)
        }
    }
}
