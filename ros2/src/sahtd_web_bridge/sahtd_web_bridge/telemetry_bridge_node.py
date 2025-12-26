#!/usr/bin/env python3
"""
Telemetry Bridge Node

Subscribes to ROS2 topics and writes merged telemetry snapshots to a JSONL file
for consumption by the web dashboard. Also polls Gazebo for human positions.
"""

import os
import re
import json
import math
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String, Bool, Float32, Int32


def quaternion_to_yaw_deg(q) -> float:
    """Convert quaternion to yaw angle in degrees."""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    yaw_rad = math.atan2(siny_cosp, cosy_cosp)
    return math.degrees(yaw_rad)


def quaternion_to_yaw_deg_xyzw(x, y, z, w) -> float:
    """Convert quaternion (xyzw) to yaw angle in degrees."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
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
        
        # Compute default telemetry path using SAHTD_ROOT or auto-detection
        _sahtd_root = os.environ.get('SAHTD_ROOT')
        if not _sahtd_root:
            # Auto-detect by walking up from this file
            current = Path(__file__).resolve().parent
            for _ in range(10):
                if (current / '.git').is_dir() or ((current / 'ros2').is_dir() and (current / 'web').is_dir()):
                    _sahtd_root = str(current)
                    break
                parent = current.parent
                if parent == current:
                    break
                current = parent
            if not _sahtd_root:
                _sahtd_root = os.path.expanduser('~/sahtd')
        
        default_telemetry_path = os.path.join(_sahtd_root, 'data/logs/telemetry.jsonl')
        self.declare_parameter('telemetry_log_path', default_telemetry_path)
        
        # Human detection parameters
        self.declare_parameter('gz_topic', '/world/default/pose/info')
        self.declare_parameter('human_frame_regex', 
                               r'(male_visitor|Casual|person|human|actor|walking)')
        self.declare_parameter('human_deny_regex', 
                               r'(x500|iris|camera|base_link|map|odom|world|ground_plane|sun)')
        self.declare_parameter('max_humans', 10)
        self.declare_parameter('enable_human_detection', True)

        self.write_hz = self.get_parameter('write_hz').value
        self.log_path = Path(self.get_parameter('telemetry_log_path').value).expanduser()
        self.gz_topic = self.get_parameter('gz_topic').value
        self.human_frame_regex = self.get_parameter('human_frame_regex').value
        self.human_deny_regex = self.get_parameter('human_deny_regex').value
        self.max_humans = self.get_parameter('max_humans').value
        self.enable_human_detection = self.get_parameter('enable_human_detection').value

        # Compile regex patterns
        self._human_allow_pattern = re.compile(self.human_frame_regex, re.IGNORECASE)
        self._human_deny_pattern = re.compile(self.human_deny_regex, re.IGNORECASE)

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
        
        # Human pose cache
        self._humans: Dict[str, dict] = {}  # name -> {x, y, z, yaw_deg, ts}
        self._human_warning_logged = False

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
        if self.enable_human_detection:
            self.get_logger().info(
                f'Human detection enabled: polling {self.gz_topic}'
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

    def _poll_gazebo_humans(self) -> List[dict]:
        """
        Poll Gazebo for human poses using `gz topic` command.
        Returns list of human dicts: [{id, name, x, y, yaw_deg, age_s}, ...]
        """
        if not self.enable_human_detection:
            return []
        
        try:
            result = subprocess.run(
                ['gz', 'topic', '-e', '-t', self.gz_topic, '-n', '1'],
                capture_output=True,
                text=True,
                timeout=0.3
            )
            
            if result.returncode != 0:
                return []
            
            output = result.stdout
            now = self._now_sec()
            
            # Parse pose blocks
            humans = {}
            blocks = re.split(r'pose\s*\{', output)
            
            for block in blocks:
                # Extract name
                name_match = re.search(r'name:\s*"([^"]+)"', block)
                if not name_match:
                    continue
                
                name = name_match.group(1)
                
                # Check if this is a human (allow pattern) and not denied
                if not self._human_allow_pattern.search(name):
                    continue
                if self._human_deny_pattern.search(name):
                    continue
                
                # Extract position
                x_match = re.search(r'position\s*\{[^}]*x:\s*([-\d.e+]+)', block, re.DOTALL)
                y_match = re.search(r'position\s*\{[^}]*y:\s*([-\d.e+]+)', block, re.DOTALL)
                z_match = re.search(r'position\s*\{[^}]*z:\s*([-\d.e+]+)', block, re.DOTALL)
                
                # Extract orientation
                ox_match = re.search(r'orientation\s*\{[^}]*x:\s*([-\d.e+]+)', block, re.DOTALL)
                oy_match = re.search(r'orientation\s*\{[^}]*y:\s*([-\d.e+]+)', block, re.DOTALL)
                oz_match = re.search(r'orientation\s*\{[^}]*z:\s*([-\d.e+]+)', block, re.DOTALL)
                ow_match = re.search(r'orientation\s*\{[^}]*w:\s*([-\d.e+]+)', block, re.DOTALL)
                
                if x_match and y_match:
                    x = float(x_match.group(1))
                    y = float(y_match.group(1))
                    z = float(z_match.group(1)) if z_match else 0.0
                    
                    # Compute yaw
                    yaw_deg = 0.0
                    if ox_match and oy_match and oz_match and ow_match:
                        yaw_deg = quaternion_to_yaw_deg_xyzw(
                            float(ox_match.group(1)),
                            float(oy_match.group(1)),
                            float(oz_match.group(1)),
                            float(ow_match.group(1))
                        )
                    
                    humans[name] = {
                        'name': name,
                        'x': round(x, 2),
                        'y': round(y, 2),
                        'yaw_deg': round(yaw_deg, 1),
                        'ts': now,
                    }
            
            # Update cache
            self._humans = humans
            
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # gz command not available
            if not self._human_warning_logged:
                self.get_logger().warn('gz command not found, human detection disabled')
                self._human_warning_logged = True
        except Exception as e:
            if not self._human_warning_logged:
                self.get_logger().warn(f'Error polling Gazebo for humans: {e}')
                self._human_warning_logged = True
        
        # Build output list with stable IDs
        now = self._now_sec()
        sorted_names = sorted(self._humans.keys())[:self.max_humans]
        result = []
        for i, name in enumerate(sorted_names):
            h = self._humans[name]
            result.append({
                'id': f'H{i+1}',
                'name': name,
                'x': h['x'],
                'y': h['y'],
                'yaw_deg': h['yaw_deg'],
                'age_s': round(now - h['ts'], 2),
            })
        return result

    def _write_telemetry(self):
        """Write a telemetry snapshot to the JSONL file."""
        self._seq += 1
        
        # Poll for human positions
        humans = self._poll_gazebo_humans()
        
        snapshot = {
            'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'seq': self._seq,
            'follow_state': self._follow_state,
            'guard_status': self._guard_status,
            'inside': self._inside,
            'distance_to_fence_m': round(self._distance_to_fence, 2) if self._distance_to_fence is not None else None,
            'pose': self._build_pose_dict(),
            'selected_id': self._selected_id,
            'seen_ids': self._seen_ids,
            'stale': self._compute_stale(),
            'humans': humans,
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
