import Foundation

/// Profilo WireGuard per JANIS fuori casa.
enum JaniceVPNProfileService {
    static func wireGuardConfig(
        serverPublicKey: String,
        serverEndpoint: String,
        clientPrivateKey: String,
        clientAddress: String = "10.8.0.2/32",
        allowedIPs: String = "192.168.1.0/24",
        dns: String = "192.168.1.1"
    ) -> String {
        """
        [Interface]
        PrivateKey = \(clientPrivateKey)
        Address = \(clientAddress)
        DNS = \(dns)

        [Peer]
        PublicKey = \(serverPublicKey)
        Endpoint = \(serverEndpoint)
        AllowedIPs = \(allowedIPs)
        PersistentKeepalive = 25
        """
    }

    static func pocketServerURLHint(lanURL: String) -> String {
        let trimmed = lanURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "http://192.168.1.72:8001" }
        return trimmed
    }

    static func setupSteps(lanURL: String) -> [String] {
        [
            "1. Router: abilita server WireGuard (UDP 51820)",
            "2. Genera coppia chiavi client (wg genkey / wg pubkey)",
            "3. Incolla config in app WireGuard iPhone",
            "4. Connetti VPN → stesso URL LAN in Pocket",
            "5. Impostazioni Pocket → URL VPN: \(pocketServerURLHint(lanURL: lanURL))",
            "6. Attiva toggle «Usa server VPN» fuori casa",
        ]
    }
}
