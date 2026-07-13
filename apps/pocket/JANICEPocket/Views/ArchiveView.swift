import SwiftData
import SwiftUI

struct ArchiveView: View {
    @Query(sort: \JournalEntry.createdAt, order: .reverse) private var entries: [JournalEntry]
    @State private var searchText = ""

    private var filteredEntries: [JournalEntry] {
        ArchiveStore.filter(entries, query: searchText)
    }

    private var sections: [ArchiveSection] {
        ArchiveStore.sections(from: filteredEntries)
    }

    var body: some View {
        NavigationStack {
            Group {
                if entries.isEmpty {
                    ContentUnavailableView(
                        "Archivio vuoto",
                        systemImage: "archivebox",
                        description: Text("Le note vocali e di testo compariranno qui.")
                    )
                } else {
                    List {
                        ForEach(sections) { section in
                            Section(section.title) {
                                ForEach(section.entries, id: \.id) { entry in
                                    NavigationLink {
                                        EntryDetailView(entry: entry)
                                    } label: {
                                        ArchiveRow(entry: entry)
                                    }
                                    .listRowBackground(JaniceColors.paperDeep.opacity(0.55))
                                }
                            }
                        }
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("Archivio")
            .searchable(text: $searchText, prompt: "Cerca note")
            .eInkScreen()
        }
    }
}

private struct ArchiveRow: View {
    let entry: JournalEntry

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: entry.type == .voice ? "waveform" : "text.alignleft")
                .foregroundStyle(JaniceColors.inkSoft)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(entry.displayTitle)
                    .font(.body)
                    .foregroundStyle(JaniceColors.ink)
                    .lineLimit(2)
                HStack(spacing: 6) {
                    Text(entry.createdAt.formatted(date: .omitted, time: .shortened))
                        .font(.caption)
                        .foregroundStyle(JaniceColors.inkSoft)
                    if entry.transcriptionPending && entry.type == .voice {
                        Text("· da trascrivere")
                            .font(.caption)
                            .foregroundStyle(JaniceColors.inkSoft.opacity(0.8))
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    ArchiveView()
        .modelContainer(for: JournalEntry.self, inMemory: true)
}
