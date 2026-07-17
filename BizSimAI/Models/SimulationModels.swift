// SimulationModels.swift
// BizSimAI
//
// Domain models for the BizSim AI marketplace simulation.
// Enhanced with decision categories, S/Q rating system,
// multi-channel sales, and investor scorecard metrics.
// All types are value types (structs/enums) for predictable behavior.

import Foundation

// MARK: - Configuration Enums


/// Controls overall market volatility and demand behavior.
enum MarketType: String, Codable, CaseIterable, Identifiable {
    case conservative
    case moderate
    case aggressive

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .conservative: return "Conservative"
        case .moderate: return "Moderate"
        case .aggressive: return "Aggressive"
        }
    }

    var demandMultiplier: Double {
        switch self {
        case .conservative: return 0.8
        case .moderate: return 1.0
        case .aggressive: return 1.3
        }
    }

    var volatility: Double {
        switch self {
        case .conservative: return 0.05
        case .moderate: return 0.10
        case .aggressive: return 0.20
        }
    }

    var description: String {
        switch self {
        case .conservative: return "Stable market with low volatility. Demand is predictable."
        case .moderate: return "Balanced market with moderate fluctuations."
        case .aggressive: return "Volatile market with large demand swings and high risk/reward."
        }
    }
}

/// Determines how smart AI competitors play.
enum AIDifficulty: String, Codable, CaseIterable, Identifiable {
    case easy
    case medium
    case hard

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .easy: return "Easy"
        case .medium: return "Medium"
        case .hard: return "Hard"
        }
    }

    var description: String {
        switch self {
        case .easy: return "AI competitors use basic strategies. Good for learning."
        case .medium: return "AI competitors use mixed strategies. A fair challenge."
        case .hard: return "AI competitors adapt to your moves. Expect tough competition."
        }
    }
}

/// How the final winner is determined (investor expectation score).
enum ScoringMetric: String, Codable, CaseIterable, Identifiable {
    case investorScore
    case cumulativeProfit
    case revenue
    case composite

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .investorScore: return "Investor Score"
        case .cumulativeProfit: return "Cumulative Profit"
        case .revenue: return "Total Revenue"
        case .composite: return "Composite Score"
        }
    }

    var description: String {
        switch self {
        case .investorScore: return "Investor scorecard: EPS + ROE + Stock Price + Image + Credit Rating (20 pts each)."
        case .cumulativeProfit: return "Win by earning the most total profit across all rounds."
        case .revenue: return "Win by generating the highest total revenue."
        case .composite: return "Balanced score: 40% profit + 30% revenue + 30% market share."
        }
    }
}

// MARK: - Materials Quality

/// Material quality choice affecting S/Q rating and cost.
enum MaterialsQuality: String, Codable, CaseIterable, Identifiable {
    case standard
    case superior

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .standard: return "Standard"
        case .superior: return "Superior"
        }
    }

    /// Cost multiplier applied to base materials cost.
    var costMultiplier: Double {
        switch self {
        case .standard: return 1.0
        case .superior: return 1.4
        }
    }

    /// S/Q bonus from materials choice.
    var sqBonus: Double {
        switch self {
        case .standard: return 0.0
        case .superior: return 2.0
        }
    }
}

// MARK: - Celebrity Endorsement Level

/// Celebrity endorsement investment tier.
enum CelebrityEndorsement: String, Codable, CaseIterable, Identifiable {
    case none
    case local
    case national
    case global

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .none: return "None"
        case .local: return "Local Celebrity"
        case .national: return "National Star"
        case .global: return "Global Icon"
        }
    }

    /// Annual cost of endorsement deal.
    var annualCost: Double {
        switch self {
        case .none: return 0
        case .local: return 5_000
        case .national: return 15_000
        case .global: return 35_000
        }
    }

    /// Demand multiplier from endorsement.
    var demandBoost: Double {
        switch self {
        case .none: return 1.0
        case .local: return 1.08
        case .national: return 1.18
        case .global: return 1.30
        }
    }

    /// Image rating contribution.
    var imageBoost: Double {
        switch self {
        case .none: return 0
        case .local: return 3
        case .national: return 8
        case .global: return 15
        }
    }
}

// MARK: - Delivery Time

/// Delivery speed option for wholesale accounts.
enum DeliveryTime: String, Codable, CaseIterable, Identifiable {
    case standard
    case rush

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .standard: return "Standard (5-7 days)"
        case .rush: return "Rush (2-3 days)"
        }
    }

    /// Extra cost per unit for rush delivery.
    var costPerUnit: Double {
        switch self {
        case .standard: return 0
        case .rush: return 2.0
        }
    }

    /// Demand boost from faster delivery.
    var demandBoost: Double {
        switch self {
        case .standard: return 1.0
        case .rush: return 1.06
        }
    }
}

// MARK: - Influencer Tier

/// Influencer marketing tier — trade-off between engagement rate and reach.
enum InfluencerTier: String, Codable, CaseIterable, Identifiable {
    case none
    case nano       // 1K-10K followers, highest engagement
    case micro      // 10K-100K followers
    case macro      // 100K-1M followers
    case mega       // 1M+ followers, lowest engagement but max reach

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .none: return "None"
        case .nano: return "Nano (1K-10K)"
        case .micro: return "Micro (10K-100K)"
        case .macro: return "Macro (100K-1M)"
        case .mega: return "Mega (1M+)"
        }
    }

    /// Cost per influencer per round.
    var costPerInfluencer: Double {
        switch self {
        case .none: return 0
        case .nano: return 300
        case .micro: return 2_500
        case .macro: return 15_000
        case .mega: return 50_000
        }
    }

    /// Engagement rate multiplier (higher = more effective per dollar).
    var engagementRate: Double {
        switch self {
        case .none: return 0
        case .nano: return 0.065    // 6.5%
        case .micro: return 0.04    // 4%
        case .macro: return 0.02    // 2%
        case .mega: return 0.01     // 1%
        }
    }

    /// Reach multiplier (how many people each influencer reaches).
    var reachMultiplier: Double {
        switch self {
        case .none: return 0
        case .nano: return 1.0
        case .micro: return 5.0
        case .macro: return 25.0
        case .mega: return 100.0
        }
    }

    /// Image boost from influencer credibility.
    var imageBoost: Double {
        switch self {
        case .none: return 0
        case .nano: return 1
        case .micro: return 3
        case .macro: return 6
        case .mega: return 10
        }
    }
}

