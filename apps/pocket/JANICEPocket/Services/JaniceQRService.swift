import Foundation
import Vision
import UIKit

/// Lettura QR/barcode dagli occhi.
enum JaniceQRService {
    static func scanFromBase64JPEG(_ base64: String) -> [String: Any] {
        guard let data = Data(base64Encoded: base64),
              let image = UIImage(data: data),
              let cgImage = image.cgImage else {
            return ["ok": false, "error": "invalid_image"]
        }
        return scan(cgImage: cgImage)
    }

    static func scanFromPhoto() async -> [String: Any] {
        guard let b64 = await JaniceVisionService.shared.captureJPEGBase64() else {
            return ["ok": false, "error": "camera_failed"]
        }
        return scanFromBase64JPEG(b64)
    }

    private static func scan(cgImage: CGImage) -> [String: Any] {
        let request = VNDetectBarcodesRequest()
        request.symbologies = [.qr, .ean8, .ean13, .code128, .pdf417]
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do {
            try handler.perform([request])
            let payloads = (request.results ?? []).compactMap { $0.payloadStringValue }
            if payloads.isEmpty {
                return ["ok": true, "found": false, "codes": [] as [String]]
            }
            return ["ok": true, "found": true, "codes": payloads, "primary": payloads[0]]
        } catch {
            return ["ok": false, "error": error.localizedDescription]
        }
    }
}
