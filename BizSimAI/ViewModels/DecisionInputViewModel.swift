import SwiftUI

// MARK: - DecisionCategory Enum

extension DecisionInputViewModel {
    enum DecisionCategory: String, CaseIterable, Identifiable {
        case pricing = "Pricing"
        case product = "Product"
        case marketing = "Marketing"
        case amazon = "Amazon"
        case socialMedia = "Social"
        case workforce = "Workforce"
        case production = "Production"
        case csr = "CSR"
        case finance = "Finance"
        
        var id: String { rawValue }
        
        var icon: String {
            switch self {
            case .pricing: return "tag"
            case .product: return "star"
            case .marketing: return "megaphone"
            case .amazon: return "shippingbox"
            case .socialMedia: return "person.3.sequence"
            case .workforce: return "person.2"
            case .production: return "hammer"
            case .csr: return "leaf"
            case .finance: return "banknote"
            }
        }
    }
}

// MARK: - DecisionInputViewModel
/// Decision input ViewModel.
/// Manages 7 decision categories: Pricing, Product Design, Marketing,
/// Workforce, Production, CSR, and Finance with validation and budget tracking.

@Observable
final class DecisionInputViewModel {

    // MARK: - Pricing & Sales
    var wholesalePrice: Double = 80.0
    var internetPrice: Double = 90.0
    var privateLabelBidPrice: Double = 45.0
    var privateLabelMaxUnits: Int = 50

    // MARK: - Product Design (S/Q Rating)
    var materialsQuality: MaterialsQuality = .standard
    var stylingBudget: Double = 3_000
    var modelsOffered: Int = 3
    var tqmInvestment: Double = 2_000
    var bestPracticesInvestment: Double = 1_000

    // MARK: - Marketing
    var advertisingBudget: Double = 8_000
    var celebrityEndorsement: CelebrityEndorsement = .none
    var retailOutlets: Int = 20
    var mailInRebate: Double = 0
    var deliveryTime: DeliveryTime = .standard
    var freeShippingThreshold: Double = 100

    // MARK: - Amazon Marketplace
    var amazonPrice: Double = 85.0
    var amazonAdBudget: Double = 0
    var fulfillmentMethod: FulfillmentMethod = .fbm

    // MARK: - Social Media & Influencer Marketing
    var tiktokBudget: Double = 0
    var instagramBudget: Double = 0
    var youtubeBudget: Double = 0
    var influencerTier: InfluencerTier = .none

    // MARK: - Workforce Compensation
    var baseWage: Double = 25_000
    var incentivePay: Double = 0.50
    var trainingHours: Double = 20

    // MARK: - Production
    var productionQuantity: Int = 200
    var overtimePercent: Double = 0

    // MARK: - Corporate Citizenship (CSR)
    var csrInvestment: Double = 2_000

    // MARK: - Finance
    var dividendsPerShare: Double = 0.50
    var newLoanAmount: Double = 0
    var sharesBuyback: Int = 0
    var sharesIssued: Int = 0

    // MARK: - Constraints
    var availableCash: Double = 100_000
    var maxProductionCapacity: Int = 500
    var unitProductionCost: Double = 30.0
    var currentSQRating: Double = 5.0
    var currentDebt: Double = 0
    var currentShares: Int = 10_000

    // MARK: - Validation Ranges
    static let wholesalePriceRange: ClosedRange<Double> = 30...200
    static let internetPriceRange: ClosedRange<Double> = 35...250
    static let privateLabelPriceRange: ClosedRange<Double> = 20...100
    static let stylingRange: ClosedRange<Double> = 0...15_000
    static let tqmRange: ClosedRange<Double> = 0...10_000
    static let bestPracticesRange: ClosedRange<Double> = 0...10_000
    static let advertisingRange: ClosedRange<Double> = 0...30_000
    static let csrRange: ClosedRange<Double> = 0...10_000
    static let modelsRange = 1...8
    static let outletsRange = 5...60
    static let productionRange = 0...600
    static let overtimeRange: ClosedRange<Double> = 0...20
    static let dividendRange: ClosedRange<Double> = 0...5.0
    static let loanRange: ClosedRange<Double> = 0...50_000
    static let buybackRange = 0...2000
    static let issuanceRange = 0...2000
    static let rebateRange: ClosedRange<Double> = 0...15
    static let freeShipRange: ClosedRange<Double> = 0...200
    static let amazonPriceRange: ClosedRange<Double> = 30...200
    static let amazonAdRange: ClosedRange<Double> = 0...15_000
    static let baseWageRange: ClosedRange<Double> = 15_000...40_000
    static let incentivePayRange: ClosedRange<Double> = 0...3.0
    static let trainingHoursRange: ClosedRange<Double> = 0...80
    static let socialMediaRange: ClosedRange<Double> = 0...15_000

