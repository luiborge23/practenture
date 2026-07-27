import Foundation

// Minimal compile-time adapter for SimulationEngine.processRound; the golden runner
// exercises processRoundPure against the production engine implementation.
final class SimulationSession {
    var config: SessionConfiguration
    var currentRound: Int
    var teams: [TeamStatus]
    var roundResults: [UUID: [Int: RoundResult]] = [:]
    init(config: SessionConfiguration, currentRound: Int, teams: [TeamStatus]) {
        self.config = config; self.currentRound = currentRound; self.teams = teams
    }
    func roundResult(for teamId: UUID, round: Int) -> RoundResult? { roundResults[teamId]?[round] }
    func recordResult(_ result: RoundResult) { roundResults[result.teamId, default: [:]][result.round] = result }
    func updateRankings() {}
}

struct Fixture: Decodable { let cases: [GoldenCase] }
struct GoldenCase: Decodable {
    let name: String; let round: Int; let config: ConfigInput
    let teams: [TeamInput]; let decisions: [String: DecisionInput]
}
struct ConfigInput: Decodable {
    let randomSeed: UInt64; let marketType: String; let startingCash: Double
    let initialEquity: Double; let plantCapacity: Int; let fixedCostsPerRound: Double
    let baseCostPerUnit: Double; let baseMarketDemand: Int; let sharesOutstanding: Int
}
struct TeamInput: Decodable {
    let id: String; let name: String; let cash: Double; let inventory: Int; let reputation: Double
    let cumulativeTQM: Double; let equity: Double; let debt: Double; let sharesOutstanding: Int
    let sqRating: Double; let imageRating: Double; let creditRating: String
    let cumulativeInvestorScore: Double; let roundsScored: Int
}
struct DecisionInput: Decodable {
    let wholesalePrice, internetPrice, amazonPrice, privateLabelBidPrice: Double
    let privateLabelMaxUnits: Int; let amazonAdBudget: Double
    let materialsQuality: String; let stylingBudget: Double; let modelsOffered: Int; let tqmInvestment: Double
    let advertisingBudget: Double; let celebrityEndorsement: String; let retailOutlets: Int
    let mailInRebate: Double; let deliveryTime: String; let freeShippingThreshold: Double
    let tiktokBudget, instagramBudget, youtubeBudget: Double; let influencerTier: String
    let baseWage, incentivePay, trainingHours, bestPracticesInvestment: Double
    let productionQuantity: Int; let overtimePercent, csrInvestment, dividendsPerShare, newLoanAmount: Double
    let sharesBuyback, sharesIssued: Int; let fulfillmentMethod: String
}

func rounded(_ value: Double, places: Int) -> Double {
    let scale = pow(10.0, Double(places))
    return (value * scale).rounded() / scale
}

func normalize(_ result: RoundResult, update: TeamUpdate) -> [String: Any] {
    [
        "round": result.round,
        // Match the backend RoundResult serialization boundary. Internal fields below
        // remain unrounded so this gate also detects state drift across later rounds.
        "revenue": rounded(result.revenue, places: 2),
        "costs": rounded(result.costs, places: 2),
        "profit": rounded(result.profit, places: 2),
        "marketShare": rounded(result.marketShare, places: 4),
        "sqRating": rounded(result.sqRating, places: 2),
        "cash": rounded(result.cash, places: 2), "inventory": result.inventory,
        "equity": rounded(update.equity, places: 2), "debt": rounded(update.totalDebt, places: 2),
        "sharesOutstanding": update.sharesOutstanding,
        "reputation": update.reputation, "imageRating": update.imageRating,
        "creditRating": update.creditRating.rawValue,
        "awarenessScore": rounded(result.awarenessScore, places: 4),
        "eps": result.scorecard.eps, "roe": result.scorecard.roe,
        "stockPrice": result.scorecard.stockPrice,
        "epsScore": rounded(result.scorecard.epsScore, places: 2),
        "roeScore": rounded(result.scorecard.roeScore, places: 2),
        "stockPriceScore": rounded(result.scorecard.stockPriceScore, places: 2),
        "imageScore": rounded(result.scorecard.imageScore, places: 2),
        "creditScore": rounded(result.scorecard.creditScore, places: 2),
        "totalScore": rounded(result.scorecard.totalScore, places: 2),
        "productionCost": rounded(result.productionCosts, places: 2),
        "marketingCost": rounded(result.marketingCosts, places: 2),
        "demand": [
            "wholesale": result.wholesaleUnitsSold, "internet": result.internetUnitsSold,
            "amazon": result.amazonUnitsSold, "privateLabel": result.privateLabelUnitsSold,
            "totalSold": result.unitsSold
        ]
    ]
}

