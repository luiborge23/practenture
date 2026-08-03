// UserFriendlyError.swift
// Practenture — Centralized error-to-user-message mapping
// All user-facing errors should go through this module to ensure consistent, friendly messaging.

import Foundation

/// Converts any Error into a user-friendly message with actionable guidance.
/// This is the SINGLE source of truth for what users see when something goes wrong.
enum UserFriendlyError {
    
    // MARK: - Network Errors (NetworkError enum)
    
    static func message(for error: Error) -> String {
        // Check if it's a NetworkError first (most common — HTTP responses)
        if let networkError = error as? NetworkError {
            return message(for: networkError)
        }
        
        // Check if it's an AuthError
        if let authError = error as? AuthError {
            return message(for: authError)
        }
        
        // Check for Apple Sign-In errors
        if let nsError = error as NSError? {
            if nsError.domain == "com.apple.AuthenticationServices.AuthorizationError" {
                return message(forAppleSignIn: nsError.code)
            }
            if nsError.domain == "com.google.GoogleSignIn" {
                return message(forGoogleSignIn: nsError.code)
            }
        }
        
        // Fallback for any other error type
        return "An unexpected error occurred. Please try again."
    }
    
    // MARK: - NetworkError mapping
    
    private static func message(for error: NetworkError) -> String {
        switch error {
        case .invalidURL:
            return "Unable to connect to the server. Please check your internet connection and try again."
            
        case .decodingError:
            return "The server returned data in an unexpected format. Please try again or contact support if the problem persists."
            
        case .serverError(let code, let message):
            // Map HTTP status codes to user-friendly messages with actionable guidance
            switch code {
            case 401:
                return "Incorrect username or password. Please check your credentials and try again."
                
            case 403:
                return message.isEmpty
                    ? "You don't have permission to access this. Please contact your professor or administrator."
                    : message
                
            case 404:
                return "The requested resource was not found. Please check your connection and try again."
                
            case 408:
                return "The request timed out. Please check your internet connection and try again."
                
            case 409:
                return message.isEmpty ? "This team name is already taken. Please choose a different team name." : message
                
            case 429:
                return message.isEmpty
                    ? "Too many attempts. Please wait a few minutes before trying again."
                    : message
                
            case 500:
                return "A server error occurred. Please try again in a moment."
                
            case 502, 503, 504:
                return "The server is temporarily unavailable. Please try again in a moment."
                
            default:
                return "An unexpected error occurred (code \(code)). Please try again."
            }
            
        case .noData:
            return "No data received from the server. Please check your internet connection and try again."
            
        case .timeout:
            return "The request timed out. Please check your internet connection and try again."
            
        case .connectionFailed:
            return "Could not connect to the server. Please check your internet connection and try again."
        }
    }
    
    // MARK: - AuthError mapping
    
    private static func message(for error: AuthError) -> String {
        switch error {
        case .invalidProviderCredentials:
            return "The sign-in credentials from Apple/Google are invalid. Please try signing in again."
            
        case .tokenExpired:
            return "Your session has expired. Please log in again."
            
        case .professorRequired:
            return "A professor account is required to access this feature. Please log in as a professor."
            
        case .professorCodeInvalid:
            return "The professor code you entered is invalid or has already been used. Please check with your administrator."

        case .secureStorageUnavailable:
            return "Secure storage is unavailable, so account deletion was not started. Restart your device and try again."
        }
    }
    
    // MARK: - Apple Sign-In errors
    
    private static func message(forAppleSignIn code: Int) -> String {
        switch code {
        case 0: // canceled
            return "Sign-in was cancelled."
        case 1: // failed
            return "Apple Sign-In failed. Please try again."
        case 2: // unauthorized
            return "Apple Sign-In is not authorized. Please check your Apple ID settings."
        case 3: // invalidResponse
            return "Invalid response from Apple. Please try again."
        default:
            return "Apple Sign-In failed. Please try again or use a different sign-in method."
        }
    }
    
    // MARK: - Google Sign-In errors
    
    private static func message(forGoogleSignIn code: Int) -> String {
        switch code {
        case -1: // general error
            return "Google Sign-In failed. Please try again."
        case -2: // cancel
            return "Sign-in was cancelled."
        case -3: // invalid config
            return "Google Sign-In is not configured properly. Please contact support."
        case -4: // no sign-in in keychain
            return "No Google account found on this device. Please add a Google account first."
        case -5: // no client ID
            return "Google Sign-In is not set up. Please contact your administrator."
        case -6: // no auth code
            return "Could not get authentication code from Google. Please try again."
        case -7: // canceled (already handled in UI)
            return "Sign-in was cancelled."
        default:
            return "Google Sign-In failed. Please try again or use a different sign-in method."
        }
    }
}
