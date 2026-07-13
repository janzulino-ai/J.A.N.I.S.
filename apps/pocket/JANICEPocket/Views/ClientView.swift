import SwiftUI

/// Dashboard client — HUD portatile stile JARVIS.
struct ClientView: View {
    @ObservedObject private var sensors = JaniceSensorHub.shared
    @ObservedObject private var identity = UserIdentityService.shared
    @ObservedObject private var mouth = JaniceMouthService.shared
    @ObservedObject private var ears = PocketTranscriptionService.shared
    @ObservedObject private var network = NetworkMonitorService.shared

    @State private var statusMessage = ""

    private var batteryProgress: Double {
        let level = UIDevice.current.batteryLevel
        return level >= 0 ? Double(level) : 0
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    heroHUD
                    metricsRow
                    telemetryPanel
                    commandPanel
                    if !statusMessage.isEmpty {
                        Text(statusMessage.uppercased())
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundStyle(JaniceColors.accent)
                            .frame(maxWidth: .infinity, alignment: .center)
                    }
                }
                .padding()
            }
            .jarvisNavTitle("Client")
            .jarvisScreen()
            .refreshable { await sensors.refreshClientDashboard() }
            .task {
                if !sensors.isRunning { sensors.start() }
                await sensors.refreshClientDashboard()
                while !Task.isCancelled {
                    await sensors.refreshClientDashboard()
                    try? await Task.sleep(nanoseconds: 5_000_000_000)
                }
            }
        }
    }

    private var heroHUD: some View {
        JarvisPanel(title: "Mobile Interface", subtitle: JaniceAPIClient.deviceID) {
            HStack(spacing: 20) {
                ZStack {
                    JarvisArcRing(progress: batteryProgress, size: 108)
                    VStack(spacing: 2) {
                        Text(batteryLabel)
                            .font(.system(size: 22, weight: .bold, design: .monospaced))
                            .foregroundStyle(JaniceColors.textPrimary)
                        Text("POWER")
                            .font(.system(size: 8, weight: .medium, design: .monospaced))
                            .foregroundStyle(JaniceColors.textSecondary)
                    }
                }
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        JarvisStatusDot(online: sensors.isRunning)
                        Text(sensors.isRunning ? "SYSTEMS ONLINE" : "STANDBY")
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .foregroundStyle(sensors.isRunning ? JaniceColors.online : JaniceColors.alert)
                    }
                    Text(identity.displayName.uppercased())
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundStyle(JaniceColors.textPrimary)
                    Text(identity.isVerified ? "OPERATOR VERIFIED" : "AUTH REQUIRED")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(identity.isVerified ? JaniceColors.online : JaniceColors.alert)
                    Text("LOCAL SENSORS · TELEMETRY · BRIDGE")
                        .font(.system(size: 8, design: .monospaced))
                        .foregroundStyle(JaniceColors.textSecondary)
                }
                Spacer(minLength: 0)
            }
        }
    }

    private var batteryLabel: String {
        let level = UIDevice.current.batteryLevel
        return level >= 0 ? "\(Int(level * 100))%" : "—"
    }

    private var metricsRow: some View {
        HStack(spacing: 8) {
            JarvisMetricChip(
                label: "Network",
                value: network.isConnected ? network.interfaceType.uppercased() : "OFF",
                icon: "dot.radiowaves.left.and.right"
            )
            JarvisMetricChip(label: "Steps", value: "\(sensors.stepCount)", icon: "figure.walk")
            JarvisMetricChip(label: "Queue", value: "\(sensors.queuedTelemetryCount)", icon: "tray.full")
            JarvisMetricChip(
                label: "STT",
                value: ears.modelReady ? "LOCAL" : "REMOTE",
                icon: "waveform"
            )
        }
    }

    private var telemetryPanel: some View {
        JarvisPanel(title: "Telemetry Feed", subtitle: "Live diagnostics") {
            VStack(spacing: 0) {
                ForEach(Array(sensors.clientDashboardRows().enumerated()), id: \.offset) { idx, row in
                    JarvisDataRow(key: row.0, value: row.1)
                    if idx < sensors.clientDashboardRows().count - 1 {
                        Divider().overlay(JaniceColors.hudDim)
                    }
                }
            }
        }
    }

    private var commandPanel: some View {
        JarvisPanel(title: "Command Deck") {
            VStack(spacing: 10) {
                HStack(spacing: 10) {
                    JarvisCommandButton(title: "Boot Systems", icon: "power") {
                        sensors.start()
                        statusMessage = "Systems online."
                    }
                    JarvisCommandButton(title: "Transmit", icon: "arrow.up") {
                        Task {
                            await sensors.flushTelemetry()
                            statusMessage = "Telemetry transmitted."
                        }
                    }
                }
                HStack(spacing: 10) {
                    JarvisCommandButton(title: "Haptic", icon: "hand.tap") {
                        Task {
                            _ = await sensors.execute(command: IOSBridgeCommand(id: UUID().uuidString, action: "vibrate"))
                            statusMessage = "Haptic pulse sent."
                        }
                    }
                    JarvisCommandButton(title: "Voice Test", icon: "speaker.wave.2") {
                        _ = mouth.speak(text: "Mobile interface active.")
                        statusMessage = "Audio output test."
                    }
                }
                if mouth.isSpeaking {
                    Label("AUDIO OUTPUT ACTIVE", systemImage: "waveform")
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundStyle(JaniceColors.accent)
                }
                if ears.isLoadingModel {
                    Label(ears.progressMessage.uppercased(), systemImage: "waveform.badge.mic")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(JaniceColors.accent)
                }
            }
        }
    }
}

#Preview {
    ClientView()
}
