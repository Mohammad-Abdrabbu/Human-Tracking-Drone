#!/usr/bin/env python3
"""
Database seeding script for SAHTD.
Creates default users if they don't exist.
Run during deployment to ensure initial users are available.
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.db import SessionLocal, init_db
from app.models import User


def seed_users():
    """Create default users if they don't exist."""
    
    default_users = [
        {
            "email": "operator@uop.edu.jo",
            "password": "operator123",
            "role": "operator",
        },
        {
            "email": "viewer@uop.edu.jo", 
            "password": "viewer123",
            "role": "viewer",
        },
        {
            "email": "admin@sahtd.com",
            "password": "admin123",
            "role": "operator",
        },
    ]
    
    db = SessionLocal()
    created_count = 0
    
    try:
        for user_data in default_users:
            # Check if user already exists
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                print(f"[SEED] User already exists: {user_data['email']}")
                continue
            
            # Hash password
            password_bytes = user_data["password"].encode("utf-8")
            hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
            
            # Create user
            user = User(
                email=user_data["email"],
                password_hash=hashed,
                role=user_data["role"],
                is_active=True,
            )
            db.add(user)
            db.commit()
            created_count += 1
            print(f"[SEED] Created user: {user_data['email']} (role: {user_data['role']})")
    
    except Exception as e:
        print(f"[SEED] Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    
    print(f"[SEED] Complete. Created {created_count} new users.")
    return created_count


def main():
    """Initialize database and seed users."""
    print("[SEED] Initializing database...")
    init_db()
    
    print("[SEED] Seeding users...")
    seed_users()
    
    print("[SEED] Done!")


if __name__ == "__main__":
    main()
