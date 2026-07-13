import Foundation
import UIKit
import UserNotifications

/// Presenza remota — push token verso JANIS.
@MainActor
final class JanicePushService: ObservableObject {
    static let shared = JanicePushService()

    @Published private(set) var isRegistered = false
    @Published private(set) var deviceTokenHex = ""
    @Published private(set) var lastError = ""

    private init() {}

    func reportError(_ message: String) {
        lastError = message
    }

    func requestRegistration() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    func handleToken(_ tokenData: Data) async {
        let hex = tokenData.map { String(format: "%02x", $0) }.joined()
        deviceTokenHex = hex
        let ok = await JaniceAPIClient.shared.postPushToken(hex: hex)
        isRegistered = ok
        if !ok { lastError = "Server non ha accettato il token push." }
    }

    func registerAction() async -> [String: Any] {
        requestRegistration()
        if !deviceTokenHex.isEmpty {
            let ok = await JaniceAPIClient.shared.postPushToken(hex: deviceTokenHex)
            isRegistered = ok
            return ["ok": ok, "token": deviceTokenHex]
        }
        return ["ok": false, "error": "token_not_ready", "hint": "register_for_remote_notifications"]
    }
}
