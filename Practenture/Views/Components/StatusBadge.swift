// StatusBadge.swift
// Practenture
//
// Reusable status indicator badge with capsule background.
// Used for session status, submission status, team states, etc.

import SwiftUI

struct StatusBadge: View {
    let text: String
    let color: Color

    var icon: String? = nil
    var size: BadgeSize = .regular

    enum BadgeSize {
        case small, regular, large

        var font: Font {
            switch self {
            case .small: return .caption2
            case .regular: return .caption
            case .large: return .subheadline
            }
        }

        var horizontalPadding: CGFloat {
            switch self {
            case .small: return 6
            case .regular: return 10
            case .large: return 14
            }
        }

        var verticalPadding: CGFloat {
            switch self {
            case .small: return 2
            case .regular: return 4
            case .large: return 6
            }
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            if let icon {
                Image(systemName: icon)
                    .font(size.font)
            }

            Text(text)
                .font(size.font)
                .fontWeight(.semibold)
        }
        .foregroundStyle(color)
        .padding(.horizontal, size.horizontalPadding)
        .padding(.vertical, size.verticalPadding)
        .background(color.opacity(0.12), in: Capsule())
    }
}

// MARK: - Convenience Initializers

extension StatusBadge {
    static func submitted() -> StatusBadge {
        StatusBadge(text: "Submitted", color: .green, icon: "checkmark.circle.fill")
    }

    static func pending() -> StatusBadge {
        StatusBadge(text: "Pending", color: .orange, icon: "clock.fill")
    }

    static func active() -> StatusBadge {
        StatusBadge(text: "Active", color: .blue, icon: "play.circle.fill")
    }

    static func completed() -> StatusBadge {
        StatusBadge(text: "Completed", color: .secondary, icon: "checkmark.seal.fill")
    }

    static func paused() -> StatusBadge {
        StatusBadge(text: "Paused", color: .yellow, icon: "pause.circle.fill")
    }
}