    // MARK: - Undo / Rollback

    /// Snapshot of decision values for undo/rollback.
    private var decisionSnapshot: DecisionSnapshot?

    /// Returns true if a snapshot exists (undo is available).
    var canUndo: Bool { decisionSnapshot != nil }

    struct DecisionSnapshot {
        var wholesalePrice: Double
        var internetPrice: Double
        var privateLabelBidPrice: Double
        var privateLabelMaxUnits: Int
        var materialsQuality: MaterialsQuality
        var stylingBudget: Double
        var modelsOffered: Int
        var tqmInvestment: Double
        var bestPracticesInvestment: Double
        var advertisingBudget: Double
        var celebrityEndorsement: CelebrityEndorsement
        var retailOutlets: Int
        var mailInRebate: Double
        var deliveryTime: DeliveryTime
        var freeShippingThreshold: Double
        var amazonPrice: Double
        var amazonAdBudget: Double
        var fulfillmentMethod: FulfillmentMethod
        var tiktokBudget: Double
        var instagramBudget: Double
        var youtubeBudget: Double
        var influencerTier: InfluencerTier
        var baseWage: Double
        var incentivePay: Double
        var trainingHours: Double
        var productionQuantity: Int
        var overtimePercent: Double
        var csrInvestment: Double
        var dividendsPerShare: Double
        var newLoanAmount: Double
        var sharesBuyback: Int
        var sharesIssued: Int
    }

    /// Save current decisions as a snapshot for undo.
    func saveSnapshot() {
        decisionSnapshot = DecisionSnapshot(
            wholesalePrice: wholesalePrice,
            internetPrice: internetPrice,
            privateLabelBidPrice: privateLabelBidPrice,
            privateLabelMaxUnits: privateLabelMaxUnits,
            materialsQuality: materialsQuality,
            stylingBudget: stylingBudget,
            modelsOffered: modelsOffered,
            tqmInvestment: tqmInvestment,
            bestPracticesInvestment: bestPracticesInvestment,
            advertisingBudget: advertisingBudget,
            celebrityEndorsement: celebrityEndorsement,
            retailOutlets: retailOutlets,
            mailInRebate: mailInRebate,
            deliveryTime: deliveryTime,
            freeShippingThreshold: freeShippingThreshold,
            amazonPrice: amazonPrice,
            amazonAdBudget: amazonAdBudget,
            fulfillmentMethod: fulfillmentMethod,
            tiktokBudget: tiktokBudget,
            instagramBudget: instagramBudget,
            youtubeBudget: youtubeBudget,
            influencerTier: influencerTier,
            baseWage: baseWage,
            incentivePay: incentivePay,
            trainingHours: trainingHours,
            productionQuantity: productionQuantity,
            overtimePercent: overtimePercent,
            csrInvestment: csrInvestment,
            dividendsPerShare: dividendsPerShare,
            newLoanAmount: newLoanAmount,
            sharesBuyback: sharesBuyback,
            sharesIssued: sharesIssued
        )
    }