@main struct Main {
    static func main() throws {
        guard CommandLine.arguments.count == 3 else {
            throw NSError(domain: "SwiftGoldenRunner", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "usage: runner FIXTURE OUTPUT"])
        }
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
        var caseOutputs: [String: Any] = [:]
        for testCase in fixture.cases {
            let c = testCase.config
            let config = SessionConfiguration(
                name: testCase.name, totalRounds: max(testCase.round, 1), startingCash: c.startingCash,
                marketType: MarketType(rawValue: c.marketType)!, numberOfAICompetitors: 0,
                randomSeed: c.randomSeed, fixedCostsPerRound: c.fixedCostsPerRound,
                baseCostPerUnit: c.baseCostPerUnit, baseMarketDemand: c.baseMarketDemand,
                sharesOutstanding: c.sharesOutstanding, initialEquity: c.initialEquity,
                plantCapacity: c.plantCapacity)
            let teams = testCase.teams.map { t in
                TeamStatus(id: UUID(uuidString: t.id)!, name: t.name, cash: t.cash,
                    inventory: t.inventory, reputation: t.reputation,
                    cumulativeTQM: t.cumulativeTQM, equity: t.equity, totalDebt: t.debt,
                    sharesOutstanding: t.sharesOutstanding, sqRating: t.sqRating,
                    imageRating: t.imageRating, creditRating: CreditRating(rawValue: t.creditRating)!,
                    cumulativeInvestorScore: t.cumulativeInvestorScore, roundsScored: t.roundsScored)
            }
            var decisions: [UUID: PlayerDecision] = [:]
            for team in teams {
                let d = testCase.decisions[team.name]!
                decisions[team.id] = PlayerDecision(
                    teamId: team.id,
                    round: testCase.round,
                    wholesalePrice: d.wholesalePrice,
                    internetPrice: d.internetPrice,
                    privateLabelBidPrice: d.privateLabelBidPrice,
                    privateLabelMaxUnits: d.privateLabelMaxUnits,
                    materialsQuality: MaterialsQuality(rawValue: d.materialsQuality)!,
                    stylingBudget: d.stylingBudget,
                    modelsOffered: d.modelsOffered,
                    tqmInvestment: d.tqmInvestment,
                    advertisingBudget: d.advertisingBudget,
                    celebrityEndorsement: CelebrityEndorsement(rawValue: d.celebrityEndorsement)!,
                    retailOutlets: d.retailOutlets,
                    mailInRebate: d.mailInRebate,
                    deliveryTime: DeliveryTime(rawValue: d.deliveryTime)!,
                    freeShippingThreshold: d.freeShippingThreshold,
                    amazonPrice: d.amazonPrice,
                    amazonAdBudget: d.amazonAdBudget,
                    fulfillmentMethod: FulfillmentMethod(rawValue: d.fulfillmentMethod)!,
                    tiktokBudget: d.tiktokBudget,
                    instagramBudget: d.instagramBudget,
                    youtubeBudget: d.youtubeBudget,
                    influencerTier: InfluencerTier(rawValue: d.influencerTier)!,
                    baseWage: d.baseWage,
                    incentivePay: d.incentivePay,
                    trainingHours: d.trainingHours,
                    bestPracticesInvestment: d.bestPracticesInvestment,
                    productionQuantity: d.productionQuantity,
                    overtimePercent: d.overtimePercent,
                    csrInvestment: d.csrInvestment,
                    dividendsPerShare: d.dividendsPerShare,
                    newLoanAmount: d.newLoanAmount,
                    sharesBuyback: d.sharesBuyback,
                    sharesIssued: d.sharesIssued)
            }
            let snapshot = SimulationSnapshot(config: config, currentRound: testCase.round, teams: teams,
                decisions: decisions, previousRoundDecisions: [:], roundResults: [:])
            let output = SimulationEngine().processRoundPure(snapshot: snapshot, decisions: decisions)
            var teamsOutput: [String: Any] = [:]
            for result in output.results {
                let update = output.teamUpdates.first { $0.teamId == result.teamId }!
                let teamName = teams.first { $0.id == result.teamId }!.name
                teamsOutput[teamName] = normalize(result, update: update)
            }
            caseOutputs[testCase.name] = teamsOutput
        }
        let data = try JSONSerialization.data(withJSONObject: ["cases": caseOutputs], options: [.prettyPrinted, .sortedKeys])
        try data.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
    }
}
