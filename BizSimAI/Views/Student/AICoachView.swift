// AICoachView.swift
// BizSimAI
//
// S-8: Chat-like coaching interface with AI-powered business advice.
// Uses AICoachViewModel for message management and response generation.

import SwiftUI

struct AICoachView: View {
    @State private var viewModel = AICoachViewModel()

    var body: some View {
        VStack(spacing: 0) {
            coachHeader
            Divider()
            messageList
            Divider()
            inputBar
        }
        .navigationTitle("AI Coach")
        #if os(macOS)
        .frame(minWidth: 500, minHeight: 450)
        #endif
        .onAppear {
            viewModel.addWelcomeMessage()
        }
    }

    // MARK: - Coach Header

    private var coachHeader: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(.blue.gradient)
                    .frame(width: 40, height: 40)
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(.white)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("Business Coach")
                    .font(.headline)
                HStack(spacing: 4) {
                    Circle()
                        .fill(.green)
                        .frame(width: 6, height: 6)
                    Text("Online")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button {
                viewModel.clearChat()
                viewModel.addWelcomeMessage()
            } label: {
                Label("Clear Chat", systemImage: "trash")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(!viewModel.hasMessages)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.gray.opacity(0.1))
    }

    // MARK: - Message List

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        CoachingBubble(
                            content: message.content,
                            isFromAI: message.role.isCoach,
                            timestamp: message.timestamp
                        )
                        .id(message.id)
                    }

                    if viewModel.isLoading {
                        typingIndicator
                            .id("loading")
                    }
                }
                .padding(16)
            }
            .onChange(of: viewModel.messages.count) { _, _ in
                if let lastId = viewModel.messages.last?.id {
                    withAnimation(.spring(duration: 0.3)) {
                        proxy.scrollTo(lastId, anchor: .bottom)
                    }
                }
            }
            .onChange(of: viewModel.isLoading) { _, isLoading in
                if isLoading {
                    withAnimation(.spring(duration: 0.3)) {
                        proxy.scrollTo("loading", anchor: .bottom)
                    }
                }
            }
        }
    }

    private var typingIndicator: some View {
        HStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(.blue.gradient)
                    .frame(width: 32, height: 32)
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.white)
            }

            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(Color.white.opacity(0.8))
                        .frame(width: 6, height: 6)
                        .animation(
                            .easeInOut(duration: 0.6)
                            .repeatForever(autoreverses: true)
                            .delay(Double(index) * 0.2),
                            value: viewModel.isLoading
                        )
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.blue, in: RoundedRectangle(cornerRadius: 16, style: .continuous))

            Spacer(minLength: 60)
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: 12) {
            TextField("Ask your AI coach a question...", text: $viewModel.userQuestion, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...4)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(Color.gray.opacity(0.1))
                )
                .onSubmit {
                    if viewModel.canSend {
                        viewModel.askQuestion()
                    }
                }

            Button {
                viewModel.askQuestion()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
                    .foregroundStyle(viewModel.canSend ? .blue : .secondary)
            }
            .buttonStyle(.borderless)
            .disabled(!viewModel.canSend)
            .keyboardShortcut(.return, modifiers: .command)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.gray.opacity(0.1))
    }
}
