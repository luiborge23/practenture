// TeamManagementView.swift
// BizSimAI
//
// Professor view for managing team composition, student enrollment, and auto-assignment.

import SwiftUI

struct TeamManagementView: View {
    @Environment(AppState.self) private var appState
    @State private var newStudentName: String = ""
    @State private var newStudentEmail: String = ""
    @State private var showAutoAssignAlert = false

    private var session: SimulationSession? { appState.activeSession }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let session = session {
                    enrollmentHeader(session)
                    addStudentSection(session)
                    teamCompositionSection(session)
                    unassignedSection(session)
                } else {
                    ContentUnavailableView(
                        "No Active Session",
                        systemImage: "person.3.fill",
                        description: Text("Create or select a session first.")
                    )
                }
            }
            .padding(24)
        }
        .navigationTitle("Team Management")
        .alert("Auto-Assign Students?", isPresented: $showAutoAssignAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Auto-Assign") {
                session?.autoAssignStudents()
            }
        } message: {
            Text("This will randomly distribute all unassigned students across teams evenly.")
        }
    }

    // MARK: - Enrollment Header

    private func enrollmentHeader(_ session: SimulationSession) -> some View {
        HStack(spacing: 20) {
            statCard(title: "Enrolled", value: "\(session.enrolledStudents.filter(\.isActive).count)", icon: "person.fill", color: .blue)
            statCard(title: "Assigned", value: "\(session.enrolledStudents.filter { $0.teamId != nil && $0.isActive }.count)", icon: "person.badge.star", color: .green)
            statCard(title: "Unassigned", value: "\(session.unassignedStudents.count)", icon: "person.badge.clock", color: .orange)
            statCard(title: "Teams", value: "\(session.teams.filter { !$0.isAI }.count)", icon: "person.3", color: .purple)
        }
    }

    private func statCard(title: String, value: String, icon: String, color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(color.opacity(0.08)))
    }

    // MARK: - Add Student

    private func addStudentSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "person.badge.plus")
                    .foregroundStyle(.blue)
                Text("Add Student")
                    .font(.headline)
            }

            HStack(spacing: 12) {
                TextField("Name", text: $newStudentName, prompt: Text("Student name"))
                    .textFieldStyle(.roundedBorder)

                TextField("Email", text: $newStudentEmail, prompt: Text("Email address"))
                    .textFieldStyle(.roundedBorder)

                Button {
                    guard !newStudentName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                    session.enrollStudent(name: newStudentName.trimmingCharacters(in: .whitespaces),
                                         email: newStudentEmail.trimmingCharacters(in: .whitespaces))
                    newStudentName = ""
                    newStudentEmail = ""
                } label: {
                    Label("Add", systemImage: "plus.circle.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(newStudentName.trimmingCharacters(in: .whitespaces).isEmpty)
            }

            HStack {
                Button {
                    showAutoAssignAlert = true
                } label: {
                    Label("Auto-Assign All", systemImage: "shuffle")
                }
                .buttonStyle(.bordered)
                .disabled(session.unassignedStudents.isEmpty)

                Spacer()

                Text("Session Code: \(session.sessionCode)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fontDesign(.monospaced)
            }
        }
        .padding(20)
        .background(RoundedRectangle(cornerRadius: 16).fill(Color.gray.opacity(0.1)))
    }

    // MARK: - Team Composition

    private func teamCompositionSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Team Composition")
                .font(.headline)

            let humanTeams = session.teams.filter { !$0.isAI }

            if humanTeams.isEmpty {
                Text("No human teams configured yet.")
                    .foregroundStyle(.secondary)
                    .font(.subheadline)
            } else {
                ForEach(humanTeams) { team in
                    teamRow(team, session: session)
                }
            }
        }
    }

    private func teamRow(_ team: TeamStatus, session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(team.name)
                    .font(.subheadline)
                    .fontWeight(.semibold)

                Spacer()

                Text("\(session.studentsForTeam(team.id).count)/\(session.config.teamSize) students")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            let students = session.studentsForTeam(team.id)
            if students.isEmpty {
                Text("No students assigned")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            } else {
                ForEach(students) { student in
                    HStack(spacing: 8) {
                        Image(systemName: "person.circle")
                            .foregroundStyle(.blue)
                        Text(student.name)
                            .font(.caption)
                        if !student.email.isEmpty {
                            Text("(\(student.email))")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }
                        Spacer()
                        Button {
                            session.assignStudentToTeam(student.id, teamId: nil) // Unassign
                        } label: {
                            Image(systemName: "xmark.circle")
                                .foregroundStyle(.red.opacity(0.6))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.08)))
    }

    // MARK: - Unassigned Students

    @ViewBuilder
    private func unassignedSection(_ session: SimulationSession) -> some View {
        let unassigned = session.unassignedStudents
        if !unassigned.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Unassigned Students")
                        .font(.headline)

                    Spacer()

                    Text("\(unassigned.count) students")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }

                ForEach(unassigned) { student in
                    HStack(spacing: 8) {
                        Image(systemName: "person.badge.clock")
                            .foregroundStyle(.orange)
                        Text(student.name)
                            .font(.subheadline)
                        Spacer()

                        // Quick-assign to a team
                        Menu {
                            ForEach(session.teams.filter { !$0.isAI }) { team in
                                Button(team.name) {
                                    session.assignStudentToTeam(student.id, teamId: team.id)
                                }
                            }
                        } label: {
                            Label("Assign", systemImage: "arrow.right.circle")
                                .font(.caption)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)

                        Button {
                            session.removeStudent(student.id)
                        } label: {
                            Image(systemName: "trash")
                                .foregroundStyle(.red)
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.vertical, 4)
                }
            }
            .padding(20)
            .background(RoundedRectangle(cornerRadius: 16).fill(Color.orange.opacity(0.05)))
        }
    }
}
