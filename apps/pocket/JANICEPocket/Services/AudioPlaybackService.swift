import AVFoundation
import Foundation

@MainActor
final class AudioPlaybackService: ObservableObject {
    @Published private(set) var isPlaying = false
    @Published private(set) var currentFileName: String?

    private var player: AVAudioPlayer?

    func play(fileName: String) throws {
        stop()
        let url = AudioStorageService.url(for: fileName)
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw PlaybackError.fileMissing
        }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .allowBluetooth])
        try session.setActive(true)

        player = try AVAudioPlayer(contentsOf: url)
        player?.delegate = PlaybackDelegate.shared
        PlaybackDelegate.shared.onFinish = { [weak self] in
            Task { @MainActor in
                self?.isPlaying = false
                self?.currentFileName = nil
            }
        }
        player?.play()
        isPlaying = true
        currentFileName = fileName
    }

    func stop() {
        player?.stop()
        player = nil
        isPlaying = false
        currentFileName = nil
    }

    func toggle(fileName: String) throws {
        if isPlaying, currentFileName == fileName {
            stop()
        } else {
            try play(fileName: fileName)
        }
    }
}

private final class PlaybackDelegate: NSObject, AVAudioPlayerDelegate {
    static let shared = PlaybackDelegate()
    var onFinish: (() -> Void)?

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish?()
    }
}

enum PlaybackError: LocalizedError {
    case fileMissing

    var errorDescription: String? {
        switch self {
        case .fileMissing:
            return "File audio non trovato."
        }
    }
}
