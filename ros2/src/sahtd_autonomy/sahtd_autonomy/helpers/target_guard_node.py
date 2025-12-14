#!/usr/bin/env python3
"""
Lane B2: Target Guard Node (Human-aware Geo-guard)

Monitors the target human's position relative to the geo-fence.
Publishes target status (inside/near_edge/outside) without modifying drone behavior.

This is ADDITIVE to geo_guard_node - it only observes and reports.
Future lanes may use this info to modify follower behavior.
"""

import math
from typing import List, Tuple, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from rcl_interfaces.msg import ParameterDescriptor, ParameterType


def point_in_polygon(x: float, y: float, verts: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm to check if point is inside polygon."""
    inside = False
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        if ((y1 > y) != (y2 > y)):
            x_int = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
            if x_int > x:
                inside = not inside
    return inside


def min_edge_distance(px: float, py: float, verts: List[Tuple[float, float]]) -> Tuple[float, str]:
    """
    Calculate minimum distance from point to polygon edges.
    Returns (distance, edge_direction) where edge_direction is like '+X', '-Y', etc.
    """
    dmin = float('inf')
    edge_dir = ''
    n = len(verts)
    
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        
        # Distance from point to line segment
        vx, vy = x2 - x1, y2 - y1
        wx, wy = px - x1, py - y1
        c1 = vx * wx + vy * wy
        
        if c1 <= 0:
            d = math.hypot(px - x1, py - y1)
        else:
            c2 = vx * vx + vy * vy
            if c2 <= c1:
                d = math.hypot(px - x2, py - y2)
            else:
                b = c1 / (c2 + 1e-12)
                bx, by = x1 + b * vx, y1 + b * vy
                d = math.hypot(px - bx, py - by)
        
        if d < dmin:
            dmin = d
            # Determine edge direction
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            if abs(vx) > abs(vy):  # Horizontal-ish edge
                edge_dir = '+Y' if mid_y > 0 else '-Y'
            else:  # Vertical-ish edge
                edge_dir = '+X' if mid_x > 0 else '-X'
    
    return dmin, edge_dir


class TargetGuardNode(Node):
    """
    Human-aware geo-guard that monitors target position relative to fence.
    
    Publishes:
      /sahtd/guard/target_status: TARGET_INSIDE_FENCE | TARGET_NEAR_EDGE | TARGET_OUTSIDE_FENCE
      /sahtd/guard/target_reason: Human-readable explanation
      /sahtd/alerts: One-shot alert when violation occurs
    """

    # Status constants
    STATUS_INSIDE = "TARGET_INSIDE_FENCE"
    STATUS_NEAR_EDGE = "TARGET_NEAR_EDGE"
    STATUS_OUTSIDE = "TARGET_OUTSIDE_FENCE"

    def __init__(self):
        super().__init__('target_guard_node')

        # --- Parameters (same semantics as geo_guard_node) ---
        vert_desc = ParameterDescriptor(type=ParameterType.PARAMETER_DOUBLE_ARRAY)
        self.declare_parameter('vertices', [-7.0, -7.0, 7.0, -7.0, 7.0, 7.0, -7.0, 7.0], vert_desc)
        self.declare_parameter('soft_margin_m', 0.8)
        self.declare_parameter('hard_margin_m', 0.0)  # Reserved for future use
        self.declare_parameter('publish_rate_hz', 2.0)  # Minimum publish rate

        # Parse vertices
        verts_param = self.get_parameter('vertices').get_parameter_value().double_array_value
        self.verts: List[Tuple[float, float]] = list(zip(verts_param[0::2], verts_param[1::2]))
        self.soft_margin = float(self.get_parameter('soft_margin_m').value)
        self.hard_margin = float(self.get_parameter('hard_margin_m').value)
        self.publish_rate = float(self.get_parameter('publish_rate_hz').value)

        # Validate
        if len(self.verts) < 3:
            self.get_logger().error('TARGET_GUARD: invalid fence (need ≥3 vertices)')
            raise SystemExit(1)

        # --- QoS ---
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        qos_status = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # --- Subscriptions ---
        self.pose_sub = self.create_subscription(
            PoseStamped,
            '/gp2/target_pose_gt',
            self._on_target_pose,
            qos_reliable
        )

        # --- Publishers ---
        self.status_pub = self.create_publisher(String, '/sahtd/guard/target_status', qos_status)
        self.reason_pub = self.create_publisher(String, '/sahtd/guard/target_reason', qos_reliable)
        self.alerts_pub = self.create_publisher(String, '/sahtd/alerts', qos_status)

        # --- State ---
        self._current_status = self.STATUS_INSIDE
        self._current_reason = "init"
        self._last_pose_time = None
        self._has_target = False
        self._last_x = 0.0
        self._last_y = 0.0
        self._violation_alerted = False  # Only alert once per violation

        # Timer for periodic publishing
        self._timer = self.create_timer(1.0 / self.publish_rate, self._timer_cb)

        # Banner
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        bbox = f"x:[{min(xs):.1f},{max(xs):.1f}] y:[{min(ys):.1f},{max(ys):.1f}]"
        self.get_logger().info(
            f'TARGET_GUARD cfg → vertices={len(self.verts)}, '
            f'soft_margin={self.soft_margin:.2f}m, {bbox}'
        )

    def _on_target_pose(self, msg: PoseStamped):
        """Process incoming target pose and compute fence status."""
        x = float(msg.pose.position.x)
        y = float(msg.pose.position.y)
        
        self._has_target = True
        self._last_pose_time = self.get_clock().now()

        # Check if inside polygon
        inside = point_in_polygon(x, y, self.verts)
        d_edge, edge_dir = min_edge_distance(x, y, self.verts)

        # Determine status
        if not inside:
            new_status = self.STATUS_OUTSIDE
            reason = f"outside_by={d_edge:.2f}m on {edge_dir}"
        elif d_edge <= self.soft_margin:
            new_status = self.STATUS_NEAR_EDGE
            reason = f"dist_to_edge={d_edge:.2f}m ({edge_dir})"
        else:
            new_status = self.STATUS_INSIDE
            reason = f"dist_to_edge={d_edge:.2f}m"

        # Update and publish if changed
        if new_status != self._current_status:
            self.get_logger().info(f'TARGET_GUARD: {self._current_status} → {new_status} ({reason})')
            
            # Check for violation transition (was inside/near_edge, now outside)
            if new_status == self.STATUS_OUTSIDE and self._current_status != self.STATUS_OUTSIDE:
                if not self._violation_alerted:
                    self._emit_violation_alert(x, y)
                    self._violation_alerted = True
            
            # Reset alert flag when target returns inside
            if new_status == self.STATUS_INSIDE and self._current_status == self.STATUS_OUTSIDE:
                self._violation_alerted = False
            
            self._current_status = new_status
            self._current_reason = reason
            self._publish_status()
        else:
            self._current_reason = reason  # Update reason even if status same
        
        self._last_x = x
        self._last_y = y

    def _publish_status(self):
        """Publish current status and reason."""
        status_msg = String()
        status_msg.data = self._current_status
        self.status_pub.publish(status_msg)

        reason_msg = String()
        reason_msg.data = self._current_reason
        self.reason_pub.publish(reason_msg)

    def _emit_violation_alert(self, x: float, y: float):
        """Emit a one-shot violation alert."""
        alert_msg = String()
        alert_msg.data = f"HUMAN GEOFENCE VIOLATION: Target exited fence at ({x:.2f}, {y:.2f})"
        self.alerts_pub.publish(alert_msg)
        self.get_logger().warn(f"🚨 ALERT: {alert_msg.data}")

    def _timer_cb(self):
        """Periodic status publish (even without pose updates)."""
        if self._has_target:
            self._publish_status()


def main():
    rclpy.init()
    node = TargetGuardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