    /// Restore decisions from the last snapshot.
    /// Returns true if a snapshot was restored, false if no snapshot exists.
    @discardableResult
    func restoreSnapshot() -> Bool {
        guard let snapshot = decisionSnapshot else { return false }
        wholesalePrice = snapshot.wholesalePrice
        internetPrice = snapshot.internetPrice
        privateLabelBidPrice = snapshot.privateLabelBidPrice
        privateLabelMaxUnits = snapshot.privateLabelMaxUnits
        materialsQuality = snapshot.materialsQuality
        stylingBudget = snapshot.stylingBudget
        modelsOffered = snapshot.modelsOffered
        tqmInvestment = snapshot.tqmInvestment
        bestPracticesInvestment = snapshot.bestPracticesInvestment
        advertisingBudget = snapshot.advertisingBudget
        celebrityEndorsement = snapshot.celebrityEndorsement
        retailOutlets = snapshot.retailOutlets
        mailInRebate = snapshot.mailInRebate
        deliveryTime = snapshot.deliveryTime
        freeShippingThreshold = snapshot.freeShippingThreshold
        amazonPrice = snapshot.amazonPrice
        amazonAdBudget = snapshot.amazonAdBudget
        fulfillmentMethod = snapshot.fulfillmentMethod
        tiktokBudget = snapshot.tiktokBudget
        instagramBudget = snapshot.instagramBudget
        youtubeBudget = snapshot.youtubeBudget
        influencerTier = snapshot.influencerTier
        baseWage = snapshot.baseWage
        incentivePay = snapshot.incentivePay
        trainingHours = snapshot.trainingHours
        productionQuantity = snapshot.productionQuantity
        overtimePercent = snapshot.overtimePercent
        csrInvestment = snapshot.csrInvestment
        dividendsPerShare = snapshot.dividendsPerShare
        newLoanAmount = snapshot.newLoanAmount
        sharesBuyback = snapshot.sharesBuyback
        sharesIssued = snapshot.sharesIssued
        // Clear the snapshot after restore
        decisionSnapshot = nil
        return true
    }

    // MARK: - State
    var isSubmitting: Bool = false
    var submissionError: String?
    var didSubmitSuccessfully: Bool = false
    var submittedViaBackend: Bool = false

    // MARK: - Computed: Spending

    var productionCost: Double {
        let materialsCost = unitProductionCost * materialsQuality.costMultiplier
        let regularUnits = min(productionQuantity, maxProductionCapacity)
        let overtimeUnits = max(0, productionQuantity - maxProductionCapacity)
        return materialsCost * Double(regularUnits) + materialsCost * 1.5 * Double(overtimeUnits)
    }

    var endorsementCost: Double {
        celebrityEndorsement.annualCost
    }

    var outletCost: Double {
        Double(retailOutlets) * 50
    }

    var workforceCost: Double {
        let workersNeeded = max(1, productionQuantity / 10)
        let wageCost = baseWage * Double(workersNeeded) / 1000.0
        let incentiveCost = incentivePay * Double(productionQuantity)
        let trainingCost = trainingHours * 50.0 * Double(workersNeeded) / 1000.0
        return wageCost + incentiveCost + trainingCost
    }

    var socialMediaCost: Double {
        let platformSpend = tiktokBudget + instagramBudget + youtubeBudget
        let influencerCount: Int
        switch influencerTier {
        case .none: influencerCount = 0
        case .nano: influencerCount = Int(platformSpend / 1000)
        case .micro: influencerCount = max(1, Int(platformSpend / 5000))
        case .macro: influencerCount = max(1, Int(platformSpend / 20000))
        case .mega: influencerCount = max(1, Int(platformSpend / 60000))
        }
        return platformSpend + Double(influencerCount) * influencerTier.costPerInfluencer
    }

    var amazonCost: Double {
        amazonAdBudget  // Ad spend is upfront; referral/FBA fees come from sales
    }

    var totalSpend: Double {
        productionCost + stylingBudget + tqmInvestment + bestPracticesInvestment
            + advertisingBudget + outletCost + endorsementCost
            + csrInvestment + dividendsPerShare * Double(currentShares + sharesIssued)
            + workforceCost + socialMediaCost + amazonCost
    }

    var remainingBudget: Double {
        availableCash - totalSpend + newLoanAmount
    }

    var isOverBudget: Bool {
        remainingBudget < -100 // Small tolerance
    }

    var budgetUtilization: Double {
        guard availableCash > 0 else { return 0 }
        return min(totalSpend / availableCash, 1.5)
    }

