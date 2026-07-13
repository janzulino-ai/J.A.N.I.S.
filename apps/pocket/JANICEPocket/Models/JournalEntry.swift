import Foundation
import SwiftData

enum EntryType: String, Codable, CaseIterable {
    case voice
    case chat
}

@Model
final class JournalEntry {
    var id: UUID
    var createdAt: Date
    var typeRaw: String
    var title: String
    var body: String
    var transcript: String
    var audioFileName: String?
    /// `apple` | `whisper` | empty se non trascritto
    var transcriptionEngine: String
    var transcriptionPending: Bool

    init(
        id: UUID = UUID(),
        createdAt: Date = .now,
        type: EntryType,
        title: String = "",
        body: String = "",
        transcript: String = "",
        audioFileName: String? = nil,
        transcriptionEngine: String = "",
        transcriptionPending: Bool = false
    ) {
        self.id = id
        self.createdAt = createdAt
        self.typeRaw = type.rawValue
        self.title = title
        self.body = body
        self.transcript = transcript
        self.audioFileName = audioFileName
        self.transcriptionEngine = transcriptionEngine
        self.transcriptionPending = transcriptionPending
    }

    var type: EntryType {
        get { EntryType(rawValue: typeRaw) ?? .chat }
        set { typeRaw = newValue.rawValue }
    }

    var displayTitle: String {
        if !title.isEmpty { return title }
        if !body.isEmpty { return String(body.prefix(60)) }
        if !transcript.isEmpty { return String(transcript.prefix(60)) }
        return type == .voice ? "Nota vocale" : "Nota di testo"
    }

    var searchableText: String {
        [title, body, transcript].joined(separator: " ").lowercased()
    }
}
