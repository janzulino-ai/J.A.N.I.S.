import Foundation

#if canImport(HealthKit)
import HealthKit
#endif

/// Passi e attività da HealthKit (opt-in).
@MainActor
final class HealthKitService: ObservableObject {
    static let shared = HealthKitService()

    @Published private(set) var isAuthorized = false
    @Published private(set) var stepCount: Int = 0
    @Published private(set) var lastError = ""

    var isEnabled: Bool {
        UserDefaults.standard.bool(forKey: "janiceHealthKitEnabled")
    }

    private init() {}

    func setEnabled(_ enabled: Bool) {
        UserDefaults.standard.set(enabled, forKey: "janiceHealthKitEnabled")
        if enabled {
            Task { await requestAuthorization() }
        }
    }

    func requestAuthorization() async {
#if canImport(HealthKit)
        guard HKHealthStore.isHealthDataAvailable() else {
            lastError = "HealthKit non disponibile"
            return
        }
        let store = HKHealthStore()
        let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        do {
            try await store.requestAuthorization(toShare: [], read: [stepType])
            isAuthorized = true
            await refreshSteps()
        } catch {
            lastError = error.localizedDescription
            isAuthorized = false
        }
#else
        lastError = "HealthKit non compilato"
#endif
    }

    func refreshSteps() async {
#if canImport(HealthKit)
        guard isEnabled, HKHealthStore.isHealthDataAvailable() else { return }
        let store = HKHealthStore()
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return }
        let start = Calendar.current.startOfDay(for: .now)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: .now)
        await withCheckedContinuation { (cont: CheckedContinuation<Void, Never>) in
            let query = HKStatisticsQuery(
                quantityType: stepType,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, stats, _ in
                Task { @MainActor in
                    if let sum = stats?.sumQuantity() {
                        self.stepCount = Int(sum.doubleValue(for: .count()))
                    }
                    cont.resume()
                }
            }
            store.execute(query)
        }
#else
        stepCount = 0
#endif
    }

    func snapshot() -> [String: Any] {
        [
            "enabled": isEnabled,
            "authorized": isAuthorized,
            "steps_today": stepCount,
        ]
    }
}