    // MARK: - Estimated S/Q Preview
    var estimatedSQRating: Double {
        var sq = 3.0 + materialsQuality.sqBonus
        sq += min(2.0, log(1 + stylingBudget / 3000) / log(5))
        sq += min(1.5, Double(modelsOffered) * 0.3)
        sq += min(1.5, log(1 + tqmInvestment / 5000) / log(10))
        sq += min(0.5, bestPracticesInvestment / 5000)
        sq += min(0.5, trainingHours / 80.0)
        return min(10, max(1, 0.4 * currentSQRating + 0.6 * sq))
    }

    // MARK: - Estimated Rejection Rate Preview
    var estimatedRejectionRate: Double {
        var rate = 0.12
        rate -= min(0.04, tqmInvestment / 200000)
        rate -= min(0.03, trainingHours / 100.0 * 0.03)
        rate -= min(0.02, incentivePay / 2.0 * 0.02)
        rate -= min(0.02, bestPracticesInvestment / 5000 * 0.02)
        return max(0.01, rate)
    }

    // MARK: - Validation

    var isValid: Bool {
        Self.wholesalePriceRange.contains(wholesalePrice)
            && Self.internetPriceRange.contains(internetPrice)
            && Self.privateLabelPriceRange.contains(privateLabelBidPrice)
            && Self.amazonPriceRange.contains(amazonPrice)
            && Self.productionRange.contains(productionQuantity)
            && Self.advertisingRange.contains(advertisingBudget)
            && Self.baseWageRange.contains(baseWage)
            && Self.dividendRange.contains(dividendsPerShare)
            && Self.loanRange.contains(newLoanAmount)
            && Self.buybackRange.contains(sharesBuyback)
            && Self.issuanceRange.contains(sharesIssued)
            && !isOverBudget
    }

    var warnings: [String] {
        var result: [String] = []

        if isOverBudget {
            result.append("Over budget. Reduce spending or take a loan.")
        }

        if wholesalePrice < unitProductionCost * materialsQuality.costMultiplier * 1.3 {
            result.append("Wholesale price is close to cost — low margin risk.")
        }

        if internetPrice < wholesalePrice {
            result.append("Internet price is below wholesale — unusual channel strategy.")
        }

        if advertisingBudget == 0 {
            result.append("No advertising — customers may not find your product.")
        }

        if csrInvestment == 0 {
            result.append("No CSR spending — image rating will suffer.")
        }

        if productionQuantity == 0 {
            result.append("Zero production means no sales this round.")
        }

        if materialsQuality == .standard && wholesalePrice > 100 {
            result.append("Standard materials with premium pricing — S/Q may not justify price.")
        }

        if dividendsPerShare > 2.0 && remainingBudget < availableCash * 0.1 {
            result.append("High dividends with low cash — consider reducing to preserve liquidity.")
        }

        if sharesIssued > 500 {
            result.append("Issuing many shares — EPS will be diluted significantly.")
        }

        if baseWage < 20_000 {
            result.append("Low wages may hurt worker productivity and increase rejection rate.")
        }

        if trainingHours == 0 && estimatedRejectionRate > 0.08 {
            result.append("No training — rejection rate will remain high, wasting materials.")
        }

        if mailInRebate > 5 && wholesalePrice < 70 {
            result.append("Large rebate on low-priced product — margin squeeze risk.")
        }

        if socialMediaCost > availableCash * 0.15 {
            result.append("Social media spend is over 15% of cash — consider reducing.")
        }

        if influencerTier != .none && (tiktokBudget + instagramBudget + youtubeBudget) == 0 {
            result.append("Influencer tier selected but no platform budget — influencers need platform spend.")
        }

        if amazonPrice < unitProductionCost * materialsQuality.costMultiplier * 1.2 {
            result.append("Amazon price barely covers production cost — after 15% referral fee, you'll lose money.")
        }

        if fulfillmentMethod == .fba && amazonAdBudget == 0 {
            result.append("Using FBA without Amazon ads — consider PPC to maximize visibility.")
        }

        return result
    }

    // MARK: - Formatted Display

