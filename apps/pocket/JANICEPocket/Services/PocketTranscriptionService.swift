import Foundation

#if canImport(WhisperKit)
import WhisperKit
#endif

enum PocketSTTEngine: String {
    case whisperKit = "whisperkit"
    case janis = "janis"
    case unavailable = "unavailable"
}

struct PocketSTTResult {
    let text: String
    let engine: PocketSTTEngine
}

/// Orecchie di JANIS — STT on-device WhisperKit con fallback server.
@MainActor
final class PocketTranscriptionService: ObservableObject {
    static let shared = PocketTranscriptionService()

    @Published private(set) var isLoadingModel = false
    @Published private(set) var modelReady = false
    @Published private(set) var progressMessage = ""
    @Published private(set) var lastEngine: PocketSTTEngine = .unavailable

#if canImport(WhisperKit)
    private var whisperPipeline: WhisperKit?
#endif

    var preferOnDevice: Bool {
        UserDefaults.standard.object(forKey: "janicePreferOnDeviceSTT") as? Bool ?? true
    }

    private init() {}

    func setPreferOnDevice(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: "janicePreferOnDeviceSTT")
    }

    func prepareModelIfNeeded() async {
#if canImport(WhisperKit)
        guard preferOnDevice, whisperPipeline == nil else { return }
        isLoadingModel = true
        progressMessage = "Caricamento modello Whisper…"
        defer {
            isLoadingModel = false
            if progressMessage.hasPrefix("Caricamento") { progressMessage = "" }
        }
        do {
            let config = WhisperKitConfig(model: "openai_whisper-base")
            whisperPipeline = try await WhisperKit(config)
            modelReady = true
        } catch {
            modelReady = false
            progressMessage = "WhisperKit: \(error.localizedDescription)"
        }
#else
        modelReady = false
#endif
    }

    func transcribe(audioURL: URL) async throws -> PocketSTTResult {
#if canImport(WhisperKit)
        if preferOnDevice {
            if whisperPipeline == nil {
                await prepareModelIfNeeded()
            }
            if let pipe = whisperPipeline {
                progressMessage = "Trascrizione on-device…"
                defer { progressMessage = "" }
                let options = DecodingOptions(language: "it")
                let results = try await pipe.transcribe(audioPath: audioURL.path, decodeOptions: options)
                let text = results
                    .map(\.text)
                    .joined(separator: " ")
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                if !text.isEmpty {
                    lastEngine = .whisperKit
                    return PocketSTTResult(text: text, engine: .whisperKit)
                }
            }
        }
#endif
        progressMessage = "Trascrizione server JANIS…"
        defer { progressMessage = "" }
        let text = try await JaniceAPIClient.shared.transcribe(audioURL: audioURL)
        lastEngine = .janis
        return PocketSTTResult(text: text, engine: .janis)
    }
}
