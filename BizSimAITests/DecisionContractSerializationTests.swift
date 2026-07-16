import XCTest
@testable import BizSimAI

final class DecisionContractSerializationTests: XCTestCase {
    func testJoinRequestUsesExactCamelCaseContract() throws {
        let data = try JSONEncoder().encode(JoinRequestBackend(teamName: "Team Alpha", studentId: "STU001"))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(Set(json.keys), ["teamName", "studentId"])
        XCTAssertEqual(json["teamName"] as? String, "Team Alpha")
        XCTAssertEqual(json["studentId"] as? String, "STU001")
        XCTAssertNil(json["team_name"])
        XCTAssertNil(json["student_id"])
    }

    func testDecisionRequestSerializesEveryGameInputInCamelCase() throws {
        let backend = PlayerDecisionBackend(
            wholesalePrice: 71, internetPrice: 72, amazonPrice: 73,
            privateLabelBidPrice: 41, privateLabelMaxUnits: 42, amazonAdBudget: 43,
            materialsQuality: 1, stylingBudget: 44, numModels: 5, modelsOffered: 5,
            tqmInvestment: 45, rdInvestment: 46, marketingInvestment: 47,
            advertisingBudget: 48, celebrityType: "actor", celebrityEndorsement: "global",
            retailOutlets: 49, mailInRebate: 2, deliveryTime: "rush",
            freeShippingThreshold: 50,
            socialMediaBudget: .init(tiktok: 51, instagram: 52, youtube: 53),
            tiktokBudget: 51, instagramBudget: 52, youtubeBudget: 53,
            influencerTier: "micro", baseWage: 26000, incentivePay: 0.75,
            trainingBudget: 1200, trainingHours: 24, bestPracticesInvestment: 54,
            productionQuantity: 9000, overtimePercent: 12, csrInvestment: 55,
            dividendsPerShare: 0.75, newLoanAmount: 10000, sharesBuyback: 100,
            sharesIssued: 50, fulfillmentMethod: "fba", internetPromotion: 0.2
        )
        let data = try JSONEncoder().encode(
            SubmitDecisionRequestBackend(round: 3, teamId: "Team Alpha", decision: backend)
        )
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(root["round"] as? Int, 3)
        XCTAssertEqual(root["teamId"] as? String, "Team Alpha")
        XCTAssertNil(root["team_id"])
        let decision = try XCTUnwrap(root["decision"] as? [String: Any])
        let requiredModernKeys: Set<String> = [
            "wholesalePrice", "internetPrice", "amazonPrice", "privateLabelBidPrice",
            "privateLabelMaxUnits", "amazonAdBudget", "materialsQuality", "stylingBudget",
            "modelsOffered", "tqmInvestment", "advertisingBudget", "celebrityEndorsement",
            "retailOutlets", "mailInRebate", "deliveryTime", "freeShippingThreshold",
            "tiktokBudget", "instagramBudget", "youtubeBudget", "influencerTier",
            "baseWage", "incentivePay", "trainingHours", "bestPracticesInvestment",
            "productionQuantity", "overtimePercent", "csrInvestment", "dividendsPerShare",
            "newLoanAmount", "sharesBuyback", "sharesIssued", "fulfillmentMethod"
        ]
        XCTAssertTrue(requiredModernKeys.isSubset(of: Set(decision.keys)),
                      "Missing modern fields: \(requiredModernKeys.subtracting(decision.keys))")
        XCTAssertEqual(decision["privateLabelBidPrice"] as? Double, 41)
        XCTAssertEqual(decision["amazonAdBudget"] as? Double, 43)
        XCTAssertEqual(decision["mailInRebate"] as? Double, 2)
        XCTAssertEqual(decision["trainingHours"] as? Double, 24)
        XCTAssertEqual(decision["bestPracticesInvestment"] as? Double, 54)
        XCTAssertFalse(decision.keys.contains { $0.contains("_") }, "Contract keys must be camelCase")
    }
}
