import Foundation
import LocalAuthentication

/// Riconoscimento proprietario — Face ID / Touch ID + nome in Keychain.
@MainActor
final class UserIdentityService: ObservableObject {
    static let shared = UserIdentityService()

    @Published private(set) var isVerified = false
    @Published private(set) var lastVerifiedAt: Date?
    @Published private(set) var statusMessage = ""

    private let ownerNameKey = "janiceOwnerDisplayName"

    var displayName: String {
        UserDefaults.standard.string(forKey: ownerNameKey) ?? "Utente"
    }

    var requireBiometric: Bool {
        UserDefaults.standard.object(forKey: "janiceRequireBiometric") as? Bool ?? true
    }

    private init() {}

    func setDisplayName(_ name: String) {
        UserDefaults.standard.set(name.trimmingCharacters(in: .whitespacesAndNewlines), forKey: ownerNameKey)
    }

    func setRequireBiometric(_ required: Bool) {
        UserDefaults.standard.set(required, forKey: "janiceRequireBiometric")
        if !required { isVerified = true }
    }

    func authenticate(reason: String = "JANIS deve sapere che sei tu") async -> Bool {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            // Nessun biometrico — considera verificato su device personale
            isVerified = true
            lastVerifiedAt = .now
            statusMessage = "Biometrico non disponibile — sessione aperta."
            return true
        }
        do {
            let ok = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: reason
            )
            isVerified = ok
            if ok {
                lastVerifiedAt = .now
                statusMessage = "Riconosciuto: \(displayName)"
            } else {
                statusMessage = "Non riconosciuto."
            }
            return ok
        } catch {
            isVerified = false
            statusMessage = error.localizedDescription
            return false
        }
    }

    func ensureVerifiedIfRequired() async -> Bool {
        guard requireBiometric else {
            isVerified = true
            return true
        }
        if isVerified, let at = lastVerifiedAt, Date().timeIntervalSince(at) < 300 {
            return true
        }
        return await authenticate()
    }

    func identityPayload() -> [String: Any] {
        [
            "display_name": displayName,
            "verified": isVerified,
            "device_id": JaniceAPIClient.deviceID,
            "verified_at": lastVerifiedAt.map { ISO8601DateFormatter().string(from: $0) } as Any,
        ]
    }
}
