import ActivityKit
import Foundation

/// Attributi condivisi app + widget per Live Activity brain/fleet.
struct JaniceBrainActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var mode: String
        var jobStatus: String
        var eventLabel: String
        var nodeCount: Int
    }

    var deviceName: String
}
