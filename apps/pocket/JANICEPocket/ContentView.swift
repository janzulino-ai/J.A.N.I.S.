import SwiftData
import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @State private var showSplash = true

    var body: some View {
        ZStack {
            JaniceColors.bg.ignoresSafeArea()

            if showSplash {
                JaniceSplashView(onFinished: {
                    withAnimation(.easeOut(duration: 0.35)) {
                        showSplash = false
                    }
                })
                .transition(.opacity)
            } else {
                MainTabView()
                    .transition(.opacity)
            }
        }
        .preferredColorScheme(.dark)
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                JaniceSensorHub.shared.start()
            case .background:
                Task { await JaniceSensorHub.shared.flushTelemetry() }
                JaniceLiveActivityService.shared.sync(from: BrainStateController.shared)
            default:
                break
            }
        }
        .task {
            _ = NetworkMonitorService.shared
            _ = JaniceEnvironmentService.shared
            JaniceSensorHub.shared.start()
            JanicePushService.shared.requestRegistration()
            if UserDefaults.standard.bool(forKey: "janiceCalendarEnabled") {
                await JaniceCalendarService.shared.requestAccess()
            }
            if UserDefaults.standard.bool(forKey: "janiceContactsEnabled") {
                await JaniceContactsService.shared.requestAccess()
            }
            if UserIdentityService.shared.requireBiometric {
                _ = await UserIdentityService.shared.authenticate(reason: "Benvenuto in JANICE Pocket")
            }
            await PocketTranscriptionService.shared.prepareModelIfNeeded()
            JaniceLiveActivityService.shared.sync(from: BrainStateController.shared)
        }
    }
}

#Preview {
    ContentView()
        .modelContainer(for: ChatMessage.self, inMemory: true)
}
