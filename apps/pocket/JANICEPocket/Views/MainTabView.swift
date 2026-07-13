import SwiftData
import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            ChatView()
                .tabItem {
                    Label("Interface", systemImage: "cpu")
                }

            ClientView()
                .tabItem {
                    Label("Client", systemImage: "iphone.gen3.radiowaves.left.and.right")
                }

            ServerView()
                .tabItem {
                    Label("Server", systemImage: "server.rack")
                }

            SettingsView()
                .tabItem {
                    Label("Impostazioni", systemImage: "gearshape")
                }
        }
        .tint(JaniceColors.accent)
        .onAppear {
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = JaniceColors.uiBg
            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
    }
}

#Preview {
    MainTabView()
        .modelContainer(for: ChatMessage.self, inMemory: true)
}