// MARK: - Amazon Fulfillment

/// Amazon fulfillment method — FBA (Fulfilled by Amazon) vs FBM (Fulfilled by Merchant).
enum FulfillmentMethod: String, Codable, CaseIterable, Identifiable {
    case fba    // Fulfilled by Amazon — higher fees, higher Buy Box win rate
    case fbm    // Fulfilled by Merchant — lower fees, lower visibility

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .fba: return "FBA (Fulfilled by Amazon)"
        case .fbm: return "FBM (Fulfilled by Merchant)"
        }
    }

    /// Per-unit fulfillment fee.
    var feePerUnit: Double {
        switch self {
        case .fba: return 4.50   // Amazon picks, packs, ships
        case .fbm: return 1.50   // You handle fulfillment
        }
    }

    /// Buy Box win rate multiplier (FBA strongly preferred by Amazon's algorithm).
    var buyBoxMultiplier: Double {
        switch self {
        case .fba: return 1.25   // 25% boost to winning Buy Box
        case .fbm: return 0.85   // Penalty for merchant-fulfilled
        }
    }

    /// Customer trust multiplier (Prime badge).
    var trustMultiplier: Double {
        switch self {
        case .fba: return 1.15   // Prime badge builds trust
        case .fbm: return 1.0
        }
    }
}

// MARK: - Credit Rating

/// Financial health grade.
enum CreditRating: String, Codable, CaseIterable, Comparable, Identifiable {
    case aPlus = "A+"
    case a = "A"
    case aMinus = "A-"
    case bPlus = "B+"
    case b = "B"
    case bMinus = "B-"
    case cPlus = "C+"
    case c = "C"
    case cMinus = "C-"

    var displayName: String { rawValue }
    var id: String { rawValue }

    /// Construct from backend string (e.g., "A+", "B-", "C")
    static func fromBackendString(_ s: String) -> CreditRating {
        CreditRating(rawValue: s) ?? .a
    }

    /// Score for the investor expectation (0-20 scale).
    var investorScore: Double {
        switch self {
        case .aPlus: return 20
        case .a: return 18
        case .aMinus: return 16
        case .bPlus: return 13
        case .b: return 10
        case .bMinus: return 7
        case .cPlus: return 4
        case .c: return 2
        case .cMinus: return 0
        }
    }

    /// Interest rate multiplier for loans.
    var interestRateMultiplier: Double {
        switch self {
        case .aPlus: return 0.8
        case .a: return 0.9
        case .aMinus: return 1.0
        case .bPlus: return 1.15
        case .b: return 1.3
        case .bMinus: return 1.5
        case .cPlus: return 1.8
        case .c: return 2.2
        case .cMinus: return 3.0
        }
    }

    private var sortOrder: Int {
        switch self {
        case .aPlus: return 0
        case .a: return 1
        case .aMinus: return 2
        case .bPlus: return 3
        case .b: return 4
        case .bMinus: return 5
        case .cPlus: return 6
        case .c: return 7
        case .cMinus: return 8
        }
    }

    static func < (lhs: CreditRating, rhs: CreditRating) -> Bool {
        lhs.sortOrder > rhs.sortOrder // Higher sortOrder = worse grade = "less than"
    }

    /// Determine credit rating from financial ratios.
    static func fromFinancials(debtToEquity: Double, interestCoverage: Double, cashRatio: Double) -> CreditRating {
        var score = 0.0
        // Debt-to-equity (lower is better, max ~40 pts)
        if debtToEquity < 0.3 { score += 40 }
        else if debtToEquity < 0.5 { score += 35 }
        else if debtToEquity < 0.8 { score += 25 }
        else if debtToEquity < 1.2 { score += 15 }
        else { score += 5 }

        // Interest coverage (higher is better, max ~35 pts)
        if interestCoverage > 8 { score += 35 }
        else if interestCoverage > 5 { score += 30 }
        else if interestCoverage > 3 { score += 20 }
        else if interestCoverage > 1.5 { score += 10 }
        else { score += 0 }

        // Cash ratio (higher is better, max ~25 pts)
        if cashRatio > 0.5 { score += 25 }
        else if cashRatio > 0.3 { score += 20 }
        else if cashRatio > 0.15 { score += 10 }
        else { score += 0 }

        switch score {
        case 90...: return .aPlus
        case 80..<90: return .a
        case 70..<80: return .aMinus
        case 60..<70: return .bPlus
        case 50..<60: return .b
        case 40..<50: return .bMinus
        case 30..<40: return .cPlus
        case 15..<30: return .c
        default: return .cMinus
        }
    }
}

// MARK: - Session Configuration

/// All parameters needed to create and run a simulation session.
struct SessionConfiguration: Codable, Identifiable {
    let id: UUID
    var name: String
    var totalRounds: Int
    var startingCash: Double
    var marketType: MarketType
    var aiDifficulty: AIDifficulty
    var numberOfAICompetitors: Int
    var scoringMetric: ScoringMetric
    var randomSeed: UInt64

    // Cost structure
    var fixedCostsPerRound: Double
    var baseCostPerUnit: Double
    var baseMarketDemand: Int

    // Financial parameters
    var sharesOutstanding: Int
    var initialEquity: Double
    var baseInterestRate: Double
    var plantCapacity: Int

    // Class & enrollment
    var courseCode: String
    var semester: String
    var maxHumanTeams: Int
    var teamSize: Int            // Students per team (1-6)

    // Timing
    var roundPacingMode: RoundPacingMode
    var roundDeadlineHours: Int  // Hours per round (for timed mode)
    var latePolicy: LateSubmissionPolicy
    var sessionExpiryDate: Date? // When the session becomes read-only

    // Template
    var template: SessionTemplate
    var isPracticeMode: Bool     // Non-graded warm-up

