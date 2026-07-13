import AVFoundation
import Foundation
import UIKit

/// Occhi di JANIS — snapshot fotocamera su richiesta bridge.
@MainActor
final class JaniceVisionService: NSObject, ObservableObject {
    static let shared = JaniceVisionService()

    @Published private(set) var lastCaptureAt: Date?
    @Published private(set) var isCapturing = false

    private var captureSession: AVCaptureSession?
    private var photoOutput: AVCapturePhotoOutput?
    private var continuation: CheckedContinuation<UIImage?, Never>?

    private override init() {
        super.init()
    }

    func capturePhoto() async -> UIImage? {
        guard !isCapturing else { return nil }
        isCapturing = true
        defer { isCapturing = false }

        let granted = await requestCameraAccess()
        guard granted else { return nil }

        return await withCheckedContinuation { cont in
            continuation = cont
            setupSessionIfNeeded()
            guard let session = captureSession, let output = photoOutput else {
                cont.resume(returning: nil)
                return
            }
            let settings = AVCapturePhotoSettings()
            output.capturePhoto(with: settings, delegate: self)
            if !session.isRunning {
                DispatchQueue.global(qos: .userInitiated).async {
                    session.startRunning()
                }
            }
        }
    }

    func captureJPEGBase64(quality: CGFloat = 0.65) async -> String? {
        guard let image = await capturePhoto(),
              let data = image.jpegData(compressionQuality: quality) else { return nil }
        lastCaptureAt = .now
        return data.base64EncodedString()
    }

    private func requestCameraAccess() async -> Bool {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        switch status {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
        default:
            return false
        }
    }

    private func setupSessionIfNeeded() {
        guard captureSession == nil else { return }
        let session = AVCaptureSession()
        session.sessionPreset = .photo
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else { return }
        session.addInput(input)
        let output = AVCapturePhotoOutput()
        guard session.canAddOutput(output) else { return }
        session.addOutput(output)
        captureSession = session
        photoOutput = output
    }
}

extension JaniceVisionService: AVCapturePhotoCaptureDelegate {
    nonisolated func photoOutput(
        _ output: AVCapturePhotoOutput,
        didFinishProcessingPhoto photo: AVCapturePhoto,
        error: Error?
    ) {
        Task { @MainActor in
            defer { self.continuation = nil }
            guard error == nil,
                  let data = photo.fileDataRepresentation(),
                  let image = UIImage(data: data) else {
                self.continuation?.resume(returning: nil)
                return
            }
            self.lastCaptureAt = .now
            self.continuation?.resume(returning: image)
            self.captureSession?.stopRunning()
        }
    }
}
