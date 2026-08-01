import secrets
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from database import db

client=TestClient(app)

def code():
    c=f"PROF-T{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
    assert db.create_professor_code(c,"Test University","auth enrollment test")
    return c

def test_password_professor_activation_is_atomic_and_one_time():
    c=code(); username=f"prof_{secrets.token_hex(4)}"
    body={"professorCode":c,"username":username,"email":f"{username}@example.edu","name":"Test Professor","universityName":"Test University","password":"StrongPass9!","confirmPassword":"StrongPass9!"}
    r=client.post('/api/auth/password/activate-professor',json=body)
    assert r.status_code==201, r.text
    assert r.json()['role']=='professor' and r.json()['accessToken']
    assert client.post('/api/auth/login',json={"provider":"password","username":username,"password":"StrongPass9!"}).status_code==200
    body.update(username=f"other_{secrets.token_hex(3)}",email=f"other_{secrets.token_hex(3)}@example.edu")
    assert client.post('/api/auth/password/activate-professor',json=body).status_code in (400,409)

def test_invalid_activation_rolls_back_user_and_code():
    c=code(); u=f"rollback_{secrets.token_hex(4)}"
    bad={"professorCode":"PROF-NOPE-NOPE","username":u,"email":f"{u}@example.edu","name":"Rollback","password":"StrongPass9!","confirmPassword":"StrongPass9!"}
    assert client.post('/api/auth/password/activate-professor',json=bad).status_code==409
    assert db.get_user(u) is None
    assert db.validate_professor_code(c) is not None

def test_apple_new_then_returning_login_and_nonce():
    c=code(); payload={"sub":f"apple-{secrets.token_hex(5)}","email":"relay@privaterelay.appleid.com","name":"Apple Professor","nonce":"nonce-a"}
    with patch('auth.verify_apple_id_token',return_value=payload):
        first=client.post('/api/auth/login',json={"provider":"apple","id_token":"valid","provider_nonce":"nonce-a"})
        assert first.status_code==200 and first.json()['professorCodeRequired'] is True
        enrolled=client.post('/api/auth/login',json={"provider":"apple","id_token":"valid","provider_nonce":"nonce-a","professor_code":c})
        assert enrolled.status_code==200, enrolled.text
        assert enrolled.json()['role']=='professor'
        returning=client.post('/api/auth/login',json={"provider":"apple","id_token":"valid","provider_nonce":"nonce-a"})
        assert returning.status_code==200 and returning.json()['userId']==enrolled.json()['userId']
        assert client.post('/api/auth/login',json={"provider":"apple","id_token":"valid","provider_nonce":"wrong"}).status_code==401

def test_google_new_professor_enrollment():
    c=code(); payload={"sub":f"google-{secrets.token_hex(5)}","email":"google@example.edu","name":"Google Professor","nonce":"nonce-g"}
    with patch('auth.verify_google_id_token',return_value=payload):
        r=client.post('/api/auth/login',json={"provider":"google","id_token":"valid","provider_nonce":"nonce-g","professor_code":c})
        assert r.status_code==200, r.text
        assert r.json()['role']=='professor' and r.json()['accessToken']

def test_returning_legacy_social_student_keeps_student_role():
    subject=f"legacy-google-{secrets.token_hex(5)}"
    username=f"social_student_{secrets.token_hex(4)}"
    assert db.create_user(
        username=username,
        password_hash="",
        role="student",
        name="Legacy Social Student",
        student_id=username,
        email=f"{username}@example.edu",
        provider="google",
        provider_uid=subject,
    )
    payload={"sub":subject,"email":f"{username}@example.edu","name":"Legacy Social Student"}
    with patch('auth.verify_google_id_token',return_value=payload):
        response=client.post('/api/auth/login',json={"provider":"google","id_token":"valid"})

    assert response.status_code==200, response.text
    assert response.json()['userId']==username
    assert response.json()['role']=='student'
    assert response.json()['professorCodeRequired'] is False
    assert response.json()['accessToken']
