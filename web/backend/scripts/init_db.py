#!/usr/bin/env python3
"""
Initialize SAHTD user database.

This script creates the database tables and optionally seeds default users.

Usage:
    python scripts/init_db.py           # Create tables only
    python scripts/init_db.py --seed    # Create tables and seed default users

Environment Variables:
    SAHTD_OPERATOR_EMAIL     - Operator account email (default: operator@uop.edu.jo)
    SAHTD_OPERATOR_PASSWORD  - Operator account password (default: secret123)
    SAHTD_VIEWER_EMAIL       - Viewer account email (default: viewer@uop.edu.jo)
    SAHTD_VIEWER_PASSWORD    - Viewer account password (default: viewer123)
"""
import argparse
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
sys.path.insert(0, backend_dir)

import bcrypt
from app.db import engine, SessionLocal, DB_PATH
from app.models import Base, User


def create_tables():
    """Create all database tables from SQLAlchemy models."""
    print(f"Creating database at: {DB_PATH}")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created successfully")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def seed_users():
    """Seed default users from environment variables or defaults."""
    db = SessionLocal()
    
    # Default users configuration
    users_config = [
        {
            "email": os.getenv("SAHTD_OPERATOR_EMAIL", "operator@uop.edu.jo"),
            "password": os.getenv("SAHTD_OPERATOR_PASSWORD", "secret123"),
            "role": "operator",
        },
        {
            "email": os.getenv("SAHTD_VIEWER_EMAIL", "viewer@uop.edu.jo"),
            "password": os.getenv("SAHTD_VIEWER_PASSWORD", "viewer123"),
            "role": "viewer",
        },
    ]
    
    created_count = 0
    skipped_count = 0
    
    for config in users_config:
        existing = db.query(User).filter(User.email == config["email"]).first()
        if existing:
            print(f"  ⊘ User '{config['email']}' already exists (skipped)")
            skipped_count += 1
            continue
        
        user = User(
            email=config["email"],
            password_hash=hash_password(config["password"]),
            role=config["role"],
            is_active=True,
            token_version=0,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        print(f"  ✓ Created user '{config['email']}' with role '{config['role']}'")
        created_count += 1
    
    db.commit()
    db.close()
    
    print(f"\nSeeding complete: {created_count} created, {skipped_count} skipped")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize SAHTD user database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed default users (operator + viewer)",
    )
    parser.add_argument(
        "--force-reseed",
        action="store_true",
        help="Delete existing users and reseed (WARNING: destructive)",
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("SAHTD Database Initialization")
    print("=" * 50)
    
    # Create tables
    create_tables()
    
    if args.force_reseed:
        print("\n⚠ Force reseed requested - deleting all users...")
        db = SessionLocal()
        db.query(User).delete()
        db.commit()
        db.close()
        print("✓ All users deleted")
        args.seed = True
    
    if args.seed:
        print("\nSeeding default users...")
        seed_users()
    else:
        print("\nNo seeding requested. Use --seed to create default users.")
    
    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
