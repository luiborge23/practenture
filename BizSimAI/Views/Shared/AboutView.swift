// AboutView.swift
// BizSimAI
//
// X-3: Help and information view explaining how the simulation works,
// decision types, and scoring methodology.

import SwiftUI

struct AboutView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                appHeader
                howItWorksSection
                decisionGuideSection
                scoringSection
                professorGuideSection
                creditsSection
            }
            .padding(24)
        }
        .navigationTitle("About BizSim AI")
        #if os(macOS)
        .frame(minWidth: 480)
        #endif
    }

    // MARK: - App Header

    private var appHeader: some View {
        HStack(spacing: 16) {
            Image(systemName: "building.2.crop.circle.fill")
                .font(.system(size: 48))
                .foregroundStyle(.blue.gradient)

            VStack(alignment: .leading, spacing: 4) {
                Text("BizSim AI")
                    .font(.title)
                    .fontWeight(.bold)

                Text("Business Marketplace Simulation")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Text("Version 1.0.0")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            Spacer()
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - How It Works

    private var howItWorksSection: some View {
        infoSection(
            title: "How the Simulation Works",
            icon: "gearshape.2.fill",
            color: .blue
        ) {
            VStack(alignment: .leading, spacing: 12) {
                infoParagraph(
                    "BizSim AI is a marketplace simulation where teams run athletic footwear companies competing in a global marketplace. Each round, you make strategic decisions across pricing, production, marketing, workforce, and finance."
                )

                bulletPoint("Each simulation runs for a fixed number of rounds (typically 5-15)")
                bulletPoint("Sell through 4 channels: Wholesale, Amazon, Internet (direct), and Private Label")
                bulletPoint("AI competitors use distinct strategies (Low-Cost, Differentiator, Best-Cost, Adaptive)")
                bulletPoint("Your S/Q (Styling/Quality) Rating drives demand and justifies premium pricing")
                bulletPoint("Social media (TikTok, Instagram, YouTube) and influencer marketing boost demand and image")
                bulletPoint("The Investor Scorecard (EPS, ROE, Stock Price, Image, Credit) determines your rank")
                bulletPoint("Scorecard targets ratchet up each round — consistent improvement is essential")
                bulletPoint("Investments in TQM, training, and CSR compound over time")
            }
        }
    }

    // MARK: - Decision Guide

    private var decisionGuideSection: some View {
        infoSection(
            title: "Decision Guide",
            icon: "slider.horizontal.3",
            color: .orange
        ) {
            VStack(alignment: .leading, spacing: 16) {
                decisionCard(
                    title: "Pricing (4 Channels)",
                    icon: "dollarsign.circle.fill",
                    color: .green,
                    description: "Set wholesale, Amazon, internet, and private-label prices. Wholesale is your primary channel (~50%). Amazon offers massive reach but charges 15% referral fees. Internet is direct-to-consumer with highest margins. Private label fills excess capacity."
                )

                decisionCard(
                    title: "Amazon Marketplace",
                    icon: "shippingbox.fill",
                    color: .orange,
                    description: "Set your Amazon listing price and PPC ad budget. Choose FBA ($4.50/unit, Prime badge, +25% Buy Box boost) or FBM ($1.50/unit, lower visibility). Amazon's 15% referral fee eats margins — price strategically."
                )

                decisionCard(
                    title: "Product Design",
                    icon: "star.fill",
                    color: .yellow,
                    description: "Choose materials quality (Standard vs Superior +2.0★), styling budget, number of models, TQM/Six Sigma investment, and best practices training. These drive your S/Q Rating (1-10★)."
                )

                decisionCard(
                    title: "Marketing & Demand",
                    icon: "megaphone.fill",
                    color: .purple,
                    description: "Set advertising budget, celebrity endorsements (Local/National/Global), retail outlets, mail-in rebates, delivery speed (Standard/Rush), and free shipping threshold for internet sales."
                )

                decisionCard(
                    title: "Social Media & Influencers",
                    icon: "person.3.fill",
                    color: .pink,
                    description: "Allocate budgets across TikTok (viral awareness), Instagram (brand image), and YouTube (credibility). Choose influencer tiers from Nano (6.5% engagement, $300/ea) to Mega (1% engagement, $50K/ea). Social media boosts internet demand, image rating, and overall awareness."
                )

                decisionCard(
                    title: "Workforce",
                    icon: "person.2.fill",
                    color: .cyan,
                    description: "Set base wages, incentive pay per pair, and training hours. Higher investment reduces your rejection/defect rate (from 12% base down to 1% minimum) and boosts S/Q rating."
                )

                decisionCard(
                    title: "Production",
                    icon: "shippingbox.fill",
                    color: .orange,
                    description: "Set production volume within plant capacity. Overtime extends capacity by 20% at 50% premium. Rejected units are wasted — reduce defects through workforce and TQM investment."
                )

                decisionCard(
                    title: "CSR & Image",
                    icon: "leaf.fill",
                    color: .green,
                    description: "Corporate Social Responsibility spending directly affects your Image Rating (worth 20 points on the investor scorecard). First $3K-5K has the most impact."
                )

                decisionCard(
                    title: "Finance",
                    icon: "banknote.fill",
                    color: .blue,
                    description: "Manage dividends, loans, share buybacks, and stock issuance. Dividends and buybacks boost stock price and EPS. Keep debt-to-equity under 0.5 to maintain your credit rating."
                )
            }
        }
    }

    // MARK: - Scoring

    private var scoringSection: some View {
        infoSection(
            title: "Scoring",
            icon: "trophy.fill",
            color: .yellow
        ) {
            VStack(alignment: .leading, spacing: 12) {
                infoParagraph(
                    "The primary scoring method is the Investor Scorecard — five metrics worth 20 points each (100 total). Targets ratchet up each round, demanding consistent improvement."
                )

                scoreMetric(
                    title: "EPS (Earnings Per Share) — 20 pts",
                    description: "Net income divided by shares outstanding. Boost with higher profits or share buybacks."
                )

                scoreMetric(
                    title: "ROE (Return on Equity) — 20 pts",
                    description: "How efficiently you use shareholder equity. High profits with moderate equity is ideal."
                )

                scoreMetric(
                    title: "Stock Price — 20 pts",
                    description: "Driven by EPS growth, dividends, and overall financial health."
                )

                scoreMetric(
                    title: "Image Rating — 20 pts",
                    description: "Built from CSR spending, celebrity endorsements, S/Q rating, and advertising."
                )

                scoreMetric(
                    title: "Credit Rating — 20 pts",
                    description: "Maintain low debt-to-equity ratio and positive cash flow. A+ is the target."
                )

                infoParagraph(
                    "Alternative scoring modes are also available: Cumulative Profit, Total Revenue, or a Composite Score (40% profit + 30% revenue + 30% market share)."
                )
            }
        }
    }

    // MARK: - Professor Guide

    private var professorGuideSection: some View {
        infoSection(
            title: "Professor Features",
            icon: "person.crop.rectangle.stack.fill",
            color: .indigo
        ) {
            VStack(alignment: .leading, spacing: 16) {
                infoParagraph(
                    "Professors can create and manage simulation sessions, enroll students, configure teams, set deadlines, post announcements, and grade student performance."
                )

                decisionCard(
                    title: "Session Templates",
                    icon: "wand.and.stars",
                    color: .indigo,
                    description: "Quick Setup with pre-built templates: Intro to Marketing (5 rounds), Advanced Strategy (12 rounds), Entrepreneurship (8 rounds), or Quick Demo (3 rounds). Customize any template further."
                )

                decisionCard(
                    title: "Teams & Enrollment",
                    icon: "person.3.fill",
                    color: .blue,
                    description: "Configure max teams and team size (1-6 students). Students join with a session code. Auto-assign distributes students evenly, or manually assign via the Teams tab."
                )

                decisionCard(
                    title: "Timing & Deadlines",
                    icon: "clock.fill",
                    color: .orange,
                    description: "Manual Advance (professor controls pacing) or Timed Rounds (auto-advance after X hours). Set late submission policies and session expiry dates for async classes."
                )

                decisionCard(
                    title: "Live Monitoring",
                    icon: "chart.bar.doc.horizontal.fill",
                    color: .green,
                    description: "Track submission status, team performance, S/Q ratings, investor scores, and cash positions in real-time. Pause/resume sessions for class discussions."
                )

                decisionCard(
                    title: "Announcements",
                    icon: "megaphone.fill",
                    color: .purple,
                    description: "Post general announcements or round-specific debrief notes visible to all teams. Keep students informed about deadlines, strategy tips, or schedule changes."
                )

                decisionCard(
                    title: "Grading",
                    icon: "graduationcap.fill",
                    color: .red,
                    description: "Automatic grade mapping from Investor Score to letter grades (A through F). View all team grades at a glance and export to CSV for LMS upload."
                )
            }
        }
    }

    // MARK: - Credits

    private var creditsSection: some View {
        VStack(spacing: 8) {
            Text("Built with SwiftUI and Swift Charts")
                .font(.caption)
                .foregroundStyle(.secondary)

            Text("AI Coaching powered by Claude")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    // MARK: - Reusable Components

    private func infoSection<Content: View>(
        title: String,
        icon: String,
        color: Color,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(color)

                Text(title)
                    .font(.title3)
                    .fontWeight(.bold)
            }

            content()
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    private func infoParagraph(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func bulletPoint(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text("\u{2022}")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Text(text)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func decisionCard(title: String, icon: String, color: Color, description: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)

                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(color.opacity(0.06))
        )
    }

    private func scoreMetric(title: String, description: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)

            Text(description)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.leading, 8)
    }
}
