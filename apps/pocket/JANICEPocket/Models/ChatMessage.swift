import Foundation
import SwiftData

enum ChatRole: String, Codable, CaseIterable {
    case user
    case assistant
    case system
}

@Model
final class ChatMessage {
    var id: UUID
    var sessionId: String
    var roleRaw: String
    var content: String
    var audioFileName: String?
    var createdAt: Date
    /// `false` mentre l'assistant sta ancora streamando.
    var isComplete: Bool

    init(
        id: UUID = UUID(),
        sessionId: String,
        role: ChatRole,
        content: String = "",
        audioFileName: String? = nil,
        createdAt: Date = .now,
        isComplete: Bool = true
    ) {
        self.id = id
        self.sessionId = sessionId
        self.roleRaw = role.rawValue
        self.content = content
        self.audioFileName = audioFileName
        self.createdAt = createdAt
        self.isComplete = isComplete
    }

    var role: ChatRole {
        get { ChatRole(rawValue: roleRaw) ?? .system }
        set { roleRaw = newValue.rawValue }
    }
}
