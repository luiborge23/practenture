// MARK: - Settings View with i18n Support (Phase 8)

import SwiftUI

struct SettingsView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedLanguageCode = I18N.currentLocale.identifier
    @State private var showLanguagePicker = false
    @State private var rememberMe: Bool = AuthManager.shared.rememberMe
    
    private var currentLanguageName: String {
        I18N.availableLanguages.first { $0.code == selectedLanguageCode }?.nativeName ?? "English"
    }
    
    var body: some View {
        NavigationStack {
            Form {
                // Language Section
                Section {
                    HStack {
                        Image(systemName: "globe")
                        Text(L10n.language)
                    }
                    Picker("", selection: $selectedLanguageCode) {
                        ForEach(I18N.availableLanguages, id: \.code) { lang in
                            Text("\(lang.nativeName) (\(lang.name))")
                                .tag(lang.code)
                        }
                    }
                    .pickerStyle(.inline)
                } header: {
                    Text(L10n.settings)
                } footer: {
                    Text(L10n.selectedLanguage)
                }
                
                // Security Section
                Section {
                    Toggle("Remember Me", isOn: $rememberMe)
                        .onChange(of: rememberMe) { _, newValue in
                            AuthManager.shared.rememberMe = newValue
                        }
                } header: {
                    Text("Security")
                } footer: {
                    Text("When enabled, your session persists across app restarts. Disable to require re-authentication on every launch.")
                }
                
                // About Section
                Section {
                    LabeledContent("BizSimAI") {
                        Text("Business Simulation Platform")
                    }
                    LabeledContent("Version") {
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                    }
                    LabeledContent("Build") {
                        Text(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")
                    }
                    Link("Documentation", destination: URL(string: "https://github.com/luisborges/BizSimAI")!)
                    Link("Report Issue", destination: URL(string: "https://github.com/luisborges/BizSimAI/issues")!)
                } header: {
                    Text(L10n.about)
                }
                
                // Account Section
                if appState.currentMode == .professor {
                    Section {
                        Button(role: .destructive) {
                            handleLogout()
                        } label: {
                            HStack {
                                Spacer()
                                Image(systemName: "rectangle.portrait.and.arrow.right")
                                Text(L10n.logout)
                                Spacer()
                            }
                        }
                    } header: {
                        Text("Account")
                    }
                }
            }
            .navigationTitle(L10n.settings)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
    
    private func handleLogout() {
        AuthManager.shared.logout()
        dismiss()
    }
}

#Preview {
    SettingsView()
        .environment(AppState())
}