    init(
        name: String = "New Session",
        totalRounds: Int = 20,
        startingCash: Double = 500_000,
        marketType: MarketType = .moderate,
        aiDifficulty: AIDifficulty = .medium,
        numberOfAICompetitors: Int = 3,
        scoringMetric: ScoringMetric = .investorScore,
        randomSeed: UInt64? = nil,
        fixedCostsPerRound: Double = 5_000,
        baseCostPerUnit: Double = 30,
        baseMarketDemand: Int = 10_000,
        sharesOutstanding: Int = 10_000,
        initialEquity: Double = 300_000,
        baseInterestRate: Double = 0.06,
        plantCapacity: Int = 10_000,
        courseCode: String = "",
        semester: String = "",
        maxHumanTeams: Int = 1,
        teamSize: Int = 4,
        roundPacingMode: RoundPacingMode = .manual,
        roundDeadlineHours: Int = 48,
        latePolicy: LateSubmissionPolicy = .usePrevious,
        sessionExpiryDate: Date? = nil,
        template: SessionTemplate = .custom,
        isPracticeMode: Bool = false
    ) {
        self.id = UUID()
        self.name = name
        self.totalRounds = totalRounds
        self.startingCash = startingCash
        self.marketType = marketType
        self.aiDifficulty = aiDifficulty
        self.numberOfAICompetitors = numberOfAICompetitors
        self.scoringMetric = scoringMetric
        self.randomSeed = randomSeed ?? UInt64.random(in: 0...UInt64.max)
        self.fixedCostsPerRound = fixedCostsPerRound
        self.baseCostPerUnit = baseCostPerUnit
        self.baseMarketDemand = baseMarketDemand
        self.sharesOutstanding = sharesOutstanding
        self.initialEquity = initialEquity
        self.baseInterestRate = baseInterestRate
        self.plantCapacity = plantCapacity
        self.courseCode = courseCode
        self.semester = semester
        self.maxHumanTeams = maxHumanTeams
        self.teamSize = teamSize
        self.roundPacingMode = roundPacingMode
        self.roundDeadlineHours = roundDeadlineHours
        self.latePolicy = latePolicy
        self.sessionExpiryDate = sessionExpiryDate
        self.template = template
        self.isPracticeMode = isPracticeMode
    }
}

// MARK: - Player Decisions

/// A player's (or AI's) complete decisions for a single round.
/// Organized into decision categories.
// MARK: - Player Decision Sub-Structures

/// Pricing decisions for the round.
struct PricingDecision: Codable, Identifiable {
    let id: UUID
    var wholesalePrice: Double
    var internetPrice: Double
    var privateLabelBidPrice: Double
    var privateLabelMaxUnits: Int
    var amazonPrice: Double
    var amazonAdBudget: Double
    
    init(
        wholesalePrice: Double = 80,
        internetPrice: Double = 90,
        privateLabelBidPrice: Double = 45,
        privateLabelMaxUnits: Int = 50,
        amazonPrice: Double = 85,
        amazonAdBudget: Double = 0
    ) {
        self.id = UUID()
        self.wholesalePrice = wholesalePrice
        self.internetPrice = internetPrice
        self.privateLabelBidPrice = privateLabelBidPrice
        self.privateLabelMaxUnits = privateLabelMaxUnits
        self.amazonPrice = amazonPrice
        self.amazonAdBudget = amazonAdBudget
    }
    
    // Validation
    var isValid: Bool {
        wholesalePrice >= 0 && internetPrice >= 0 &&
        privateLabelBidPrice >= 0 && amazonPrice >= 0 &&
        privateLabelMaxUnits >= 0
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if wholesalePrice < 0 { errors.append("Wholesale price cannot be negative") }
        if internetPrice < 0 { errors.append("Internet price cannot be negative") }
        if privateLabelBidPrice < 0 { errors.append("Private label bid price cannot be negative") }
        if amazonPrice < 0 { errors.append("Amazon price cannot be negative") }
        if privateLabelMaxUnits < 0 { errors.append("Private label max units cannot be negative") }
        return errors
    }
}

/// Product design decisions (S/Q rating factors).
struct ProductDecision: Codable, Identifiable {
    let id: UUID
    var materialsQuality: MaterialsQuality
    var stylingBudget: Double
    var modelsOffered: Int
    var tqmInvestment: Double
    
    init(
        materialsQuality: MaterialsQuality = .standard,
        stylingBudget: Double = 3_000,
        modelsOffered: Int = 3,
        tqmInvestment: Double = 2_000
    ) {
        self.id = UUID()
        self.materialsQuality = materialsQuality
        self.stylingBudget = stylingBudget
        self.modelsOffered = modelsOffered
        self.tqmInvestment = tqmInvestment
    }
    
    var isValid: Bool {
        stylingBudget >= 0 && modelsOffered >= 1 && tqmInvestment >= 0
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if stylingBudget < 0 { errors.append("Styling budget cannot be negative") }
        if modelsOffered < 1 { errors.append("Must offer at least 1 model") }
        if tqmInvestment < 0 { errors.append("TQM investment cannot be negative") }
        return errors
    }
}

/// Marketing channel decisions.
struct MarketingDecision: Codable, Identifiable {
    let id: UUID
    var advertisingBudget: Double
    var celebrityEndorsement: CelebrityEndorsement
    var retailOutlets: Int
    var mailInRebate: Double
    var deliveryTime: DeliveryTime
    var freeShippingThreshold: Double
    var tiktokBudget: Double
    var instagramBudget: Double
    var youtubeBudget: Double
    var influencerTier: InfluencerTier
    
    init(
        advertisingBudget: Double = 8_000,
        celebrityEndorsement: CelebrityEndorsement = .none,
        retailOutlets: Int = 20,
        mailInRebate: Double = 0,
        deliveryTime: DeliveryTime = .standard,
        freeShippingThreshold: Double = 100,
        tiktokBudget: Double = 0,
        instagramBudget: Double = 0,
        youtubeBudget: Double = 0,
        influencerTier: InfluencerTier = .none
    ) {
        self.id = UUID()
        self.advertisingBudget = advertisingBudget
        self.celebrityEndorsement = celebrityEndorsement
        self.retailOutlets = retailOutlets
        self.mailInRebate = mailInRebate
        self.deliveryTime = deliveryTime
        self.freeShippingThreshold = freeShippingThreshold
        self.tiktokBudget = tiktokBudget
        self.instagramBudget = instagramBudget
        self.youtubeBudget = youtubeBudget
        self.influencerTier = influencerTier
    }
    
