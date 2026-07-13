import EventKit
import Foundation

/// Agenda — eventi imminenti per contesto JANIS.
@MainActor
final class JaniceCalendarService: ObservableObject {
    static let shared = JaniceCalendarService()

    @Published private(set) var isAuthorized = false
    @Published private(set) var lastError = ""

    private let store = EKEventStore()

    private init() {}

    func requestAccess() async {
        do {
            if #available(iOS 17.0, *) {
                isAuthorized = try await store.requestFullAccessToEvents()
            } else {
                isAuthorized = try await store.requestAccess(to: .event)
            }
        } catch {
            lastError = error.localizedDescription
            isAuthorized = false
        }
    }

    func upcomingEvents(days: Int = 3, limit: Int = 10) -> [String: Any] {
        guard isAuthorized else {
            return ["ok": false, "error": "not_authorized"]
        }
        let start = Date()
        let end = Calendar.current.date(byAdding: .day, value: days, to: start) ?? start
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        let events = store.events(matching: predicate)
            .sorted { $0.startDate < $1.startDate }
            .prefix(limit)
            .map { event -> [String: Any] in
                [
                    "title": event.title ?? "",
                    "start": ISO8601DateFormatter().string(from: event.startDate),
                    "end": ISO8601DateFormatter().string(from: event.endDate),
                    "location": event.location ?? "",
                    "all_day": event.isAllDay,
                ]
            }
        return ["ok": true, "events": Array(events), "count": events.count]
    }
}
