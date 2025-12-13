"""Altitude controller for altitude hold and guard."""


class AltitudeController:
    """
    Altitude controller with:
    - Altitude hold: maintain target altitude
    - Altitude guard: prevent exceeding max altitude
    """
    
    def __init__(
        self,
        alt_hold_m: float = 3.0,
        k_z_up: float = 0.8,
        k_z_down: float = 0.8,
        vz_up_max: float = 0.7,
        vz_down_max: float = 0.7,
        alt_guard_enable: bool = True,
        alt_max_m: float = 2.5,
        alt_deadband_m: float = 0.05
    ):
        """
        Initialize altitude controller.
        
        Args:
            alt_hold_m: Target altitude to hold (m)
            k_z_up: Proportional gain for climbing (m/s per m)
            k_z_down: Proportional gain for descending (m/s per m)
            vz_up_max: Maximum climb rate (m/s)
            vz_down_max: Maximum descent rate (m/s)
            alt_guard_enable: Enable altitude guard
            alt_max_m: Maximum allowed altitude (m)
            alt_deadband_m: Deadband around target (m)
        """
        self.alt_hold_m = alt_hold_m
        self.k_z_up = k_z_up
        self.k_z_down = k_z_down
        self.vz_up_max = vz_up_max
        self.vz_down_max = vz_down_max
        self.alt_guard_enable = alt_guard_enable
        self.alt_max_m = alt_max_m
        self.alt_deadband_m = alt_deadband_m
        
        # Enable flags
        self.alt_hold_enable = True
    
    def compute(self, current_alt: float) -> float:
        """
        Compute vertical velocity command.
        
        Args:
            current_alt: Current altitude (m, AGL)
        
        Returns:
            Vertical velocity command (m/s), positive = up
        """
        vz = 0.0
        
        # Altitude guard (priority)
        if self.alt_guard_enable and current_alt > self.alt_max_m + self.alt_deadband_m:
            # Force descent
            error = self.alt_max_m - current_alt  # Negative error
            vz = max(-self.vz_down_max, self.k_z_down * error)
            return vz
        
        # Altitude hold
        if self.alt_hold_enable:
            error = self.alt_hold_m - current_alt
            
            if abs(error) <= self.alt_deadband_m:
                vz = 0.0
            elif error > 0:
                # Need to climb
                vz = min(self.vz_up_max, self.k_z_up * error)
            else:
                # Need to descend
                vz = max(-self.vz_down_max, self.k_z_down * error)
        
        return vz
    
    def update_target(self, alt_hold_m: float):
        """Update target altitude."""
        self.alt_hold_m = alt_hold_m
    
    def update_params(
        self,
        alt_hold_m: float = None,
        k_z_up: float = None,
        k_z_down: float = None,
        vz_up_max: float = None,
        vz_down_max: float = None,
        alt_guard_enable: bool = None,
        alt_max_m: float = None
    ):
        """Update controller parameters dynamically."""
        if alt_hold_m is not None:
            self.alt_hold_m = alt_hold_m
        if k_z_up is not None:
            self.k_z_up = k_z_up
        if k_z_down is not None:
            self.k_z_down = k_z_down
        if vz_up_max is not None:
            self.vz_up_max = vz_up_max
        if vz_down_max is not None:
            self.vz_down_max = vz_down_max
        if alt_guard_enable is not None:
            self.alt_guard_enable = alt_guard_enable
        if alt_max_m is not None:
            self.alt_max_m = alt_max_m
