import AVFoundation
import Foundation

/// Bocca di JANIS — sintesi vocale con coda e interruzione.
@MainActor
final class JaniceMouthService: NSObject, ObservableObject {
    static let shared = JaniceMouthService()

    @Published private(set) var isSpeaking = false
    @Published private(set) var lastSpokenAt: Date?

    private let synthesizer = AVSpeechSynthesizer()
    private var pendingTexts: [String] = []

    private override init() {
        super.init()
        synthesizer.delegate = self
    }

    func speak(text: String, language: String = "it-IT", rate: Float = 0.48) -> [String: Any] {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return ["ok": false, "error": "empty_text"] }
        pendingTexts.append(trimmed)
        if !isSpeaking { speakNext(language: language, rate: rate) }
        return ["ok": true, "queued": trimmed]
    }

    func stop() -> [String: Any] {
        synthesizer.stopSpeaking(at: .immediate)
        pendingTexts.removeAll()
        isSpeaking = false
        return ["ok": true, "stopped": true]
    }

    private func speakNext(language: String, rate: Float) {
        guard !pendingTexts.isEmpty else {
            isSpeaking = false
            return
        }
        let text = pendingTexts.removeFirst()
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: language)
        utterance.rate = rate
        isSpeaking = true
        synthesizer.speak(utterance)
    }
}

extension JaniceMouthService: AVSpeechSynthesizerDelegate {
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            self.lastSpokenAt = .now
            self.speakNext(language: "it-IT", rate: 0.48)
        }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor in
            self.isSpeaking = false
        }
    }
}
