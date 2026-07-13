import ActivityKit
import SwiftUI
import WidgetKit

struct JANICEPocketWidgetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: JaniceBrainActivityAttributes.self) { context in
            lockScreenView(context: context)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: icon(for: context.state.mode))
                        .foregroundStyle(Color(red: 0.24, green: 0.91, blue: 1.0))
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.mode)
                        .font(.caption.weight(.semibold))
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(alignment: .leading, spacing: 4) {
                        if !context.state.jobStatus.isEmpty {
                            Text(context.state.jobStatus)
                                .font(.caption2)
                        }
                        if !context.state.eventLabel.isEmpty {
                            Text(context.state.eventLabel)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            } compactLeading: {
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(Color(red: 0.24, green: 0.91, blue: 1.0))
            } compactTrailing: {
                Text(shortMode(context.state.mode))
                    .font(.caption2.weight(.bold))
            } minimal: {
                Image(systemName: "circle.fill")
                    .foregroundStyle(color(for: context.state.mode))
            }
        }
    }

    @ViewBuilder
    private func lockScreenView(context: ActivityViewContext<JaniceBrainActivityAttributes>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon(for: context.state.mode))
                .font(.title2)
                .foregroundStyle(Color(red: 0.24, green: 0.91, blue: 1.0))
            VStack(alignment: .leading, spacing: 4) {
                Text("JANIS · \(context.state.mode)")
                    .font(.headline)
                if !context.state.jobStatus.isEmpty {
                    Text(context.state.jobStatus)
                        .font(.caption)
                } else if !context.state.eventLabel.isEmpty {
                    Text(context.state.eventLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Text("\(context.state.nodeCount) nodi")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(.vertical, 4)
        .activityBackgroundTint(Color(red: 0.04, green: 0.09, blue: 0.16))
    }

    private func icon(for mode: String) -> String {
        switch mode.uppercased() {
        case "ACTING": return "gearshape.2.fill"
        case "THINKING": return "brain.head.profile"
        default: return "circle.hexagonpath"
        }
    }

    private func shortMode(_ mode: String) -> String {
        switch mode.uppercased() {
        case "ACTING": return "ACT"
        case "THINKING": return "THK"
        default: return "IDL"
        }
    }

    private func color(for mode: String) -> Color {
        switch mode.uppercased() {
        case "ACTING": return .orange
        case "THINKING": return Color(red: 0.24, green: 0.91, blue: 1.0)
        default: return .green
        }
    }
}
