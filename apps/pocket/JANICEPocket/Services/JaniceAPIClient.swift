import Foundation
#if os(iOS)
import UIKit
#endif
import Darwin
import UIKit

enum JaniceAPIError: LocalizedError {
    case notConfigured
    case invalidURL
    case httpError(Int, String)
    case emptyResponse

    var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Server JANICE non configurato nelle Impostazioni."
        case .invalidURL:
            return "URL server non valido."
        case .httpError(let code, let msg):
            return "HTTP \(code): \(msg)"
        case .emptyResponse:
            return "Risposta vuota dal server."
        }
    }
}

struct JaniceSTTResponse: Decodable {
    let text: String
    let language: String?
    let engine: String?
}

struct JaniceFleetNode: Identifiable, Equatable {
    let id: String
    let label: String
    let status: String
    let detail: String
}

struct JaniceStatusSnapshot {
    let online: Bool
    let version: String
    let nodes: [JaniceFleetNode]
    let jobs: [String]
    let rawJSON: [String: Any]

    static let empty = JaniceStatusSnapshot(online: false, version: "", nodes: [], jobs: [], rawJSON: [:])
}

struct IOSBridgeCommand: Decodable {
    let id: String
    let action: String
    let params: [String: String]?

    init(id: String, action: String, params: [String: String]? = nil) {
        self.id = id
        self.action = action
        self.params = params
    }

    enum CodingKeys: String, CodingKey {
        case id
        case commandId = "command_id"
        case action
        case params
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id)
            ?? c.decodeIfPresent(String.self, forKey: .commandId)
            ?? UUID().uuidString
        action = try c.decodeIfPresent(String.self, forKey: .action) ?? ""
        if let dict = try? c.decode([String: String].self, forKey: .params) {
            params = dict
        } else {
            params = nil
        }
    }
}

/// Client HTTP verso il hub JANIS.
final class JaniceAPIClient {
    static let shared = JaniceAPIClient()

    /// ID fleet univoco per modello hardware (allineato a infra/fleet.yaml).
    static var deviceID: String {
        #if os(iOS)
        if let override = UserDefaults.standard.string(forKey: "janiceFleetDeviceID")?
            .trimmingCharacters(in: .whitespacesAndNewlines), !override.isEmpty {
            return override
        }
        switch machineIdentifier {
        case "iPhone16,2":
            return "iphone-15-pro-max"
        case "iPhone15,2":
            return "iphone-14-pro"
        case "iPad8,11", "iPad8,12", "iPad8,9", "iPad8,10":
            return "ipad-pro-2020"
        default:
            return UIDevice.current.userInterfaceIdiom == .pad ? "ipad-pro-2020" : "iphone-15-pro-max"
        }
        #else
        return "pocket"
        #endif
    }