    var isValid: Bool {
        advertisingBudget >= 0 && retailOutlets >= 0 &&
        mailInRebate >= 0 && freeShippingThreshold >= 0 &&
        tiktokBudget >= 0 && instagramBudget >= 0 && youtubeBudget >= 0
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if advertisingBudget < 0 { errors.append("Advertising budget cannot be negative") }
        if retailOutlets < 0 { errors.append("Retail outlets cannot be negative") }
        if mailInRebate < 0 { errors.append("Mail-in rebate cannot be negative") }
        if freeShippingThreshold < 0 { errors.append("Free shipping threshold cannot be negative") }
        if tiktokBudget < 0 { errors.append("TikTok budget cannot be negative") }
        if instagramBudget < 0 { errors.append("Instagram budget cannot be negative") }
        if youtubeBudget < 0 { errors.append("YouTube budget cannot be negative") }
        return errors
    }
    
    var totalSocialMediaBudget: Double {
        tiktokBudget + instagramBudget + youtubeBudget
    }
}

/// Workforce compensation decisions.
struct WorkforceDecision: Codable, Identifiable {
    let id: UUID
    var baseWage: Double
    var incentivePay: Double
    var trainingHours: Double
    var bestPracticesInvestment: Double
    
    init(
        baseWage: Double = 25_000,
        incentivePay: Double = 0.50,
        trainingHours: Double = 20,
        bestPracticesInvestment: Double = 1_000
    ) {
        self.id = UUID()
        self.baseWage = baseWage
        self.incentivePay = incentivePay
        self.trainingHours = trainingHours
        self.bestPracticesInvestment = bestPracticesInvestment
    }
    
    var isValid: Bool {
        baseWage >= 0 && incentivePay >= 0 && trainingHours >= 0 && bestPracticesInvestment >= 0
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if baseWage < 0 { errors.append("Base wage cannot be negative") }
        if incentivePay < 0 { errors.append("Incentive pay cannot be negative") }
        if trainingHours < 0 { errors.append("Training hours cannot be negative") }
        if bestPracticesInvestment < 0 { errors.append("Best practices investment cannot be negative") }
        return errors
    }
}

/// Production decisions.
struct ProductionDecision: Codable, Identifiable {
    let id: UUID
    var productionQuantity: Int
    var overtimePercent: Double
    
    init(
        productionQuantity: Int = 200,
        overtimePercent: Double = 0
    ) {
        self.id = UUID()
        self.productionQuantity = productionQuantity
        self.overtimePercent = overtimePercent
    }
    
    var isValid: Bool {
        productionQuantity >= 0 && overtimePercent >= 0 && overtimePercent <= 20
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if productionQuantity < 0 { errors.append("Production quantity cannot be negative") }
        if overtimePercent < 0 { errors.append("Overtime cannot be negative") }
        if overtimePercent > 20 { errors.append("Overtime cannot exceed 20%") }
        return errors
    }
}

/// Finance decisions for the round.
struct FinanceDecision: Codable, Identifiable {
    let id: UUID
    var csrInvestment: Double
    var dividendsPerShare: Double
    var newLoanAmount: Double
    var sharesBuyback: Int
    var sharesIssued: Int
    
    init(
        csrInvestment: Double = 2_000,
        dividendsPerShare: Double = 0.50,
        newLoanAmount: Double = 0,
        sharesBuyback: Int = 0,
        sharesIssued: Int = 0
    ) {
        self.id = UUID()
        self.csrInvestment = csrInvestment
        self.dividendsPerShare = dividendsPerShare
        self.newLoanAmount = newLoanAmount
        self.sharesBuyback = sharesBuyback
        self.sharesIssued = sharesIssued
    }
    
    var isValid: Bool {
        csrInvestment >= 0 && dividendsPerShare >= 0 && newLoanAmount >= 0 &&
        sharesBuyback >= 0 && sharesIssued >= 0
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        if csrInvestment < 0 { errors.append("CSR investment cannot be negative") }
        if dividendsPerShare < 0 { errors.append("Dividends cannot be negative") }
        if newLoanAmount < 0 { errors.append("New loan amount cannot be negative") }
        if sharesBuyback < 0 { errors.append("Shares buyback cannot be negative") }
        if sharesIssued < 0 { errors.append("Shares issued cannot be negative") }
        return errors
    }
}

// MARK: - Player Decision

/// Aggregated player decision for a round, composed of logical sub-structures.
struct PlayerDecision: Codable, Identifiable {
    let id: UUID
    let teamId: UUID
    let round: Int
    let submittedAt: Date
    
    // Composed sub-structures
    var pricing: PricingDecision
    var product: ProductDecision
    var marketing: MarketingDecision
    var workforce: WorkforceDecision
    var production: ProductionDecision
    var finance: FinanceDecision
    
    // Legacy compatibility helpers
    var price: Double { pricing.wholesalePrice }
    var marketingBudget: Double { marketing.advertisingBudget }
    var rdInvestment: Double { product.stylingBudget + product.tqmInvestment }
    
    var socialMediaBudget: Double { marketing.totalSocialMediaBudget }
    
    // Fulfillment method (Amazon)
    var fulfillmentMethod: FulfillmentMethod
    
    init(
        teamId: UUID,
        round: Int,
        pricing: PricingDecision = PricingDecision(),
        product: ProductDecision = ProductDecision(),
        marketing: MarketingDecision = MarketingDecision(),
        workforce: WorkforceDecision = WorkforceDecision(),
        production: ProductionDecision = ProductionDecision(),
        finance: FinanceDecision = FinanceDecision(),
        fulfillmentMethod: FulfillmentMethod = .fbm
    ) {
        self.id = UUID()
        self.teamId = teamId
        self.round = round
        self.submittedAt = Date()
        self.pricing = pricing
        self.product = product
        self.marketing = marketing
        self.workforce = workforce
        self.production = production
        self.finance = finance
        self.fulfillmentMethod = fulfillmentMethod
    }
    
