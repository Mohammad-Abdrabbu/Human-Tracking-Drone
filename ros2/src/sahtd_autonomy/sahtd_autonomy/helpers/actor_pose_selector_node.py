#!/usr/bin/env python3
"""
Lane B2: Actor Pose Selector Node (Fixed)

Polls Gazebo directly using 'gz topic' to get the pose of a specific actor.
The ros_gz_bridge TFMessage approach doesn't preserve model names, so we
parse the raw Gazebo topic output instead.

Publishes the selected actor's pose as geometry_msgs/PoseStamped on /gp2/target_pose_gt.
"""

import subprocess
import re
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String


class ActorPoseSelectorNode(Node):
    def __init__(self):
        super().__init__('actor_pose_selector_node')

        # Parameters
        self.declare_parameter('target_actor_name', 'human_violate')
        self.declare_parameter('output_frame_id', 'map')
        self.declare_parameter('publish_rate_hz', 10.0)
        self.declare_parameter('gz_topic', '/world/default/pose/info')

        self.target_actor = self.get_parameter('target_actor_name').value
        self.output_frame = self.get_parameter('output_frame_id').value
        self.publish_rate = self.get_parameter('publish_rate_hz').value
        self.gz_topic = self.get_parameter('gz_topic').value

        # QoS
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Publishers
        self.pose_pub = self.create_publisher(
            PoseStamped,
            '/gp2/target_pose_gt',
            qos_reliable
        )
        self.info_pub = self.create_publisher(
            String,
            '/gp2/target_pose_gt/info',
            qos_reliable
        )

        # State
        self._last_pose: PoseStamped = None
        self._actor_found = False

        # Timer to poll Gazebo
        self._timer = self.create_timer(1.0 / self.publish_rate, self._poll_gz)

        self.get_logger().info(
            f'[ActorPoseSelector] Polling Gazebo for actor: "{self.target_actor}" → /gp2/target_pose_gt'
        )

    def _poll_gz(self):
        """Poll Gazebo topic and extract target actor pose."""
        # Read target actor name dynamically (allows runtime changes)
        target_actor = self.get_parameter('target_actor_name').value
        
        try:
            # Run gz topic to get one message
            result = subprocess.run(
                ['gz', 'topic', '-e', '-t', self.gz_topic, '-n', '1'],
                capture_output=True,
                text=True,
                timeout=0.5
            )
            
            if result.returncode != 0:
                return
            
            output = result.stdout
            
            # Parse the output to find the target actor's pose
            pose = self._parse_pose_from_output(output, target_actor)
            
            if pose:
                self._actor_found = True
                self._last_pose = pose
                self.pose_pub.publish(pose)
                
                # Publish info
                info = String()
                info.data = f'actor={target_actor} x={pose.pose.position.x:.2f} y={pose.pose.position.y:.2f}'
                self.info_pub.publish(info)
            
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            self.get_logger().warn(f'Error polling Gazebo: {e}')

    def _parse_pose_from_output(self, output: str, target_name: str) -> PoseStamped:
        """
        Parse gz topic output to find pose of target model.
        
        The output format is like:
        pose {
          name: "human_stand"
          id: 123
          position {
            x: 2.0
            y: 0.0
            z: 0.02
          }
          orientation {
            x: 0.0
            y: 0.0
            z: 0.0
            w: 1.0
          }
        }
        """
        # Split into pose blocks
        blocks = re.split(r'pose\s*\{', output)
        
        for block in blocks:
            # Check if this block is for our target
            name_match = re.search(r'name:\s*"([^"]+)"', block)
            if not name_match:
                continue
                
            if name_match.group(1) != target_name:
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
                ps = PoseStamped()
                ps.header.stamp = self.get_clock().now().to_msg()
                ps.header.frame_id = self.output_frame
                ps.pose.position.x = float(x_match.group(1))
                ps.pose.position.y = float(y_match.group(1))
                ps.pose.position.z = float(z_match.group(1)) if z_match else 0.0
                ps.pose.orientation.x = float(ox_match.group(1)) if ox_match else 0.0
                ps.pose.orientation.y = float(oy_match.group(1)) if oy_match else 0.0
                ps.pose.orientation.z = float(oz_match.group(1)) if oz_match else 0.0
                ps.pose.orientation.w = float(ow_match.group(1)) if ow_match else 1.0
                return ps
        
        return None


def main():
    rclpy.init()
    node = ActorPoseSelectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
