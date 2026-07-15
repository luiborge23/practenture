"""
Automated password reset script for BizSimAI.
This ensures professor and owner accounts always have correct passwords after Docker rebuilds.
"""

import sqlite3
import sys
import os

# Database path (matches docker-compose.yml)
DB_PATH = "/data/bizsim.db"

# Default credentials
DEFAULT_USERS = [
    {
        "username": "professor",
        "password": "Prof@2026X",
        "role": "professor"
    },
    {
        "username": "owner",
        "password": "Owner@2026X",
        "role": "owner"
    }
]

def hash_password(password):
    """Hash password using bcrypt (same as auth.py)"""
    import bcrypt
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def reset_passwords():
    """Reset default user passwords in the database"""
    print(f"🔑 Connecting to database: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for user in DEFAULT_USERS:
        username = user["username"]
        password = user["password"]
        role = user["role"]
        
        # Hash the password
        hashed_pw = hash_password(password)
        
        # Check if user exists (users table uses username as PK, no 'id' column)
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing user
            cursor.execute(
                "UPDATE users SET password_hash = ?, role = ? WHERE username = ?",
                (hashed_pw, role, username)
            )
            print(f"✅ Reset password for {username} ({role})")
        else:
            # Create new user
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hashed_pw, role)
            )
            print(f"✅ Created user {username} ({role})")
    
    conn.commit()
    conn.close()
    print("\n🎉 All passwords reset successfully!")

if __name__ == "__main__":
    reset_passwords()
