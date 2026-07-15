// WebSocketManager.swift
// BizSimAI
//
// iOS-side WebSocket client for real-time session communication.
// Mirrors the backend's ws_manager.py session-based connection model.
// Handles reconnection, heartbeat ping/pong, and message broadcasting to observers.

import Foundation
import Combine
import os

// MARK: - Events

enum WebSocketEvent {
    case connected
    case disconnected(reason: String?)
    case message(String)
    case error(String)
}

// MARK: - Delegate Protocol (SwiftUI-compatible via Combine)

@MainActor
protocol WebSocketManagerDelegate: AnyObject {
    func didReceive(event: WebSocketEvent, from manager: WebSocketManager)
}

// MARK: - WebSocket Manager

final class WebSocketManager: NSObject, ObservableObject {
    
    static let shared = WebSocketManager()
    
    // Session-specific connection state
    private var wsURL: URL?
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession!
    private var isConnected: Bool = false
    
    // Reconnection config
    private var reconnectTimer: Timer?
    private var maxReconnectAttempts = 10
    private var currentReconnectAttempt = 0
    private let baseReconnectDelay: TimeInterval = 2.0
    private let maxReconnectDelay: TimeInterval = 30.0
    
    // Heartbeat config
    private var heartbeatTimer: Timer?
    private let heartbeatInterval: TimeInterval = 15.0
    
    // Message observers (Combine-like pattern)
    @Published var latestEvent: WebSocketEvent?
    
    weak var delegate: WebSocketManagerDelegate?
    
    override init() {
        super.init()
        
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Connection Lifecycle
    
    func connect(toSession sessionCode: String, baseURL: String) {
        disconnect(reason: "Replacing connection")
        
        let urlString = "\(baseURL.replacingOccurrences(of: "http", with: "ws"))/ws/\(sessionCode)"
        guard let url = URL(string: urlString) else {
            reportEvent(.error("Invalid WebSocket URL: \(urlString)"))
            return
        }
        
        self.wsURL = url
        
        webSocketTask = session.webSocketTask(with: url)
        startReceiving()
    }
    
    func disconnect(reason: String? = nil) {
        reconnectTimer?.invalidate()
        reconnectTimer = nil
        
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil
        
        webSocketTask?.cancel(with: .normalClosure, reason: nil as Data?)
        webSocketTask = nil
        
        isConnected = false
        currentReconnectAttempt = 0
        
        reportEvent(.disconnected(reason: reason))
    }
    
    func sendMessage(_ message: String) {
        guard message.data(using: .utf8) != nil else { return }
        
        webSocketTask?.send(.string(message)) { error in
            if let error = error {
                self.reportEvent(.error("Send failed: \(UserFriendlyError.message(for: error))"))
            }
        }
    }
    
    // MARK: - Reconnection
    
    private func startReconnect() {
        guard !isConnected else { return }
        
        currentReconnectAttempt += 1
        
        let delay = min(
            baseReconnectDelay * pow(2.0, Double(currentReconnectAttempt)),
            maxReconnectDelay
        )
        
        reconnectTimer?.invalidate()
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            guard let self else { return }
            
            if currentReconnectAttempt >= maxReconnectAttempts {
                reportEvent(.error("Max reconnection attempts (\(maxReconnectAttempts)) reached"))
                currentReconnectAttempt = 0
                return
            }
            
            guard let wsURL = self.wsURL else { return }
            
            webSocketTask = session.webSocketTask(with: wsURL)
            startReceiving()
            
            reportEvent(.disconnected(reason: "Reconnecting (attempt \(currentReconnectAttempt)/\(maxReconnectAttempts))"))
        }
    }
    
    // MARK: - Heartbeat
    
    private func startHeartbeat() {
        heartbeatTimer?.invalidate()
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: heartbeatInterval, repeats: true) { [weak self] _ in
            guard let self else { return }
            
            if isConnected {
                webSocketTask?.sendPing { error in
                    if let error = error {
                        Logger.webSocket.error("Ping failed: \(UserFriendlyError.message(for: error))")
                    }
                }
            }
        }
    }
    
    // MARK: - Message Handling
    
    private func startReceiving() {
        webSocketTask?.resume()
        
        webSocketTask?.receive { [weak self] result in
            guard let self else { return }
            
            switch result {
            case .success(let message):
                if !isConnected {
                    isConnected = true
                    currentReconnectAttempt = 0
                    reportEvent(.connected)
                    startHeartbeat()
                }
                
                switch message {
                case .string(let text):
                    reportEvent(.message(text))
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        reportEvent(.message(text))
                    }
                @unknown default:
                    break
                }
                
                // Continue receiving recursively
                let task = webSocketTask
                Task.detached {
                    await MainActor.run {
                        task?.receive { _ in }
                    }
                }
            case .failure:
                if isConnected {
                    isConnected = false
                    heartbeatTimer?.invalidate()
                    heartbeatTimer = nil
                    reportEvent(.disconnected(reason: "Connection closed"))
                }
                startReconnect()
            @unknown default:
                break
            }
        }
    }
    
    // MARK: - Event Reporting
    
    private func reportEvent(_ event: WebSocketEvent) {
        Task { @MainActor in
            self.latestEvent = event
            
            switch event {
            case .connected:
                Logger.webSocket.info("WebSocket connected")
            case .disconnected(let reason):
                Logger.webSocket.info("WebSocket disconnected: \(reason ?? "unknown")")
            default:
                break
            }
            if case .error(let msg) = event {
                Logger.webSocket.error("\(msg)")
            }
            
            delegate?.didReceive(event: event, from: self)
        }
    }
}
