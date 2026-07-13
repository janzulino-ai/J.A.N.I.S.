import Foundation

enum JaniceChatConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case error(String)
}

struct JaniceChatEvent {
    let type: String
    let text: String?
    let payload: [String: Any]
}

/// WebSocket chat verso JANIS — streaming `chat_chunk` / `chat_end` e eventi `state`, `tool_*`, `brain_*`.
@MainActor
final class JaniceChatService: ObservableObject {
    @Published private(set) var connectionState: JaniceChatConnectionState = .disconnected
    @Published private(set) var agentState = ""
    @Published private(set) var isStreaming = false

    var onEvent: ((JaniceChatEvent) -> Void)?

    private var sessionId: String
    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var reconnectTask: Task<Void, Never>?
    private var shouldStayConnected = false
    private var isSocketOpen = false

    init(sessionId: String) {
        self.sessionId = sessionId
    }

    func updateSession(_ newSessionId: String) {
        sessionId = newSessionId
    }

    func connect() {
        shouldStayConnected = true
        guard connectionState != .connecting else { return }
        reconnectTask?.cancel()
        reconnectTask = Task { await maintainConnection() }
    }

    func disconnect() {
        shouldStayConnected = false
        reconnectTask?.cancel()
        receiveTask?.cancel()
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
        isSocketOpen = false
        connectionState = .disconnected
        isStreaming = false
    }

    func sendChat(text: String) async throws {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        await ensureConnected()
        guard connectionState == .connected else {
            throw JaniceAPIError.notConfigured
        }
        let payload: [String: Any] = [
            "type": "chat",
            "text": trimmed,
            "device_id": JaniceAPIClient.deviceID,
            "identity": UserIdentityService.shared.identityPayload(),
        ]
        try await sendJSON(payload)
        isStreaming = true
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: 90_000_000_000)
            await MainActor.run { self?.isStreaming = false }
        }
    }

    // MARK: - Private

    private func maintainConnection() async {
        while shouldStayConnected && !Task.isCancelled {
            if !isSocketOpen && connectionState != .connecting {
                await openSocket()
            }
            try? await Task.sleep(nanoseconds: 3_000_000_000)
        }
    }

    private func ensureConnected() async {
        if connectionState == .connected { return }
        await openSocket()
        for _ in 0..<20 {
            if connectionState == .connected { return }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
    }

    private func openSocket() async {
        guard shouldStayConnected, !isSocketOpen else { return }
        guard let url = JaniceAPIClient.shared.chatWebSocketURL(sessionId: sessionId) else {
            connectionState = .error("Server non configurato")
            return
        }

        receiveTask?.cancel()
        socket?.cancel(with: .goingAway, reason: nil)

        connectionState = .connecting
        var request = URLRequest(url: url)
        if let token = KeychainService.loadDeviceToken(), !token.isEmpty {
            request.setValue(token, forHTTPHeaderField: "X-JANIS-Token")
        }

        let session = URLSession(configuration: .default)
        let task = session.webSocketTask(with: request)
        socket = task
        task.resume()
        connectionState = .connected
        isSocketOpen = true
        await JaniceAPIClient.shared.claimPresence()

        receiveTask = Task { [weak self] in
            await self?.receiveLoop(task)
        }
    }

    private func receiveLoop(_ task: URLSessionWebSocketTask) async {
        while !Task.isCancelled && shouldStayConnected {
            do {
                let message = try await task.receive()
                guard case .string(let text) = message else { continue }
                handleIncoming(text)
            } catch {
                isSocketOpen = false
                if shouldStayConnected {
                    connectionState = .disconnected
                }
                break
            }
        }
    }

    private func handleIncoming(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        let chunkText = (json["text"] as? String)
            ?? (json["content"] as? String)
            ?? (json["delta"] as? String)

        switch type {
        case "chat_chunk", "chat_delta", "message_chunk", "assistant_chunk":
            onEvent?(JaniceChatEvent(type: "chat_chunk", text: chunkText, payload: json))
        case "chat_end", "chat_done", "chat_complete", "done":
            isStreaming = false
            onEvent?(JaniceChatEvent(type: "chat_end", text: chunkText, payload: json))
            BrainStateController.shared.resetToIdle()
        case "state":
            if let state = json["state"] as? String ?? json["status"] as? String {
                agentState = state
            }
            onEvent?(JaniceChatEvent(type: type, text: chunkText, payload: json))
            BrainStateController.shared.handleChatEvent(JaniceChatEvent(type: type, text: chunkText, payload: json))
        case "knowledge_update", "brain_node", "brain_agent":
            onEvent?(JaniceChatEvent(type: type, text: chunkText, payload: json))
            BrainStateController.shared.handleChatEvent(JaniceChatEvent(type: type, text: chunkText, payload: json))
        default:
            if type.hasPrefix("tool_") || type.hasPrefix("brain_") || type.hasPrefix("job_") {
                onEvent?(JaniceChatEvent(type: type, text: chunkText, payload: json))
                BrainStateController.shared.handleChatEvent(JaniceChatEvent(type: type, text: chunkText, payload: json))
            }
        }
    }

    private func sendJSON(_ object: [String: Any]) async throws {
        guard let socket else { throw JaniceAPIError.notConfigured }
        let data = try JSONSerialization.data(withJSONObject: object)
        guard let text = String(data: data, encoding: .utf8) else {
            throw JaniceAPIError.emptyResponse
        }
        try await socket.send(.string(text))
    }
}

enum ChatSessionStore {
    private static let key = "janiceChatSessionId"

    static var currentSessionId: String {
        if let existing = UserDefaults.standard.string(forKey: key), !existing.isEmpty {
            return existing
        }
        let fresh = UUID().uuidString
        UserDefaults.standard.set(fresh, forKey: key)
        return fresh
    }

    static func startNewSession() -> String {
        let fresh = UUID().uuidString
        UserDefaults.standard.set(fresh, forKey: key)
        return fresh
    }
}
