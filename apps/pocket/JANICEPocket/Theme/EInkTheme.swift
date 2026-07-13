import SwiftUI
import UIKit

// MARK: - JARVIS portable palette (Marvel HUD)

enum JaniceColors {
    static let accent = Color(red: 0.30, green: 0.82, blue: 1.0)       // arc cyan
    static let accentBright = Color(red: 0.55, green: 0.95, blue: 1.0)
    static let bg = Color(red: 0.01, green: 0.03, blue: 0.07)         // near black
    static let surface = Color(red: 0.03, green: 0.07, blue: 0.12)
    static let surfaceRaised = Color(red: 0.05, green: 0.10, blue: 0.16)
    static let hudLine = Color(red: 0.30, green: 0.82, blue: 1.0).opacity(0.35)
    static let hudDim = Color(red: 0.30, green: 0.82, blue: 1.0).opacity(0.12)
    static let textPrimary = Color(red: 0.86, green: 0.94, blue: 1.0)
    static let textSecondary = Color(red: 0.45, green: 0.62, blue: 0.74)
    static let alert = Color(red: 1.0, green: 0.45, blue: 0.25)
    static let online = Color(red: 0.2, green: 1.0, blue: 0.55)
    static let gold = Color(red: 1.0, green: 0.78, blue: 0.2)

    static let uiAccent = UIColor(red: 0.30, green: 0.82, blue: 1.0, alpha: 1)
    static let uiGold = UIColor(red: 1.0, green: 0.78, blue: 0.2, alpha: 1)
    static let uiBg = UIColor(red: 0.01, green: 0.03, blue: 0.07, alpha: 1)

    static let paper = textPrimary
    static let paperDeep = surfaceRaised
    static let ink = textPrimary
    static let inkSoft = textSecondary
    static let cyan = accent
    static let navy = bg
}

// MARK: - Background

struct JarvisScreenBackground: ViewModifier {
    func body(content: Content) -> some View {
        ZStack {
            LinearGradient(
                colors: [JaniceColors.bg, JaniceColors.surface, JaniceColors.bg],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            GeometryReader { geo in
                Path { path in
                    let step: CGFloat = 28
                    var y: CGFloat = 0
                    while y < geo.size.height {
                        path.move(to: CGPoint(x: 0, y: y))
                        path.addLine(to: CGPoint(x: geo.size.width, y: y))
                        y += step
                    }
                    var x: CGFloat = 0
                    while x < geo.size.width {
                        path.move(to: CGPoint(x: x, y: 0))
                        path.addLine(to: CGPoint(x: x, y: geo.size.height))
                        x += step
                    }
                }
                .stroke(JaniceColors.hudDim, lineWidth: 0.5)
            }
            .ignoresSafeArea()

            RadialGradient(
                colors: [JaniceColors.accent.opacity(0.08), .clear],
                center: .top,
                startRadius: 10,
                endRadius: 420
            )
            .ignoresSafeArea()

            content
        }
    }
}

extension View {
    func jarvisScreen() -> some View { modifier(JarvisScreenBackground()) }
    func janiceScreen() -> some View { jarvisScreen() }
    func eInkScreen() -> some View { jarvisScreen() }
}

// MARK: - HUD components

struct JarvisArcRing: View {
    var progress: Double
    var lineWidth: CGFloat = 3
    var size: CGFloat = 120

    var body: some View {
        ZStack {
            Circle()
                .stroke(JaniceColors.hudDim, lineWidth: 1)
            Circle()
                .trim(from: 0, to: min(max(progress, 0.04), 1))
                .stroke(
                    AngularGradient(
                        colors: [JaniceColors.accent.opacity(0.15), JaniceColors.accent, JaniceColors.accentBright],
                        center: .center
                    ),
                    style: StrokeStyle(lineWidth: lineWidth, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
                .shadow(color: JaniceColors.accent.opacity(0.45), radius: 6)
            Circle()
                .stroke(JaniceColors.accent.opacity(0.25), lineWidth: 0.5)
                .padding(lineWidth + 6)
        }
        .frame(width: size, height: size)
    }
}

struct JarvisPanel<Content: View>: View {
    let title: String
    var subtitle: String? = nil
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Rectangle()
                    .fill(JaniceColors.accent)
                    .frame(width: 3, height: 14)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title.uppercased())
                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                        .foregroundStyle(JaniceColors.accent)
                        .tracking(1.2)
                    if let subtitle {
                        Text(subtitle)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(JaniceColors.textSecondary)
                    }
                }
                Spacer()
            }
            content
        }
        .padding(14)
        .background {
            RoundedRectangle(cornerRadius: 4)
                .fill(JaniceColors.surfaceRaised.opacity(0.65))
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(JaniceColors.hudLine, lineWidth: 1)
                )
        }
    }
}

struct JarvisMetricChip: View {
    let label: String
    let value: String
    let icon: String

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(JaniceColors.accent)
            Text(value)
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundStyle(JaniceColors.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.65)
            Text(label.uppercased())
                .font(.system(size: 8, weight: .medium, design: .monospaced))
                .foregroundStyle(JaniceColors.textSecondary)
                .tracking(0.8)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background {
            RoundedRectangle(cornerRadius: 4)
                .stroke(JaniceColors.hudLine, lineWidth: 1)
                .background(JaniceColors.surface.opacity(0.5))
        }
    }
}

struct JarvisDataRow: View {
    let key: String
    let value: String

    var body: some View {
        HStack(alignment: .top) {
            Text(key.uppercased())
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundStyle(JaniceColors.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(value)
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundStyle(JaniceColors.textPrimary)
                .multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 6)
    }
}

struct JarvisCommandButton: View {
    let title: String
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                Text(title.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .tracking(0.6)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 11)
            .foregroundStyle(JaniceColors.accent)
            .background {
                RoundedRectangle(cornerRadius: 2)
                    .stroke(JaniceColors.accent.opacity(0.55), lineWidth: 1)
                    .background(JaniceColors.accent.opacity(0.08))
            }
        }
        .buttonStyle(.plain)
    }
}

struct JarvisStatusDot: View {
    let online: Bool
    var body: some View {
        Circle()
            .fill(online ? JaniceColors.online : JaniceColors.alert)
            .frame(width: 8, height: 8)
            .shadow(color: (online ? JaniceColors.online : JaniceColors.alert).opacity(0.8), radius: 4)
    }
}

struct JarvisPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .bold, design: .monospaced))
            .foregroundStyle(JaniceColors.bg)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(JaniceColors.accent.opacity(configuration.isPressed ? 0.7 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 2))
            .shadow(color: JaniceColors.accent.opacity(0.35), radius: configuration.isPressed ? 2 : 8)
    }
}

typealias JanicePrimaryButtonStyle = JarvisPrimaryButtonStyle
typealias EInkButtonStyle = JarvisPrimaryButtonStyle

struct JarvisNavigationTitle: ViewModifier {
    let text: String
    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text(text.uppercased())
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundStyle(JaniceColors.accent)
                        .tracking(2)
                }
            }
    }
}

extension View {
    func jarvisNavTitle(_ text: String) -> some View {
        modifier(JarvisNavigationTitle(text: text))
    }
}
