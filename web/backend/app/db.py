"""
SQLAlchemy database configuration for SAHTD backend.

Provides session management and database connection for the user authentication system.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------

def _get_sahtd_root() -> Path:
    """
    Get SAHTD repository root directory.
    
    Resolution order:
    1. SAHTD_ROOT environment variable
    2. Auto-detect by walking up from this file
    """
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

# Database path
DB_DIR = Path(os.getenv("SAHTD_DB_DIR", str(_SAHTD_ROOT / "data" / "db")))
DB_PATH = DB_DIR / "sahtd.db"

# Ensure database directory exists
DB_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SQLAlchemy Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
    echo=False,  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


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
