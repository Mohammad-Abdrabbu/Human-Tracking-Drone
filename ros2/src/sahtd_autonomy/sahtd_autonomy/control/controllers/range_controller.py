"""Range controller for forward velocity with progressive speed."""
import math
from typing import Literal

ZoneType = Literal["FAR", "HOV", "NEAR"]


class RangeController:
    """
    Forward velocity controller with:
    - Progressive speed (taper as target gets closer)
    - Zone-aware control (FAR/HOV/NEAR)
    - Proximity braking
    - Rate limiting for smooth commands
    """
    
    def __init__(
        self,
        stand_off_px: float = 300.0,
        kx: float = 0.012,
        vx_max: float = 0.5,
        rate_limit_vx: float = 0.15,
        max_close_px: float = 420.0,
        h_deadband_px: float = 10.0,
        allow_reverse: bool = False,
        # Progressive speed params
        progressive_enable: bool = True,
        progressive_hf_start: float = 80.0,
        progressive_hf_full: float = 160.0,
        progressive_vx_min: float = 0.08,
        # Proximity brake params
        prox_brake_enable: bool = True,
        prox_brake_hf_thresh: float = 200.0,
        prox_brake_vx_max: float = 0.10,
        prox_brake_decel_rate: float = 0.50,
        # NEAR back-off params
        near_backoff_enable: bool = True,
        near_backoff_vx: float = 0.15,
        near_backoff_kx: float = 0.006
    ):
        """
        Initialize range controller.
        
        Args:
            stand_off_px: Target bbox height at desired stand-off (pixels)
            kx: Proportional gain (m/s per pixel error)
            vx_max: Maximum forward velocity (m/s)
            rate_limit_vx: Rate limit for vx changes (m/s²)
            max_close_px: Beyond this h_f, never command positive vx
            h_deadband_px: No vx when |eR| <= this
            allow_reverse: Allow negative vx commands
            progressive_enable: Enable progressive speed tapering
            progressive_hf_start: h_f where speed reduction starts
            progressive_hf_full: h_f where speed is minimum
            progressive_vx_min: Minimum vx_max when very close
            prox_brake_enable: Enable proximity braking
            prox_brake_hf_thresh: h_f threshold for proximity brake
            prox_brake_vx_max: Max vx in proximity brake zone
            prox_brake_decel_rate: Deceleration rate in proximity brake
        """
        self.stand_off_px = stand_off_px
        self.kx = kx
        self.vx_max = vx_max
        self.rate_limit_vx = rate_limit_vx
        self.max_close_px = max_close_px
        self.h_deadband_px = h_deadband_px
        self.allow_reverse = allow_reverse
        
        # Progressive
        self.progressive_enable = progressive_enable
        self.progressive_hf_start = progressive_hf_start
        self.progressive_hf_full = progressive_hf_full
        self.progressive_vx_min = progressive_vx_min
        
        # Proximity brake
        self.prox_brake_enable = prox_brake_enable
        self.prox_brake_hf_thresh = prox_brake_hf_thresh
        self.prox_brake_vx_max = prox_brake_vx_max
        self.prox_brake_decel_rate = prox_brake_decel_rate
        
        # NEAR back-off
        self.near_backoff_enable = near_backoff_enable
        self.near_backoff_vx = near_backoff_vx
        self.near_backoff_kx = near_backoff_kx
        
        # State
        self._prev_vx = 0.0
        self._h_lpf = 0.0
        self._h_velocity = 0.0
    
    def reset(self):
        """Reset controller state."""
        self._prev_vx = 0.0
        self._h_lpf = 0.0
        self._h_velocity = 0.0
    
    def _compute_progressive_vx_max(self, h_f: float) -> float:
        """Compute effective vx_max with progressive tapering."""
        if not self.progressive_enable:
            return self.vx_max
        
        if h_f <= self.progressive_hf_start:
            return self.vx_max
        elif h_f >= self.progressive_hf_full:
            return self.progressive_vx_min
        else:
            ratio = (h_f - self.progressive_hf_start) / (self.progressive_hf_full - self.progressive_hf_start)
            return self.vx_max - (self.vx_max - self.progressive_vx_min) * ratio
    
    def compute(
        self,
        h_f: float,
        zone: ZoneType,
        centered_ok: bool,
        effective_stand_off: float,
        dt: float
    ) -> float:
        """
        Compute forward velocity command.
        
        Args:
            h_f: Filtered bbox height (pixels)
            zone: Current zone ("FAR", "HOV", or "NEAR")
            centered_ok: True if yaw is centered enough to advance
            effective_stand_off: Current stand-off target (may include boost)
            dt: Time step (seconds)
        
        Returns:
            Forward velocity command (m/s), positive = forward
        """
        eR = effective_stand_off - h_f  # Range error
        vx_max_prog = self._compute_progressive_vx_max(h_f)
        
        vx_des = 0.0
        
        # Zone-aware control
        if zone == "HOV":
            # HOVER zone: explicitly set vx = 0
            vx_des = 0.0
        elif zone == "NEAR":
            # NEAR zone: back off proportionally if enabled
            if self.near_backoff_enable:
                # Proportional back-off based on overshoot
                overshoot = h_f - effective_stand_off
                if overshoot > 0:
                    vx_des = -min(self.near_backoff_vx, self.near_backoff_kx * overshoot)
                else:
                    vx_des = 0.0
            elif self.allow_reverse and eR < -self.h_deadband_px:
                # Legacy behavior (only if explicitly enabled)
                vx_des = max(-vx_max_prog, min(0.0, self.kx * eR))
            else:
                vx_des = 0.0
        else:
            # FAR zone: normal proportional control
            if centered_ok:
                if h_f >= self.max_close_px:
                    # Too close - no positive vx
                    if self.allow_reverse and eR < -self.h_deadband_px:
                        vx_des = max(-vx_max_prog, min(0.0, self.kx * eR))
                    else:
                        vx_des = 0.0
                elif eR > self.h_deadband_px:
                    # Need to move forward
                    vx_des = min(vx_max_prog, max(0.0, self.kx * eR))
                elif eR < -self.h_deadband_px and self.allow_reverse:
                    # Need to back off
                    vx_des = max(-vx_max_prog, min(0.0, self.kx * eR))
                else:
                    vx_des = 0.0
            else:
                vx_des = 0.0
        
        # Proximity brake
        if self.prox_brake_enable and h_f > self.prox_brake_hf_thresh:
            vx_des = min(vx_des, self.prox_brake_vx_max)
            if self._prev_vx > vx_des:
                max_decel = self.prox_brake_decel_rate * dt
                vx_des = max(vx_des, self._prev_vx - max_decel)
        
        # Rate limiting
        if dt > 0:
            max_delta = self.rate_limit_vx * dt
            delta = vx_des - self._prev_vx
            if abs(delta) > max_delta:
                vx_des = self._prev_vx + max_delta * (1 if delta > 0 else -1)
        
        self._prev_vx = vx_des
        return vx_des
    
    def update_params(
        self,
        stand_off_px: float = None,
        vx_max: float = None,
        progressive_hf_start: float = None,
        progressive_hf_full: float = None,
        progressive_vx_min: float = None
    ):
        """Update controller parameters dynamically."""
        if stand_off_px is not None:
            self.stand_off_px = stand_off_px
        if vx_max is not None:
            self.vx_max = vx_max
        if progressive_hf_start is not None:
            self.progressive_hf_start = progressive_hf_start
        if progressive_hf_full is not None:
            self.progressive_hf_full = progressive_hf_full
        if progressive_vx_min is not None:
            self.progressive_vx_min = progressive_vx_min
