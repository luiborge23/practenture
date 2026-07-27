"""
Create STU001-STU020 student accounts for 20-student testing.
Run inside the practenture-backend container: docker exec practenture-backend python3 /app/create_20_students.py
"""
import sqlite3
import bcrypt
import sys

DB_PATH = "/data/practenture.db"

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    created = 0
    updated = 0
    
    for i in range(1, 21):
        username = f"STU{i:03d}"
        password = "Stu1@2026X"
        role = "student"
        hashed_pw = hash_password(password)
        
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE users SET password_hash = ?, role = ?, name = ?, student_id = ? WHERE username = ?",
                (hashed_pw, role, username, username, username)
            )
            updated += 1
            print(f"✅ Updated {username}")
        else:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, name, student_id) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_pw, role, username, username)
            )
            created += 1
            print(f"✅ Created {username}")
    
    conn.commit()
    conn.close()
    print(f"\n🎉 Done! Created: {created}, Updated: {updated}")

if __name__ == "__main__":
    main()
