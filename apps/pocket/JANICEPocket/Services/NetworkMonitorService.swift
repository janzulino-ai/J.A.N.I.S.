import Foundation
import Network

@MainActor
final class NetworkMonitorService: ObservableObject {
    static let shared = NetworkMonitorService()

    @Published private(set) var isConnected = true
    @Published private(set) var isExpensive = false
    @Published private(set) var interfaceType = "unknown"

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "janice.network.monitor")

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isConnected = path.status == .satisfied
                self?.isExpensive = path.isExpensive
                if path.usesInterfaceType(.wifi) {
                    self?.interfaceType = "wifi"
                } else if path.usesInterfaceType(.cellular) {
                    self?.interfaceType = "cellular"
                } else if path.usesInterfaceType(.wiredEthernet) {
                    self?.interfaceType = "ethernet"
                } else {
                    self?.interfaceType = "other"
                }
            }
        }
        monitor.start(queue: queue)
    }

    func snapshot() -> [String: Any] {
        [
            "connected": isConnected,
            "expensive": isExpensive,
            "interface": interfaceType,
        ]
    }
}
