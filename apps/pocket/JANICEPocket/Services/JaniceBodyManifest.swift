import Foundation

/// Mappa organi sensoriali/attuatori — contratto verso JANIS.
enum JaniceBodyPart: String, CaseIterable, Identifiable {
    case eyes
    case ears
    case mouth
    case nose
    case touch
    case mind
    case pulse
    case reach
    case calendar
    case contacts
    case push

    var id: String { rawValue }

    var label: String {
        switch self {
        case .eyes: return "Occhi"
        case .ears: return "Orecchie"
        case .mouth: return "Bocca"
        case .nose: return "Naso"
        case .touch: return "Tatto"
        case .mind: return "Mente"
        case .pulse: return "Polso"
        case .reach: return "Braccia"
        case .calendar: return "Agenda"
        case .contacts: return "Rubrica"
        case .push: return "Presenza"
        }
    }

    var icon: String {
        switch self {
        case .eyes: return "eye.fill"
        case .ears: return "ear.fill"
        case .mouth: return "mouth.fill"
        case .nose: return "aqi.medium"
        case .touch: return "hand.tap.fill"
        case .mind: return "brain.head.profile"
        case .pulse: return "heart.fill"
        case .reach: return "hand.raised.fill"
        case .calendar: return "calendar"
        case .contacts: return "person.crop.circle"
        case .push: return "bell.badge.fill"
        }
    }
}

enum JaniceBodyManifest {
    static let bridgeActions: [String] = [
        "notify", "speak", "stop_speak", "open_url",
        "get_location", "get_heading", "get_battery", "get_motion", "get_network",
        "get_environment", "get_altitude", "get_brightness", "get_orientation",
        "vibrate", "camera_snap", "scan_qr", "torch_on", "torch_off",
        "whoami", "authenticate",
        "get_clipboard", "set_clipboard",
        "get_calendar", "search_contacts",
        "register_push", "body_manifest",
    ]

    @MainActor
    static func organStatus() -> [JaniceBodyPart: String] {
        [
            .eyes: JaniceVisionService.shared.isCapturing ? "Cattura…" : (JaniceVisionService.shared.lastCaptureAt != nil ? "Pronto" : "Idle"),
            .ears: PocketTranscriptionService.shared.modelReady ? "WhisperKit" : "Server fallback",
            .mouth: JaniceMouthService.shared.isSpeaking ? "Parla…" : "Pronta",
            .nose: JaniceEnvironmentService.shared.isBarometerAvailable ? "Attivo" : "N/D",
            .touch: "Haptics",
            .mind: UserIdentityService.shared.isVerified ? "Verificato" : "Bloccato",
            .pulse: HealthKitService.shared.isEnabled ? "HealthKit" : "CoreMotion",
            .reach: "Clipboard/Torch",
            .calendar: JaniceCalendarService.shared.isAuthorized ? "Autorizzato" : "Off",
            .contacts: JaniceContactsService.shared.isAuthorized ? "Autorizzato" : "Off",
            .push: JanicePushService.shared.isRegistered ? "Push OK" : "Locale",
        ]
    }

    @MainActor
    static func snapshot() -> [String: Any] {
        var organs: [String: String] = [:]
        for (part, status) in organStatus() {
            organs[part.rawValue] = status
        }
        return [
            "organs": organs,
            "bridge_actions": bridgeActions,
            "device_id": JaniceAPIClient.deviceID,
            "version": "3.0.0",
        ]
    }
}
