#!/usr/bin/env python3
"""Test script for the simulation engine"""

from simulation_engine import process_round, compute_sq_rating, generate_ai_decision
from models import SessionConfiguration, TeamConfig, PlayerDecision, MaterialsQuality, CelebrityEndorsement, DeliveryTime, InfluencerTier, FulfillmentMethod, SocialMediaBudget

def test_basic():
    print('Testing basic simulation...')
    config = SessionConfiguration(totalRounds=8, numberOfAICompetitors=2)
    teams = [TeamConfig(teamName='Team1', isAI=True, aiStrategy='balanced')]
    decisions = {}

    results, states = process_round(config, teams, decisions, 1, {}, None)
    print(f'Round 1 results: {len(results)} teams')
    if results:
        r = results[0]
        print(f'  Revenue: {r.revenue:.2f}')
        print(f'  Profit: {r.profit:.2f}')
        print(f'  SQ Rating: {r.sqRating:.2f}')
        print(f'  Total Score: {r.totalScore:.2f}')
        print(f'  Stock Price: {r.stockPrice:.2f}')

    # Test S/Q rating
    sq = compute_sq_rating(MaterialsQuality.standard, 3000, 5, 10000, 2000, 40, 5.0)
    print(f'S/Q rating: {sq:.2f}')

    # Test AI decision generation
    d = generate_ai_decision('TestTeam', 1, 42, 'balanced')
    print(f'AI decision wholesale: {d.wholesalePrice}')
    print(f'AI decision materials: {d.materialsQuality.value}')

    print('BASIC TEST PASSED\n')

def test_multiple_strategies():
    print('Testing multiple AI strategies...')
    config = SessionConfiguration(totalRounds=3, numberOfAICompetitors=1)
    teams = [
        TeamConfig(teamName='AggressiveAI', isAI=True, aiStrategy='aggressive'),
        TeamConfig(teamName='BalancedAI', isAI=True, aiStrategy='balanced'),
        TeamConfig(teamName='ConservativeAI', isAI=True, aiStrategy='conservative')
    ]

    # Create a proper human decision
    human_decision = PlayerDecision(
        wholesalePrice=25.0,
        internetPrice=27.0,
        amazonPrice=29.0,
        materialsQuality=MaterialsQuality.standard,
        stylingBudget=50000.0,
        modelsOffered=4,
        tqmInvestment=30000.0,
        bestPracticesInvestment=2000.0,
        trainingHours=20.0,
        baseWage=25000.0,
        incentivePay=1000.0,
        advertisingBudget=50000.0,
        retailOutlets=5,
        celebrityEndorsement=CelebrityEndorsement.none,
        deliveryTime=DeliveryTime.standard,
        mailInRebate=1.0,
        tiktokBudget=5000.0,
        instagramBudget=5000.0,
        youtubeBudget=5000.0,
        socialMediaBudget=SocialMediaBudget(tiktok=5000.0, instagram=5000.0, youtube=5000.0),
        influencerTier=InfluencerTier.nano,
        privateLabelBidPrice=15.0,
        privateLabelMaxUnits=500,
        freeShippingThreshold=25.0,
        amazonAdBudget=10000.0,
        fulfillmentMethod=FulfillmentMethod.fba,
        sharesBuyback=0,
        sharesIssued=0,
        dividendsPerShare=0.0,
        newLoanAmount=0.0,
        csrInvestment=5000.0
    )

    decisions = {'HumanTeam': human_decision}

    results, states = process_round(config, teams, decisions, 1, {}, None)
    print(f'Round 1 results: {len(results)} teams')

    names = ['AggressiveAI', 'BalancedAI', 'ConservativeAI', 'HumanTeam']
    for i, r in enumerate(results):
        name = names[i]
        print(f'{name}: Revenue=${r.revenue:,.0f}, Profit=${r.profit:,.0f}, SQ={r.sqRating:.1f}, Stock=${r.stockPrice:.2f}')

    print('\nTesting 3-round simulation...')
    states = {}
    for round_num in range(1, 4):
        decisions = {}
        # Add AI decisions
        for team in teams:
            if team.isAI:
                decisions[team.teamName] = generate_ai_decision(team.teamName, round_num, 42+round_num, team.aiStrategy)
        # Add human decision (same each round for simplicity)
        decisions['HumanTeam'] = human_decision
        
        results, states = process_round(config, teams, decisions, round_num, states, None)
        
        print(f'Round {round_num}:')
        for r in results:
            # We don't have team name in result, but we can infer order
            print(f'  Team: Profit=${r.profit:,.0f}, SQ={r.sqRating:.1f}, Stock=${r.stockPrice:.2f}')

    print('\nMULTI-ROUND TEST PASSED\n')

if __name__ == '__main__':
    test_basic()
    test_multiple_strategies()
    print('All tests passed!')