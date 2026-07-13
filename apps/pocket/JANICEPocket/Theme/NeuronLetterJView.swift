import SwiftUI

enum NeuronLetterJ {
    struct Node: Identifiable {
        let id: Int
        let point: CGPoint
        let radius: CGFloat
        let isGold: Bool
    }

    struct Segment: Identifiable {
        let id: Int
        let from: Int?
        let to: Int
    }

    /// Grafo che traccia una «J» con ramificazioni da neurone.
    static let nodes: [Node] = [
        Node(id: 0, point: CGPoint(x: 0.34, y: 0.20), radius: 0.042, isGold: true),   // soma
        Node(id: 1, point: CGPoint(x: 0.50, y: 0.18), radius: 0.028, isGold: false),
        Node(id: 2, point: CGPoint(x: 0.66, y: 0.20), radius: 0.028, isGold: true),
        Node(id: 3, point: CGPoint(x: 0.34, y: 0.38), radius: 0.024, isGold: false),
        Node(id: 4, point: CGPoint(x: 0.34, y: 0.56), radius: 0.024, isGold: true),
        Node(id: 5, point: CGPoint(x: 0.34, y: 0.74), radius: 0.026, isGold: false),
        Node(id: 6, point: CGPoint(x: 0.44, y: 0.84), radius: 0.024, isGold: true),
        Node(id: 7, point: CGPoint(x: 0.58, y: 0.88), radius: 0.024, isGold: false),
        Node(id: 8, point: CGPoint(x: 0.70, y: 0.78), radius: 0.028, isGold: true),
        Node(id: 9, point: CGPoint(x: 0.24, y: 0.48), radius: 0.020, isGold: false),  // dendrite
        Node(id: 10, point: CGPoint(x: 0.56, y: 0.10), radius: 0.020, isGold: true),
        Node(id: 11, point: CGPoint(x: 0.78, y: 0.62), radius: 0.020, isGold: false),
    ]

    static let segments: [Segment] = [
        Segment(id: 0, from: nil, to: 0),
        Segment(id: 1, from: 0, to: 1),
        Segment(id: 2, from: 1, to: 2),
        Segment(id: 3, from: 0, to: 3),
        Segment(id: 4, from: 3, to: 4),
        Segment(id: 5, from: 4, to: 5),
        Segment(id: 6, from: 5, to: 6),
        Segment(id: 7, from: 6, to: 7),
        Segment(id: 8, from: 7, to: 8),
        Segment(id: 9, from: 4, to: 9),
        Segment(id: 10, from: 1, to: 10),
        Segment(id: 11, from: 2, to: 11),
    ]

    static var totalStages: Int { segments.count }

    static func growthStage(entryCount: Int, isRecording: Bool, recordingElapsed: TimeInterval) -> Double {
        let saved = Double(entryCount) * 1.05
        let live = isRecording ? min(1.4, recordingElapsed / 6.0) : 0
        return min(Double(totalStages), max(1, saved + live + 0.5))
    }
}

enum NeuronPalette {
    case splash
    case eInk

    func axon(for gold: Bool) -> Color {
        switch self {
        case .splash: gold ? JaniceColors.gold.opacity(0.9) : JaniceColors.cyan.opacity(0.85)
        case .eInk: gold ? JaniceColors.gold.opacity(0.95) : JaniceColors.cyan.opacity(0.9)
        }
    }

    func soma(for gold: Bool) -> Color {
        switch self {
        case .splash: gold ? JaniceColors.gold : JaniceColors.cyan
        case .eInk: gold ? JaniceColors.gold : JaniceColors.cyan
        }
    }

    func glowColor() -> Color {
        switch self {
        case .splash: JaniceColors.cyan
        case .eInk: JaniceColors.cyan.opacity(0.35)
        }
    }
}

struct GrowingNeuronJView: View {
    var growthStage: Double
    var palette: NeuronPalette = .eInk
    var pulse: Bool = false
    var size: CGFloat = 200

    private var visibleStage: Int {
        Int(growthStage.rounded(.down))
    }

    var body: some View {
        TimelineView(.animation(minimumInterval: pulse ? 1.0 / 30.0 : nil)) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            let scale = pulse ? (0.94 + 0.06 * sin(t * 2.2)) : 1.0
            let glow = pulse ? (0.22 + 0.18 * (0.5 + 0.5 * sin(t * 1.6))) : 0.18

            Canvas { context, canvasSize in
                let side = min(canvasSize.width, canvasSize.height)
                let origin = CGPoint(
                    x: (canvasSize.width - side) / 2,
                    y: (canvasSize.height - side) / 2
                )

                func point(_ node: NeuronLetterJ.Node) -> CGPoint {
                    CGPoint(
                        x: origin.x + node.point.x * side,
                        y: origin.y + node.point.y * side
                    )
                }

                if glow > 0 {
                    let soma = point(NeuronLetterJ.nodes[0])
                    let glowRect = CGRect(
                        x: soma.x - side * 0.22,
                        y: soma.y - side * 0.22,
                        width: side * 0.44,
                        height: side * 0.44
                    )
                    context.fill(
                        Path(ellipseIn: glowRect),
                        with: .color(palette.glowColor().opacity(glow))
                    )
                }

                var visibleNodes = Set<Int>()
                for segment in NeuronLetterJ.segments where segment.id <= visibleStage {
                    if let fromID = segment.from {
                        visibleNodes.insert(fromID)
                        let from = point(NeuronLetterJ.nodes[fromID])
                        let to = point(NeuronLetterJ.nodes[segment.to])
                        var path = Path()
                        path.move(to: from)
                        path.addLine(to: to)
                        context.stroke(
                            path,
                            with: .color(palette.axon(for: segment.id.isMultiple(of: 3)).opacity(0.9)),
                            lineWidth: max(2, side * 0.014)
                        )
                    }
                    visibleNodes.insert(segment.to)
                }

                for node in NeuronLetterJ.nodes where visibleNodes.contains(node.id) {
                    let center = point(node)
                    let radius = node.radius * side
                    let rect = CGRect(
                        x: center.x - radius,
                        y: center.y - radius,
                        width: radius * 2,
                        height: radius * 2
                    )
                    context.fill(Path(ellipseIn: rect), with: .color(palette.soma(for: node.isGold)))
                }
            }
            .scaleEffect(scale)
        }
        .frame(width: size, height: size)
        .accessibilityLabel("Neurone JANICE")
    }
}

#Preview {
    VStack(spacing: 24) {
        GrowingNeuronJView(growthStage: 3, palette: .eInk, pulse: false)
        GrowingNeuronJView(growthStage: 11, palette: .splash, pulse: true, size: 220)
    }
    .padding()
    .background(JaniceColors.paper)
}
