#!/usr/bin/env python3
"""
Lane B3: Target Select Helper Node

CLI helper to select a target ID based on currently visible tracks.
Prints seen IDs and allows interactive selection via stdin.

Subscriptions:
  /gp2/follow/seen_ids (std_msgs/String) - preferred
  /perception/tracks (vision_msgs/Detection2DArray) - fallback

Publications:
  /perception/target_select (std_msgs/Int32)
"""

import sys
import re
import threading
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Int32, String
from vision_msgs.msg import Detection2DArray


class TargetSelectHelperNode(Node):
    def __init__(self):
        super().__init__('target_select_helper_node')

        # State
        self.seen_ids = set()
        self.current_selected = None
        self.running = True

        # QoS
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Publisher
        self.select_pub = self.create_publisher(
            Int32,
            '/perception/target_select',
            qos_reliable
        )

        # Try subscribing to seen_ids first (preferred)
        self.seen_ids_sub = self.create_subscription(
            String,
            '/gp2/follow/seen_ids',
            self._on_seen_ids,
            qos_reliable
        )

        # Fallback: subscribe to tracks
        self.tracks_sub = self.create_subscription(
            Detection2DArray,
            '/perception/tracks',
            self._on_tracks,
            qos_reliable
        )

        # Timer to print status
        self.print_timer = self.create_timer(1.5, self._print_status)

        # Input thread
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()

        self.get_logger().info('[TargetSelectHelper] Started. Type ID to select, "q" to quit.')

    def _on_seen_ids(self, msg: String):
        """Parse seen IDs from follow_node's seen_ids topic."""
        # Format: "ids=1,3,5" or "ids="
        data = msg.data
        if data.startswith('ids='):
            ids_str = data[4:]
            if ids_str:
                try:
                    self.seen_ids = set(int(x.strip()) for x in ids_str.split(',') if x.strip())
                except ValueError:
                    pass
            else:
                self.seen_ids = set()

    def _on_tracks(self, msg: Detection2DArray):
        """Extract IDs from tracks (fallback)."""
        ids = set()
        for det in msg.detections:
            if det.results:
                hyp = det.results[0].hypothesis
                try:
                    track_id = int(hyp.class_id)
                    ids.add(track_id)
                except (ValueError, TypeError, AttributeError):
                    # Try parsing from string
                    try:
                        match = re.search(r'(\d+)', str(hyp.class_id))
                        if match:
                            ids.add(int(match.group(1)))
                    except:
                        pass
        # Only update if seen_ids is empty (prefer seen_ids topic)
        if not self.seen_ids:
            self.seen_ids = ids

    def _print_status(self):
        """Print current status to console."""
        if not self.running:
            return

        ids_list = sorted(self.seen_ids)
        print(f"\n{'='*50}")
        print(f"[target_select_helper_node]")
        print(f"  Seen IDs: {ids_list if ids_list else '(none)'}")
        print(f"  Current selected: {self.current_selected}")
        print(f"  Type ID to select (or 'q' to quit): ", end='', flush=True)

    def _input_loop(self):
        """Read input from stdin in a separate thread."""
        while self.running:
            try:
                line = input()
                line = line.strip().lower()

                if line in ('q', 'quit', 'exit'):
                    print("\n[TargetSelectHelper] Exiting...")
                    self.running = False
                    rclpy.shutdown()
                    break

                if not line:
                    continue

                try:
                    target_id = int(line)
                    self._select_target(target_id)
                except ValueError:
                    print(f"  Invalid input: '{line}'. Enter a number or 'q' to quit.")

            except EOFError:
                self.running = False
                break
            except KeyboardInterrupt:
                self.running = False
                break

    def _select_target(self, target_id: int):
        """Publish target selection."""
        msg = Int32()
        msg.data = target_id
        self.select_pub.publish(msg)
        self.current_selected = target_id
        print(f"  ✓ Selected ID {target_id} (published to /perception/target_select)")
        self.get_logger().info(f'[TargetSelectHelper] Selected ID: {target_id}')


def main():
    rclpy.init()
    node = TargetSelectHelperNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        node.running = False
        node.destroy_node()
        try:
            rclpy.shutdown()
        except:
            pass


if __name__ == '__main__':
    main()
