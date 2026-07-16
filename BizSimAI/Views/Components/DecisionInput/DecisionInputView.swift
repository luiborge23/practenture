// DecisionInputView.swift
// BizSimAI
//
// Refactored decision input with 9 tabbed categories.
// Each category is a separate component in Views/Components/DecisionInput/.
// Reduced from 731 lines to ~150 lines.

import SwiftUI

struct DecisionInputView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppState.self) private var appState
    
    @State private var viewModel = DecisionInputViewModel()
    @State private var selectedCategory = DecisionInputViewModel.DecisionCategory.pricing
    @State private var showUndoConfirmation = false
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Category picker — scrollable tab bar for iPhone
                DecisionInputCategoryPicker(
                    selectedCategory: $selectedCategory,
                    categories: DecisionInputViewModel.DecisionCategory.allCases
                )
                
                Divider()
                
                // Category content
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        switch selectedCategory {
                        case .pricing: PricingSectionView(viewModel: viewModel)
                        case .product: ProductDesignSectionView(viewModel: viewModel)
                        case .marketing: MarketingSectionView(viewModel: viewModel)
                        case .amazon: PricingSectionView(viewModel: viewModel) // Amazon pricing handled in PricingSection
                        case .socialMedia: SocialMediaSectionView(viewModel: viewModel)
                        case .workforce: WorkforceSectionView(viewModel: viewModel)
                        case .production: ProductionSectionView(viewModel: viewModel)
                        case .csr: CSRSectionView(viewModel: viewModel)
                        case .finance: FinanceSectionView(viewModel: viewModel)
                        }
                    }
                    .padding(16)
                }
                
                Divider()
                
                // Budget summary bar
                BudgetBarView(viewModel: viewModel)
            }
            .navigationTitle("Round Decisions")
            #if os(macOS)
            .frame(minWidth: 500, minHeight: 550)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .principal) {
                    // Undo button — visible only when snapshot exists
                    if viewModel.canUndo {
                        Button {
                            showUndoConfirmation = true
                        } label: {
                            Label("Undo", systemImage: "arrow.uturn.backward")
                        }
                        .alert("Restore Previous Decisions?", isPresented: $showUndoConfirmation) {
                            Button("Cancel", role: .cancel) {}
                            Button("Restore") {
                                viewModel.restoreSnapshot()
                            }
                        } message: {
                            Text("Your decisions will be restored to the values from when you opened this screen.")
                        }
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        submitDecisions()
                    } label: {
                        Label("Submit", systemImage: "paperplane.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!viewModel.isValid || viewModel.isSubmitting)
                }
            }
            .onAppear {
                if let session = appState.activeSession, let team = session.playerTeam {
                    viewModel.configure(from: team, config: session.config)
                    // Save snapshot for undo when view appears
                    viewModel.saveSnapshot()
                }
            }
        }
    }
    
    // MARK: - Submit
    
    private func submitDecisions() {
        guard let session = appState.activeSession,
              let teamId = session.playerTeam?.id else { return }
        
        Task {
            let success = await viewModel.submitDecisions(to: session, teamId: teamId)
            if success {
                // Online classroom sessions are backend-authoritative: students only
                // submit, then wait for the professor/backend to process the round.
                // Local processing is reserved for an explicit offline/demo session.
                let isBackendSession = !session.sessionCode.isEmpty
                    && session.sessionCode != session.id.uuidString
                if !isBackendSession {
                    appState.gameController?.processRoundAfterPlayerSubmit()
                }
                dismiss()
            }
        }
    }
}
