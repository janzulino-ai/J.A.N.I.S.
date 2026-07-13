import AVFoundation
import CoreLocation
import CoreMotion
import Foundation
import UIKit
import UserNotifications

/// Sensori iPhone — occhi, orecchie e contesto per JANIS.
@MainActor
final class JaniceSensorHub: NSObject, ObservableObject {
    static let shared = JaniceSensorHub()

    @Published private(set) var isRunning = false
    @Published private(set) var lastTelemetryAt: Date?
    @Published private(set) var queuedTelemetryCount = 0
    @Published private(set) var lastCommandLabel = ""
    @Published private(set) var activityLabel = "unknown"
    @Published private(set) var stepCount: Int = 0
    @Published private(set) var distanceMeters: Double = 0
    @Published private(set) var lastLocationSummary = "—"
    @Published private(set) var lastHeadingDegrees: Double?

    private let locationManager = CLLocationManager()
    private let motionManager = CMMotionManager()
    private let activityManager = CMMotionActivityManager()
    private let pedometer = CMPedometer()
    private var telemetryTask: Task<Void, Never>?
    private var bridgeTask: Task<Void, Never>?
    private var lastLocation: CLLocation?
    private var lastHeading: CLHeading?
    private let queueKey = "janiceTelemetryQueue"

    private override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
        locationManager.allowsBackgroundLocationUpdates = false
        locationManager.pausesLocationUpdatesAutomatically = true
        UIDevice.current.isBatteryMonitoringEnabled = true
        queuedTelemetryCount = loadQueue().count
    }

    func start() {
        guard !isRunning else { return }
        isRunning = true
        requestPermissions()
        startLocation()
        startMotionSampling()
        startPedometer()
        startActivityUpdates()

        telemetryTask = Task {
            while !Task.isCancelled {
                await HealthKitService.shared.refreshSteps()
                await sendTelemetry()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
        bridgeTask = Task {
            while !Task.isCancelled {
                await pollBridgeCommands()
                try? await Task.sleep(nanoseconds: 8_000_000_000)
            }
        }
    }

    func stop() {
        isRunning = false
        telemetryTask?.cancel()
        bridgeTask?.cancel()
        locationManager.stopUpdatingLocation()
        motionManager.stopAccelerometerUpdates()
        activityManager.stopActivityUpdates()
        pedometer.stopUpdates()
    }

    func flushTelemetry() async {
        await sendTelemetry()
        await drainQueue()
    }

    func setBackgroundLocationEnabled(_ enabled: Bool) {
        UserDefaults.standard.set(enabled, forKey: "janiceBackgroundLocation")
        if enabled {
            locationManager.requestAlwaysAuthorization()
            locationManager.allowsBackgroundLocationUpdates = true
        } else {
            locationManager.allowsBackgroundLocationUpdates = false
            locationManager.requestWhenInUseAuthorization()
        }
        if isRunning { startLocation() }
    }

    /// Snapshot live per dashboard Client.
    func clientDashboardRows() -> [(String, String)] {
        let battery = UIDevice.current.batteryLevel >= 0
            ? "\(Int(UIDevice.current.batteryLevel * 100))%"
            : "—"
        let net = NetworkMonitorService.shared.snapshot()
        let iface = (net["interface"] as? String) ?? "—"
        let connected = (net["connected"] as? Bool) == true ? "OK" : "Off"
        let env = JaniceEnvironmentService.shared
        var rows: [(String, String)] = [
            ("Hub", isRunning ? "ONLINE" : "STANDBY"),
            ("Power", battery),
            ("Network", "\(iface) · \(connected)"),
            ("Motion", activityLabel),
            ("Steps", "\(stepCount)"),
            ("Distance", String(format: "%.0f m", distanceMeters)),
            ("Position", lastLocationSummary),
            ("Telemetry", lastTelemetryAt?.formatted(date: .omitted, time: .shortened) ?? "—"),
            ("Buffer", "\(queuedTelemetryCount)"),
            ("Bridge", lastCommandLabel.isEmpty ? "—" : lastCommandLabel),
            ("Transcribe", PocketTranscriptionService.shared.modelReady ? "WHISPERKIT" : "REMOTE"),
            ("Auth", UserIdentityService.shared.isVerified ? "OK" : "LOCKED"),
            ("Push", JanicePushService.shared.isRegistered ? "REGISTERED" : "—"),
            ("HUD", JaniceLiveActivityService.shared.isActive ? "ACTIVE" : "—"),
        ]
        if let h = lastHeadingDegrees {
            rows.append(("Heading", String(format: "%.0f°", h)))
        }
        if let p = env.pressureKPa {
            rows.append(("Pressure", String(format: "%.1f kPa", p)))
        }
        if HealthKitService.shared.isEnabled {
            rows.append(("HealthKit", "\(HealthKitService.shared.stepCount) steps"))
        }
        return rows
    }

    func refreshClientDashboard() async {
        await HealthKitService.shared.refreshSteps()
        updateLocationSummary()
    }

    private func updateLocationSummary() {
        guard let loc = lastLocation else {
            lastLocationSummary = "In attesa GPS…"
            return
        }
        lastLocationSummary = String(
            format: "%.5f, %.5f (±%.0fm)",
            loc.coordinate.latitude,
            loc.coordinate.longitude,
            loc.horizontalAccuracy
        )
    }

    // MARK: - Telemetry

    private func sendTelemetry() async {
        let payload = buildTelemetryPayload()
        let ok = await JaniceAPIClient.shared.postTelemetry(payload)
        if ok {
            lastTelemetryAt = .now
            await drainQueue()
        } else {
            enqueueTelemetry(payload)
        }
    }

    func buildTelemetryPayload() -> [String: Any] {
        var motion: [String: Double] = [:]
        if let data = motionManager.accelerometerData {
            motion = ["x": data.acceleration.x, "y": data.acceleration.y, "z": data.acceleration.z]
        }
        var location: [String: Any] = [:]
        if let loc = lastLocation {
            location = [
                "lat": loc.coordinate.latitude,
                "lon": loc.coordinate.longitude,
                "accuracy": loc.horizontalAccuracy,
                "altitude": loc.altitude,
                "speed": loc.speed,
            ]
        }
        return [
            "battery": UIDevice.current.batteryLevel >= 0 ? Double(UIDevice.current.batteryLevel) : -1,
            "battery_state": UIDevice.current.batteryState.rawValue,
            "thermal": ProcessInfo.processInfo.thermalState.rawValue,
            "low_power": ProcessInfo.processInfo.isLowPowerModeEnabled,
            "motion": motion,
            "location": location,
            "environment": JaniceEnvironmentService.shared.snapshot(heading: lastHeading),
            "activity": activityLabel,
            "steps_today": stepCount,
            "distance_m": distanceMeters,
            "network": NetworkMonitorService.shared.snapshot(),
            "health": HealthKitService.shared.snapshot(),
            "owner": UserIdentityService.shared.identityPayload(),
            "body": JaniceBodyManifest.snapshot(),
            "surface": "mobile",
            "capabilities": JaniceBodyManifest.bridgeActions,
        ]
    }

    private func enqueueTelemetry(_ payload: [String: Any]) {
        var queue = loadQueue()
        queue.append(payload)
        if queue.count > 50 { queue.removeFirst(queue.count - 50) }
        saveQueue(queue)
        queuedTelemetryCount = queue.count
    }

    private func drainQueue() async {
        var queue = loadQueue()
        guard !queue.isEmpty else { return }
        var remaining: [[String: Any]] = []
        for item in queue {
            let ok = await JaniceAPIClient.shared.postTelemetry(item)
            if !ok { remaining.append(item) }
        }
        saveQueue(remaining)
        queuedTelemetryCount = remaining.count
    }

    private func loadQueue() -> [[String: Any]] {
        guard let data = UserDefaults.standard.data(forKey: queueKey),
              let arr = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return []
        }
        return arr
    }

    private func saveQueue(_ queue: [[String: Any]]) {
        if let data = try? JSONSerialization.data(withJSONObject: queue) {
            UserDefaults.standard.set(data, forKey: queueKey)
        }
    }

    // MARK: - ios_bridge

    private func pollBridgeCommands() async {
        let commands = await JaniceAPIClient.shared.fetchPendingCommands()
        for cmd in commands {
            lastCommandLabel = cmd.action
            let result = await execute(command: cmd)
            await JaniceAPIClient.shared.completeCommand(id: cmd.id, result: result)
        }
    }

    func execute(command: IOSBridgeCommand) async -> [String: Any] {
        let action = command.action.lowercased()
        let params = command.params ?? [:]
        switch action {
        case "notify":
            return await notify(title: params["title"] ?? "JANIS", body: params["body"] ?? params["text"] ?? "")
        case "speak":
            return JaniceMouthService.shared.speak(
                text: params["text"] ?? params["message"] ?? "",
                language: params["language"] ?? "it-IT"
            )
        case "stop_speak":
            return JaniceMouthService.shared.stop()
        case "open_url":
            return await openURL(params["url"] ?? "")
        case "get_location":
            return locationResult()
        case "get_heading":
            return headingResult()
        case "get_battery":
            return batteryResult()
        case "get_motion":
            return motionResult()
        case "get_network":
            return ["ok": true, "network": NetworkMonitorService.shared.snapshot()]
        case "get_environment":
            return ["ok": true, "environment": JaniceEnvironmentService.shared.snapshot(heading: lastHeading)]
        case "get_altitude":
            return altitudeResult()
        case "get_brightness", "get_orientation":
            return ["ok": true, "environment": JaniceEnvironmentService.shared.snapshot(heading: lastHeading)]
        case "vibrate":
            return vibrate(style: params["style"] ?? "medium")
        case "camera_snap", "get_vision":
            return await cameraSnap(upload: params["upload"] == "1")
        case "scan_qr":
            return await JaniceQRService.scanFromPhoto()
        case "torch_on":
            return JaniceReachService.shared.setTorch(on: true)
        case "torch_off":
            return JaniceReachService.shared.setTorch(on: false)
        case "get_clipboard":
            return JaniceReachService.shared.getClipboard()
        case "set_clipboard":
            return JaniceReachService.shared.setClipboard(text: params["text"] ?? "")
        case "get_calendar":
            let days = Int(params["days"] ?? "3") ?? 3
            return JaniceCalendarService.shared.upcomingEvents(days: days)
        case "search_contacts":
            return JaniceContactsService.shared.search(query: params["query"] ?? params["name"] ?? "")
        case "register_push":
            return await JanicePushService.shared.registerAction()
        case "body_manifest":
            return ["ok": true, "body": JaniceBodyManifest.snapshot()]
        case "whoami", "get_identity":
            return ["ok": true, "identity": UserIdentityService.shared.identityPayload()]
        case "authenticate":
            let ok = await UserIdentityService.shared.authenticate()
            return ["ok": ok, "identity": UserIdentityService.shared.identityPayload()]
        default:
            return ["ok": false, "error": "unknown_action", "action": action]
        }
    }

    private func notify(title: String, body: String) async -> [String: Any] {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        do {
            try await UNUserNotificationCenter.current().add(request)
            return ["ok": true]
        } catch {
            return ["ok": false, "error": error.localizedDescription]
        }
    }

    private func headingResult() -> [String: Any] {
        guard let h = lastHeading, h.trueHeading >= 0 else {
            return ["ok": false, "error": "no_heading"]
        }
        return [
            "ok": true,
            "true": h.trueHeading,
            "magnetic": h.magneticHeading,
            "accuracy": h.headingAccuracy,
        ]
    }

    private func altitudeResult() -> [String: Any] {
        var result: [String: Any] = ["ok": true]
        if let loc = lastLocation { result["gps_altitude"] = loc.altitude }
        if let rel = JaniceEnvironmentService.shared.relativeAltitude {
            result["barometer_relative_m"] = rel
        }
        if let p = JaniceEnvironmentService.shared.pressureKPa {
            result["pressure_kpa"] = p
        }
        return result
    }

    private func openURL(_ raw: String) async -> [String: Any] {
        guard let url = URL(string: raw), await UIApplication.shared.open(url) else {
            return ["ok": false, "error": "invalid_url"]
        }
        return ["ok": true, "url": raw]
    }

    private func locationResult() -> [String: Any] {
        guard let loc = lastLocation else { return ["ok": false, "error": "no_location"] }
        return [
            "ok": true,
            "lat": loc.coordinate.latitude,
            "lon": loc.coordinate.longitude,
            "accuracy": loc.horizontalAccuracy,
        ]
    }

    private func batteryResult() -> [String: Any] {
        [
            "ok": true,
            "level": UIDevice.current.batteryLevel,
            "state": UIDevice.current.batteryState.rawValue,
            "thermal": ProcessInfo.processInfo.thermalState.rawValue,
        ]
    }

    private func motionResult() -> [String: Any] {
        [
            "ok": true,
            "activity": activityLabel,
            "steps_today": stepCount,
            "distance_m": distanceMeters,
        ]
    }

    private func vibrate(style: String) -> [String: Any] {
        let generator: UIImpactFeedbackGenerator
        switch style.lowercased() {
        case "light": generator = UIImpactFeedbackGenerator(style: .light)
        case "heavy": generator = UIImpactFeedbackGenerator(style: .heavy)
        default: generator = UIImpactFeedbackGenerator(style: .medium)
        }
        generator.impactOccurred()
        return ["ok": true]
    }

    private func cameraSnap(upload: Bool) async -> [String: Any] {
        guard let b64 = await JaniceVisionService.shared.captureJPEGBase64() else {
            return ["ok": false, "error": "camera_failed"]
        }
        if upload {
            let ok = await JaniceAPIClient.shared.postVision(jpegBase64: b64)
            return ["ok": ok, "uploaded": ok, "bytes": b64.count]
        }
        return ["ok": true, "image_base64": b64, "bytes": b64.count]
    }

    // MARK: - Sensors

    private func requestPermissions() {
        locationManager.requestWhenInUseAuthorization()
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
        if UserDefaults.standard.bool(forKey: "janiceBackgroundLocation") {
            setBackgroundLocationEnabled(true)
        }
    }

    private func startLocation() {
        locationManager.startUpdatingLocation()
        if CLLocationManager.headingAvailable() {
            locationManager.startUpdatingHeading()
        }
    }

    private func startMotionSampling() {
        guard motionManager.isAccelerometerAvailable else { return }
        motionManager.accelerometerUpdateInterval = 1
        motionManager.startAccelerometerUpdates()
    }

    private func startPedometer() {
        guard CMPedometer.isStepCountingAvailable() else { return }
        let start = Calendar.current.startOfDay(for: .now)
        pedometer.startUpdates(from: start) { [weak self] data, _ in
            guard let data else { return }
            Task { @MainActor in
                self?.stepCount = data.numberOfSteps.intValue
                self?.distanceMeters = data.distance?.doubleValue ?? 0
            }
        }
    }

    private func startActivityUpdates() {
        guard CMMotionActivityManager.isActivityAvailable() else { return }
        activityManager.startActivityUpdates(to: .main) { [weak self] activity in
            guard let activity else { return }
            Task { @MainActor in
                if activity.walking { self?.activityLabel = "walking" }
                else if activity.running { self?.activityLabel = "running" }
                else if activity.automotive { self?.activityLabel = "automotive" }
                else if activity.stationary { self?.activityLabel = "stationary" }
                else { self?.activityLabel = "unknown" }
            }
        }
    }
}

extension JaniceSensorHub: CLLocationManagerDelegate {
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        Task { @MainActor in
            self.lastLocation = loc
            self.updateLocationSummary()
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateHeading newHeading: CLHeading) {
        Task { @MainActor in
            self.lastHeading = newHeading
            if newHeading.trueHeading >= 0 {
                self.lastHeadingDegrees = newHeading.trueHeading
            }
        }
    }
}