    // Full validation
    var isValid: Bool {
        pricing.isValid && product.isValid && marketing.isValid &&
        workforce.isValid && production.isValid && finance.isValid
    }
    
    var validationErrors: [String] {
        var errors: [String] = []
        errors.append(contentsOf: pricing.validationErrors)
        errors.append(contentsOf: product.validationErrors)
        errors.append(contentsOf: marketing.validationErrors)
        errors.append(contentsOf: workforce.validationErrors)
        errors.append(contentsOf: production.validationErrors)
        errors.append(contentsOf: finance.validationErrors)
        return errors
    }
    
    // Legacy convenience accessors
    var wholesalePrice: Double { pricing.wholesalePrice }
    var internetPrice: Double { pricing.internetPrice }
    var privateLabelBidPrice: Double { pricing.privateLabelBidPrice }
    var privateLabelMaxUnits: Int { pricing.privateLabelMaxUnits }
    var amazonPrice: Double { pricing.amazonPrice }
    var amazonAdBudget: Double { pricing.amazonAdBudget }
    
    var materialsQuality: MaterialsQuality { product.materialsQuality }
    var stylingBudget: Double { product.stylingBudget }
    var modelsOffered: Int { product.modelsOffered }
    var tqmInvestment: Double { product.tqmInvestment }
    
    var advertisingBudget: Double { marketing.advertisingBudget }
    var celebrityEndorsement: CelebrityEndorsement { marketing.celebrityEndorsement }
    var retailOutlets: Int { marketing.retailOutlets }
    var mailInRebate: Double { marketing.mailInRebate }
    var deliveryTime: DeliveryTime { marketing.deliveryTime }
    var freeShippingThreshold: Double { marketing.freeShippingThreshold }
    var tiktokBudget: Double { marketing.tiktokBudget }
    var instagramBudget: Double { marketing.instagramBudget }
    var youtubeBudget: Double { marketing.youtubeBudget }
    var influencerTier: InfluencerTier { marketing.influencerTier }
    
    var baseWage: Double { workforce.baseWage }
    var incentivePay: Double { workforce.incentivePay }
    var trainingHours: Double { workforce.trainingHours }
    var bestPracticesInvestment: Double { workforce.bestPracticesInvestment }
    
    var productionQuantity: Int { production.productionQuantity }
    var overtimePercent: Double { production.overtimePercent }
    
    var csrInvestment: Double { finance.csrInvestment }
    var dividendsPerShare: Double { finance.dividendsPerShare }
    var newLoanAmount: Double { finance.newLoanAmount }
    var sharesBuyback: Int { finance.sharesBuyback }
    var sharesIssued: Int { finance.sharesIssued }
}

// MARK: - Investor Scorecard

/// The 5 investor expectation metrics for a single round.
struct InvestorScorecard: Codable, Identifiable {
    let id: UUID
    let round: Int

    // The 5 investor metrics
    var eps: Double              // Earnings Per Share
    var roe: Double              // Return on Equity (as percentage)
    var stockPrice: Double       // Simulated stock price
    var imageRating: Double      // 0-100 scale
    var creditRating: CreditRating

    // Scoring (each metric max 20 pts, total 100)
    var epsScore: Double
    var roeScore: Double
    var stockPriceScore: Double
    var imageScore: Double
    var creditScore: Double

    var totalScore: Double {
        epsScore + roeScore + stockPriceScore + imageScore + creditScore
    }

    init(round: Int, eps: Double, roe: Double, stockPrice: Double,
         imageRating: Double, creditRating: CreditRating,
         epsScore: Double, roeScore: Double, stockPriceScore: Double,
         imageScore: Double, creditScore: Double) {
        self.id = UUID()
        self.round = round
        self.eps = eps
        self.roe = roe
        self.stockPrice = stockPrice
        self.imageRating = imageRating
        self.creditRating = creditRating
        self.epsScore = epsScore
        self.roeScore = roeScore
        self.stockPriceScore = stockPriceScore
        self.imageScore = imageScore
        self.creditScore = creditScore
    }
}

// MARK: - Round Results (Enhanced)

/// Complete results for one team in one round.
struct RoundResult: Codable, Identifiable {
    let id: UUID
    let teamId: UUID
    let round: Int

    // Revenue breakdown by channel
    let wholesaleRevenue: Double
    let internetRevenue: Double
    let amazonRevenue: Double
    let privateLabelRevenue: Double
    var revenue: Double { wholesaleRevenue + internetRevenue + amazonRevenue + privateLabelRevenue }

    // Cost breakdown
    let productionCosts: Double
    let marketingCosts: Double
    let csrCosts: Double
    let endorsementCosts: Double
    let interestExpense: Double
    let dividendsPaid: Double
    let workforceCosts: Double       // Base wage + incentive + training + best practices
    let storageCosts: Double          // Inventory carrying costs
    let rebateCosts: Double           // Mail-in rebate expense
    let deliveryCosts: Double         // Rush delivery premium
    let socialMediaCosts: Double      // TikTok + Instagram + YouTube + influencer costs
    let amazonFees: Double            // Referral fee + FBA/FBM fees

    /// When non-nil, overrides the computed `profit` (used by backend results
    /// where the full cost breakdown isn't available but the authoritative
    /// profit value is).
    let overrideProfit: Double?

