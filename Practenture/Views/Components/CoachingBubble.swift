// CoachingBubble.swift
// Practenture
//
// Chat message bubble for AI coaching interface.

import SwiftUI

struct CoachingBubble: View {
    let content: String
    let isFromAI: Bool
    var timestamp: Date = .now

    private var bubbleColor: Color {
        isFromAI ? .blue : Color.gray.opacity(0.2)
    }

    private var textColor: Color {
        isFromAI ? .white : .primary
    }

    private var alignment: HorizontalAlignment {
        isFromAI ? .leading : .trailing
    }

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if isFromAI {
                aiAvatar
            }

            if !isFromAI { Spacer(minLength: 60) }

            VStack(alignment: isFromAI ? .leading : .trailing, spacing: 4) {
                Text(content)
                    .font(.body)
                    .foregroundStyle(textColor)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(bubbleColor, in: bubbleShape)
                    .textSelection(.enabled)

                Text(timestamp, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .padding(.horizontal, 4)
            }

            if isFromAI { Spacer(minLength: 60) }

            if !isFromAI {
                userAvatar
            }
        }
    }

    private var bubbleShape: some Shape {
        RoundedRectangle(cornerRadius: 16, style: .continuous)
    }

    private var aiAvatar: some View {
        ZStack {
            Circle()
                .fill(Color.blue.gradient)
                .frame(width: 32, height: 32)
            Image(systemName: "brain.head.profile")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
        }
    }

    private var userAvatar: some View {
        ZStack {
            Circle()
                .fill(Color.gray.gradient)
                .frame(width: 32, height: 32)
            Image(systemName: "person.fill")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
        }
    }
}
