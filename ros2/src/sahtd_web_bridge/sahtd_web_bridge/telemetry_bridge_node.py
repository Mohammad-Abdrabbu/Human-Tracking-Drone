#!/usr/bin/env python3
"""
Telemetry Bridge Node

Subscribes to ROS2 topics and writes merged telemetry snapshots to a JSONL file
for consumption by the web dashboard.
"""

import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String, Bool, Float32, Int32


def quaternion_to_yaw_deg(q) -> float:
    """Convert quaternion to yaw angle in degrees."""
    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    yaw_rad = math.atan2(siny_cosp, cosy_cosp)
    return math.degrees(yaw_rad)


class TelemetryBridgeNode(Node):
    """
    Subscribes to various ROS2 topics and writes merged telemetry
    to a JSONL file at a configurable rate.
    """

    def __init__(self):
        super().__init__('telemetry_bridge_node')

        # Parameters
        self.declare_parameter('write_hz', 2.0)
        self.declare_parameter('telemetry_log_path', 
                               os.path.expanduser('~/sahtd/data/logs/telemetry.jsonl'))

        self.write_hz = self.get_parameter('write_hz').value
        self.log_path = Path(self.get_parameter('telemetry_log_path').value).expanduser()

        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # State storage
        self._seq = 0
        self._pose: Optional[PoseStamped] = None
        self._pose_time: Optional[float] = None
        self._guard_status: Optional[str] = None
        self._guard_time: Optional[float] = None
        self._inside: Optional[bool] = None
        self._distance_to_fence: Optional[float] = None
        self._follow_state: Optional[str] = None
        self._follow_time: Optional[float] = None
        self._selected_id: Optional[int] = None
        self._seen_ids: Optional[str] = None

        # QoS for sensor data (best effort, volatile)
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Required: Pose subscription
        self.create_subscription(
            PoseStamped,
            '/gp2/vehicle/pose_local',
            self._pose_callback,
            sensor_qos
        )

        # Optional subscriptions
        self._setup_optional_subscriptions(sensor_qos)

        # Timer for writing telemetry
        period = 1.0 / self.write_hz
        self.create_timer(period, self._write_telemetry)

        self.get_logger().info(
            f'TelemetryBridgeNode started: writing to {self.log_path} at {self.write_hz} Hz'
        )

    def _setup_optional_subscriptions(self, qos: QoSProfile):
        """Set up optional subscriptions, handling missing topics gracefully."""
        
        # Guard status (String)
        self.create_subscription(
            String,
            '/gp2/guard/status',
            self._guard_status_callback,
            qos
        )

        # Guard inside (Bool)
        self.create_subscription(
            Bool,
            '/gp2/guard/inside',
            self._inside_callback,
            qos
        )

        # Distance to fence - use Float32
        # If your system uses Float64, change Float32 to Float64 here
        self.create_subscription(
            Float32,
            '/gp2/guard/distance_to_fence',
            self._distance_callback,
            qos
        )

        # Follow state
        self.create_subscription(
            String,
            '/sahtd/follow/state',
            self._follow_state_callback,
            qos
        )

        # Target selection
        self.create_subscription(
            Int32,
            '/perception/target_select',
            self._target_select_callback,
            qos
        )

        # Seen IDs
        self.create_subscription(
            String,
            '/perception/seen_ids',
            self._seen_ids_callback,
            qos
        )

    def _now_sec(self) -> float:
        """Get current ROS time in seconds."""
        return self.get_clock().now().nanoseconds / 1e9

    def _pose_callback(self, msg: PoseStamped):
        self._pose = msg
        self._pose_time = self._now_sec()

    def _guard_status_callback(self, msg: String):
        self._guard_status = msg.data
        self._guard_time = self._now_sec()

    def _inside_callback(self, msg: Bool):
        self._inside = msg.data

    def _distance_callback(self, msg: Float32):
        self._distance_to_fence = float(msg.data)

    def _follow_state_callback(self, msg: String):
        self._follow_state = msg.data
        self._follow_time = self._now_sec()

    def _target_select_callback(self, msg: Int32):
        self._selected_id = msg.data

    def _seen_ids_callback(self, msg: String):
        self._seen_ids = msg.data

    def _build_pose_dict(self) -> Optional[dict]:
        """Build pose dictionary from stored PoseStamped."""
        if self._pose is None:
            return None
        
        p = self._pose.pose.position
        q = self._pose.pose.orientation
        yaw_deg = quaternion_to_yaw_deg(q)
        
        return {
            'x': round(p.x, 3),
            'y': round(p.y, 3),
            'z': round(p.z, 3),
            'yaw_deg': round(yaw_deg, 1),
        }

    def _compute_stale(self) -> dict:
        """Compute staleness for each data source."""
        now = self._now_sec()
        stale = {}
        
        if self._pose_time is not None:
            stale['pose_age_s'] = round(now - self._pose_time, 2)
        else:
            stale['pose_age_s'] = None
            
        if self._guard_time is not None:
            stale['guard_age_s'] = round(now - self._guard_time, 2)
        else:
            stale['guard_age_s'] = None
            
        if self._follow_time is not None:
            stale['follow_age_s'] = round(now - self._follow_time, 2)
        else:
            stale['follow_age_s'] = None
            
        return stale

    def _write_telemetry(self):
        """Write a telemetry snapshot to the JSONL file."""
        self._seq += 1
        
        snapshot = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'seq': self._seq,
            'follow_state': self._follow_state,
            'guard_status': self._guard_status,
            'inside': self._inside,
            'distance_to_fence_m': round(self._distance_to_fence, 2) if self._distance_to_fence is not None else None,
            'pose': self._build_pose_dict(),
            'selected_id': self._selected_id,
            'seen_ids': self._seen_ids,
            'stale': self._compute_stale(),
        }

        try:
            line = json.dumps(snapshot, separators=(',', ':'))
            if len(line) > 4096:
                self.get_logger().warn('Telemetry line exceeds 4KB, truncating seen_ids')
                snapshot['seen_ids'] = None
                line = json.dumps(snapshot, separators=(',', ':'))
            
            with open(self.log_path, 'a') as f:
                f.write(line + '\n')
                
        except Exception as e:
            self.get_logger().error(f'Failed to write telemetry: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = TelemetryBridgeNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
