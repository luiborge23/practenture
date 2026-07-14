// HapticsManager.swift
// BizSimAI
//
// Centralized haptic feedback for key user interactions.
// Uses UIImpactFeedbackGenerator, UINotificationFeedbackGenerator,
// and UISelectionFeedbackGenerator.

import UIKit

enum HapticsManager {
    
    // MARK: - Impact Feedback
    
    /// Light impact — button taps, small state changes.
    static func light() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
    }
    
    /// Medium impact — decision submissions, card selections.
    static func medium() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }
    
    /// Heavy impact — significant state transitions, round completions.
    static func heavy() {
        let generator = UIImpactFeedbackGenerator(style: .heavy)
        generator.impactOccurred()
    }
    
    // MARK: - Notification Feedback
    
    /// Success haptic — login success, data synced, decision confirmed.
    static func success() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }
    
    /// Warning haptic — over budget, approaching deadline.
    static func warning() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.warning)
    }
    
    /// Error haptic — submission failed, network error.
    static func error() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.error)
    }
    
    // MARK: - Selection Feedback
    
    /// Selection changed — picker, tab switch, category selection.
    static func selection() {
        let generator = UISelectionFeedbackGenerator()
        generator.selectionChanged()
    }
}
