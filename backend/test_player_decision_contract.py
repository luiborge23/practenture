"""Contract tests for modern and production-legacy PlayerDecision payloads."""

from models import PlayerDecision


def test_legacy_test_backend_payload_translates_and_serializes() -> None:
    payload = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "athlete",
        "socialMediaBudget": {
            "tiktok": 10000,
            "instagram": 15000,
            "youtube": 5000,
        },
        "baseWage": 25000.0,
        "incentivePay": 1000.0,
        "trainingBudget": 50000.0,
        "productionQuantity": 8000,
        "overtimePercent": 10,
        "csrInvestment": 20000.0,
        "dividendsPerShare": 0.5,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 5,
        "fulfillmentMethod": "fba",
        "internetPromotion": 0.2,
    }

    serialized = PlayerDecision.model_validate(payload).model_dump(mode="json")

    assert serialized["materialsQuality"] == "standard"
    assert serialized["modelsOffered"] == 5
    assert serialized["celebrityEndorsement"] == "local"
    assert serialized["trainingHours"] == 1000.0
    assert serialized["productionQuantity"] == 8000
    assert serialized["overtimePercent"] == 10.0
    assert serialized["rdInvestment"] == 100000.0
    assert serialized["marketingInvestment"] == 150000.0
    assert serialized["internetPromotion"] == 0.2
    assert serialized["socialMediaBudget"] == {
        "tiktok": 10000.0,
        "instagram": 15000.0,
        "youtube": 5000.0,
    }
    assert serialized["tiktokBudget"] == 10000.0
    assert serialized["instagramBudget"] == 15000.0
    assert serialized["youtubeBudget"] == 5000.0


def test_modern_ios_payload_preserves_modern_contract_on_serialization() -> None:
    payload = {
        "wholesalePrice": 80.0,
        "internetPrice": 90.0,
        "amazonPrice": 85.0,
        "privateLabelBidPrice": 45.0,
        "privateLabelMaxUnits": 50,
        "amazonAdBudget": 1200.0,
        "materialsQuality": "superior",
        "stylingBudget": 5000.0,
        "modelsOffered": 4,
        "tqmInvestment": 2500.0,
        "advertisingBudget": 9000.0,
        "celebrityEndorsement": "global",
        "retailOutlets": 25,
        "mailInRebate": 2.0,
        "deliveryTime": "rush",
        "freeShippingThreshold": 75.0,
        "tiktokBudget": 1100.0,
        "instagramBudget": 2200.0,
        "youtubeBudget": 3300.0,
        "influencerTier": "micro",
        "baseWage": 26000.0,
        "incentivePay": 0.75,
        "trainingHours": 24.0,
        "bestPracticesInvestment": 1500.0,
        "productionQuantity": 9000,
        "overtimePercent": 12.5,
        "csrInvestment": 2500.0,
        "dividendsPerShare": 0.75,
        "newLoanAmount": 10000.0,
        "sharesBuyback": 100,
        "sharesIssued": 50,
        "fulfillmentMethod": "fba",
    }

    serialized = PlayerDecision.model_validate(payload).model_dump(mode="json")

    assert serialized["materialsQuality"] == "superior"
    assert serialized["modelsOffered"] == 4
    assert serialized["celebrityEndorsement"] == "global"
    assert serialized["trainingHours"] == 24.0
    assert serialized["overtimePercent"] == 12.5
    assert serialized["fulfillmentMethod"] == "fba"
    assert serialized["socialMediaBudget"] == {
        "tiktok": 1100.0,
        "instagram": 2200.0,
        "youtube": 3300.0,
    }


def test_modern_fields_take_precedence_in_transition_payload() -> None:
    decision = PlayerDecision.model_validate(
        {
            "materialsQuality": "superior",
            "modelsOffered": 7,
            "numModels": 2,
            "celebrityEndorsement": "national",
            "celebrityType": "athlete",
            "trainingHours": 16,
            "trainingBudget": 50000,
        }
    )

    assert decision.materialsQuality.value == "superior"
    assert decision.modelsOffered == 7
    assert decision.celebrityEndorsement.value == "national"
    assert decision.trainingHours == 16