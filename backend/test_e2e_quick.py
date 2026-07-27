"""Quick E2E test for Practenture backend."""
import requests
import json

BASE_URL = 'http://localhost:8000'

# Login as professor
resp = requests.post(f'{BASE_URL}/api/auth/login', json={
    'provider': 'password',
    'username': 'testprof',
    'password': 'Test1234!'
})
print('Login:', resp.status_code)
token = resp.json()['accessToken']
headers = {'Authorization': f'Bearer {token}'}

# Create session
resp = requests.post(f'{BASE_URL}/api/sessions', json={
    'name': 'Test Session',
    'config': {
        'rounds': 3,
        'student_count': 4,
        'initial_cash': 10000,
        'initial_inventory': 100,
        'initial_equipment': 5,
        'marketing_budget': 1000,
        'production_capacity': 500
    }
}, headers=headers)
print('Create Session:', resp.status_code, resp.json())
session_id = resp.json()['sessionId']

# Get session (public endpoint)
resp = requests.get(f'{BASE_URL}/api/sessions/BIZ-EKFK/public')
print('Get Session:', resp.status_code, resp.json())

# Join session as student
resp = requests.put(f'{BASE_URL}/api/sessions/BIZ-MQT8/join', json={
    'teamName': 'Team A',
    'studentId': 'student1'
})
print('Join Session:', resp.status_code, resp.json())

print('\nE2E test completed!')
