import SwiftData
import SwiftUI

struct ChatEntryView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var title = ""
    @State private var bodyText = ""
    @State private var savedMessage = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    TextField("Titolo (opzionale)", text: $title)
                        .textFieldStyle(.plain)
                        .padding(12)
                        .background(JaniceColors.paperDeep.opacity(0.8))
                        .clipShape(RoundedRectangle(cornerRadius: 10))

                    Text("Contenuto")
                        .font(.caption)
                        .foregroundStyle(JaniceColors.inkSoft)

                    TextEditor(text: $bodyText)
                        .frame(minHeight: 220)
                        .padding(8)
                        .scrollContentBackground(.hidden)
                        .background(JaniceColors.paperDeep.opacity(0.8))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .foregroundStyle(JaniceColors.ink)

                    Button("Salva nota") {
                        saveEntry()
                    }
                    .buttonStyle(EInkButtonStyle())
                    .disabled(bodyText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                    if !savedMessage.isEmpty {
                        Text(savedMessage)
                            .font(.footnote)
                            .foregroundStyle(JaniceColors.inkSoft)
                    }
                }
                .padding()
            }
            .navigationTitle("Scrivi")
            .eInkScreen()
        }
    }

    private func saveEntry() {
        let trimmed = bodyText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let entry = JournalEntry(
            type: .chat,
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            body: trimmed
        )
        modelContext.insert(entry)
        try? modelContext.save()
        let savedTitle = entry.title.isEmpty ? String(trimmed.prefix(80)) : entry.title
        title = ""
        bodyText = ""
        savedMessage = "Nota salvata nell'archivio."
    }
}

#Preview {
    ChatEntryView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
