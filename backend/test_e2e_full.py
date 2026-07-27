"""Full E2E test for Practenture backend."""
import requests
import json

BASE_URL = 'http://localhost:8000'

# Login as professor
resp = requests.post(f'{BASE_URL}/api/auth/login', json={
    'provider': 'password',
    'username': 'testprof',
    'password': 'Test1234!'
})
print('Login (professor):', resp.status_code)
token = resp.json()['accessToken']
headers = {'Authorization': f'Bearer {token}'}

# Create session
resp = requests.post(f'{BASE_URL}/api/sessions', json={
    'name': 'Test Session',
    'config': {
        'totalRounds': 3,
        'numberOfAICompetitors': 3,
        'randomSeed': 42,
        'startingCash': 500000,
        'initialEquity': 300000,
        'plantCapacity': 10000,
        'maxOvertimePercent': 25,
        'minWage': 12000,
        'maxWage': 40000,
        'minDividend': 0.0,
        'maxDividend': 5.0,
        'marketType': 'moderate',
        'aiDifficulty': 'medium',
        'scoringMetric': 'investor_score',
        'fixedCostsPerRound': 5000,
        'baseCostPerUnit': 30,
        'baseMarketDemand': 10000,
        'sharesOutstanding': 10000,
        'baseInterestRate': 0.06
    }
}, headers=headers)
print('Create Session:', resp.status_code, resp.json())
session_code = resp.json()['code']

# Get session (public endpoint)
resp = requests.get(f'{BASE_URL}/api/sessions/{session_code}/public')
print('Get Session (public):', resp.status_code, resp.json()['code'])

# Login as student
resp = requests.post(f'{BASE_URL}/api/auth/login', json={
    'provider': 'password',
    'username': 'teststudent',
    'password': 'Test1234!'
})
print('Login (student):', resp.status_code)
student_token = resp.json()['accessToken']
student_headers = {'Authorization': f'Bearer {student_token}'}

# Join session as student
resp = requests.put(f'{BASE_URL}/api/sessions/{session_code}/join', json={
    'teamName': 'Team A',
    'studentId': 'teststudent'
}, headers=student_headers)
print('Join Session:', resp.status_code, resp.json())

print('\nE2E test completed!')
