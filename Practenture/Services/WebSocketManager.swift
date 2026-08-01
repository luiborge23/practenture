// WebSocketManager.swift
// Practenture
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

@MainActor
final class WebSocketManager: NSObject, ObservableObject {
    
    static let shared = WebSocketManager()
    
    // Session-specific connection state
    private var connectionRequest: URLRequest?
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession!
    private var isConnected: Bool = false
    private var shouldReconnect: Bool = false
    
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
    
    func connect(toSession sessionCode: String, baseURL: String, accessToken: String) {
        disconnect(reason: "Replacing connection")

        guard !accessToken.isEmpty,
              var components = URLComponents(string: baseURL) else {
            reportEvent(.error("A valid authenticated WebSocket configuration is required"))
            return
        }
        components.scheme = components.scheme == "https" ? "wss" : "ws"
        components.path = "/ws/\(sessionCode.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? sessionCode)"
        components.query = nil
        guard let url = components.url else {
            reportEvent(.error("Invalid WebSocket URL"))
            return
        }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        connectionRequest = request
        shouldReconnect = true
        startSocket(with: request)
    }
    
    func disconnect(reason: String? = nil) {
        reconnectTimer?.invalidate()
        reconnectTimer = nil
        
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil
        
        webSocketTask?.cancel(with: .normalClosure, reason: nil as Data?)
        webSocketTask = nil
        
        isConnected = false
        shouldReconnect = false
        connectionRequest = nil
        currentReconnectAttempt = 0
        
        reportEvent(.disconnected(reason: reason))
    }
    
    func sendMessage(_ message: String) {
        guard message.data(using: .utf8) != nil else { return }
        
        Task {
            do {
                try await webSocketTask?.send(.string(message))
            } catch {
                reportEvent(.error("Send failed: \(UserFriendlyError.message(for: error))"))
            }
        }
    }
    
    // MARK: - Reconnection
    
    private func startReconnect() {
        guard shouldReconnect, !isConnected else { return }
        
        currentReconnectAttempt += 1
        
        let delay = min(
            baseReconnectDelay * pow(2.0, Double(currentReconnectAttempt)),
            maxReconnectDelay
        )
        
        reconnectTimer?.invalidate()
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self else { return }

                if self.currentReconnectAttempt >= self.maxReconnectAttempts {
                    self.reportEvent(.error("Max reconnection attempts (\(self.maxReconnectAttempts)) reached"))
                    self.currentReconnectAttempt = 0
                    return
                }

                guard var request = self.connectionRequest,
                      let accessToken = AuthManager.shared.accessToken,
                      !accessToken.isEmpty else {
                    self.reportEvent(.error("Authentication expired; WebSocket reconnect stopped"))
                    self.shouldReconnect = false
                    return
                }
                request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
                self.connectionRequest = request
                self.startSocket(with: request)

                self.reportEvent(.disconnected(reason: "Reconnecting (attempt \(self.currentReconnectAttempt)/\(self.maxReconnectAttempts))"))
            }
        }
    }
    
    // MARK: - Heartbeat
    
    private func startHeartbeat() {
        heartbeatTimer?.invalidate()
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: heartbeatInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self else { return }

                if self.isConnected {
                    self.sendMessage(#"{"type":"ping"}"#)
                }
            }
        }
    }
    
    // MARK: - Message Handling
    
    private func startSocket(with request: URLRequest) {
        let task = session.webSocketTask(with: request)
        webSocketTask = task
        task.resume()
        receiveNextMessage(from: task)
    }

    private func receiveNextMessage(from task: URLSessionWebSocketTask) {
        Task {
            do {
                let message = try await task.receive()
                guard task === webSocketTask else { return }
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

                receiveNextMessage(from: task)
            } catch {
                guard task === webSocketTask else { return }
                if isConnected {
                    isConnected = false
                    heartbeatTimer?.invalidate()
                    heartbeatTimer = nil
                    reportEvent(.disconnected(reason: "Connection closed"))
                }
                startReconnect()
            }
        }
    }
    
    // MARK: - Event Reporting
    
    private func reportEvent(_ event: WebSocketEvent) {
        latestEvent = event
            
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
