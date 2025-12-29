"""
SQLAlchemy models for SAHTD backend.

Defines the User model for authentication and user management.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .db import Base


class User(Base):
    """
    User model for authentication.
    
    Attributes:
        id: Primary key
        email: Unique email address (used as username)
        password_hash: bcrypt hashed password
        role: User role ('operator' or 'viewer')
        is_active: Whether the user account is active
        token_version: Incremented when tokens should be revoked
        created_at: Account creation timestamp
        last_login_at: Last successful login timestamp
        failed_attempts: Count of consecutive failed login attempts
        locked_until: Optional lockout timestamp (for brute-force protection)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    is_active = Column(Boolean, default=True, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user to dictionary for API responses.
        
        Args:
            include_sensitive: If True, includes password_hash (for admin use only)
        """
        data = {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "token_version": self.token_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "failed_attempts": self.failed_attempts,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data
