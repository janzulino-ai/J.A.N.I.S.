import BackgroundTasks
import Foundation

/// Presenza in background — bridge poll quando l'app è sospesa.
enum JaniceBackgroundRefresh {
    static let taskId = "ai.janzulino.janice.pocket.refresh"

    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskId, using: nil) { task in
            guard let refresh = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            handle(refresh)
        }
    }

    static func schedule() {
        let request = BGAppRefreshTaskRequest(identifier: taskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }

    private static func handle(_ task: BGAppRefreshTask) {
        schedule()
        let work = Task {
            await MainActor.run {
                JaniceSensorHub.shared.start()
            }
            await JaniceSensorHub.shared.flushTelemetry()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = {
            work.cancel()
        }
    }
}
