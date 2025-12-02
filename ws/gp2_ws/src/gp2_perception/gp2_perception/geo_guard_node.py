#!/usr/bin/env python3
import math, time
from typing import List, Tuple, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped, Twist
from std_msgs.msg import String
from rcl_interfaces.msg import ParameterDescriptor, ParameterType

def point_in_polygon(x: float, y: float, verts: List[Tuple[float,float]]) -> bool:
    # Ray casting
    inside = False
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        # check edge intersects horizontal ray
        cond = ((y1 > y) != (y2 > y))
        if cond:
            x_int = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x_int > x:
                inside = not inside
    return inside

def dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    # distance from P to segment AB
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

def min_edge_distance(px: float, py: float, verts: List[Tuple[float,float]]) -> float:
    dmin = float('inf')
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        dmin = min(dmin, dist_point_to_segment(px, py, x1, y1, x2, y2))
    return dmin

class GeoGuardNode(Node):
    def __init__(self):
        super().__init__('geo_guard_node')

        # --- Params ---
        vert_desc = ParameterDescriptor(type=ParameterType.PARAMETER_DOUBLE_ARRAY)
        self.declare_parameter('vertices', [0.0,0.0, 1.0,0.0, 0.0,1.0], vert_desc)
        self.declare_parameter('soft_margin_m', 0.8)
        self.declare_parameter('hard_margin_m', 0.0)  # 0.0 = disabled
        self.declare_parameter('debounce_samples', 3)
        self.declare_parameter('min_hold_ms', 200)

        verts_param = self.get_parameter('vertices').get_parameter_value().double_array_value
        # flattened list → pairs
        verts = list(zip(verts_param[0::2], verts_param[1::2])) if len(verts_param) >= 6 else []
        self.verts: List[Tuple[float,float]] = verts
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
        self.cmd_tap_sub = self.create_subscription(Twist, '/gp2/follow/cmd_body', self._on_cmd, q_rel)
        self.status_pub = self.create_publisher(String, '/gp2/guard/status', q_status)
        self.reason_pub = self.create_publisher(String, '/gp2/guard/reason', q_rel)
        self.cmd_pub = self.create_publisher(Twist, '/gp2/follow/cmd_body', q_rel)  # override only on HOLD/VIOLATION

        # --- State ---
        self._last_cmd: Optional[Twist] = None
        self._state = 'NORMAL'
        self._last_state_change = self.get_clock().now()
        self._deb_hist: List[str] = []

        # banner
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        bbox = f"x:[{min(xs):.2f},{max(xs):.2f}] y:[{min(ys):.2f},{max(ys):.2f}]"
        self.get_logger().info(
            f'GEOGUARD cfg → frame=map(ENU), vertices={len(self.verts)}, '
            f'soft={self.soft_margin:.2f}m, hard={self.hard_margin:.2f}m, '
            f'debounce={self.debounce_samples}, min_hold={self.min_hold_ms}ms, {bbox}'
        )

        # publish initial status
        self._publish_status('NORMAL', 'init')

    def _on_cmd(self, msg: Twist):
        self._last_cmd = msg

    def _publish_status(self, st: str, reason: str):
        s = String(); s.data = st
        r = String(); r.data = reason
        self.status_pub.publish(s)
        self.reason_pub.publish(r)

    def _transition(self, new_state: str, reason: str):
        if new_state != self._state:
            self.get_logger().info(f'GEOGUARD: {self._state}→{new_state} ({reason})')
            self._state = new_state
            self._last_state_change = self.get_clock().now()
            self._publish_status(new_state, reason)

    def _stable_vote(self, label: str) -> Optional[str]:
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
        inside = point_in_polygon(x, y, self.verts)
        d_edge = min_edge_distance(x, y, self.verts)

        label = 'NORMAL'
        reason = f'edge={d_edge:.2f}m'

        if inside and d_edge <= self.soft_margin + 1e-6:
            label = 'GEOGUARD_HOLD'
            reason = f'edge={d_edge:.2f}m'
            if self.hard_margin > 0.0 and d_edge <= self.hard_margin + 1e-6:
                label = 'GEOGUARD_VIOLATION'
                reason = f'inside_hard={d_edge:.2f}m'

        voted = self._stable_vote(label)
        if voted is None:
            return  # keep collecting samples

        # optional minimum hold time to avoid instant release
        now = self.get_clock().now()
        hold_guard = (self._state in ('GEOGUARD_HOLD', 'GEOGUARD_VIOLATION')
                      and (now - self._last_state_change).nanoseconds < self.min_hold_ms * 1e6)

        if voted == 'NORMAL' and hold_guard:
            # still within min_hold window; keep holding
            voted = self._state

        # state machine
        self._transition(voted, reason)

        # override behavior
        if self._state == 'NORMAL':
            return  # follower is authoritative; do nothing

        # HOLD or VIOLATION → publish zero-forward override; preserve yawrate
        out = Twist()
        out.linear.x = 0.0
        out.linear.y = 0.0 if self._state == 'GEOGUARD_VIOLATION' else (self._last_cmd.linear.y if self._last_cmd else 0.0)
        out.linear.z = 0.0 if self._state == 'GEOGUARD_VIOLATION' else (self._last_cmd.linear.z if self._last_cmd else 0.0)
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
