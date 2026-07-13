import AVFoundation
import Foundation
import Speech

struct TranscriptionResult {
    let text: String
    let engine: TranscriptionEngine
}

enum TranscriptionEngine: String {
    case apple = "apple"
    case whisper = "whisper"
    case janice = "janice"
}

@MainActor
final class TranscriptionService: ObservableObject {
    @Published var isTranscribing = false
    @Published var progressMessage = ""

    private let locale = Locale(identifier: "it-IT")
    private let longRecordingThreshold: TimeInterval = 55

    func requestSpeechAuthorization() async -> SFSpeechRecognizerAuthorizationStatus {
        await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }
    }

    /// Trascrizione con retry, fallback e preferenza qualità (Whisper per audio lunghi).
    func transcribe(
        audioURL: URL,
        preferWhisper: Bool,
        whisperAPIKey: String?,
        allowFallback: Bool = true,
        preferJaniceServer: Bool = true
    ) async throws -> TranscriptionResult {
        isTranscribing = true
        defer {
            isTranscribing = false
            progressMessage = ""
        }

        let duration = audioDuration(for: audioURL)
        let hasWhisperKey = whisperAPIKey.map { !$0.isEmpty } ?? false
        let hasJanice = JaniceAPIClient.shared.baseURL() != nil
        let preferWhisperForLength = duration >= longRecordingThreshold && hasWhisperKey
        let useJaniceFirst = preferJaniceServer && hasJanice
        let useWhisperFirst = !useJaniceFirst && (preferWhisper || preferWhisperForLength) && hasWhisperKey

        if useJaniceFirst {
            progressMessage = "Trascrizione JANICE (server)…"
            do {
                let text = try await JaniceAPIClient.shared.transcribe(audioURL: audioURL)
                return TranscriptionResult(text: text, engine: .janice)
            } catch where allowFallback {
                progressMessage = "Server JANICE non riuscito, provo alternativa…"
            }
        }

        if useWhisperFirst, let key = whisperAPIKey {
            progressMessage = preferWhisperForLength
                ? "Audio lungo — trascrizione Whisper…"
                : "Trascrizione Whisper…"
            do {
                let text = try await transcribeWithRetryWhisper(audioURL: audioURL, apiKey: key)
                return TranscriptionResult(text: text, engine: .whisper)
            } catch where allowFallback {
                progressMessage = "Whisper non riuscito, provo Apple Speech…"
            }
        }

        progressMessage = "Trascrizione Apple Speech…"
        do {
            let text = try await transcribeWithRetryAppleSpeech(audioURL: audioURL)
            return TranscriptionResult(text: text, engine: .apple)
        } catch {
            if allowFallback, hasJanice, !useJaniceFirst {
                progressMessage = "Provo server JANICE…"
                let text = try await JaniceAPIClient.shared.transcribe(audioURL: audioURL)
                return TranscriptionResult(text: text, engine: .janice)
            }
            if allowFallback, hasWhisperKey, let key = whisperAPIKey, !useWhisperFirst {
                progressMessage = "Apple Speech non riuscito, provo Whisper…"
                let text = try await transcribeWithRetryWhisper(audioURL: audioURL, apiKey: key)
                return TranscriptionResult(text: text, engine: .whisper)
            }
            throw error
        }
    }

    private func transcribeWithRetryAppleSpeech(audioURL: URL, attempts: Int = 2) async throws -> String {
        var lastError: Error?
        for attempt in 1...attempts {
            do {
                return try await transcribeWithAppleSpeech(audioURL: audioURL)
            } catch {
                lastError = error
                if attempt < attempts {
                    progressMessage = "Nuovo tentativo Apple Speech (\(attempt + 1)/\(attempts))…"
                    try await Task.sleep(nanoseconds: 600_000_000)
                }
            }
        }
        throw lastError ?? TranscriptionError.recognizerUnavailable
    }

    private func transcribeWithRetryWhisper(audioURL: URL, apiKey: String, attempts: Int = 3) async throws -> String {
        var lastError: Error?
        for attempt in 1...attempts {
            do {
                return try await transcribeWithWhisper(audioURL: audioURL, apiKey: apiKey)
            } catch {
                lastError = error
                if attempt < attempts {
                    progressMessage = "Nuovo tentativo Whisper (\(attempt + 1)/\(attempts))…"
                    try await Task.sleep(nanoseconds: UInt64(attempt) * 800_000_000)
                }
            }
        }
        throw lastError ?? TranscriptionError.invalidResponse
    }

    private func audioDuration(for url: URL) -> TimeInterval {
        let asset = AVURLAsset(url: url)
        let seconds = CMTimeGetSeconds(asset.duration)
        guard seconds.isFinite, seconds > 0 else { return 0 }
        return seconds
    }

    private func transcribeWithAppleSpeech(audioURL: URL) async throws -> String {
        let status = await requestSpeechAuthorization()
        guard status == .authorized else {
            throw TranscriptionError.speechNotAuthorized
        }

        guard let recognizer = SFSpeechRecognizer(locale: locale), recognizer.isAvailable else {
            throw TranscriptionError.recognizerUnavailable
        }

        let request = SFSpeechURLRecognitionRequest(url: audioURL)
        request.requiresOnDeviceRecognition = recognizer.supportsOnDeviceRecognition
        request.taskHint = .dictation
        request.shouldReportPartialResults = false
        request.addsPunctuation = true

        return try await withCheckedThrowingContinuation { continuation in
            var resumed = false
            recognizer.recognitionTask(with: request) { result, error in
                if resumed { return }
                if let error {
                    resumed = true
                    continuation.resume(throwing: error)
                    return
                }
                guard let result, result.isFinal else { return }
                let text = result.bestTranscription.formattedString
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                guard !text.isEmpty else {
                    resumed = true
                    continuation.resume(throwing: TranscriptionError.emptyTranscript)
                    return
                }
                resumed = true
                continuation.resume(returning: text)
            }
        }
    }

    private func transcribeWithWhisper(audioURL: URL, apiKey: String) async throws -> String {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: URL(string: "https://api.openai.com/v1/audio/transcriptions")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let audioData = try Data(contentsOf: audioURL)
        guard !audioData.isEmpty else {
            throw TranscriptionError.emptyTranscript
        }

        var body = Data()
        func append(_ string: String) {
            body.append(Data(string.utf8))
        }

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"model\"\r\n\r\n")
        append("whisper-1\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"language\"\r\n\r\n")
        append("it\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"prompt\"\r\n\r\n")
        append("Trascrizione accurata in italiano di una nota vocale personale.\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"temperature\"\r\n\r\n")
        append("0\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"file\"; filename=\"note.m4a\"\r\n")
        append("Content-Type: audio/m4a\r\n\r\n")
        body.append(audioData)
        append("\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"response_format\"\r\n\r\n")
        append("json\r\n")

        append("--\(boundary)--\r\n")
        request.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw TranscriptionError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            throw TranscriptionError.whisperFailed(message)
        }

        struct WhisperResponse: Decodable { let text: String }
        let decoded = try JSONDecoder().decode(WhisperResponse.self, from: data)
        let text = decoded.text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            throw TranscriptionError.emptyTranscript
        }
        return text
    }
}

enum TranscriptionError: LocalizedError {
    case speechNotAuthorized
    case recognizerUnavailable
    case invalidResponse
    case emptyTranscript
    case whisperFailed(String)

    var errorDescription: String? {
        switch self {
        case .speechNotAuthorized:
            return "Permesso riconoscimento vocale negato."
        case .recognizerUnavailable:
            return "Riconoscitore italiano non disponibile su questo dispositivo."
        case .invalidResponse:
            return "Risposta non valida dal servizio di trascrizione."
        case .emptyTranscript:
            return "Trascrizione vuota — riprova parlando più vicino al microfono."
        case .whisperFailed(let message):
            return "Whisper: \(message)"
        }
    }
}
