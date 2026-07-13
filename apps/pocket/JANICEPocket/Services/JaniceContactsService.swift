import Contacts
import Foundation

/// Rubrica — ricerca contatti per JANIS.
@MainActor
final class JaniceContactsService: ObservableObject {
    static let shared = JaniceContactsService()

    @Published private(set) var isAuthorized = false
    @Published private(set) var lastError = ""

    private let store = CNContactStore()

    private init() {}

    func requestAccess() async {
        do {
            isAuthorized = try await store.requestAccess(for: .contacts)
        } catch {
            lastError = error.localizedDescription
            isAuthorized = false
        }
    }

    func search(query: String, limit: Int = 8) -> [String: Any] {
        guard isAuthorized else {
            return ["ok": false, "error": "not_authorized"]
        }
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return ["ok": false, "error": "empty_query"]
        }
        let keys: [CNKeyDescriptor] = [
            CNContactGivenNameKey as CNKeyDescriptor,
            CNContactFamilyNameKey as CNKeyDescriptor,
            CNContactPhoneNumbersKey as CNKeyDescriptor,
            CNContactEmailAddressesKey as CNKeyDescriptor,
        ]
        var results: [[String: Any]] = []
        let predicate = CNContact.predicateForContacts(matchingName: trimmed)
        do {
            let contacts = try store.unifiedContacts(matching: predicate, keysToFetch: keys)
            for contact in contacts.prefix(limit) {
                let phones = contact.phoneNumbers.map { $0.value.stringValue }
                let emails = contact.emailAddresses.map { $0.value as String }
                results.append([
                    "name": "\(contact.givenName) \(contact.familyName)".trimmingCharacters(in: .whitespaces),
                    "phones": phones,
                    "emails": emails,
                ])
            }
            return ["ok": true, "contacts": results, "count": results.count]
        } catch {
            return ["ok": false, "error": error.localizedDescription]
        }
    }
}
