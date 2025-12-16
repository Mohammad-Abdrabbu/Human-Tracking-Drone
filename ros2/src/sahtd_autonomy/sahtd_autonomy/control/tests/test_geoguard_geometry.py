#!/usr/bin/env python3
"""
test_geoguard_geometry.py - Unit tests for geo_guard geometry functions.

Tests point_in_polygon and min_edge_distance_with_index with known values.
Run: python3 test_geoguard_geometry.py
"""
import math
import sys
from typing import List, Tuple


def point_in_polygon(x: float, y: float, verts: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm for point-in-polygon test."""
    inside = False
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_int = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x_int > x:
                inside = not inside
    return inside


def dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Distance from point P to line segment AB."""
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return math.hypot(px - x1, py - y1)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - x2, py - y2)
    b = c1 / (c2 + 1e-12)
    bx, by = x1 + b * vx, y1 + b * vy
    return math.hypot(px - bx, py - by)


def min_edge_distance_with_index(px: float, py: float, verts: List[Tuple[float, float]]) -> Tuple[float, int]:
    """Returns (min_distance, nearest_edge_index) for point to polygon."""
    dmin = float('inf')
    nearest_idx = 0
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        d = dist_point_to_segment(px, py, x1, y1, x2, y2)
        if d < dmin:
            dmin = d
            nearest_idx = i
    return dmin, nearest_idx


def test_point_in_polygon():
    """Test point_in_polygon with a simple square."""
    # Square: (0,0) -> (10,0) -> (10,10) -> (0,10)
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    
    # Test cases: (x, y, expected_inside)
    tests = [
        (5, 5, True, "center of square"),
        (1, 1, True, "near corner inside"),
        (9, 9, True, "near opposite corner inside"),
        (-1, 5, False, "outside left"),
        (11, 5, False, "outside right"),
        (5, -1, False, "outside bottom"),
        (5, 11, False, "outside top"),
        (-1, -1, False, "outside corner"),
    ]
    
    print("=== point_in_polygon tests ===")
    passed = 0
    for x, y, expected, desc in tests:
        result = point_in_polygon(x, y, square)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        print(f"  {status} ({x},{y}): inside={result}, expected={expected}  [{desc}]")
    
    print(f"\n  Result: {passed}/{len(tests)} passed\n")
    return passed == len(tests)


def test_min_edge_distance():
    """Test min_edge_distance_with_index with a simple square."""
    # Square: (0,0) -> (10,0) -> (10,10) -> (0,10)
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    
    # Test cases: (x, y, expected_dist, expected_edge, description)
    tests = [
        (5, 5, 5.0, None, "center - equidistant to all edges"),
        (5, 1, 1.0, 0, "near bottom edge"),
        (9, 5, 1.0, 1, "near right edge"),
        (5, 9, 1.0, 2, "near top edge"),
        (1, 5, 1.0, 3, "near left edge"),
        (0, 0, 0.0, None, "on corner"),
        (12, 5, 2.0, 1, "outside right"),
    ]
    
    print("=== min_edge_distance tests ===")
    passed = 0
    for x, y, expected_dist, expected_edge, desc in tests:
        dist, edge = min_edge_distance_with_index(x, y, square)
        dist_ok = abs(dist - expected_dist) < 0.01
        edge_ok = expected_edge is None or edge == expected_edge
        status = "✓" if dist_ok and edge_ok else "✗"
        if dist_ok and edge_ok:
            passed += 1
        print(f"  {status} ({x},{y}): dist={dist:.2f}, edge={edge}  [expected dist={expected_dist}, {desc}]")
    
    print(f"\n  Result: {passed}/{len(tests)} passed\n")
    return passed == len(tests)


def main():
    print("\n" + "=" * 50)
    print("  GeoGuard Geometry Unit Tests")
    print("=" * 50 + "\n")
    
    pip_ok = test_point_in_polygon()
    dist_ok = test_min_edge_distance()
    
    print("=" * 50)
    if pip_ok and dist_ok:
        print("  ALL TESTS PASSED ✓")
        print("=" * 50 + "\n")
        return 0
    else:
        print("  SOME TESTS FAILED ✗")
        print("=" * 50 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
