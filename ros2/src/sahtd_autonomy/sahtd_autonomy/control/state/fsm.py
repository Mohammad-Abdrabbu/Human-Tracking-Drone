"""Finite State Machine for follower node."""
from enum import Enum


class FollowState(Enum):
    """Follower node states."""
    GROUND = 0    # On ground, waiting for takeoff
    TAKEOFF = 1   # Taking off to target altitude
    SEARCH = 2    # Airborne, searching for target
    LOCKED = 3    # Tracking locked target


# Alias for backward compatibility (original was just 'S')
S = FollowState
