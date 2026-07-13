import CoreLocation
import Foundation
import UIKit

/// Riconoscimento volto via brain Linux (enroll + verify).
@MainActor
final class JaniceFaceService: ObservableObject {
    static let shared = JaniceFaceService()

    @Published private(set) var lastVerified = false
    @Published private(set) var verifiedName: String?

    private init() {}

    func enroll(displayName: String, frameCount: Int = 5) async -> Bool {
        var frames: [String] = []
        for _ in 0..<frameCount {
            if let img = await JaniceVisionService.shared.capturePhoto(),
               let b64 = img.jpegData(compressionQuality: 0.5)?.base64EncodedString() {
                frames.append(b64)
            }
            try? await Task.sleep(nanoseconds: 400_000_000)
        }
        guard !frames.isEmpty else { return false }
        return await JaniceAPIClient.shared.enrollIdentity(displayName: displayName, framesBase64: frames)
    }

    func verifySession() async {
        guard let img = await JaniceVisionService.shared.capturePhoto(),
              let b64 = img.jpegData(compressionQuality: 0.45)?.base64EncodedString() else {
            lastVerified = false
            verifiedName = nil
            return
        }
        let result = await JaniceAPIClient.shared.verifyIdentity(jpegBase64: b64)
        lastVerified = result.verified
        verifiedName = result.displayName
    }
}

/// Emergenza SOS verso brain Linux.
@MainActor
final class JaniceEmergencyService: ObservableObject {
    static let shared = JaniceEmergencyService()

    private let locationManager = CLLocationManager()

    func triggerSOS(text: String = "Mi sono fatto male, ho bisogno di aiuto") async -> Bool {
        var loc: [String: Any]?
        if let c = locationManager.location?.coordinate {
            loc = ["lat": c.latitude, "lon": c.longitude]
        }
        var imageB64: String?
        if let img = await JaniceVisionService.shared.capturePhoto(),
           let data = img.jpegData(compressionQuality: 0.4) {
            imageB64 = data.base64EncodedString()
        }
        return await JaniceAPIClient.shared.postEmergencySOS(text: text, location: loc, imageBase64: imageB64)
    }
}