    init(teamId: UUID, round: Int, wholesaleRevenue: Double, internetRevenue: Double, amazonRevenue: Double, privateLabelRevenue: Double, productionCosts: Double, marketingCosts: Double, csrCosts: Double, endorsementCosts: Double, interestExpense: Double, dividendsPaid: Double, workforceCosts: Double, storageCosts: Double, rebateCosts: Double, deliveryCosts: Double, socialMediaCosts: Double, amazonFees: Double, wholesaleUnitsSold: Int, internetUnitsSold: Int, amazonUnitsSold: Int, privateLabelUnitsSold: Int, marketShare: Double, customerSatisfaction: Double, inventory: Int, rejectionRate: Double, cash: Double, sqRating: Double, awarenessScore: Double, scorecard: InvestorScorecard, overrideProfit: Double? = nil) {
        self.id = UUID()
        self.teamId = teamId
        self.round = round
        self.wholesaleRevenue = wholesaleRevenue
        self.internetRevenue = internetRevenue
        self.amazonRevenue = amazonRevenue
        self.privateLabelRevenue = privateLabelRevenue
        self.productionCosts = productionCosts
        self.marketingCosts = marketingCosts
        self.csrCosts = csrCosts
        self.endorsementCosts = endorsementCosts
        self.interestExpense = interestExpense
        self.dividendsPaid = dividendsPaid
        self.workforceCosts = workforceCosts
        self.storageCosts = storageCosts
        self.rebateCosts = rebateCosts
        self.deliveryCosts = deliveryCosts
        self.socialMediaCosts = socialMediaCosts
        self.amazonFees = amazonFees
        self.overrideProfit = overrideProfit
        self.wholesaleUnitsSold = wholesaleUnitsSold
        self.internetUnitsSold = internetUnitsSold
        self.amazonUnitsSold = amazonUnitsSold
        self.privateLabelUnitsSold = privateLabelUnitsSold
        self.marketShare = marketShare
        self.customerSatisfaction = customerSatisfaction
        self.inventory = inventory
        self.rejectionRate = rejectionRate
        self.cash = cash
        self.sqRating = sqRating
        self.awarenessScore = awarenessScore
        self.qualityScore = sqRating / 10
        self.scorecard = scorecard
    }
    var costs: Double {
        productionCosts + marketingCosts + csrCosts + endorsementCosts
            + interestExpense + dividendsPaid + workforceCosts + storageCosts
            + rebateCosts + deliveryCosts + socialMediaCosts + amazonFees
    }
    var profit: Double { overrideProfit ?? (revenue - costs) }

    // Operations
    let wholesaleUnitsSold: Int
    let internetUnitsSold: Int
    let amazonUnitsSold: Int
    let privateLabelUnitsSold: Int
    var unitsSold: Int { wholesaleUnitsSold + internetUnitsSold + amazonUnitsSold + privateLabelUnitsSold }
    let marketShare: Double
    let customerSatisfaction: Double
    let inventory: Int
    let rejectionRate: Double         // % of production wasted (0-1)

    // Running totals
    let cash: Double

    // S/Q and brand metrics
    let sqRating: Double          // 1-10 star scale
    let awarenessScore: Double    // 0-1 scale
    let qualityScore: Double      // Legacy compatibility (= sqRating / 10)

    // Investor Scorecard
    let scorecard: InvestorScorecard

    init(
        teamId: UUID, round: Int,
        wholesaleRevenue: Double, internetRevenue: Double, amazonRevenue: Double = 0, privateLabelRevenue: Double,
        productionCosts: Double, marketingCosts: Double, csrCosts: Double,
        endorsementCosts: Double, interestExpense: Double, dividendsPaid: Double,
        workforceCosts: Double = 0, storageCosts: Double = 0,
        rebateCosts: Double = 0, deliveryCosts: Double = 0,
        socialMediaCosts: Double = 0,
        amazonFees: Double = 0,
        wholesaleUnitsSold: Int, internetUnitsSold: Int, amazonUnitsSold: Int = 0, privateLabelUnitsSold: Int,
        marketShare: Double, customerSatisfaction: Double, inventory: Int,
        rejectionRate: Double = 0,
        cash: Double, sqRating: Double, awarenessScore: Double,
        scorecard: InvestorScorecard
    ) {
        self.id = UUID()
        self.teamId = teamId
        self.round = round
        self.wholesaleRevenue = wholesaleRevenue
        self.internetRevenue = internetRevenue
        self.amazonRevenue = amazonRevenue
        self.privateLabelRevenue = privateLabelRevenue
        self.productionCosts = productionCosts
        self.marketingCosts = marketingCosts
        self.csrCosts = csrCosts
        self.endorsementCosts = endorsementCosts
        self.interestExpense = interestExpense
        self.dividendsPaid = dividendsPaid
        self.workforceCosts = workforceCosts
        self.storageCosts = storageCosts
        self.rebateCosts = rebateCosts
        self.deliveryCosts = deliveryCosts
        self.socialMediaCosts = socialMediaCosts
        self.amazonFees = amazonFees
        self.wholesaleUnitsSold = wholesaleUnitsSold
        self.internetUnitsSold = internetUnitsSold
        self.amazonUnitsSold = amazonUnitsSold
        self.privateLabelUnitsSold = privateLabelUnitsSold
        self.marketShare = marketShare
        self.customerSatisfaction = customerSatisfaction
        self.inventory = inventory
        self.rejectionRate = rejectionRate
        self.cash = cash
        self.sqRating = sqRating
        self.awarenessScore = awarenessScore
        self.qualityScore = sqRating / 10.0
        self.scorecard = scorecard
        self.overrideProfit = nil
    }
}

/// Summarized competitor results shown to the player after each round.
struct CompetitorResult: Codable, Identifiable {
    let id: UUID
    let name: String
    let revenue: Double
    let profit: Double
    let marketShare: Double
    let price: Double
    let sqRating: Double
    let imageRating: Double

    init(
        name: String, revenue: Double, profit: Double,
        marketShare: Double, price: Double,
        sqRating: Double = 5.0, imageRating: Double = 50
    ) {
        self.id = UUID()
        self.name = name
        self.revenue = revenue
        self.profit = profit
        self.marketShare = marketShare
        self.price = price
        self.sqRating = sqRating
        self.imageRating = imageRating
    }
}

// MARK: - Team & Session State (Enhanced)

/// Current status of a team in the session.
struct TeamStatus: Codable, Identifiable {
    let id: UUID
    var name: String
    var cash: Double
    var inventory: Int
    var reputation: Double
    var rank: Int
    var hasSubmittedDecisions: Bool
    let isAI: Bool

    // Cumulative metrics
    var cumulativeRD: Double
    var cumulativeMarketing: Double
    var cumulativeCSR: Double
    var cumulativeTQM: Double
    var cumulativeProfit: Double

    // Financial state
    var equity: Double
    var totalDebt: Double
    var sharesOutstanding: Int
    var sqRating: Double           // Current S/Q rating (1-10)
    var imageRating: Double        // Current image rating (0-100)
    var creditRating: CreditRating
    var cumulativeInvestorScore: Double  // Running average of yearly scores
    var roundsScored: Int

