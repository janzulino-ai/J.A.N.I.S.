import AppIntents
import Foundation

/// Scorciatoia Siri — apre JANIS con un messaggio.
@available(iOS 16.0, *)
struct AskJANISIntent: AppIntent {
    static var title: LocalizedStringResource = "Chiedi a JANIS"
    static var description = IntentDescription("Invia un messaggio al brain JANIS da JANICE Pocket.")
    static var openAppWhenRun: Bool = true

    @Parameter(title: "Messaggio")
    var message: String

    static var parameterSummary: some ParameterSummary {
        Summary("Chiedi a JANIS: \(\.$message)")
    }

    func perform() async throws -> some IntentResult {
        let trimmed = message.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return .result(dialog: "Messaggio vuoto.")
        }
        UserDefaults.standard.set(trimmed, forKey: "janicePendingSiriMessage")
        return .result(dialog: "Apro JANICE per JANIS.")
    }
}

@available(iOS 16.0, *)
struct JANICEPocketShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskJANISIntent(),
            phrases: [
                "Chiedi a \(.applicationName)",
                "Parla con \(.applicationName)",
                "JANIS tramite \(.applicationName)",
            ],
            shortTitle: "Chiedi a JANIS",
            systemImageName: "bubble.left.and.bubble.right.fill"
        )
    }
}
