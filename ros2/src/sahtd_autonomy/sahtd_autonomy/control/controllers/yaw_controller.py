"""Yaw controller for heading alignment."""
import math


class YawController:
    """
    PD controller for yaw alignment with target.
    
    Features:
    - Low-pass filter on error
    - Deadzone for small errors
    - Center hold for precision
    - Rate limiting for smooth commands
    """
    
    def __init__(
        self,
        k_yaw: float = 1.2,
        kd_yaw: float = 0.0,
        lpf_alpha: float = 0.20,
        deadzone: float = 0.08,
        center_hold_deg: float = 1.5,
        yawrate_max: float = 0.5,
        rate_limit_deg_s2: float = 60.0
    ):
        """
        Initialize yaw controller.
        
        Args:
            k_yaw: Proportional gain (rad/s per rad)
            kd_yaw: Derivative gain (rad/s per rad/s)
            lpf_alpha: Low-pass filter coefficient (0..1)
            deadzone: No response below this error (rad)
            center_hold_deg: Precision zone for center hold (deg)
            yawrate_max: Maximum yaw rate (rad/s)
            rate_limit_deg_s2: Rate limit for yaw rate change (deg/s²)
        """
        self.k_yaw = k_yaw
        self.kd_yaw = kd_yaw
        self.lpf_alpha = lpf_alpha
        self.deadzone = deadzone
        self.center_hold_rad = math.radians(center_hold_deg)
        self.yawrate_max = yawrate_max
        self.rate_limit_rad_s2 = math.radians(rate_limit_deg_s2)
        
        # State
        self._ex_f = 0.0          # Filtered error
        self._prev_ex_f = 0.0     # Previous filtered error (for derivative)
        self._prev_yawspeed = 0.0 # Previous yaw command (for rate limiting)
    
    def reset(self):
        """Reset controller state."""
        self._ex_f = 0.0
        self._prev_ex_f = 0.0
        self._prev_yawspeed = 0.0
    
    def compute(self, ex_raw: float, dt: float) -> float:
        """
        Compute yaw rate command.
        
        Args:
            ex_raw: Raw horizontal error, normalized [-1, 1]
            dt: Time step (seconds)
        
        Returns:
            Yaw rate command (rad/s), positive = turn right
        """
        # Low-pass filter
        self._ex_f = self.lpf_alpha * ex_raw + (1 - self.lpf_alpha) * self._ex_f
        
        # Convert to radians (ex_f is normalized, multiply by FOV/2 ≈ π)
        ex_rad = self._ex_f * math.pi
        
        # Center hold: if very close to center, don't oscillate
        if abs(ex_rad) < self.center_hold_rad:
            yawspeed = 0.0
        elif abs(ex_rad) < self.deadzone:
            yawspeed = 0.0
        else:
            # PD control
            ex_d = (self._ex_f - self._prev_ex_f) / dt if dt > 0.001 else 0.0
            yawspeed = self.k_yaw * ex_rad + self.kd_yaw * ex_d * math.pi
        
        # Clamp to max rate
        yawspeed = max(-self.yawrate_max, min(self.yawrate_max, yawspeed))
        
        # Rate limit
        if dt > 0:
            max_delta = self.rate_limit_rad_s2 * dt
            delta = yawspeed - self._prev_yawspeed
            if abs(delta) > max_delta:
                yawspeed = self._prev_yawspeed + max_delta * (1 if delta > 0 else -1)
        
        # Update state
        self._prev_ex_f = self._ex_f
        self._prev_yawspeed = yawspeed
        
        return yawspeed
    
    @property
    def filtered_error(self) -> float:
        """Get current filtered error (normalized)."""
        return self._ex_f
    
    @property
    def filtered_error_rad(self) -> float:
        """Get current filtered error in radians."""
        return self._ex_f * math.pi
