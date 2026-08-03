#if DEBUG
import SwiftUI

/// Deterministic, process-local UI fixture used only when the app is launched with
/// `-UITesting`. It never creates a URLSession or contacts the configured backend.
struct UITestHarnessView: View {
    enum Scenario: String {
        case professor
        case student
        case offlineQueue
        case visibleError
        case accountSettings
        case accountSettingsStudent
        case accountSettingsProfessor
        case accountDeletionPasswordMFA
        case accountDeletionApple
        case accountDeletionGoogle
    }

    let scenario: Scenario

    @ViewBuilder
    var body: some View {
        if scenario == .accountSettings {
            // SettingsView owns its NavigationStack. Avoid nesting navigation
            // containers because the inner title and toolbar disappear in UI tests.
            SettingsView()
                .accessibilityIdentifier("qa.harness")
        } else if scenario == .accountSettingsStudent {
            StudentSettingsRouteFixture()
                .accessibilityIdentifier("qa.harness")
        } else if scenario == .accountSettingsProfessor {
            ProfessorSettingsRouteFixture()
                .accessibilityIdentifier("qa.harness")
        } else if scenario == .accountDeletionPasswordMFA {
            AccountDeletionRequirementsFixture(provider: "password", mfaRequired: true)
                .accessibilityIdentifier("qa.harness")
        } else if scenario == .accountDeletionApple {
            AccountDeletionRequirementsFixture(provider: "apple", mfaRequired: false)
                .accessibilityIdentifier("qa.harness")
        } else if scenario == .accountDeletionGoogle {
            AccountDeletionRequirementsFixture(provider: "google", mfaRequired: false)
                .accessibilityIdentifier("qa.harness")
        } else {
            NavigationStack {
                switch scenario {
                case .professor:
                    ProfessorFixture()
                case .student:
                    StudentFixture()
                case .offlineQueue:
                    OfflineQueueFixture()
                case .visibleError:
                    VisibleErrorFixture()
                case .accountSettings:
                    EmptyView()
                case .accountSettingsStudent,
                     .accountSettingsProfessor,
                     .accountDeletionPasswordMFA,
                     .accountDeletionApple,
                     .accountDeletionGoogle:
                    EmptyView()
                }
            }
            .accessibilityIdentifier("qa.harness")
        }
    }
}

private struct StudentSettingsRouteFixture: View {
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            Text("Student workspace")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            showSettings = true
                        } label: {
                            Label("Settings", systemImage: "gearshape")
                        }
                        .accessibilityIdentifier("studentSettingsButton")
                    }
                }
        }
        .sheet(isPresented: $showSettings) { SettingsView() }
    }
}

private struct ProfessorSettingsRouteFixture: View {
    var body: some View {
        TabView {
            Text("Professor sessions")
                .tabItem { Label("Sessions", systemImage: "calendar") }
            NavigationStack { SettingsView() }
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}

private struct AccountDeletionRequirementsFixture: View {
    let provider: String
    let mfaRequired: Bool

    var body: some View {
        AccountDeletionView {
            AccountDeletionRequirements(
                provider: provider,
                reauthentication: provider,
                mfaRequired: mfaRequired,
                confirmationPhrase: "DELETE",
                challengeId: "qa-challenge",
                challenge: "qa-operation-token-with-at-least-thirty-two-characters",
                challengeExpiresAt: 9_999_999_999,
                operationToken: "qa-operation-token-with-at-least-thirty-two-characters"
            )
        }
    }
}

private struct ProfessorFixture: View {
    @State private var created = false
    @State private var round = 1

    var body: some View {
        VStack(spacing: 20) {
            Text("Professor Sessions").font(.largeTitle.bold())
                .accessibilityIdentifier("professor.title")
            if created {
                Text("Session QA-PROF").accessibilityIdentifier("professor.sessionCode")
                Text("Round \(round) of 8").accessibilityIdentifier("professor.round")
                Button("Advance Round") { round += 1 }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("professor.advanceRound")
            } else {
                Text("No active sessions")
                Button("Create Session") { created = true }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("professor.createSession")
            }
        }
        .padding()
        .navigationTitle("Professor")
    }
}

private struct StudentFixture: View {
    @State private var sessionCode = ""
    @State private var teamName = ""
    @State private var joined = false
    @State private var submitted = false

    var body: some View {
        VStack(spacing: 16) {
            if joined {
                Text("Team Dashboard").font(.largeTitle.bold())
                    .accessibilityIdentifier("student.dashboard")
                Text("QA Strategists")
                Text("Round 1")
                if submitted {
                    Text("Decision submitted").foregroundStyle(.green)
                        .accessibilityIdentifier("student.submitted")
                } else {
                    Button("Submit Decision") { submitted = true }
                        .buttonStyle(.borderedProminent)
                        .accessibilityIdentifier("student.submitDecision")
                }
            } else {
                Text("Join a Session").font(.largeTitle.bold())
                    .accessibilityIdentifier("student.title")
                TextField("Session Code", text: $sessionCode)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.characters)
                    .accessibilityIdentifier("student.sessionCode")
                TextField("Team Name", text: $teamName)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("student.teamName")
                Button("Join Session") { joined = true }
                    .buttonStyle(.borderedProminent)
                    .disabled(sessionCode != "QA1234" || teamName.isEmpty)
                    .accessibilityIdentifier("student.join")
            }
        }
        .padding()
        .navigationTitle("Student")
    }
}

private struct OfflineQueueFixture: View {
    @State private var pending = 0
    @State private var status = "Offline"

    var body: some View {
        VStack(spacing: 18) {
            Text("Connection Recovery").font(.largeTitle.bold())
            SyncBannerView(status: status == "Online" ? .online : (status == "Syncing..." ? .syncing : .offline))
                .accessibilityIdentifier("sync.banner")
            Text(status).accessibilityIdentifier("sync.status")
            Text("Pending actions: \(pending)").accessibilityIdentifier("sync.pending")
            Button("Queue Decision") { pending += 1 }
                .accessibilityIdentifier("sync.queue")
            Button("Reconnect") {
                status = "Syncing..."
                Task { @MainActor in
                    try? await Task.sleep(for: .milliseconds(250))
                    pending = 0
                    status = "Online"
                }
            }
            .disabled(pending == 0)
            .accessibilityIdentifier("sync.reconnect")
        }
        .padding()
        .navigationTitle("Offline Queue")
    }
}

private struct VisibleErrorFixture: View {
    @State private var failed = false
    @State private var recovered = false

    var body: some View {
        VStack(spacing: 18) {
            Text("Error Handling").font(.largeTitle.bold())
            if failed && !recovered {
                SyncBannerView(status: .error("Request timed out")) {
                    recovered = true
                }
                .accessibilityIdentifier("error.banner")
                Text("Your decision is saved locally and will retry.")
                    .accessibilityIdentifier("error.message")
            } else if recovered {
                SyncBannerView(status: .online)
                Text("Connection restored").foregroundStyle(.green)
                    .accessibilityIdentifier("error.recovered")
            } else {
                Button("Simulate Timeout") { failed = true }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("error.trigger")
            }
        }
        .padding()
        .navigationTitle("Visible Error")
    }
}
#endif
