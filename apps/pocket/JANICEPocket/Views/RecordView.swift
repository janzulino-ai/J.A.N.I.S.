import SwiftData
import SwiftUI

struct RecordView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var recorder = AudioRecorderService()
    @StateObject private var transcription = TranscriptionService()
    @AppStorage("useWhisperTranscription") private var useWhisper = false
    @AppStorage("useJaniceServerSTT") private var useJaniceServer = true
    @AppStorage("transcriptionAllowFallback") private var allowFallback = true

    @State private var statusMessage = "Tocca per registrare una nota vocale."
    @State private var lastTranscript = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 28) {
                Spacer()

                Text(formattedElapsed)
                    .font(.system(size: 44, weight: .light, design: .monospaced))
                    .foregroundStyle(JaniceColors.ink)

                Button {
                    Task { await toggleRecording() }
                } label: {
                    ZStack {
                        Circle()
                            .fill(recorder.isRecording ? JaniceColors.inkSoft : JaniceColors.paperDeep)
                            .frame(width: 120, height: 120)
                            .overlay(
                                Circle()
                                    .stroke(JaniceColors.ink.opacity(0.2), lineWidth: 2)
                            )
                        Image(systemName: recorder.isRecording ? "stop.fill" : "mic.fill")
                            .font(.system(size: 36))
                            .foregroundStyle(JaniceColors.ink)
                    }
                }
                .disabled(transcription.isTranscribing)

                if transcription.isTranscribing {
                    ProgressView(transcription.progressMessage)
                        .foregroundStyle(JaniceColors.inkSoft)
                } else {
                    Text(statusMessage)
                        .font(.body)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(JaniceColors.inkSoft)
                        .padding(.horizontal)
                }

                if !lastTranscript.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Ultima trascrizione")
                            .font(.caption)
                            .foregroundStyle(JaniceColors.inkSoft)
                        Text(lastTranscript)
                            .font(.body)
                            .foregroundStyle(JaniceColors.ink)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(JaniceColors.paperDeep.opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal)
                }

                Spacer()
            }
            .navigationTitle("Registra")
            .eInkScreen()
        }
    }

    private var formattedElapsed: String {
        let total = Int(recorder.elapsed)
        return String(format: "%02d:%02d", total / 60, total % 60)
    }

    private func toggleRecording() async {
        if recorder.isRecording {
            guard let url = recorder.stopRecording() else { return }
            statusMessage = "Salvataggio audio…"
            do {
                let fileName = try AudioStorageService.persistTempRecording(from: url)
                let audioURL = AudioStorageService.url(for: fileName)

                var entry = JournalEntry(
                    type: .voice,
                    title: "Nota vocale",
                    transcript: "",
                    audioFileName: fileName,
                    transcriptionPending: true
                )
                modelContext.insert(entry)
                try modelContext.save()

                statusMessage = "Trascrizione in corso…"
                do {
                    let result = try await transcription.transcribe(
                        audioURL: audioURL,
                        preferWhisper: useWhisper,
                        whisperAPIKey: KeychainService.loadWhisperAPIKey(),
                        allowFallback: allowFallback,
                        preferJaniceServer: useJaniceServer
                    )
                    entry.transcript = result.text
                    entry.title = String(result.text.prefix(80))
                    entry.transcriptionEngine = result.engine.rawValue
                    entry.transcriptionPending = false
                    try modelContext.save()
                    lastTranscript = result.text
                    let engineLabel: String = {
                        switch result.engine {
                        case .janice: return "JANICE"
                        case .whisper: return "Whisper"
                        case .apple: return "Apple Speech"
                        }
                    }()
                    statusMessage = "Nota salvata (\(engineLabel))."
                } catch {
                    entry.transcript = ""
                    entry.transcriptionPending = true
                    try? modelContext.save()
                    statusMessage = "Audio salvato. Trascrizione fallita — ritenta dall'archivio.\n\(error.localizedDescription)"
                }
            } catch {
                statusMessage = error.localizedDescription
            }
        } else {
            do {
                try await recorder.startRecording()
                statusMessage = "Registrazione in corso…"
            } catch {
                statusMessage = error.localizedDescription
            }
        }
    }
}

#Preview {
    RecordView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
