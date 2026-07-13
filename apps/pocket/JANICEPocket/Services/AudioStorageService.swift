import Foundation

enum AudioStorageService {
    static var audioDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = base.appendingPathComponent("JANICEPocket/Audio", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func newRecordingURL() -> URL {
        audioDirectory.appendingPathComponent("\(UUID().uuidString).m4a")
    }

    static func url(for fileName: String) -> URL {
        audioDirectory.appendingPathComponent(fileName)
    }

    static func persistTempRecording(from tempURL: URL) throws -> String {
        let fileName = tempURL.lastPathComponent
        let destination = url(for: fileName)
        if tempURL != destination {
            if FileManager.default.fileExists(atPath: destination.path) {
                try FileManager.default.removeItem(at: destination)
            }
            try FileManager.default.moveItem(at: tempURL, to: destination)
        }
        return fileName
    }

    static func deleteRecording(named fileName: String) {
        let fileURL = url(for: fileName)
        try? FileManager.default.removeItem(at: fileURL)
    }
}