    init(
        id: UUID = UUID(),
        name: String,
        cash: Double,
        inventory: Int = 0,
        reputation: Double = 0.5,
        rank: Int = 0,
        hasSubmittedDecisions: Bool = false,
        isAI: Bool = false,
        cumulativeRD: Double = 0,
        cumulativeMarketing: Double = 0,
        cumulativeCSR: Double = 0,
        cumulativeTQM: Double = 0,
        cumulativeProfit: Double = 0,
        equity: Double = 80_000,
        totalDebt: Double = 0,
        sharesOutstanding: Int = 10_000,
        sqRating: Double = 5.0,
        imageRating: Double = 50,
        creditRating: CreditRating = .a,
        cumulativeInvestorScore: Double = 0,
        roundsScored: Int = 0
    ) {
        self.id = id
        self.name = name
        self.cash = cash
        self.inventory = inventory
        self.reputation = reputation
        self.rank = rank
        self.hasSubmittedDecisions = hasSubmittedDecisions
        self.isAI = isAI
        self.cumulativeRD = cumulativeRD
        self.cumulativeMarketing = cumulativeMarketing
        self.cumulativeCSR = cumulativeCSR
        self.cumulativeTQM = cumulativeTQM
        self.cumulativeProfit = cumulativeProfit
        self.equity = equity
        self.totalDebt = totalDebt
        self.sharesOutstanding = sharesOutstanding
        self.sqRating = sqRating
        self.imageRating = imageRating
        self.creditRating = creditRating
        self.cumulativeInvestorScore = cumulativeInvestorScore
        self.roundsScored = roundsScored
    }
}

/// The lifecycle state of a simulation session.
enum SessionState: String, Codable, CaseIterable, Identifiable {
    case waitingForPlayers
    case inProgress
    case roundProcessing
    case completed

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .waitingForPlayers: return "Waiting"
        case .inProgress: return "In Progress"
        case .roundProcessing: return "Processing"
        case .completed: return "Completed"
        }
    }
}

// MARK: - Display & Analysis Models

/// Compact round summary for leaderboard/history views.
struct RoundSummary: Codable, Identifiable {
    let id: UUID
    let roundNumber: Int
    let profit: Double
    let revenue: Double
    let marketShare: Double
    let price: Double
    let satisfaction: Double
    let sqRating: Double
    let investorScore: Double

    init(
        roundNumber: Int, profit: Double, revenue: Double,
        marketShare: Double, price: Double, satisfaction: Double,
        sqRating: Double = 5.0, investorScore: Double = 0
    ) {
        self.id = UUID()
        self.roundNumber = roundNumber
        self.profit = profit
        self.revenue = revenue
        self.marketShare = marketShare
        self.price = price
        self.satisfaction = satisfaction
        self.sqRating = sqRating
        self.investorScore = investorScore
    }

    /// Create a RoundSummary from a full RoundResult.
    init(from result: RoundResult, price: Double) {
        self.id = UUID()
        self.roundNumber = result.round
        self.profit = result.profit
        self.revenue = result.revenue
        self.marketShare = result.marketShare
        self.price = price
        self.satisfaction = result.customerSatisfaction
        self.sqRating = result.sqRating
        self.investorScore = result.scorecard.totalScore
    }
}

/// Impact direction for result explanations.
enum Impact: String, Codable {
    case positive
    case negative
    case neutral
}

/// Explains what happened and why for a specific metric after a round.
struct ResultExplanation: Codable, Identifiable {
    let id: UUID
    let metric: String
    let explanation: String
    let impact: Impact

    init(metric: String, explanation: String, impact: Impact) {
        self.id = UUID()
        self.metric = metric
        self.explanation = explanation
        self.impact = impact
    }
}

/// A single message in the AI coaching conversation.
struct CoachMessage: Codable, Identifiable {
    let id: UUID
    let content: String
    let isFromAI: Bool
    let timestamp: Date

    init(content: String, isFromAI: Bool, timestamp: Date = Date()) {
        self.id = UUID()
        self.content = content
        self.isFromAI = isFromAI
        self.timestamp = timestamp
    }
}

/// A single data point for charts and graphs.
struct ChartDataPoint: Codable, Identifiable {
    let id: UUID
    let round: Int
    let value: Double
    let label: String

    init(round: Int, value: Double, label: String) {
        self.id = UUID()
        self.round = round
        self.value = value
        self.label = label
    }
}

/// Which performance metric to display in charts.
enum PerformanceMetric: String, Codable, CaseIterable, Identifiable {
    case profit
    case revenue
    case marketShare
    case satisfaction
    case cash
    case sqRating
    case eps
    case imageRating
    case investorScore
    case rejectionRate

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .profit: return "Profit"
        case .revenue: return "Revenue"
        case .marketShare: return "Market Share"
        case .satisfaction: return "Customer Satisfaction"
        case .cash: return "Cash"
        case .sqRating: return "S/Q Rating"
        case .eps: return "EPS"
        case .imageRating: return "Image Rating"
        case .investorScore: return "Investor Score"
        case .rejectionRate: return "Rejection Rate"
        }
    }

    var unit: String {
        switch self {
        case .profit, .revenue, .cash, .eps: return "$"
        case .marketShare, .satisfaction, .rejectionRate: return "%"
        case .sqRating: return "★"
        case .imageRating, .investorScore: return "pts"
        }
    }
}

// MARK: - Income Statement

/// Structured income statement for post-round financial review.
struct IncomeStatement: Identifiable {
    let id = UUID()
    let round: Int
    let teamName: String

    // Revenue
    let wholesaleRevenue: Double
    let internetRevenue: Double
    let amazonRevenue: Double
    let privateLabelRevenue: Double
    var grossRevenue: Double { wholesaleRevenue + internetRevenue + amazonRevenue + privateLabelRevenue }

    // Cost of Goods Sold
    let materialsCost: Double
    let laborCost: Double
    let workforceCosts: Double
    let rejectionCost: Double
    var cogs: Double { materialsCost + laborCost + workforceCosts + rejectionCost }

    var grossProfit: Double { grossRevenue - cogs }
    var grossMargin: Double { grossRevenue > 0 ? grossProfit / grossRevenue : 0 }

