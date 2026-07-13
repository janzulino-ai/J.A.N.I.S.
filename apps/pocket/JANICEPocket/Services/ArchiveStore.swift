import Foundation
import SwiftData

struct ArchiveSection: Identifiable {
    let id: String
    let title: String
    let entries: [JournalEntry]
}

enum ArchiveStore {
    static func sections(from entries: [JournalEntry]) -> [ArchiveSection] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: entries) { entry -> Date in
            calendar.startOfDay(for: entry.createdAt)
        }

        return grouped.keys.sorted(by: >).map { day in
            let dayEntries = (grouped[day] ?? []).sorted { $0.createdAt > $1.createdAt }
            let title = sectionTitle(for: day, calendar: calendar)
            return ArchiveSection(id: ISO8601DateFormatter().string(from: day), title: title, entries: dayEntries)
        }
    }

    static func filter(_ entries: [JournalEntry], query: String) -> [JournalEntry] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return entries.sorted { $0.createdAt > $1.createdAt } }
        let needle = trimmed.lowercased()
        return entries
            .filter { $0.searchableText.contains(needle) }
            .sorted { $0.createdAt > $1.createdAt }
    }

    private static func sectionTitle(for day: Date, calendar: Calendar) -> String {
        if calendar.isDateInToday(day) { return "Oggi" }
        if calendar.isDateInYesterday(day) { return "Ieri" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "it_IT")
        formatter.dateStyle = .full
        formatter.timeStyle = .none
        return formatter.string(from: day)
    }
}
