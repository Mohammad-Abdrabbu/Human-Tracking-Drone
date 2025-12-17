"""
SAHTD Paths Utility Module

Provides helpers for computing repo-relative paths so that SAHTD works
after git clone to any location.

Usage:
    from sahtd_autonomy.utils.paths import get_sahtd_root, default_events_log
    
    root = get_sahtd_root()
    log_path = default_events_log()
"""
import os
from pathlib import Path
from typing import Optional

_cached_root: Optional[Path] = None


def get_sahtd_root() -> Path:
    """
    Get SAHTD repository root directory.
    
    Resolution order:
    1. SAHTD_ROOT environment variable (if set)
    2. Auto-detect by walking up from this file until markers found
    
    Markers (checked in order):
    - .git directory exists
    - Both ros2/ and web/ directories exist
    
    Returns:
        Path to SAHTD repo root
        
    Raises:
        RuntimeError if root cannot be determined
    """
    global _cached_root
    
    if _cached_root is not None:
        return _cached_root
    
    # 1. Check environment variable
    env_root = os.environ.get('SAHTD_ROOT')
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if root.is_dir():
            _cached_root = root
            return root
    
    # 2. Auto-detect by walking up from this file
    current = Path(__file__).resolve().parent
    
    # Walk up to find repo root (max 10 levels)
    for _ in range(10):
        # Check for .git directory
        if (current / '.git').is_dir():
            _cached_root = current
            return current
        
        # Check for ros2/ and web/ directories (repo structure markers)
        if (current / 'ros2').is_dir() and (current / 'web').is_dir():
            _cached_root = current
            return current
        
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    # Fallback: use home directory ~/sahtd (legacy behavior)
    fallback = Path.home() / 'sahtd'
    if fallback.is_dir():
        _cached_root = fallback
        return fallback
    
    raise RuntimeError(
        "Cannot determine SAHTD root. Set SAHTD_ROOT environment variable "
        "or ensure repo structure markers exist."
    )


def data_dir() -> Path:
    """Return path to data directory: $SAHTD_ROOT/data"""
    return get_sahtd_root() / 'data'


def logs_dir() -> Path:
    """Return path to logs directory: $SAHTD_ROOT/data/logs"""
    return data_dir() / 'logs'


def default_events_log() -> Path:
    """Return default events log path: $SAHTD_ROOT/data/logs/events.jsonl"""
    return logs_dir() / 'events.jsonl'


def default_telemetry_log() -> Path:
    """Return default telemetry log path: $SAHTD_ROOT/data/logs/telemetry.jsonl"""
    return logs_dir() / 'telemetry.jsonl'


def default_fence_yaml() -> Path:
    """Return default geo-fence YAML path."""
    return get_sahtd_root() / 'ros2' / 'src' / 'sahtd_launch' / 'config' / 'geo_guard.yaml'


def weights_dir() -> Path:
    """Return path to model weights: $SAHTD_ROOT/simulation/weights"""
    return get_sahtd_root() / 'simulation' / 'weights'
