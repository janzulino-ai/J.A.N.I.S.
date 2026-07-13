import AVFoundation
import Foundation
import UIKit

/// Braccia di JANIS — clipboard, torcia, flash schermo.
@MainActor
final class JaniceReachService: ObservableObject {
    static let shared = JaniceReachService()

    private init() {}

    func getClipboard() -> [String: Any] {
        let text = UIPasteboard.general.string ?? ""
        return ["ok": true, "text": text, "has_content": !text.isEmpty]
    }

    func setClipboard(text: String) -> [String: Any] {
        UIPasteboard.general.string = text
        return ["ok": true, "length": text.count]
    }

    func setTorch(on: Bool) -> [String: Any] {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else {
            return ["ok": false, "error": "no_torch"]
        }
        do {
            try device.lockForConfiguration()
            device.torchMode = on ? .on : .off
            device.unlockForConfiguration()
            return ["ok": true, "torch": on]
        } catch {
            return ["ok": false, "error": error.localizedDescription]
        }
    }
}
