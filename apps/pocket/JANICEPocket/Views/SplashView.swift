import SwiftUI

struct JaniceSplashView: View {
    let onFinished: () -> Void
    @State private var bootLine = 0
    private let bootLines = [
        "INITIALIZING MOBILE CORE…",
        "LOADING NEURAL INTERFACE…",
        "CALIBRATING SENSORS…",
        "J.A.R.V.I.S. PORTABLE — ONLINE",
    ]

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            let pulse = 0.9 + 0.1 * sin(t * 2.4)
            let sweep = (t.truncatingRemainder(dividingBy: 3)) / 3

            ZStack {
                JaniceColors.bg.ignoresSafeArea()

                GeometryReader { geo in
                    Circle()
                        .stroke(JaniceColors.hudDim, lineWidth: 1)
                        .frame(width: geo.size.width * 0.78)
                        .position(x: geo.size.width / 2, y: geo.size.height * 0.42)
                    Circle()
                        .trim(from: 0, to: 0.65)
                        .stroke(
                            JaniceColors.accent.opacity(0.6),
                            style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: [4, 8])
                        )
                        .frame(width: geo.size.width * 0.78)
                        .rotationEffect(.degrees(sweep * 360 - 90))
                        .position(x: geo.size.width / 2, y: geo.size.height * 0.42)
                }

                RadialGradient(
                    colors: [JaniceColors.accent.opacity(0.18), .clear],
                    center: .center,
                    startRadius: 20,
                    endRadius: 260
                )
                .scaleEffect(pulse)
                .blur(radius: 18)

                BrainSceneView(
                    mode: BrainStateController.shared.mode,
                    nodeCount: BrainStateController.shared.nodeCount,
                    knowledgeLevel: BrainStateController.shared.knowledgeLevel
                )
                .frame(width: 190, height: 150)
                .scaleEffect(pulse)

                VStack(spacing: 14) {
                    Spacer()
                    Text("J.A.R.V.I.S.")
                        .font(.system(size: 30, weight: .thin, design: .default))
                        .foregroundStyle(JaniceColors.textPrimary)
                        .tracking(6)
                    Text("PORTABLE INTERFACE")
                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                        .foregroundStyle(JaniceColors.accent)
                        .tracking(3)
                    Text(bootLines[min(bootLine, bootLines.count - 1)])
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(JaniceColors.textSecondary)
                        .padding(.bottom, 56)
                }
            }
        }
        .onAppear {
            for i in 0..<bootLines.count {
                DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 0.45) {
                    bootLine = i
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) {
                onFinished()
            }
        }
    }
}

typealias NeuronSplashView = JaniceSplashView

#Preview {
    JaniceSplashView(onFinished: {})
}
