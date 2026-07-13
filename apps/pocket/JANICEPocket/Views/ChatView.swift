import SwiftData
import SwiftUI

struct ChatView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var allMessages: [ChatMessage]

    @StateObject private var recorder = AudioRecorderService()
    @StateObject private var chatService: JaniceChatService
    @StateObject private var playback = AudioPlaybackService()
    @ObservedObject private var brain = BrainStateController.shared
    @ObservedObject private var identity = UserIdentityService.shared
    @ObservedObject private var stt = PocketTranscriptionService.shared

    @State private var composerText = ""
    @State private var sessionId: String
    @State private var statusLine = ""
    @State private var isTranscribing = false
    @State private var lastSTTEngine = ""
    @State private var needsUnlock = false
    @State private var streamingMessageId: UUID?
    @State private var scrollTarget: UUID?
    @FocusState private var composerFocused: Bool

    init() {
        let sid = ChatSessionStore.currentSessionId
        _sessionId = State(initialValue: sid)
        _chatService = StateObject(wrappedValue: JaniceChatService(sessionId: sid))
    }

    private var messages: [ChatMessage] {
        allMessages
            .filter { $0.sessionId == sessionId }
            .sorted { $0.createdAt < $1.createdAt }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                brainHeader

                if !chatService.agentState.isEmpty || !statusLine.isEmpty {
                    statusBanner
                }

                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            if messages.isEmpty {
                                emptyState
                            }
                            ForEach(messages, id: \.id) { message in
                                ChatBubble(
                                    message: message,
                                    isPlaying: playback.isPlaying && playback.currentFileName == message.audioFileName,
                                    onPlayAudio: { playAudio(message) }
                                )
                                .id(message.id)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _, _ in
                        scrollToBottom(proxy: proxy)
                    }
                    .onChange(of: messages.last?.content) { _, _ in
                        scrollToBottom(proxy: proxy)
                    }
                }

                composer
            }
            .jarvisNavTitle("Interface")
            .jarvisScreen()
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    identityBadge
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Nuova conversazione", systemImage: "plus.bubble") {
                            startNewSession()
                        }
                        Button(chatService.connectionState == .connected ? "Connesso" : "Riconnetti",
                               systemImage: "antenna.radiowaves.left.and.right") {
                            chatService.connect()
                        }
                    } label: {
                        connectionIcon
                    }
                }
            }
            .onAppear {
                wireChatEvents()
                chatService.connect()
                Task {
                    await stt.prepareModelIfNeeded()
                    if identity.requireBiometric && !identity.isVerified {
                        needsUnlock = true
                    }
                    await deliverPendingSiriMessage()
                }
            }
            .sheet(isPresented: $needsUnlock) {
                unlockSheet
            }
            .onDisappear {
                chatService.disconnect()
            }
        }
    }

    // MARK: - Subviews

    private var identityBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: identity.isVerified ? "person.crop.circle.badge.checkmark" : "person.crop.circle")
                .font(.caption)
                .foregroundStyle(identity.isVerified ? .green : JaniceColors.textSecondary)
            Text(identity.displayName)
                .font(.caption2)
                .foregroundStyle(JaniceColors.textSecondary)
        }
    }

    private var unlockSheet: some View {
        VStack(spacing: 20) {
            Image(systemName: "faceid")
                .font(.system(size: 48))
                .foregroundStyle(JaniceColors.accent)
            Text("Riconoscimento richiesto")
                .font(.headline)
            Text("JANIS deve sapere che sei \(identity.displayName).")
                .font(.subheadline)
                .foregroundStyle(JaniceColors.textSecondary)
                .multilineTextAlignment(.center)
            Button("Verifica identità") {
                Task {
                    let ok = await identity.authenticate()
                    if ok { needsUnlock = false }
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(JaniceColors.accent)
        }
        .padding(32)
        .presentationDetents([.medium])
        .eInkScreen()
    }

    private var brainHeader: some View {
        VStack(spacing: 4) {
            BrainSceneView(
                mode: brain.mode,
                nodeCount: brain.nodeCount,
                knowledgeLevel: brain.knowledgeLevel
            )
                .frame(height: 120)
            if !brain.lastEventLabel.isEmpty {
                Text(brain.lastEventLabel)
                    .font(.caption2)
                    .foregroundStyle(JaniceColors.accent.opacity(0.85))
            }
        }
        .padding(.top, 4)
        .background(JaniceColors.surface.opacity(0.5))
    }

    private var statusBanner: some View {
        HStack(spacing: 8) {
            if chatService.isStreaming || isTranscribing {
                ProgressView()
                    .controlSize(.small)
            }
            Text(statusLine.isEmpty ? (stt.progressMessage.isEmpty ? chatService.agentState : stt.progressMessage) : statusLine)
                .font(.caption)
                .foregroundStyle(JaniceColors.inkSoft)
                .lineLimit(2)
            if !lastSTTEngine.isEmpty {
                Text(lastSTTEngine)
                    .font(.caption2)
                    .foregroundStyle(JaniceColors.accent.opacity(0.7))
            }
            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(JaniceColors.surfaceRaised.opacity(0.9))
        .overlay(Rectangle().frame(height: 1).foregroundStyle(JaniceColors.hudLine), alignment: .top)
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 36))
                .foregroundStyle(JaniceColors.inkSoft.opacity(0.5))
            Text("AWAITING INPUT")
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundStyle(JaniceColors.accent)
                .tracking(1.5)
            Text("Hold mic or type to reach JANIS.")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(JaniceColors.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 48)
    }

    private var connectionIcon: some View {
        Group {
            switch chatService.connectionState {
            case .connected:
                Image(systemName: "circle.fill")
                    .foregroundStyle(.green)
                    .font(.caption2)
            case .connecting:
                Image(systemName: "circle.fill")
                    .foregroundStyle(.yellow)
                    .font(.caption2)
            default:
                Image(systemName: "circle.fill")
                    .foregroundStyle(JaniceColors.inkSoft.opacity(0.4))
                    .font(.caption2)
            }
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Messaggio…", text: $composerText, axis: .vertical)
                .lineLimit(1...5)
                .padding(10)
                .background(JaniceColors.surfaceRaised)
                .foregroundStyle(JaniceColors.textPrimary)
                .clipShape(RoundedRectangle(cornerRadius: 18))
                .focused($composerFocused)

            Button {
                Task { await sendTextMessage() }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundStyle(canSend ? JaniceColors.accent : JaniceColors.textSecondary.opacity(0.35))
            }
            .disabled(!canSend)

            micButton
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(JaniceColors.surfaceRaised.opacity(0.95))
    }

    private var canSend: Bool {
        !composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !chatService.isStreaming
            && !isTranscribing
    }

    private var micButton: some View {
        ZStack {
            Circle()
                .fill(recorder.isRecording ? JaniceColors.accent.opacity(0.35) : JaniceColors.surfaceRaised)
                .frame(width: 44, height: 44)
                .overlay(Circle().stroke(JaniceColors.accent.opacity(0.35), lineWidth: 1.5))
            Image(systemName: recorder.isRecording ? "waveform" : "mic.fill")
                .font(.system(size: 18))
                .foregroundStyle(JaniceColors.accent)
        }
        .contentShape(Circle())
        .onLongPressGesture(minimumDuration: 0.12, maximumDistance: 50, pressing: { pressing in
            if pressing {
                guard !recorder.isRecording, !isTranscribing else { return }
                Task { await beginVoiceRecording() }
            } else if recorder.isRecording {
                Task { await finishVoiceMessage() }
            }
        }, perform: {})
        .opacity(isTranscribing ? 0.45 : 1)
    }

    private func beginVoiceRecording() async {
        do {
            try await recorder.startRecording()
            statusLine = "Registrazione…"
        } catch {
            statusLine = error.localizedDescription
        }
    }

    // MARK: - Actions

    private func wireChatEvents() {
        chatService.onEvent = { event in
            handleChatEvent(event)
        }
    }

    private func handleChatEvent(_ event: JaniceChatEvent) {
        switch event.type {
        case "chat_chunk":
            guard let chunk = event.text, !chunk.isEmpty else { return }
            appendAssistantChunk(chunk)
        case "chat_end":
            finalizeStreamingMessage(extra: event.text)
            statusLine = ""
            if UserDefaults.standard.bool(forKey: "janiceSpeakResponses") {
                speakLastAssistantMessage()
            }
        case "state":
            if let state = event.payload["state"] as? String ?? event.payload["status"] as? String {
                statusLine = state
            }
        default:
            if event.type.hasPrefix("tool_") {
                let name = event.payload["name"] as? String ?? event.payload["tool"] as? String ?? event.type
                statusLine = "Tool: \(name)"
            } else if event.type.hasPrefix("brain_") {
                statusLine = event.text ?? event.type.replacingOccurrences(of: "_", with: " ")
            }
        }
    }

    private func appendAssistantChunk(_ chunk: String) {
        if let id = streamingMessageId,
           let existing = messages.first(where: { $0.id == id }) {
            existing.content += chunk
            try? modelContext.save()
            return
        }
        let msg = ChatMessage(
            sessionId: sessionId,
            role: .assistant,
            content: chunk,
            isComplete: false
        )
        modelContext.insert(msg)
        streamingMessageId = msg.id
        try? modelContext.save()
    }

    private func finalizeStreamingMessage(extra: String?) {
        if let id = streamingMessageId,
           let existing = messages.first(where: { $0.id == id }) {
            if let extra, !extra.isEmpty, !existing.content.contains(extra) {
                existing.content += extra
            }
            existing.isComplete = true
        } else if let extra, !extra.isEmpty {
            let msg = ChatMessage(sessionId: sessionId, role: .assistant, content: extra)
            modelContext.insert(msg)
        }
        streamingMessageId = nil
        try? modelContext.save()
    }

    private func sendTextMessage() async {
        let text = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        guard await identity.ensureVerifiedIfRequired() else {
            needsUnlock = true
            return
        }
        composerText = ""
        composerFocused = false
        await sendUserMessage(text: text, audioFileName: nil)
    }

    private func finishVoiceMessage() async {
        guard let tempURL = recorder.stopRecording() else { return }
        guard await identity.ensureVerifiedIfRequired() else {
            needsUnlock = true
            return
        }
        isTranscribing = true
        statusLine = "Trascrizione…"
        defer {
            isTranscribing = false
            statusLine = ""
        }

        do {
            let fileName = try AudioStorageService.persistTempRecording(from: tempURL)
            let audioURL = AudioStorageService.url(for: fileName)
            let result = try await stt.transcribe(audioURL: audioURL)
            lastSTTEngine = result.engine == .whisperKit ? "STT: WhisperKit" : "STT: JANIS"
            await sendUserMessage(text: result.text, audioFileName: fileName)
        } catch {
            statusLine = "STT: \(error.localizedDescription)"
        }
    }

    private func sendUserMessage(text: String, audioFileName: String?) async {
        guard await identity.ensureVerifiedIfRequired() else {
            needsUnlock = true
            return
        }
        let msg = ChatMessage(
            sessionId: sessionId,
            role: .user,
            content: text,
            audioFileName: audioFileName
        )
        modelContext.insert(msg)
        try? modelContext.save()

        statusLine = "Invio…"
        do {
            try await chatService.sendChat(text: text)
            statusLine = ""
        } catch {
            statusLine = error.localizedDescription
        }
    }

    private func playAudio(_ message: ChatMessage) {
        guard let fileName = message.audioFileName else { return }
        do {
            try playback.toggle(fileName: fileName)
        } catch {
            statusLine = error.localizedDescription
        }
    }

    private func startNewSession() {
        chatService.disconnect()
        sessionId = ChatSessionStore.startNewSession()
        streamingMessageId = nil
        statusLine = ""
        composerText = ""
        chatService.updateSession(sessionId)
        wireChatEvents()
        chatService.connect()
    }

    private func deliverPendingSiriMessage() async {
        let key = "janicePendingSiriMessage"
        guard let text = UserDefaults.standard.string(forKey: key)?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !text.isEmpty else { return }
        UserDefaults.standard.removeObject(forKey: key)
        guard await identity.ensureVerifiedIfRequired() else {
            needsUnlock = true
            return
        }
        await sendUserMessage(text: text, audioFileName: nil)
    }

    private func speakLastAssistantMessage() {
        guard let last = messages.last(where: { $0.role == .assistant && $0.isComplete }),
              !last.content.isEmpty else { return }
        _ = JaniceMouthService.shared.speak(text: last.content)
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        guard let last = messages.last else { return }
        withAnimation(.easeOut(duration: 0.2)) {
            proxy.scrollTo(last.id, anchor: .bottom)
        }
    }
}

// MARK: - Bubble

private struct ChatBubble: View {
    let message: ChatMessage
    let isPlaying: Bool
    let onPlayAudio: () -> Void

    private var isUser: Bool { message.role == .user }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 48) }
            VStack(alignment: isUser ? .trailing : .leading, spacing: 6) {
                Text(message.content.isEmpty && !message.isComplete ? "…" : message.content)
                    .font(.body)
                    .foregroundStyle(isUser ? JaniceColors.bg : JaniceColors.textPrimary)
                    .textSelection(.enabled)

                HStack(spacing: 8) {
                    Text(message.createdAt.formatted(date: .omitted, time: .shortened))
                        .font(.caption2)
                        .foregroundStyle(isUser ? JaniceColors.bg.opacity(0.7) : JaniceColors.textSecondary)

                    if message.audioFileName != nil {
                        Button(action: onPlayAudio) {
                            Image(systemName: isPlaying ? "stop.circle" : "play.circle")
                                .font(.caption)
                        }
                        .foregroundStyle(isUser ? JaniceColors.bg.opacity(0.85) : JaniceColors.accent)
                    }

                    if !message.isComplete {
                        ProgressView()
                            .controlSize(.mini)
                    }
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background {
                if isUser {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(JaniceColors.accent)
                        .shadow(color: JaniceColors.accent.opacity(0.35), radius: 6)
                } else {
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(JaniceColors.hudLine, lineWidth: 1)
                        .background(JaniceColors.surfaceRaised.opacity(0.8))
                }
            }
            if !isUser { Spacer(minLength: 48) }
        }
    }
}

#Preview {
    ChatView()
        .modelContainer(for: ChatMessage.self, inMemory: true)
}
