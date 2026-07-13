import Foundation
import Security

enum KeychainService {
    private static let service = "ai.janzulino.janice.pocket"
    private static let whisperAccount = "whisper-api-key"
    private static let serverAccount = "server-base-url"
    private static let vpnServerAccount = "vpn-server-base-url"
    private static let tokenAccount = "device-token"

    private static func save(account: String, value: String) throws {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        SecItemDelete(query as CFDictionary)
        var addQuery = query
        addQuery[kSecValueData as String] = data
        let status = SecItemAdd(addQuery as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError.unhandled(status) }
    }

    private static func load(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private static func delete(account: String) {
        SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ] as CFDictionary)
    }

    static func saveWhisperAPIKey(_ key: String) throws { try save(account: whisperAccount, value: key) }
    static func loadWhisperAPIKey() -> String? { load(account: whisperAccount) }
    static func deleteWhisperAPIKey() { delete(account: whisperAccount) }

    static func saveServerBaseURL(_ url: String) throws { try save(account: serverAccount, value: url) }
    static func loadServerBaseURL() -> String? { load(account: serverAccount) }
    static func deleteServerBaseURL() { delete(account: serverAccount) }

    static func saveVPNServerBaseURL(_ url: String) throws { try save(account: vpnServerAccount, value: url) }
    static func loadVPNServerBaseURL() -> String? { load(account: vpnServerAccount) }
    static func deleteVPNServerBaseURL() { delete(account: vpnServerAccount) }

    static func saveDeviceToken(_ token: String) throws { try save(account: tokenAccount, value: token) }
    static func loadDeviceToken() -> String? { load(account: tokenAccount) }
    static func deleteDeviceToken() { delete(account: tokenAccount) }
}

enum KeychainError: LocalizedError {
    case unhandled(OSStatus)

    var errorDescription: String? {
        switch self {
        case .unhandled(let status):
            return "Keychain error: \(status)"
        }
    }
}
