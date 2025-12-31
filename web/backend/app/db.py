"""
SQLAlchemy database configuration for SAHTD backend.

Supports both SQLite (local development) and PostgreSQL (production/Render).
Database URL is configured via DATABASE_URL environment variable.

Examples:
    SQLite:     DATABASE_URL=sqlite:///./data/db/sahtd.db
    PostgreSQL: DATABASE_URL=postgresql://user:pass@host:5432/dbname
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------------------------------------------------------------------
# Path Resolution (for SQLite fallback)
# ---------------------------------------------------------------------------

def _get_sahtd_root() -> Path:
    """Get SAHTD repository root directory."""
    env_root = os.getenv("SAHTD_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / '.git').is_dir():
            return current
        if (current / 'ros2').is_dir() and (current / 'web').is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    return Path.home() / 'sahtd'


_SAHTD_ROOT = _get_sahtd_root()

# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------

# Get DATABASE_URL from environment, fallback to SQLite for local dev
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to SQLite for local development
    DB_DIR = Path(os.getenv("SAHTD_DB_DIR", str(_SAHTD_ROOT / "data" / "db")))
    DB_PATH = DB_DIR / "sahtd.db"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# Render uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Determine if using SQLite
_is_sqlite = DATABASE_URL.startswith("sqlite")

# Create engine with appropriate settings
if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
        echo=False,
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before use
        pool_size=5,
        max_overflow=10,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db():
    """
    Create all database tables.
    Call this once at startup or for initial setup.
    """
    from . import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Tables created using: {DATABASE_URL[:50]}...")


# ---------------------------------------------------------------------------
# Dependency for FastAPI
# ---------------------------------------------------------------------------

def get_db():
    """
    FastAPI dependency that provides a database session.
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

