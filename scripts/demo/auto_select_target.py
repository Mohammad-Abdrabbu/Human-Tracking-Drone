#!/usr/bin/env python3
"""
auto_select_target.py - Auto-select target for committee demo

Policies:
  best (default): Subscribe to /perception/tracks, select detection with
                  largest bbox area, publish ID once and exit.
  first:          Read /sahtd/follow/seen_ids, select first ID, publish once.

Usage:
  python3 auto_select_target.py --policy best --timeout 5
  python3 auto_select_target.py --policy first --timeout 5
"""
import argparse
import re
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Int32, String
from vision_msgs.msg import Detection2DArray


class AutoSelectNode(Node):
    def __init__(self, policy: str, timeout: float, 
                 tracks_topic: str, seen_ids_topic: str, select_topic: str):
        super().__init__('auto_select_target')
        
        self.policy = policy
        self.timeout = timeout
        self.start_time = time.time()
        self.selected = False
        
        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Publisher for target selection
        self.select_pub = self.create_publisher(Int32, select_topic, qos)
        
        if policy == 'best':
            # Best policy: subscribe to tracks for bbox area
            self.tracks_sub = self.create_subscription(
                Detection2DArray,
                tracks_topic,
                self._on_tracks_best,
                qos
            )
            self.get_logger().info(f'Policy=best: waiting for tracks on {tracks_topic}')
        else:
            # First policy: subscribe to seen_ids
            self.seen_sub = self.create_subscription(
                String,
                seen_ids_topic,
                self._on_seen_ids,
                qos
            )
            # Fallback to tracks if seen_ids empty
            self.tracks_sub = self.create_subscription(
                Detection2DArray,
                tracks_topic,
                self._on_tracks_first,
                qos
            )
            self.get_logger().info(f'Policy=first: waiting for seen_ids on {seen_ids_topic}')
        
        # Timeout timer
        self.timer = self.create_timer(0.5, self._check_timeout)
    
    def _extract_id(self, det) -> int:
        """Extract track ID from detection. Returns None if not parseable."""
        if det.results:
            hyp = det.results[0].hypothesis
            class_id = getattr(hyp, 'class_id', '')
            
            # Try direct int conversion
            try:
                return int(class_id)
            except (ValueError, TypeError):
                pass
            
            # Fallback: extract digits from string
            match = re.search(r'(\d+)', str(class_id))
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        return None
    
    def _on_tracks_best(self, msg: Detection2DArray):
        """Best policy: find detection with largest bbox area."""
        if self.selected or not msg.detections:
            return
        
        best_id = None
        best_area = -1.0
        
        for det in msg.detections:
            track_id = self._extract_id(det)
            if track_id is None:
                continue
            
            try:
                area = float(det.bbox.size_x) * float(det.bbox.size_y)
            except:
                area = 0.0
            
            if area > best_area:
                best_area = area
                best_id = track_id
        
        if best_id is not None:
            self._publish_selection(best_id, f"policy=best area={best_area:.0f}")
    
    def _on_seen_ids(self, msg: String):
        """First policy: parse seen_ids and select first."""
        if self.selected:
            return
        
        data = msg.data
        if not data.startswith('ids='):
            return
        
        ids_str = data[4:]
        if not ids_str:
            return
        
        try:
            ids = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
            if ids:
                self._publish_selection(ids[0], "policy=first source=seen_ids")
        except ValueError:
            pass
    
    def _on_tracks_first(self, msg: Detection2DArray):
        """First policy fallback: select first detection from tracks."""
        if self.selected or not msg.detections:
            return
        
        for det in msg.detections:
            track_id = self._extract_id(det)
            if track_id is not None:
                self._publish_selection(track_id, "policy=first source=tracks")
                return
    
    def _publish_selection(self, target_id: int, info: str):
        """Publish selection once and exit."""
        if self.selected:
            return
        
        msg = Int32()
        msg.data = target_id
        self.select_pub.publish(msg)
        
        self.selected = True
        print(f"Selected id={target_id} {info}")
        self.get_logger().info(f'Selected id={target_id} {info}')
        
        # Exit after selection
        rclpy.shutdown()
    
    def _check_timeout(self):
        elapsed = time.time() - self.start_time
        if elapsed >= self.timeout and not self.selected:
            print(f"Error: No targets found after {self.timeout}s", file=sys.stderr)
            self.get_logger().error(f'Timeout: No targets found after {self.timeout}s')
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Auto-select target for demo')
    parser.add_argument('--policy', choices=['best', 'first'], default='best',
                        help='Selection policy (default: best)')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='Timeout in seconds (default: 5)')
    parser.add_argument('--tracks-topic', default='/perception/tracks',
                        help='Tracks topic (default: /perception/tracks)')
    parser.add_argument('--seen-ids-topic', default='/sahtd/follow/seen_ids',
                        help='Seen IDs topic (default: /sahtd/follow/seen_ids)')
    parser.add_argument('--select-topic', default='/perception/target_select',
                        help='Select topic (default: /perception/target_select)')
    args = parser.parse_args()
    
    rclpy.init()
    node = AutoSelectNode(
        policy=args.policy,
        timeout=args.timeout,
        tracks_topic=args.tracks_topic,
        seen_ids_topic=args.seen_ids_topic,
        select_topic=args.select_topic
    )
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()
    
    # Exit with error if no selection was made
    return 0 if node.selected else 1


if __name__ == '__main__':
    sys.exit(main())