    #if os(iOS)
    private static var machineIdentifier: String {
        var systemInfo = utsname()
        uname(&systemInfo)
        return withUnsafePointer(to: &systemInfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: 1) {
                String(validatingUTF8: $0) ?? "unknown"
            }
        }
    }
    #endif

    private init() {}

    func baseURL() -> URL? {
        let useVPN = UserDefaults.standard.bool(forKey: "janicePreferVPNServer")
        let fromDefaults = UserDefaults.standard.string(forKey: useVPN ? "janiceVPNServerURL" : "janiceServerURL")?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let keychainURL = useVPN ? KeychainService.loadVPNServerBaseURL() : KeychainService.loadServerBaseURL()
        let raw = (fromDefaults?.isEmpty == false ? fromDefaults : keychainURL)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let raw, !raw.isEmpty else { return nil }
        var s = raw
        if !s.hasPrefix("http") { s = "http://\(s)" }
        return URL(string: s)
    }

    private func applyAuth(_ request: inout URLRequest) {
        if let token = KeychainService.loadDeviceToken(), !token.isEmpty {
            request.setValue(token, forHTTPHeaderField: "X-JANIS-Token")
            request.setValue(token, forHTTPHeaderField: "X-JANICE-Token")
        }
    }

    func transcribe(audioURL: URL) async throws -> String {
        guard let base = baseURL() else { throw JaniceAPIError.notConfigured }
        let endpoint = base.appendingPathComponent("api/stt")
        let data = try Data(contentsOf: audioURL)
        guard !data.isEmpty else { throw JaniceAPIError.emptyResponse }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 180
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)

        var body = Data()
        func append(_ s: String) { body.append(Data(s.utf8)) }

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"file\"; filename=\"note.m4a\"\r\n")
        append("Content-Type: audio/m4a\r\n\r\n")
        body.append(data)
        append("\r\n")
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"language\"\r\n\r\n")
        append("it\r\n")
        append("--\(boundary)--\r\n")
        request.httpBody = body

        let (respData, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw JaniceAPIError.emptyResponse }
        guard (200...299).contains(http.statusCode) else {
            let msg = String(data: respData, encoding: .utf8) ?? ""
            throw JaniceAPIError.httpError(http.statusCode, msg)
        }
        let decoded = try JSONDecoder().decode(JaniceSTTResponse.self, from: respData)
        let text = decoded.text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw JaniceAPIError.emptyResponse }
        return text
    }

    func chatWebSocketURL(sessionId: String) -> URL? {
        guard let base = baseURL() else { return nil }
        let wsBase = base.absoluteString
            .replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "ws://")
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        var components = URLComponents(string: "\(wsBase)/ws/janis")
        components?.queryItems = [
            URLQueryItem(name: "device_id", value: Self.deviceID),
            URLQueryItem(name: "session_id", value: sessionId),
        ]
        return components?.url
    }

    func brainPageURL() -> URL? {
        guard let base = baseURL() else { return nil }
        var components = URLComponents(url: base.appendingPathComponent("brain"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "device_id", value: Self.deviceID),
            URLQueryItem(name: "compact", value: "1"),
        ]
        return components?.url
    }

    func claimPresence() async {
        guard let base = baseURL() else { return }
        var request = URLRequest(url: base.appendingPathComponent("api/presence/claim"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let body: [String: Any] = [
            "device_id": Self.deviceID,
            "surface": "mobile",
            "follow_user": true,
            "body": await MainActor.run { JaniceBodyManifest.snapshot() },
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        _ = try? await URLSession.shared.data(for: request)
    }


    func ping() async -> Bool {
        guard let base = baseURL() else { return false }
        var request = URLRequest(url: base.appendingPathComponent("api/status"))
        request.timeoutInterval = 8
        applyAuth(&request)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    func fetchStatus() async -> JaniceStatusSnapshot {
        guard let base = baseURL() else { return .empty }
        var request = URLRequest(url: base.appendingPathComponent("api/status"))
        request.timeoutInterval = 10
        applyAuth(&request)
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return .empty
        }
        return Self.parseStatus(json)
    }

    func postTelemetry(_ payload: [String: Any]) async -> Bool {
        guard let base = baseURL() else { return false }
        var request = URLRequest(url: base.appendingPathComponent("api/pocket/telemetry"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        applyAuth(&request)
        var body = payload
        body["device_id"] = Self.deviceID
        body["timestamp"] = ISO8601DateFormatter().string(from: Date())
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    func fetchPendingCommands() async -> [IOSBridgeCommand] {
        guard let base = baseURL() else { return [] }
        var components = URLComponents(url: base.appendingPathComponent("api/devices/ios/pending"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "device", value: Self.deviceID)]
        guard let url = components?.url else { return [] }
        var request = URLRequest(url: url)
        request.timeoutInterval = 10
        applyAuth(&request)
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return []
        }
        if let list = try? JSONDecoder().decode([IOSBridgeCommand].self, from: data) {
            return list
        }
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let commands = json["commands"] as? [[String: Any]] {
            return commands.compactMap { dict in
                guard let data = try? JSONSerialization.data(withJSONObject: dict),
                      let cmd = try? JSONDecoder().decode(IOSBridgeCommand.self, from: data) else { return nil }
                return cmd
            }
        }
        return []
    }

    func completeCommand(id: String, result: [String: Any]) async {
        guard let base = baseURL() else { return }
        var request = URLRequest(url: base.appendingPathComponent("api/devices/ios/complete"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let body: [String: Any] = [
            "device": Self.deviceID,
            "command_id": id,
            "result": result,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        _ = try? await URLSession.shared.data(for: request)
    }

    func postVision(jpegBase64: String, context: String? = nil) async -> Bool {
        guard let base = baseURL() else { return false }
        let owner = await MainActor.run { UserIdentityService.shared.identityPayload() }
        var request = URLRequest(url: base.appendingPathComponent("api/pocket/vision"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30
        applyAuth(&request)
        var body: [String: Any] = [
            "device_id": Self.deviceID,
            "image_base64": jpegBase64,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "owner": owner,
        ]
        if let context, !context.isEmpty { body["context"] = context }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    func enrollIdentity(displayName: String, framesBase64: [String]) async -> Bool {
        guard let base = baseURL() else { return false }
        var request = URLRequest(url: base.appendingPathComponent("api/identity/enroll"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let body: [String: Any] = ["display_name": displayName, "frames": framesBase64]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    func verifyIdentity(jpegBase64: String) async -> (verified: Bool, displayName: String?) {
        guard let base = baseURL() else { return (false, nil) }
        var request = URLRequest(url: base.appendingPathComponent("api/identity/verify"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let body: [String: Any] = ["image_base64": jpegBase64]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return (false, nil)
        }
        let verified = json["verified"] as? Bool ?? false
        let name = json["display_name"] as? String
        return (verified, name)
    }

    func postEmergencySOS(text: String, location: [String: Any]?, imageBase64: String?) async -> Bool {
        guard let base = baseURL() else { return false }
        var request = URLRequest(url: base.appendingPathComponent("api/emergency/sos"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let identity = await MainActor.run { UserIdentityService.shared.identityPayload() }
        var body: [String: Any] = [
            "device_id": Self.deviceID,
            "text": text,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "identity": identity,
        ]
        if let location { body["location"] = location }
        if let imageBase64, !imageBase64.isEmpty { body["image_base64"] = imageBase64 }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    func postPushToken(hex: String) async -> Bool {
        guard let base = baseURL() else { return false }
        var request = URLRequest(url: base.appendingPathComponent("api/pocket/push/register"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyAuth(&request)
        let owner = await MainActor.run { UserIdentityService.shared.identityPayload() }
        let body: [String: Any] = [
            "device_id": Self.deviceID,
            "token": hex,
            "platform": "ios",
            "owner": owner,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return (200...299).contains(http.statusCode)
    }

    private static func parseStatus(_ json: [String: Any]) -> JaniceStatusSnapshot {
        let version = json["version"] as? String ?? json["janis_version"] as? String ?? ""
        var nodes: [JaniceFleetNode] = []

        let candidates: [[String: Any]] = {
            if let n = json["nodes"] as? [[String: Any]] { return n }
            if let f = json["fleet"] as? [[String: Any]] { return f }
            if let d = json["devices"] as? [[String: Any]] { return d }
            return []
        }()

        for item in candidates {
            let id = item["id"] as? String ?? item["name"] as? String ?? item["node"] as? String ?? "node"
            let status = item["status"] as? String ?? item["state"] as? String ?? "unknown"
            let detail = item["detail"] as? String ?? item["host"] as? String ?? ""
            nodes.append(JaniceFleetNode(id: id, label: id, status: status, detail: detail))
        }

        if nodes.isEmpty {
            for key in ["mac-node", "mac_node", "win-vm", "win_vm", "server"] {
                if let value = json[key] {
                    let status = (value as? [String: Any])?["status"] as? String
                        ?? (value as? String) ?? "present"
                    nodes.append(JaniceFleetNode(id: key, label: key, status: status, detail: ""))
                }
            }
        }

        let jobs: [String] = {
            if let arr = json["jobs"] as? [String] { return arr }
            if let arr = json["jobs"] as? [[String: Any]] {
                return arr.compactMap { $0["id"] as? String ?? $0["status"] as? String }
            }
            if let active = json["active_job"] as? String { return [active] }
            return []
        }()

        return JaniceStatusSnapshot(online: true, version: version, nodes: nodes, jobs: jobs, rawJSON: json)
    }
}
