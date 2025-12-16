#!/usr/bin/env python3
"""
geo_guard_node.py - Polygon geofence enforcer with committee-proof debug output.

Publishes:
  /gp2/guard/status   (String, TRANSIENT_LOCAL) - NORMAL / GEOGUARD_HOLD / GEOGUARD_VIOLATION
  /gp2/guard/reason   (String) - human-readable reason
  /gp2/guard/debug    (String) - detailed single-line debug string
  /gp2/guard/distance_to_fence (Float32) - min distance to polygon edges
  /gp2/guard/inside   (Bool) - point-in-polygon result

Override behavior:
  NORMAL: passthrough (guard does nothing)
  HOLD: vx=0, preserves vy/vz/yaw
  VIOLATION: vx=vy=vz=0, preserves yaw
"""
import math
import time
from typing import List, Tuple, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import String, Empty, Float32, Bool
from rcl_interfaces.msg import ParameterDescriptor, ParameterType


def point_in_polygon(x: float, y: float, verts: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm for point-in-polygon test."""
    inside = False
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        # check if edge crosses horizontal ray from (x,y) going right
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


class GeoGuardNode(Node):
    def __init__(self):
        super().__init__('geo_guard_node')

        # --- Params ---
        vert_desc = ParameterDescriptor(type=ParameterType.PARAMETER_DOUBLE_ARRAY)
        self.declare_parameter('vertices', [0.0, 0.0, 1.0, 0.0, 0.0, 1.0], vert_desc)
        self.declare_parameter('soft_margin_m', 0.8)
        self.declare_parameter('hard_margin_m', 0.0)  # 0.0 = disabled for VIOLATION threshold
        self.declare_parameter('debounce_samples', 3)
        self.declare_parameter('min_hold_ms', 200)
        self.declare_parameter('guard_enabled', True)  # Can be toggled at runtime

        verts_param = self.get_parameter('vertices').get_parameter_value().double_array_value
        # flattened list → pairs
        verts = list(zip(verts_param[0::2], verts_param[1::2])) if len(verts_param) >= 6 else []
        self.verts: List[Tuple[float, float]] = verts
        self.soft_margin = float(self.get_parameter('soft_margin_m').value)
        self.hard_margin = float(self.get_parameter('hard_margin_m').value)
        self.debounce_samples = int(self.get_parameter('debounce_samples').value)
        self.min_hold_ms = int(self.get_parameter('min_hold_ms').value)

        # validate
        if len(self.verts) < 3:
            self.get_logger().error('GEOGUARD: invalid fence (need ≥3 vertices)')
            raise SystemExit(1)
        if self.hard_margin > 0.0 and self.hard_margin > self.soft_margin:
            self.get_logger().error('GEOGUARD: hard_margin_m must be ≤ soft_margin_m')
            raise SystemExit(1)

        # --- QoS ---
        q_rel = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                           history=HistoryPolicy.KEEP_LAST, depth=20)
        q_status = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                              durability=DurabilityPolicy.TRANSIENT_LOCAL,
                              history=HistoryPolicy.KEEP_LAST, depth=10)

        # --- I/O ---
        self.pose_sub = self.create_subscription(PoseStamped, '/gp2/vehicle/pose_local', self._on_pose, q_rel)
        self.cmd_tap_sub = self.create_subscription(Twist, '/sahtd/follow/cmd_body', self._on_cmd, q_rel)
        
        # Status publishers
        self.status_pub = self.create_publisher(String, '/gp2/guard/status', q_status)
        self.reason_pub = self.create_publisher(String, '/gp2/guard/reason', q_rel)
        
        # NEW: Debug publishers for committee verification
        self.debug_pub = self.create_publisher(String, '/gp2/guard/debug', 10)
        self.dist_pub = self.create_publisher(Float32, '/gp2/guard/distance_to_fence', 10)
        self.inside_pub = self.create_publisher(Bool, '/gp2/guard/inside', 10)
        
        # Override publisher (HOLD/VIOLATION → zero cmd_body)
        self.cmd_pub = self.create_publisher(Twist, '/sahtd/follow/cmd_body', q_rel)

        # Reset subscription
        self.reset_sub = self.create_subscription(Empty, '/gp2/guard/reset', self._on_guard_reset, 10)

        # --- State ---
        self._last_cmd: Optional[Twist] = None
        self._state = 'NORMAL'
        self._last_state_change = self.get_clock().now()
        self._deb_hist: List[str] = []
        
        # Cache for debug
        self._last_pose_x = 0.0
        self._last_pose_y = 0.0
        self._last_inside = True
        self._last_dist = 0.0
        self._last_nearest_edge = 0

        # --- Startup banner with full polygon info ---
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        bbox = f"x:[{min(xs):.2f},{max(xs):.2f}] y:[{min(ys):.2f},{max(ys):.2f}]"
        self.get_logger().info('=' * 60)
        self.get_logger().info('GEOGUARD CONFIGURATION')
        self.get_logger().info(f'  frame: map (ENU)')
        self.get_logger().info(f'  vertices ({len(self.verts)}): {self.verts}')
        self.get_logger().info(f'  bbox: {bbox}')
        self.get_logger().info(f'  soft_margin: {self.soft_margin:.2f}m')
        self.get_logger().info(f'  hard_margin: {self.hard_margin:.2f}m')
        self.get_logger().info(f'  debounce: {self.debounce_samples} samples')
        self.get_logger().info(f'  min_hold: {self.min_hold_ms}ms')
        self.get_logger().info('=' * 60)

        # publish initial status
        self._publish_status('NORMAL', 'init')

    def _on_cmd(self, msg: Twist):
        self._last_cmd = msg

    def _publish_status(self, st: str, reason: str):
        s = String()
        s.data = st
        r = String()
        r.data = reason
        self.status_pub.publish(s)
        self.reason_pub.publish(r)

    def _publish_debug(self):
        """Publish detailed debug info for committee verification."""
        # Check if guard is enabled (read dynamically for toggling)
        guard_enabled = bool(self.get_parameter('guard_enabled').value)
        
        # Debug string
        dbg = String()
        dbg.data = (
            f"state={self._state} "
            f"enabled={str(guard_enabled).lower()} "
            f"inside={str(self._last_inside).lower()} "
            f"dist_m={self._last_dist:.2f} "
            f"soft_m={self.soft_margin:.2f} "
            f"hard_m={self.hard_margin:.2f} "
            f"pose=(x={self._last_pose_x:.2f},y={self._last_pose_y:.2f}) "
            f"nearest_edge={self._last_nearest_edge}"
        )
        self.debug_pub.publish(dbg)
        
        # Distance
        dist_msg = Float32()
        dist_msg.data = float(self._last_dist)
        self.dist_pub.publish(dist_msg)
        
        # Inside bool
        inside_msg = Bool()
        inside_msg.data = self._last_inside
        self.inside_pub.publish(inside_msg)

    def _transition(self, new_state: str, reason: str):
        if new_state != self._state:
            self.get_logger().info(f'GEOGUARD: {self._state} → {new_state} ({reason})')
            self._state = new_state
            self._last_state_change = self.get_clock().now()
            self._publish_status(new_state, reason)

    def _on_guard_reset(self, msg: Empty):
        """Reset geo-guard state to NORMAL."""
        self._state = 'NORMAL'
        self._deb_hist = []
        self._last_cmd = None
        self._publish_status('NORMAL', 'manual_reset')
        self.get_logger().info('[reset] geo_guard_node state reset to NORMAL')

    def _stable_vote(self, label: str) -> Optional[str]:
        """Debounce state changes with hysteresis."""
        self._deb_hist.append(label)
        if len(self._deb_hist) > self.debounce_samples:
            self._deb_hist.pop(0)
        if len(self._deb_hist) < self.debounce_samples:
            return None
        if all(x == self._deb_hist[0] for x in self._deb_hist):
            return self._deb_hist[0]
        return None

    def _on_pose(self, ps: PoseStamped):
        x = float(ps.pose.position.x)
        y = float(ps.pose.position.y)
        
        # Compute geometry
        inside = point_in_polygon(x, y, self.verts)
        d_edge, nearest_edge = min_edge_distance_with_index(x, y, self.verts)
        
        # Cache for debug
        self._last_pose_x = x
        self._last_pose_y = y
        self._last_inside = inside
        self._last_dist = d_edge
        self._last_nearest_edge = nearest_edge

        # --- STATE LOGIC (corrected) ---
        # Priority: VIOLATION > HOLD > NORMAL
        label = 'NORMAL'
        reason = f'dist={d_edge:.2f}m'

        if not inside:
            # Outside polygon = VIOLATION (most severe)
            label = 'GEOGUARD_VIOLATION'
            reason = f'VIOLATION: outside_polygon (dist={d_edge:.2f}m)'
        elif d_edge <= self.soft_margin + 1e-6:
            # Inside but within soft margin = HOLD
            label = 'GEOGUARD_HOLD'
            reason = f'HOLD: dist<soft_margin ({d_edge:.2f}m < {self.soft_margin:.2f}m)'
            # Check hard margin for escalation (if enabled)
            if self.hard_margin > 0.0 and d_edge <= self.hard_margin + 1e-6:
                label = 'GEOGUARD_VIOLATION'
                reason = f'VIOLATION: dist<hard_margin ({d_edge:.2f}m < {self.hard_margin:.2f}m)'
        # else: NORMAL (inside and dist > soft_margin)

        # Debounce
        voted = self._stable_vote(label)
        if voted is None:
            # Still collecting samples, but still publish debug
            self._publish_debug()
            return

        # Minimum hold time to avoid instant release
        now = self.get_clock().now()
        hold_guard = (self._state in ('GEOGUARD_HOLD', 'GEOGUARD_VIOLATION')
                      and (now - self._last_state_change).nanoseconds < self.min_hold_ms * 1e6)

        if voted == 'NORMAL' and hold_guard:
            # Still within min_hold window; keep current state
            voted = self._state

        # State transition
        self._transition(voted, reason)
        
        # Always publish debug
        self._publish_debug()

        # --- Override behavior ---
        if self._state == 'NORMAL':
            return  # Follower is authoritative; do nothing

        # Check if guard is enabled (read dynamically for toggling)
        guard_enabled = bool(self.get_parameter('guard_enabled').value)
        if not guard_enabled:
            return  # Guard disabled, skip override

        # HOLD or VIOLATION → publish override
        out = Twist()
        if self._state == 'GEOGUARD_VIOLATION':
            # Full stop: vx=vy=vz=0, preserve yaw
            out.linear.x = 0.0
            out.linear.y = 0.0
            out.linear.z = 0.0
            out.angular.z = self._last_cmd.angular.z if self._last_cmd else 0.0
        else:  # GEOGUARD_HOLD
            # Stop forward motion, preserve other controls
            out.linear.x = 0.0
            out.linear.y = self._last_cmd.linear.y if self._last_cmd else 0.0
            out.linear.z = self._last_cmd.linear.z if self._last_cmd else 0.0
            out.angular.z = self._last_cmd.angular.z if self._last_cmd else 0.0
        
        self.cmd_pub.publish(out)


def main():
    rclpy.init()
    node = GeoGuardNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

