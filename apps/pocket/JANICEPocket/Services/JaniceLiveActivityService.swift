import ActivityKit
import Foundation

/// Live Activity — brain + job fleet su Lock Screen / Dynamic Island.
@MainActor
final class JaniceLiveActivityService: ObservableObject {
    static let shared = JaniceLiveActivityService()

    @Published private(set) var isActive = false
    @Published private(set) var isEnabled: Bool

    private var activity: Activity<JaniceBrainActivityAttributes>?

    private init() {
        isEnabled = UserDefaults.standard.object(forKey: "janiceLiveActivityEnabled") as? Bool ?? true
    }

    func setEnabled(_ value: Bool) {
        isEnabled = value
        UserDefaults.standard.set(value, forKey: "janiceLiveActivityEnabled")
        if !value { end() }
    }

    func sync(from brain: BrainStateController) {
        guard isEnabled else { return }
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }

        let state = JaniceBrainActivityAttributes.ContentState(
            mode: brain.mode.rawValue,
            jobStatus: brain.fleetJobStatus,
            eventLabel: brain.lastEventLabel,
            nodeCount: brain.nodeCount
        )
        let content = ActivityContent(state: state, staleDate: Date().addingTimeInterval(120))

        if let activity {
            Task { await activity.update(content) }
            isActive = true
            return
        }

        let attributes = JaniceBrainActivityAttributes(deviceName: UserIdentityService.shared.displayName)
        do {
            activity = try Activity.request(attributes: attributes, content: content, pushType: nil)
            isActive = true
        } catch {
            isActive = false
        }
    }

    func end() {
        guard let activity else {
            isActive = false
            return
        }
        Task {
            await activity.end(nil, dismissalPolicy: .immediate)
            await MainActor.run {
                self.activity = nil
                self.isActive = false
            }
        }
    }
}
