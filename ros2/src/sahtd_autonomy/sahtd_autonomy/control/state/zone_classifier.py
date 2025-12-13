"""Zone classification for three-zone control (FAR/HOV/NEAR)."""
import math
from typing import Literal

ZoneType = Literal["FAR", "HOV", "NEAR"]


class ZoneClassifier:
    """
    Classifies current state into FAR, HOVER, or NEAR zones based on:
    - h_f: Filtered bbox height (pixels)
    - ex_rad: Absolute yaw error (radians)
    - eR: Range error (pixels) = stand_off - h_f
    """
    
    def __init__(
        self,
        hover_lower_px: float = 150.0,
        hover_upper_px: float = 185.0,
        near_thresh_px: float = 220.0,
        hover_yaw_deg: float = 4.0,
        hover_eR_thresh: float = 20.0
    ):
        """
        Initialize zone boundaries.
        
        Args:
            hover_lower_px: h_f below this = FAR
            hover_upper_px: h_f above this (but < near) = transition
            near_thresh_px: h_f above this = NEAR
            hover_yaw_deg: Max yaw error for HOVER zone
            hover_eR_thresh: Max |eR| for HOVER zone
        """
        self.hover_lower = hover_lower_px
        self.hover_upper = hover_upper_px
        self.near_thresh = near_thresh_px
        self.hover_yaw_rad = math.radians(hover_yaw_deg)
        self.hover_eR_thresh = hover_eR_thresh
    
    def classify(self, h_f: float, ex_rad: float, eR: float) -> ZoneType:
        """
        Classify current state into zone.
        
        Precedence: NEAR > HOV > FAR
        
        Args:
            h_f: Filtered bbox height (pixels)
            ex_rad: Absolute yaw error (radians)
            eR: Range error (pixels) = stand_off - h_f
        
        Returns:
            "FAR", "HOV", or "NEAR"
        """
        in_hover_yaw = ex_rad < self.hover_yaw_rad
        in_hover_eR = abs(eR) < self.hover_eR_thresh
        
        # Zone classification with precedence: NEAR > HOV > FAR
        if h_f > self.near_thresh:
            return "NEAR"
        elif (self.hover_lower <= h_f <= self.hover_upper 
              and in_hover_yaw and in_hover_eR):
            return "HOV"
        else:
            return "FAR"
    
    def update_params(
        self,
        hover_lower_px: float = None,
        hover_upper_px: float = None,
        near_thresh_px: float = None,
        hover_yaw_deg: float = None,
        hover_eR_thresh: float = None
    ):
        """Update zone parameters dynamically (e.g., from ROS params)."""
        if hover_lower_px is not None:
            self.hover_lower = hover_lower_px
        if hover_upper_px is not None:
            self.hover_upper = hover_upper_px
        if near_thresh_px is not None:
            self.near_thresh = near_thresh_px
        if hover_yaw_deg is not None:
            self.hover_yaw_rad = math.radians(hover_yaw_deg)
        if hover_eR_thresh is not None:
            self.hover_eR_thresh = hover_eR_thresh
