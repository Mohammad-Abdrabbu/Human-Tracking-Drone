
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db import SessionLocal
from app.models import User
from app.main import hash_password

def reset_password(email, new_password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"Resetting password for {email}...")
            user.password_hash = hash_password(new_password)
            db.commit()
            print("Password updated successfully.")
        else:
            print(f"User {email} not found.")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password("operator@uop.edu.jo", "operator123")