    func formatted(_ value: Double) -> String {
        value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    var formattedTotalSpend: String { formatted(totalSpend) }
    var formattedRemainingBudget: String { formatted(remainingBudget) }
    var formattedAvailableCash: String { formatted(availableCash) }

    // MARK: - Actions

    func submitDecisions(to session: SimulationSession, teamId: UUID) async -> Bool {
        guard isValid else {
            submissionError = warnings.first ?? "Invalid decisions. Please review."
            return false
        }

        isSubmitting = true
        submissionError = nil
        submittedViaBackend = false

        let pricing = PricingDecision(
            wholesalePrice: wholesalePrice,
            internetPrice: internetPrice,
            privateLabelBidPrice: privateLabelBidPrice,
            privateLabelMaxUnits: privateLabelMaxUnits,
            amazonPrice: amazonPrice,
            amazonAdBudget: amazonAdBudget
        )
        
        let product = ProductDecision(
            materialsQuality: materialsQuality,
            stylingBudget: stylingBudget,
            modelsOffered: modelsOffered,
            tqmInvestment: tqmInvestment
        )
        
        let marketing = MarketingDecision(
            advertisingBudget: advertisingBudget,
            celebrityEndorsement: celebrityEndorsement,
            retailOutlets: retailOutlets,
            mailInRebate: mailInRebate,
            deliveryTime: deliveryTime,
            freeShippingThreshold: freeShippingThreshold,
            tiktokBudget: tiktokBudget,
            instagramBudget: instagramBudget,
            youtubeBudget: youtubeBudget,
            influencerTier: influencerTier
        )
        
        let workforce = WorkforceDecision(
            baseWage: baseWage,
            incentivePay: incentivePay,
            trainingHours: trainingHours,
            bestPracticesInvestment: bestPracticesInvestment
        )
        
        let production = ProductionDecision(
            productionQuantity: productionQuantity,
            overtimePercent: overtimePercent
        )
        
        let finance = FinanceDecision(
            csrInvestment: csrInvestment,
            dividendsPerShare: dividendsPerShare,
            newLoanAmount: newLoanAmount,
            sharesBuyback: sharesBuyback,
            sharesIssued: sharesIssued
        )
        
        let decision = PlayerDecision(
            teamId: teamId,
            round: session.currentRound,
            pricing: pricing,
            product: product,
            marketing: marketing,
            workforce: workforce,
            production: production,
            finance: finance,
            fulfillmentMethod: fulfillmentMethod
        )

        // Try to submit to backend first (if online)
        let sessionCode = session.sessionCode
        
        // Store locally first (optimistic)
        session.submitDecision(decision)

        // Try backend submission
        do {
            try await SyncService.shared.syncDecisionSubmission(
                sessionCode: sessionCode,
                round: session.currentRound,
                teamId: teamId,
                decision: decision
            )
            submittedViaBackend = true
        } catch {
            // Backend failed — decision is already stored locally, keep working
            submissionError = "Decision saved locally. Cloud sync failed: \(error.localizedDescription)"
        }

        isSubmitting = false
        didSubmitSuccessfully = true
        return true
    }

    func configure(from team: TeamStatus, config: SessionConfiguration) {
        self.availableCash = team.cash
        self.maxProductionCapacity = config.plantCapacity
        self.unitProductionCost = config.baseCostPerUnit
        self.currentSQRating = team.sqRating
        self.currentDebt = team.totalDebt
        self.currentShares = team.sharesOutstanding
    }

    func resetForm() {
        wholesalePrice = 80.0
        internetPrice = 90.0
        privateLabelBidPrice = 45.0
        privateLabelMaxUnits = 50
        materialsQuality = .standard
        stylingBudget = 3_000
        modelsOffered = 3
        tqmInvestment = 2_000
        bestPracticesInvestment = 1_000
        advertisingBudget = 8_000
        celebrityEndorsement = .none
        retailOutlets = 20
        mailInRebate = 0
        deliveryTime = .standard
        freeShippingThreshold = 100
        amazonPrice = 85.0
        amazonAdBudget = 0
        fulfillmentMethod = .fbm
        tiktokBudget = 0
        instagramBudget = 0
        youtubeBudget = 0
        influencerTier = .none
        baseWage = 25_000
        incentivePay = 0.50
        trainingHours = 20
        productionQuantity = 200
        overtimePercent = 0
        csrInvestment = 2_000
        dividendsPerShare = 0.50
        newLoanAmount = 0
        sharesBuyback = 0
        sharesIssued = 0
        submissionError = nil
        didSubmitSuccessfully = false
    }
}
