import SwiftUI

// MARK: - AICoachViewModel
/// ViewModel for the AI coach screen (S-8).
/// Manages a conversational coaching interface with rule-based advice and Q&A.

@Observable
final class AICoachViewModel {

    // MARK: - Supporting Types

    /// View-specific chat message type.
    /// Named `ChatMessage` to avoid conflict with the model-layer `CoachMessage`.
    struct ChatMessage: Identifiable {
        let id = UUID()
        let role: Role
        let content: String
        let timestamp: Date

        enum Role: String {
            case coach
            case student

            var displayName: String {
                switch self {
                case .coach: return "AI Coach"
                case .student: return "You"
                }
            }

            var isCoach: Bool { self == .coach }
        }

        var formattedTime: String {
            timestamp.formatted(date: .omitted, time: .shortened)
        }
    }

    // MARK: - Properties

    var messages: [ChatMessage] = []
    var userQuestion: String = ""
    var isLoading: Bool = false

    // MARK: - Computed

    var hasMessages: Bool { !messages.isEmpty }

    var canSend: Bool {
        !userQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isLoading
    }

    var latestCoachMessage: ChatMessage? {
        messages.last { $0.role == .coach }
    }

    // MARK: - Actions

    /// Send the user's question and generate a coaching response.
    func askQuestion() {
        let trimmed = userQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        // Add the student's message
        let studentMessage = ChatMessage(
            role: .student,
            content: trimmed,
            timestamp: Date()
        )
        messages.append(studentMessage)
        userQuestion = ""

        isLoading = true

        // MVP: Generate a rule-based response.
        // Future: Send to an AI coaching service (OpenAI, on-device model, etc.)
        let response = generateResponse(to: trimmed)

        let coachMessage = ChatMessage(
            role: .coach,
            content: response,
            timestamp: Date()
        )
        messages.append(coachMessage)

        isLoading = false
    }

    /// Generate automatic advice based on the latest round result.
    func getAutomaticAdvice(from roundResult: RoundResult) {
        var tips: [String] = []

        // Profitability analysis
        if roundResult.profit < 0 {
            tips.append("You lost money this round. Check if your wholesale/internet prices cover production costs (including materials quality). Consider raising prices or switching to standard materials to cut costs.")
        } else if roundResult.profit > 0 && roundResult.marketShare < 0.15 {
            tips.append("You're profitable but have low market share. Consider increasing advertising, adding celebrity endorsements, or expanding retail outlets to grow your customer base.")
        }

        // S/Q Rating analysis
        if roundResult.sqRating < 4.0 {
            tips.append("Your S/Q rating is weak at \(String(format: "%.1f", roundResult.sqRating))★. Switch to superior materials (+2.0★), increase styling budget, and invest in TQM programs to improve quality.")
        } else if roundResult.sqRating >= 8.0 {
            tips.append("Excellent S/Q at \(String(format: "%.1f", roundResult.sqRating))★! You can command premium pricing. Make sure your wholesale and internet prices reflect your quality advantage.")
        }

        // Investor scorecard
        let score = roundResult.scorecard.totalScore
        if score < 40 {
            tips.append("Investor score is low at \(String(format: "%.0f", score))/100. Focus on improving EPS (boost profits), ROE (reduce equity drain), and Image Rating (increase CSR and endorsements).")
        }

        // Channel mix
        if roundResult.revenue > 0 {
            let internetPct = roundResult.internetRevenue / roundResult.revenue
            if internetPct < 0.15 {
                tips.append("Internet sales are only \(String(format: "%.0f", internetPct * 100))% of revenue. The internet channel has higher margins — consider more competitive internet pricing to grow this channel.")
            }
        }

        // Image rating
        if roundResult.scorecard.imageRating < 35 {
            tips.append("Image rating is low. Boost CSR spending, add celebrity endorsements, and improve S/Q to strengthen your brand perception.")
        }

        // Rejection rate
        if roundResult.rejectionRate > 0.08 {
            tips.append("Your rejection rate is \(String(format: "%.1f", roundResult.rejectionRate * 100))% — wasting production. Increase training hours, incentive pay, and TQM investment to reduce defects.")
        }

        // Inventory
        if roundResult.inventory > 20 {
            tips.append("You have \(roundResult.inventory) units in unsold inventory. Reduce production next round or boost demand with advertising, rebates, or competitive pricing.")
        }

        if tips.isEmpty {
            tips.append("Solid performance! Monitor competitor moves, maintain your S/Q advantage, and keep building your investor score.")
        }

        let advice = tips.joined(separator: "\n\n")

        let coachMessage = ChatMessage(
            role: .coach,
            content: advice,
            timestamp: Date()
        )
        messages.append(coachMessage)
    }