    // Operating Expenses
    let advertisingExpense: Double
    let outletExpense: Double
    let endorsementExpense: Double
    let stylingExpense: Double
    let tqmExpense: Double
    let bestPracticesExpense: Double
    let csrExpense: Double
    let storageCosts: Double
    let rebateCosts: Double
    let deliveryCosts: Double
    let socialMediaCosts: Double
    let amazonFees: Double
    var operatingExpenses: Double {
        advertisingExpense + outletExpense + endorsementExpense
            + stylingExpense + tqmExpense + bestPracticesExpense
            + csrExpense + storageCosts + rebateCosts + deliveryCosts
            + socialMediaCosts + amazonFees
    }

    var operatingIncome: Double { grossProfit - operatingExpenses }

    // Below the line
    let interestExpense: Double
    let dividendsPaid: Double

    var netIncome: Double { operatingIncome - interestExpense - dividendsPaid }
    var netMargin: Double { grossRevenue > 0 ? netIncome / grossRevenue : 0 }
}

// MARK: - Round Pacing Mode

/// How round timing is managed by the professor.
enum RoundPacingMode: String, Codable, CaseIterable, Identifiable {
    case manual       // Professor clicks "advance round"
    case timed        // Auto-advance after deadline

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .manual: return "Manual Advance"
        case .timed: return "Timed Rounds"
        }
    }

    var description: String {
        switch self {
        case .manual: return "Professor manually advances each round after reviewing submissions."
        case .timed: return "Rounds auto-advance after the deadline passes."
        }
    }
}

/// What happens when a team misses the submission deadline.
enum LateSubmissionPolicy: String, Codable, CaseIterable, Identifiable {
    case allowWithPenalty    // Accept late, apply score penalty
    case usePrevious         // Auto-submit previous round's decisions
    case lockOut             // Team gets zero sales for the round

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .allowWithPenalty: return "Allow (with penalty)"
        case .usePrevious: return "Use Previous Decisions"
        case .lockOut: return "Lock Out (no sales)"
        }
    }
}

/// Pre-built session templates for common course types.
enum SessionTemplate: String, Codable, CaseIterable, Identifiable {
    case introMarketing
    case advancedStrategy
    case entrepreneurship
    case quickDemo
    case custom

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .introMarketing: return "Intro to Marketing (5 rounds)"
        case .advancedStrategy: return "Advanced Strategy (12 rounds)"
        case .entrepreneurship: return "Entrepreneurship (8 rounds)"
        case .quickDemo: return "Quick Demo (3 rounds)"
        case .custom: return "Custom Configuration"
        }
    }

    var description: String {
        switch self {
        case .introMarketing: return "5 rounds, easy AI, moderate market. Perfect for first-time students."
        case .advancedStrategy: return "12 rounds, hard AI, aggressive market. For experienced students."
        case .entrepreneurship: return "8 rounds, medium AI, high starting cash. Focus on growth strategies."
        case .quickDemo: return "3 rounds, easy AI. Quick demonstration or practice session."
        case .custom: return "Configure all settings manually."
        }
    }

    var rounds: Int {
        switch self {
        case .introMarketing: return 5
        case .advancedStrategy: return 12
        case .entrepreneurship: return 8
        case .quickDemo: return 3
        case .custom: return 10
        }
    }

    var difficulty: AIDifficulty {
        switch self {
        case .introMarketing, .quickDemo: return .easy
        case .advancedStrategy: return .hard
        case .entrepreneurship, .custom: return .medium
        }
    }

    var marketType: MarketType {
        switch self {
        case .introMarketing, .quickDemo: return .moderate
        case .advancedStrategy: return .aggressive
        case .entrepreneurship, .custom: return .moderate
        }
    }

    var startingCash: Double {
        switch self {
        case .introMarketing: return 100_000
        case .advancedStrategy: return 80_000
        case .entrepreneurship: return 150_000
        case .quickDemo: return 120_000
        case .custom: return 100_000
        }
    }
}

// MARK: - Grade Mapping

/// Maps simulation rank/score ranges to letter grades.
struct GradeMapping: Codable, Identifiable {
    let id: UUID
    var label: String          // e.g. "A", "B+", "C"
    var minScore: Double       // Minimum investor score threshold
    var maxScore: Double       // Maximum investor score threshold

    init(label: String, minScore: Double, maxScore: Double) {
        self.id = UUID()
        self.label = label
        self.minScore = minScore
        self.maxScore = maxScore
    }

    /// Default grade scale based on investor score (0-100).
    static var defaultScale: [GradeMapping] {
        [
            GradeMapping(label: "A", minScore: 80, maxScore: 100),
            GradeMapping(label: "B+", minScore: 70, maxScore: 80),
            GradeMapping(label: "B", minScore: 60, maxScore: 70),
            GradeMapping(label: "C+", minScore: 50, maxScore: 60),
            GradeMapping(label: "C", minScore: 40, maxScore: 50),
            GradeMapping(label: "D", minScore: 30, maxScore: 40),
            GradeMapping(label: "F", minScore: 0, maxScore: 30),
        ]
    }
}

// MARK: - Announcement

/// Professor announcement visible to all teams in a session.
struct Announcement: Codable, Identifiable {
    let id: UUID
    let message: String
    let postedAt: Date
    let roundNumber: Int?      // nil = general announcement, Int = round-specific debrief

    init(message: String, roundNumber: Int? = nil) {
        self.id = UUID()
        self.message = message
        self.postedAt = Date()
        self.roundNumber = roundNumber
    }

    init(message: String, roundNumber: Int?, postedAt: Date) {
        self.id = UUID()
        self.message = message
        self.postedAt = postedAt
        self.roundNumber = roundNumber
    }
}

// MARK: - Enrolled Student

/// A student enrolled in a session (for roster management).
struct EnrolledStudent: Codable, Identifiable {
    let id: UUID
    var name: String
    var email: String
    var teamId: UUID?          // nil = unassigned
    var isActive: Bool         // false = dropped/withdrawn
    var joinedAt: Date

    init(name: String, email: String) {
        self.id = UUID()
        self.name = name
        self.email = email
        self.teamId = nil
        self.isActive = true
        self.joinedAt = Date()
    }
}
