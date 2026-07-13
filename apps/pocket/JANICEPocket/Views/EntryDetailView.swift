import SwiftData
import SwiftUI

struct EntryDetailView: View {
    @Environment(\.modelContext) private var modelContext
    @Bindable var entry: JournalEntry
    @StateObject private var playback = AudioPlaybackService()
    @StateObject private var transcription = TranscriptionService()
    @AppStorage("useWhisperTranscription") private var useWhisper = false
    @AppStorage("useJaniceServerSTT") private var useJaniceServer = true
    @AppStorage("transcriptionAllowFallback") private var allowFallback = true

    @State private var statusMessage = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                metadataHeader

                if entry.type == .voice, let fileName = entry.audioFileName {
                    voiceSection(fileName: fileName)
                }

                if entry.transcriptionPending && entry.transcript.isEmpty {
                    pendingTranscriptionBanner
                }

                if !entry.body.isEmpty {
                    textSection(title: "Testo", content: entry.body)
                }

                if !entry.transcript.isEmpty {
                    textSection(title: "Trascrizione", content: entry.transcript)
                }

                if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .font(.footnote)
                        .foregroundStyle(JaniceColors.inkSoft)
                }
            }
            .padding()
        }
        .navigationTitle(entry.displayTitle)
        .navigationBarTitleDisplayMode(.inline)
        .eInkScreen()
        .onDisappear {
            playback.stop()
        }
    }

    private var metadataHeader: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(entry.type == .voice ? "Nota vocale" : "Nota di testo", systemImage: entry.type == .voice ? "mic" : "text.bubble")
                .font(.subheadline)
                .foregroundStyle(JaniceColors.inkSoft)
            Text(entry.createdAt.formatted(date: .complete, time: .shortened))
                .font(.caption)
                .foregroundStyle(JaniceColors.inkSoft.opacity(0.85))
            if !entry.transcriptionEngine.isEmpty {
                Text("Motore: \(engineLabel(entry.transcriptionEngine))")
                    .font(.caption2)
                    .foregroundStyle(JaniceColors.inkSoft.opacity(0.75))
            }
        }
    }

    private var pendingTranscriptionBanner: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Trascrizione mancante")
                .font(.headline)
                .foregroundStyle(JaniceColors.ink)
            Text("L'audio è salvato. Puoi ritentare la trascrizione quando vuoi.")
                .font(.subheadline)
                .foregroundStyle(JaniceColors.inkSoft)
            retranscribeButton
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(JaniceColors.paperDeep.opacity(0.75))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func voiceSection(fileName: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Audio")
                .font(.headline)
                .foregroundStyle(JaniceColors.ink)

            Button {
                try? playback.toggle(fileName: fileName)
            } label: {
                Label(
                    playback.isPlaying && playback.currentFileName == fileName ? "Pausa" : "Riproduci",
                    systemImage: playback.isPlaying && playback.currentFileName == fileName ? "pause.circle.fill" : "play.circle.fill"
                )
                .font(.title3)
            }
            .foregroundStyle(JaniceColors.inkSoft)

            if entry.type == .voice {
                retranscribeButton
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(JaniceColors.paperDeep.opacity(0.75))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var retranscribeButton: some View {
        Button {
            Task { await retranscribe() }
        } label: {
            if transcription.isTranscribing {
                HStack {
                    ProgressView()
                    Text(transcription.progressMessage)
                }
            } else {
                Label("Ritrascrivere", systemImage: "text.quote")
            }
        }
        .disabled(transcription.isTranscribing || entry.audioFileName == nil)
        .foregroundStyle(JaniceColors.inkSoft)
    }

    private func textSection(title: String, content: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
                .foregroundStyle(JaniceColors.ink)
            Text(content)
                .font(.body)
                .foregroundStyle(JaniceColors.ink)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(JaniceColors.paperDeep.opacity(0.75))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func retranscribe() async {
        guard let fileName = entry.audioFileName else { return }
        statusMessage = ""
        entry.transcriptionPending = true
        do {
            let result = try await transcription.transcribe(
                audioURL: AudioStorageService.url(for: fileName),
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
            statusMessage = "Trascrizione aggiornata (\(engineLabel(result.engine.rawValue)))."
        } catch {
            entry.transcriptionPending = true
            try? modelContext.save()
            statusMessage = error.localizedDescription
        }
    }

    private func engineLabel(_ raw: String) -> String {
        switch raw {
        case "janice": return "JANICE"
        case "whisper": return "Whisper"
        default: return "Apple Speech"
        }
    }
}

#Preview {
    NavigationStack {
        EntryDetailView(entry: JournalEntry(type: .voice, transcript: "Esempio di trascrizione", audioFileName: "demo.m4a"))
    }
    .modelContainer(for: JournalEntry.self, inMemory: true)
}
