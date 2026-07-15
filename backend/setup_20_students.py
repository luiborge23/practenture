"""Setup script for 20-student test: creates professor, 20 students, and a session."""
import sys
sys.path.insert(0, 'backend')

from database import Database
from models import SessionConfiguration, TeamConfig
import bcrypt

def setup():
    db = Database()
    
    # 1. Create professor user
    print("Creating professor...")
    password_hash = bcrypt.hashpw(b"Professor@2026X", bcrypt.gensalt()).decode()
    db.create_user(
        username="professor",
        password_hash=password_hash,
        role="professor",
        name="Professor"
    )
    print("  ✅ Professor created (username: professor, password: Professor@2026X)")
    
    # 2. Create 20 students in 5 teams of 4
    print("\nCreating 20 students...")
    team_names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    students_per_team = 4
    
    for team_idx, team_name in enumerate(team_names):
        print(f"\n  Team {team_name}:")
        for student_idx in range(students_per_team):
            student_num = team_idx * students_per_team + student_idx + 1
            username = f"STU{student_num:03d}"
            student_id = f"S{student_num:04d}"
            
            password_hash = bcrypt.hashpw(b"Student@2026X", bcrypt.gensalt()).decode()
            db.create_user(
                username=username,
                password_hash=password_hash,
                role="student",
                name=f"Student {student_num}",
                student_id=student_id
            )
            print(f"    ✅ {username} (ID: {student_id}) - Team {team_name}")
    
    # 3. Create session with 5 teams
    print("\nCreating session...")
    config = SessionConfiguration(
        totalRounds=8,
        numberOfAICompetitors=3,
        startingCash=500000.0,
    )
    
    teams = []
    for team_name in team_names:
        teams.append(TeamConfig(
            teamName=team_name,
            isAI=False,
        ))
    
    code = db.create_session(config, teams, "professor", max_human_teams=30)
    print(f"  ✅ Session created: {code}")
    
    # Print summary
    print("\n" + "="*60)
    print("SETUP COMPLETE - TEST DATA READY")
    print("="*60)
    print(f"\nSession Code: {code}")
    print(f"Teams: {', '.join(team_names)}")
    print(f"\nProfessor Login:")
    print(f"  Username: professor")
    print(f"  Password: Professor@2026X")
    print(f"\nStudent Logins (all same password): Student@2026X")
    print(f"{'Username':<15} {'Student ID':<15} {'Team'}")
    print("-"*45)
    
    for team_idx, team_name in enumerate(team_names):
        for student_idx in range(students_per_team):
            student_num = team_idx * students_per_team + student_idx + 1
            username = f"STU{student_num:03d}"
            student_id = f"S{student_num:04d}"
            print(f"{username:<15} {student_id:<15} {team_name}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    setup()
