"""Geometry utilities for control nodes."""


def fov_ex(cx_px: float, img_w: int, hfov_rad: float, invert: bool = False) -> float:
    """
    Calculate normalized horizontal error from pixel position.
    
    Args:
        cx_px: Center x position of bbox in pixels
        img_w: Image width in pixels
        hfov_rad: Horizontal field of view in radians
        invert: If True, invert the error sign
    
    Returns:
        Normalized error in range [-1, 1], where 0 is center
    """
    ex = (cx_px - 0.5 * img_w) / img_w
    return -ex if invert else ex
