import SwiftUI
import WebKit

/// Orbita brain stile Siri — solo quando questo device ha la presenza attiva.
struct BrainLiveView: View {
    @StateObject private var monitor = PresenceMonitor()

    var body: some View {
        VStack {
            Spacer()
            if monitor.isActive, let url = JaniceAPIClient.shared.brainPageURL() {
                BrainWebView(url: url)
                    .frame(width: 76, height: 76)
                    .allowsHitTesting(false)
                    .transition(.scale.combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.bottom, 108)
        .animation(.easeInOut(duration: 0.45), value: monitor.isActive)
        .allowsHitTesting(false)
        .task { await monitor.start() }
    }
}

struct BrainWebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let webView = WKWebView(frame: CGRect(x: 0, y: 0, width: 76, height: 76), configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.isScrollEnabled = false
        webView.scrollView.backgroundColor = .clear
        webView.isUserInteractionEnabled = false
        if #available(iOS 16.4, *) {
            webView.isInspectable = false
        }
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

@MainActor
final class PresenceMonitor: ObservableObject {
    @Published var isActive = false

    private var pollTask: Task<Void, Never>?
    private var socketTask: Task<Void, Never>?

    func start() async {
        pollTask?.cancel()
        socketTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled {
                await refreshHTTP()
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
        socketTask = Task {
            await listenWebSocket()
        }
    }

    private func refreshHTTP() async {
        guard let base = JaniceAPIClient.shared.baseURL() else {
            isActive = false
            return
        }
        var request = URLRequest(url: base.appendingPathComponent("api/presence"))
        request.timeoutInterval = 6
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let activeId = (json["device_id"] as? String)?.lowercased() else {
            return
        }
        isActive = activeId == JaniceAPIClient.deviceID.lowercased()
    }

    private func listenWebSocket() async {
        guard let base = JaniceAPIClient.shared.baseURL() else { return }
        let wsBase = base.absoluteString.replacingOccurrences(of: "https://", with: "wss://")
            .replacingOccurrences(of: "http://", with: "ws://")
        let device = JaniceAPIClient.deviceID
        guard let url = URL(string: "\(wsBase)/ws/janice?device_id=\(device)") else { return }

        while !Task.isCancelled {
            do {
                let session = URLSession(configuration: .default)
                let socket = session.webSocketTask(with: url)
                socket.resume()
                while !Task.isCancelled {
                    let message = try await socket.receive()
                    if case .string(let text) = message,
                       let data = text.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       json["type"] as? String == "presence_changed",
                       let activeId = (json["device_id"] as? String)?.lowercased() {
                        isActive = activeId == device.lowercased()
                    }
                }
            } catch {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }
}
