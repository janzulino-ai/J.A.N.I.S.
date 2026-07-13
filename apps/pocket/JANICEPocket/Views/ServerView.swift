import SwiftUI

/// Dashboard server — uplink JARVIS verso hub JANIS.
struct ServerView: View {
    @ObservedObject private var hub = JaniceHubMonitor.shared
    @ObservedObject private var brain = BrainStateController.shared

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    uplinkPanel
                    neuralCorePanel
                    fleetPanel
                    jobsPanel
                    if !hub.snapshot.rawJSON.isEmpty {
                        rawPanel
                    }
                }
                .padding()
            }
            .jarvisNavTitle("Server")
            .jarvisScreen()
            .refreshable { await hub.refresh() }
            .task {
                await hub.refresh()
                while !Task.isCancelled {
                    await hub.refresh()
                    try? await Task.sleep(nanoseconds: 5_000_000_000)
                }
            }
        }
    }

    private var uplinkPanel: some View {
        JarvisPanel(title: "Uplink Status", subtitle: hub.serverURL) {
            HStack {
                JarvisStatusDot(online: hub.isReachable)
                Text(hub.isReachable ? "JANIS HUB ONLINE" : "NO SIGNAL")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(hub.isReachable ? JaniceColors.online : JaniceColors.alert)
                Spacer()
                if hub.isLoading {
                    ProgressView().tint(JaniceColors.accent).controlSize(.small)
                }
            }
            if !hub.snapshot.version.isEmpty {
                JarvisDataRow(key: "Hub Version", value: hub.snapshot.version)
            }
            if let at = hub.lastRefresh {
                JarvisDataRow(key: "Last Ping", value: at.formatted(date: .omitted, time: .shortened))
            }
            if !hub.errorMessage.isEmpty {
                Text(hub.errorMessage.uppercased())
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(JaniceColors.alert)
            }
        }
    }

    private var neuralCorePanel: some View {
        JarvisPanel(title: "Neural Core", subtitle: "WebSocket stream") {
            HStack {
                modeBadge(brain.mode.rawValue)
                Spacer()
                Text("\(brain.nodeCount) NODES")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(JaniceColors.textSecondary)
            }
            ProgressView(value: brain.knowledgeLevel)
                .tint(JaniceColors.accent)
            Text(String(format: "KNOWLEDGE MATRIX %.0f%%", brain.knowledgeLevel * 100))
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(JaniceColors.textSecondary)
            if !brain.lastEventLabel.isEmpty {
                JarvisDataRow(key: "Last Event", value: brain.lastEventLabel)
            }
            if !brain.fleetJobStatus.isEmpty {
                JarvisDataRow(key: "Fleet Job", value: brain.fleetJobStatus)
            }
        }
    }

    private func modeBadge(_ mode: String) -> some View {
        Text(mode)
            .font(.system(size: 10, weight: .bold, design: .monospaced))
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .foregroundStyle(JaniceColors.accent)
            .background {
                Capsule().stroke(JaniceColors.accent.opacity(0.5), lineWidth: 1)
                    .background(JaniceColors.accent.opacity(0.1))
            }
    }

    private var fleetPanel: some View {
        JarvisPanel(title: "Fleet Grid") {
            if hub.snapshot.nodes.isEmpty {
                Text("NO NODES REPORTED")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(JaniceColors.textSecondary)
            } else {
                ForEach(hub.snapshot.nodes) { node in
                    HStack {
                        Image(systemName: iconForNode(node.id))
                            .foregroundStyle(JaniceColors.accent)
                            .frame(width: 22)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(node.label.uppercased())
                                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                .foregroundStyle(JaniceColors.textPrimary)
                            if !node.detail.isEmpty {
                                Text(node.detail)
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundStyle(JaniceColors.textSecondary)
                            }
                        }
                        Spacer()
                        Text(node.status.uppercased())
                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                            .foregroundStyle(statusColor(node.status))
                    }
                    .padding(.vertical, 6)
                }
            }
        }
    }

    private var jobsPanel: some View {
        JarvisPanel(title: "Orchestration") {
            if hub.snapshot.jobs.isEmpty && brain.fleetJobStatus.isEmpty {
                Text("NO ACTIVE JOBS")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(JaniceColors.textSecondary)
            } else {
                ForEach(hub.snapshot.jobs, id: \.self) { job in
                    Text(job.uppercased())
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundStyle(JaniceColors.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 4)
                }
            }
        }
    }

    private var rawPanel: some View {
        JarvisPanel(title: "Raw Feed") {
            Text(prettyJSON(hub.snapshot.rawJSON))
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(JaniceColors.textSecondary)
                .textSelection(.enabled)
        }
    }

    private func statusColor(_ status: String) -> Color {
        let s = status.lowercased()
        if s.contains("online") || s.contains("ok") { return JaniceColors.online }
        if s.contains("busy") || s.contains("run") { return JaniceColors.accent }
        return JaniceColors.alert
    }

    private func iconForNode(_ id: String) -> String {
        let lower = id.lowercased()
        if lower.contains("mac") { return "desktopcomputer" }
        if lower.contains("win") { return "pc" }
        if lower.contains("server") { return "server.rack" }
        return "circle.hexagonpath"
    }

    private func prettyJSON(_ dict: [String: Any]) -> String {
        guard !dict.isEmpty,
              let data = try? JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted, .sortedKeys]),
              let str = String(data: data, encoding: .utf8) else { return "{}" }
        return str
    }
}

#Preview {
    ServerView()
}
