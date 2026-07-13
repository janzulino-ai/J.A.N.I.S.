import CoreLocation
import CoreMotion
import Foundation
import UIKit

/// Naso + contesto ambientale — pressione, orientamento, luminosità.
@MainActor
final class JaniceEnvironmentService: ObservableObject {
    static let shared = JaniceEnvironmentService()

    @Published private(set) var pressureKPa: Double?
    @Published private(set) var relativeAltitude: Double?
    @Published private(set) var isBarometerAvailable = false

    private let altimeter = CMAltimeter()

    private init() {
        isBarometerAvailable = CMAltimeter.isRelativeAltitudeAvailable()
        if isBarometerAvailable {
            altimeter.startRelativeAltitudeUpdates(to: .main) { [weak self] data, _ in
                guard let data else { return }
                Task { @MainActor in
                    self?.pressureKPa = data.pressure.doubleValue
                    self?.relativeAltitude = data.relativeAltitude.doubleValue
                }
            }
        }
    }

    func snapshot(heading: CLHeading?) -> [String: Any] {
        var env: [String: Any] = [
            "orientation": orientationLabel(),
            "brightness": UIScreen.main.brightness,
            "low_power": ProcessInfo.processInfo.isLowPowerModeEnabled,
            "thermal": ProcessInfo.processInfo.thermalState.rawValue,
        ]
        if let pressureKPa { env["pressure_kpa"] = pressureKPa }
        if let relativeAltitude { env["relative_altitude_m"] = relativeAltitude }
        if let heading, heading.trueHeading >= 0 {
            env["heading_true"] = heading.trueHeading
            env["heading_magnetic"] = heading.magneticHeading
        }
        return env
    }

    private func orientationLabel() -> String {
        switch UIDevice.current.orientation {
        case .portrait: return "portrait"
        case .portraitUpsideDown: return "portrait_upside_down"
        case .landscapeLeft: return "landscape_left"
        case .landscapeRight: return "landscape_right"
        case .faceUp: return "face_up"
        case .faceDown: return "face_down"
        default: return "unknown"
        }
    }
}
