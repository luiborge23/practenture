// SyncBannerView.swift
// BizSimAI
//
// A compact banner showing sync status — online/offline/syncing/error.
// Appears at the top of key screens when sync state changes.

import SwiftUI

enum SyncStatus: Equatable {
    case online
    case offline
    case syncing
    case error(String)
    case savedLocally
    
    var label: String {
        switch self {
        case .online: return "Online"
        case .offline: return "Offline"
        case .syncing: return "Syncing..."
        case .error(let msg): return "Sync failed: \(msg)"
        case .savedLocally: return "Saved locally"
        }
    }
    
    var iconName: String {
        switch self {
        case .online: return "checkmark.icloud"
        case .offline: return "icloud.slash"
        case .syncing: return "arrow.triangle.2.circlepath.icloud"
        case .error: return "exclamationmark.icloud"
        case .savedLocally: return "icloud.and.arrow.down"
        }
    }
    
    var color: Color {
        switch self {
        case .online: return .green
        case .offline: return .gray
        case .syncing: return .blue
        case .error: return .red
        case .savedLocally: return .orange
        }
    }
}

struct SyncBannerView: View {
    let status: SyncStatus
    var onRetry: (() -> Void)? = nil
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: status.iconName)
                .font(.caption)
                .foregroundStyle(status.color)
            
            Text(status.label)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)
            
            if case .error = status, onRetry != nil {
                Spacer()
                Button {
                    onRetry?()
                    HapticsManager.light()
                } label: {
                    Text("Retry")
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundStyle(.blue)
                }
                .buttonStyle(.plain)
            }
            
            if case .syncing = status {
                Spacer()
                ProgressView()
                    .scaleEffect(0.6)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(status.color.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(status.color.opacity(0.2), lineWidth: 0.5)
        )
    }
}

#Preview("Sync States") {
    VStack(spacing: 12) {
        SyncBannerView(status: .online)
        SyncBannerView(status: .offline)
        SyncBannerView(status: .syncing)
        SyncBannerView(status: .error("Network timeout"))
        SyncBannerView(status: .savedLocally)
    }
    .padding()
}