    /// Add a welcome message when the coach screen first loads.
    func addWelcomeMessage() {
        guard messages.isEmpty else { return }

        let welcome = ChatMessage(
            role: .coach,
            content: """
            Welcome! I'm your AI business coach for the marketplace simulation. I can help you \
            understand your results and develop winning strategies. Here are some things you can ask:

            - "How do I improve my S/Q rating?"
            - "Should I use superior or standard materials?"
            - "What's a good pricing strategy for wholesale vs internet?"
            - "How do I boost my investor score?"
            - "Should I invest in celebrity endorsements?"
            - "How does CSR affect my image rating?"
            - "How do I reduce my rejection rate?"
            - "What should I set for workforce compensation?"
            - "Should I offer mail-in rebates or free shipping?"

            Ask me anything about your business decisions!
            """,
            timestamp: Date()
        )
        messages.append(welcome)
    }

    /// Clear the conversation history.
    func clearChat() {
        messages.removeAll()
    }

    // MARK: - Private: Rule-Based Response Engine

    private func generateResponse(to question: String) -> String {
        let lower = question.lowercased()

        // S/Q Rating questions
        if lower.contains("s/q") || lower.contains("sq") || lower.contains("quality rating") {
            return """
            The S/Q (Styling/Quality) rating is one of the most important metrics in this simulation:

            1. **Materials**: Superior materials add +2.0★ but cost 40% more. Worth it for premium strategies.
            2. **Styling Budget**: Higher styling investment directly improves S/Q. Aim for $5,000+ per model.
            3. **Models Offered**: More models = broader appeal, but each model needs styling investment.
            4. **TQM/Six Sigma**: Cumulative effect — consistent investment pays off more over time.
            5. **Target**: S/Q above 7.0★ lets you charge premium prices. Below 4.0★ hurts demand significantly.
            """
        }

        // Pricing questions
        if lower.contains("price") || lower.contains("pricing") {
            return """
            There are three pricing channels, each with different dynamics:

            1. **Wholesale** (60% of market): Your primary channel. Price competitively — the market average matters.
            2. **Internet** (25% of market): Higher margins, direct-to-consumer. Can price 10-20% above wholesale.
            3. **Private Label** (15% of market): Bid-based — lowest bid wins. Good for filling excess capacity.

            **Key insight**: High S/Q rating justifies premium pricing. If your S/Q is 8+★, price 15-25% above average.
            """
        }

        // Marketing questions
        if lower.contains("marketing") || lower.contains("advertis") || lower.contains("endorsement") {
            return """
            Marketing drives demand through multiple levers:

            1. **Advertising**: Increases brand awareness. Diminishing returns above $15,000/round.
            2. **Celebrity Endorsements**: Local ($5K) → National ($15K) → Global ($35K). Global gives +30% demand boost.
            3. **Retail Outlets**: More outlets = broader reach. Cost: $50/outlet/round.
            4. **Image Rating**: Marketing + CSR + S/Q all contribute to your image, which affects the investor score.

            Start with advertising, then add endorsements as revenue grows.
            """
        }

        // Materials questions
        if lower.contains("material") || lower.contains("superior") || lower.contains("standard") {
            return """
            Materials quality is a strategic choice:

            **Standard Materials**: Baseline cost, no S/Q bonus. Good for low-cost strategies.
            **Superior Materials**: +2.0★ S/Q boost, 40% higher material cost.

            **When to use Superior**: If you're pursuing a differentiation or best-cost strategy. The S/Q boost is huge.
            **When to stay Standard**: If you're a low-cost leader competing on price volume.

            Most winning strategies eventually move to superior materials by round 4-5.
            """
        }

        // Investor score questions
        if lower.contains("investor") || lower.contains("scorecard") || lower.contains("eps") || lower.contains("roe") {
            return """
            The Investor Scorecard has 5 metrics, each worth 20 points (total 100):

            1. **EPS** (Earnings Per Share): Boost by increasing profits or buying back shares.
            2. **ROE** (Return on Equity): Keep equity working efficiently. High profits / moderate equity.
            3. **Stock Price**: Driven by EPS growth, dividends, and overall performance.
            4. **Image Rating**: Improve with CSR, endorsements, high S/Q, and advertising.
            5. **Credit Rating**: Maintain low debt-to-equity ratio and positive cash flow.

            Targets ratchet up each round — you need consistent improvement, not just one good round.
            """
        }

        // CSR questions
        if lower.contains("csr") || lower.contains("citizenship") || lower.contains("image") {
            return """
            CSR (Corporate Social Responsibility) is a key lever for Image Rating:

            1. **Diminishing returns**: First $3,000-5,000 has the most impact. Over $10,000 adds little.
            2. **Image Rating**: Combines CSR + endorsements + S/Q + advertising reputation.
            3. **Investor Score**: Image Rating is worth 20 points on the investor scorecard.
            4. **Long-term**: Image builds over time — start investing early for compounding benefits.
            """
        }

        // Production questions
        if lower.contains("production") || lower.contains("produce") || lower.contains("overtime") || lower.contains("capacity") || lower.contains("rejection") || lower.contains("defect") {
            return """
            Production management in practenture:

            1. **Plant Capacity**: Your base limit. Overtime can extend it by up to 20%.
            2. **Overtime**: 50% premium on overtime units. Use only when demand justifies it.
            3. **Rejection Rate**: Starts at ~12%. Reduce with TQM, training hours, incentive pay, and best practices.
            4. **Target Rejection Rate**: Under 5% is excellent. Under 3% gives you a real cost advantage.
            5. **Private Label**: Use excess capacity for private-label bids to reduce per-unit fixed costs.
            """
        }

        // Workforce questions
        if lower.contains("workforce") || lower.contains("wage") || lower.contains("training") || lower.contains("incentive") || lower.contains("worker") {
            return """
            Workforce management affects quality, cost, and S/Q:

            1. **Base Wage**: Industry average is $25,000. Higher wages attract better workers (less defects).
            2. **Incentive Pay**: Per-pair bonus ($0-3.00). Motivates output and reduces rejection rate.
            3. **Training Hours**: More training = higher quality, lower rejection rate, better S/Q rating.
            4. **Best Practices**: Additional investment in quality programs — reduces defects further.

            **Strategy**: Invest early in training and incentive pay. Lower rejection = less waste = lower effective cost.
            """
        }

        // Rebate and shipping questions
        if lower.contains("rebate") || lower.contains("shipping") || lower.contains("delivery") || lower.contains("mail-in") || lower.contains("free ship") {
            return """
            Demand levers beyond pricing and quality:

            **Mail-in Rebates (Wholesale)**:
            - Effectively lowers consumer price without changing your wholesale price
            - ~60% redemption rate, so cost is manageable
            - Good for boosting wholesale volume without a full price cut

            **Rush Delivery (Wholesale)**:
            - +6% demand boost but $2/unit extra cost
            - Worth it if margins support the cost

            **Free Shipping Threshold (Internet)**:
            - Lower threshold = more internet orders
            - $0 = free shipping on all orders (maximum demand boost)
            - Balance the shipping cost against internet margin advantage
            """
        }

        // Finance questions
        if lower.contains("dividend") || lower.contains("loan") || lower.contains("debt") || lower.contains("buyback") || lower.contains("finance") || lower.contains("stock") || lower.contains("issu") {
            return """
            Financial decisions affect multiple investor metrics:

            1. **Dividends**: Investors expect stable/growing dividends. Cutting hurts stock price. Start at $0.50/share.
            2. **Loans**: Borrow to fund growth, but high debt hurts credit rating. Keep debt-to-equity under 0.5.
            3. **Share Buybacks**: Reduces shares outstanding → boosts EPS and ROE. Powerful late-game move.
            4. **Stock Issuance**: Raises capital but DILUTES EPS. Use sparingly — signals weakness.
            5. **Credit Rating**: Affected by debt-to-equity, cash flow, and interest coverage. A+ is the goal.
            """
        }

        // Strategy questions
        if lower.contains("strategy") || lower.contains("approach") || lower.contains("what should") {
            return """
            Three winning marketplace strategies:

            **Low-Cost Leader**: Standard materials, competitive prices, high volume. Win on efficiency.
            **Differentiator**: Superior materials, high S/Q, celebrity endorsements, premium pricing.
            **Best-Cost Provider**: Balance — superior materials by round 4, moderate pricing, strong marketing.

            **Key principle**: Pick one strategy and execute consistently. Dramatic shifts between rounds confuse the market.

            Most successful teams transition to a Best-Cost strategy by mid-game.
            """
        }

        // Default response
        return """
        That's a great question! Here are some key tips to consider:

        1. **S/Q Rating** is king — it drives demand across all channels and justifies premium pricing.
        2. **Balance your investor scorecard** — don't over-optimize one metric at the expense of others.
        3. **Watch competitor moves** — if they all go low-cost, differentiation can be very profitable.
        4. **Think long-term** — TQM, CSR, and image compound over rounds.

        Try asking about specific topics: pricing, S/Q rating, marketing, materials, investor score, CSR, or strategy!
        """
    }
}
