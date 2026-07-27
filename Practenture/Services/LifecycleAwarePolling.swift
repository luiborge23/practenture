// LifecycleAwarePolling.swift
// Practenture
//
// Manages polling that respects app lifecycle — pauses in background,
// resumes in foreground with adaptive intervals.

import SwiftUI
import Combine
import os

@Observable
final class LifecycleAwarePolling: NSObject, ObservableObject {
    
    /// Current polling interval in seconds.
    var interval: TimeInterval = 10.0
    
    /// Whether polling is currently active.
    var isActive: Bool = false
    
    /// Whether the app is in the foreground.
    private var isForegrounded: Bool = true
    
    private var timer: Timer?
    private var onTick: (() async -> Void)?
    
    // MARK: - Configuration
    
    /// Foreground polling interval.
    var foregroundInterval: TimeInterval = 10.0
    
    /// Background polling interval (slower to save battery).
    var backgroundInterval: TimeInterval = 60.0
    
    /// Interval right after returning to foreground (faster sync).
    var reentryInterval: TimeInterval = 3.0
    
    /// How many fast ticks after re-entering foreground before slowing down.
    var reentryFastTicks: Int = 3
    
    private var reentryTickCount: Int = 0
    
    // MARK: - Lifecycle
    
    override init() {
        super.init()
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appDidEnterBackground),
            name: UIApplication.didEnterBackgroundNotification,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appWillEnterForeground),
            name: UIApplication.willEnterForegroundNotification,
            object: nil
        )
    }
    
    deinit {
        stop()
        NotificationCenter.default.removeObserver(self)
    }
    
    // MARK: - Start / Stop
    
    func start(action: @escaping () async -> Void) {
        onTick = action
        isActive = true
        self.interval = foregroundInterval
        scheduleNextTick()
        Logger.sync.info("Polling started (interval: \(self.interval)s)")
    }
    
    func stop() {
        timer?.invalidate()
        timer = nil
        isActive = false
        Logger.sync.info("Polling stopped")
    }
    
    /// Manually trigger a poll (e.g., pull-to-refresh).
    func pollNow() async {
        await onTick?()
    }
    
    // MARK: - Private
    
    private func scheduleNextTick() {
        timer?.invalidate()
        guard isActive else { return }
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: false) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                await self.onTick?()
                self.scheduleNextTick()
            }
        }
    }
    
    @objc private func appDidEnterBackground() {
        isForegrounded = false
        guard isActive else { return }
        self.interval = backgroundInterval
        scheduleNextTick()
        Logger.sync.info("Polling: background mode (interval: \(self.interval)s)")
    }
    
    @objc private func appWillEnterForeground() {
        isForegrounded = true
        guard isActive else { return }
        reentryTickCount = 0
        self.interval = reentryInterval
        scheduleNextTick()
        // Also fire an immediate sync
        Task { @MainActor in
            await onTick?()
        }
        Logger.sync.info("Polling: foreground reentry (interval: \(self.interval)s)")
    }
    
    /// Called after each tick to potentially slow down the interval.
    func tickCompleted() {
        guard isForegrounded else { return }
        reentryTickCount += 1
        if reentryTickCount >= reentryFastTicks {
            self.interval = foregroundInterval
            Logger.sync.debug("Polling: settled to foreground interval (\(self.interval)s)")
        }
    }
}
