import Foundation

/// Stato hub JANIS lato server — usato dalla tab Server.
@MainActor
final class JaniceHubMonitor: ObservableObject {
    static let shared = JaniceHubMonitor()

    @Published private(set) var snapshot = JaniceStatusSnapshot.empty
    @Published private(set) var isReachable = false
    @Published private(set) var isLoading = false
    @Published private(set) var lastRefresh: Date?
    @Published private(set) var serverURL = "—"
    @Published private(set) var errorMessage = ""

    private init() {}

    func refresh() async {
        isLoading = true
        defer { isLoading = false }

        serverURL = JaniceAPIClient.shared.baseURL()?.absoluteString ?? "Non configurato"
        guard JaniceAPIClient.shared.baseURL() != nil else {
            isReachable = false
            snapshot = .empty
            errorMessage = "Server non configurato in Impostazioni."
            lastRefresh = .now
            return
        }

        isReachable = await JaniceAPIClient.shared.ping()
        snapshot = await JaniceAPIClient.shared.fetchStatus()
        lastRefresh = .now
        errorMessage = isReachable ? "" : "Server non raggiungibile. Verifica Wi‑Fi/VPN e che JANIS sia avviato."
    }
}
