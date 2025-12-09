#!/usr/bin/env python3
"""
Lane B3: Target Visualization Node

Overlays bounding boxes and track IDs onto the camera image.
Highlights the currently selected target with a thicker border.

Subscriptions:
  /camera/image_raw (sensor_msgs/Image, BEST_EFFORT)
  /perception/tracks (vision_msgs/Detection2DArray, RELIABLE)
  /perception/target_select (std_msgs/Int32, RELIABLE)

Publications:
  /perception/debug_image_tracks (sensor_msgs/Image, BEST_EFFORT)
"""

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray
from std_msgs.msg import Int32
from cv_bridge import CvBridge
import message_filters


# Color palette (BGR format) for track IDs
COLOR_PALETTE = [
    (0, 255, 0),     # Green
    (255, 0, 0),     # Blue
    (0, 0, 255),     # Red
    (255, 255, 0),   # Cyan
    (255, 0, 255),   # Magenta
    (0, 255, 255),   # Yellow
    (128, 0, 255),   # Orange
    (255, 128, 0),   # Light blue
    (0, 128, 255),   # Light orange
    (128, 255, 0),   # Lime
]
GRAY_COLOR = (128, 128, 128)
SELECTED_COLOR = (0, 255, 255)  # Yellow for selected


class TargetVizNode(Node):
    def __init__(self):
        super().__init__('target_viz_node')

        # Parameters
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('tracks_topic', '/perception/tracks')
        self.declare_parameter('target_select_topic', '/perception/target_select')
        self.declare_parameter('output_image_topic', '/perception/debug_image_tracks')
        self.declare_parameter('font_scale', 0.5)
        self.declare_parameter('line_thickness', 2)

        self.image_topic = self.get_parameter('image_topic').value
        self.tracks_topic = self.get_parameter('tracks_topic').value
        self.target_select_topic = self.get_parameter('target_select_topic').value
        self.output_topic = self.get_parameter('output_image_topic').value
        self.font_scale = self.get_parameter('font_scale').value
        self.line_thickness = self.get_parameter('line_thickness').value

        # State
        self.selected_id = None
        self.bridge = CvBridge()

        # QoS profiles
        qos_image = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Publisher
        self.image_pub = self.create_publisher(Image, self.output_topic, qos_image)

        # Target select subscription (simple, not synchronized)
        self.target_sub = self.create_subscription(
            Int32,
            self.target_select_topic,
            self._on_target_select,
            qos_reliable
        )

        # Synchronized subscriptions for image + tracks
        self.image_sub = message_filters.Subscriber(
            self, Image, self.image_topic, qos_profile=qos_image
        )
        self.tracks_sub = message_filters.Subscriber(
            self, Detection2DArray, self.tracks_topic, qos_profile=qos_reliable
        )

        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.image_sub, self.tracks_sub],
            queue_size=10,
            slop=0.2
        )
        self.sync.registerCallback(self._on_sync)

        self.get_logger().info(
            f'[TargetViz] Started:\n'
            f'  Image: {self.image_topic}\n'
            f'  Tracks: {self.tracks_topic}\n'
            f'  Select: {self.target_select_topic}\n'
            f'  Output: {self.output_topic}'
        )

    def _on_target_select(self, msg: Int32):
        """Handle target selection updates."""
        new_id = msg.data
        if new_id != self.selected_id:
            self.get_logger().info(f'[TargetViz] Selected ID changed: {self.selected_id} → {new_id}')
            self.selected_id = new_id

    def _on_sync(self, image_msg: Image, tracks_msg: Detection2DArray):
        """Process synchronized image and tracks."""
        try:
            # Convert ROS Image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'[TargetViz] cv_bridge error: {e}')
            return

        # Draw overlay
        self._draw_overlay(cv_image, tracks_msg)

        # Convert back to ROS Image and publish
        try:
            out_msg = self.bridge.cv2_to_imgmsg(cv_image, encoding='bgr8')
            out_msg.header = image_msg.header
            self.image_pub.publish(out_msg)
        except Exception as e:
            self.get_logger().warn(f'[TargetViz] Publish error: {e}')

    def _draw_overlay(self, img: np.ndarray, tracks_msg: Detection2DArray):
        """Draw bounding boxes and labels on the image."""
        num_tracks = len(tracks_msg.detections)

        # Draw HUD
        hud_text = f"Tracks: {num_tracks} | Selected: {self.selected_id or 'None'}"
        cv2.putText(img, hud_text, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, hud_text, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

        for det in tracks_msg.detections:
            # Extract bbox
            try:
                cx = det.bbox.center.position.x
                cy = det.bbox.center.position.y
            except AttributeError:
                cx = det.bbox.center.x
                cy = det.bbox.center.y

            w = det.bbox.size_x
            h = det.bbox.size_y

            x1 = int(cx - w / 2.0)
            y1 = int(cy - h / 2.0)
            x2 = int(cx + w / 2.0)
            y2 = int(cy + h / 2.0)

            # Extract track ID
            track_id = -1
            score = 0.0
            if det.results:
                hyp = det.results[0].hypothesis
                try:
                    # Try numeric ID first
                    track_id = int(hyp.class_id)
                except (ValueError, TypeError, AttributeError):
                    # Try parsing from string
                    try:
                        import re
                        match = re.search(r'(\d+)', str(hyp.class_id))
                        if match:
                            track_id = int(match.group(1))
                    except:
                        pass
                try:
                    score = float(hyp.score)
                except:
                    pass

            # Choose color
            is_selected = (track_id == self.selected_id and self.selected_id is not None)
            if track_id < 0:
                color = GRAY_COLOR
            else:
                idx = abs(track_id) % len(COLOR_PALETTE)
                color = COLOR_PALETTE[idx]

            # Adjust for selected target
            thickness = self.line_thickness + 2 if is_selected else self.line_thickness
            if is_selected:
                color = SELECTED_COLOR

            # Draw rectangle
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

            # Draw label
            label = f"ID:{track_id}"
            label_y = max(y1 - 8, 15)
            cv2.putText(img, label, (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, color, 2, cv2.LINE_AA)
            cv2.putText(img, label, (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (0, 0, 0), 1, cv2.LINE_AA)


def main():
    rclpy.init()
    node = TargetVizNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
