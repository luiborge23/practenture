// ProfessorTabView.swift
// Practenture
//
// Full-screen Professor workspace. Uses the native iOS tab bar so navigation
// remains anchored to the bottom safe area at every Dynamic Type size.

import SwiftUI

struct ProfessorTabView: View {
    @Environment(AppState.self) private var appState

    private var selectedTab: Binding<String> {
        Binding(
            get: {
                appState.professorSelectedTab == "activeSession"
                    ? "monitor"
                    : appState.professorSelectedTab
            },
            set: { appState.professorSelectedTab = $0 }
        )
    }

    var body: some View {
        TabView(selection: selectedTab) {
            NavigationStack {
                SessionListView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
            .tabItem {
                Label("Sessions", systemImage: "calendar")
            }
            .tag("sessions")

            NavigationStack {
                SessionMonitorView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
            .tabItem {
                Label("Active", systemImage: "play.rectangle")
            }
            .tag("monitor")

            NavigationStack {
                SettingsView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape")
            }
            .tag("settings")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .ignoresSafeArea(.keyboard, edges: .bottom)
    }
}
