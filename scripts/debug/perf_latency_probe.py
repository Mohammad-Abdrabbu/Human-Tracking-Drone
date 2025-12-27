#!/usr/bin/env python3
"""
perf_latency_probe.py - Pipeline Latency Measurement Node (Fixed)

Uses ROS_TIME (simulation time) correctly to measure message age.
Outputs per-topic age_sim_ms and inter-arrival dt_ms.

Usage:
    python3 scripts/debug/perf_latency_probe.py --output-dir /path/to/run_dir

Output Files:
    - latency_age.csv: wall_ts, topic, stamp_s, age_sim_ms, dt_ms
    - latency_probe_summary.txt: mismatch counts and statistics
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.time import Time
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray
import csv
import argparse
import signal
import sys
import os
from datetime import datetime
from threading import Lock
from collections import deque


def stamp_to_sec(stamp) -> float:
    """Convert ROS Time stamp to float seconds."""
    if stamp is None:
        return 0.0
    return stamp.sec + stamp.nanosec / 1e9


class LatencyProbeNode(Node):
    """
    Fixed latency probe using ROS_TIME (simulation time).
    
    Measures:
    - age_sim_ms: how old the message is in simulation time
    - dt_ms: inter-arrival time between messages
    - stamp mismatch detection between camera and detections/tracks
    """
    
    def __init__(self, output_dir: str):
        super().__init__('perf_latency_probe', 
                        allow_undeclared_parameters=True,
                        automatically_declare_parameters_from_overrides=True)
        
        self.output_dir = output_dir
        
        # Lock for thread safety
        self._lock = Lock()
        
        # Track last received timestamps for inter-arrival
        self._last_recv = {
            'camera': None,
            'detections': None,
            'tracks': None
        }
        
        # Track recent camera stamps for lineage matching (last 100)
        self._recent_cam_stamps = deque(maxlen=100)
        
        # Statistics
        self._stats = {
            'camera_count': 0,
            'det_count': 0,
            'trk_count': 0,
            'det_match': 0,
            'det_mismatch': 0,
            'trk_match': 0,
            'trk_mismatch': 0,
            'max_cam_age': 0.0,
            'max_det_age': 0.0,
            'max_trk_age': 0.0,
        }
        
        # QoS for best-effort, latest only
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscriptions
        self.sub_cam = self.create_subscription(
            Image, '/camera/image_raw', self._on_camera, qos)
        self.sub_det = self.create_subscription(
            Detection2DArray, '/perception/detections', self._on_detections, qos)
        self.sub_trk = self.create_subscription(
            Detection2DArray, '/perception/tracks', self._on_tracks, qos)
        
        # Open CSV file
        csv_path = os.path.join(output_dir, 'latency_age.csv')
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'wall_ts', 'topic', 'stamp_s', 'age_sim_ms', 'dt_ms', 'count'
        ])
        
        self.get_logger().info(
            f'LatencyProbe (fixed) started: output_dir={output_dir}'
        )
    
    def _compute_age_and_log(self, topic: str, msg_stamp, item_count: int = 0):
        """Compute message age using ROS clock and log to CSV."""
        # Get current ROS time (respects use_sim_time)
        now = self.get_clock().now()
        msg_time = Time.from_msg(msg_stamp)
        
        # Compute age in simulation time
        age_ns = (now - msg_time).nanoseconds
        age_sim_ms = age_ns / 1e6
        
        # Compute inter-arrival time
        wall_now = datetime.now()
        with self._lock:
            last = self._last_recv[topic]
            if last is not None:
                dt_ms = (wall_now - last).total_seconds() * 1000
            else:
                dt_ms = 0.0
            self._last_recv[topic] = wall_now
        
        # Log to CSV
        stamp_s = stamp_to_sec(msg_stamp)
        wall_ts = wall_now.isoformat(timespec='milliseconds')
        
        self.csv_writer.writerow([
            wall_ts, topic, f"{stamp_s:.6f}", f"{age_sim_ms:.1f}", f"{dt_ms:.1f}", item_count
        ])
        self.csv_file.flush()
        
        return age_sim_ms, stamp_s
    
    def _on_camera(self, msg: Image):
        """Handle camera message."""
        age_ms, stamp_s = self._compute_age_and_log('camera', msg.header.stamp)
        
        with self._lock:
            self._stats['camera_count'] += 1
            self._stats['max_cam_age'] = max(self._stats['max_cam_age'], age_ms)
            # Store stamp for lineage matching
            self._recent_cam_stamps.append(stamp_s)
    
    def _on_detections(self, msg: Detection2DArray):
        """Handle detections message."""
        age_ms, stamp_s = self._compute_age_and_log(
            'detections', msg.header.stamp, len(msg.detections))
        
        with self._lock:
            self._stats['det_count'] += 1
            self._stats['max_det_age'] = max(self._stats['max_det_age'], age_ms)
            
            # Check lineage: does this stamp match a recent camera stamp?
            if self._stamp_matches_recent_cam(stamp_s):
                self._stats['det_match'] += 1
            else:
                self._stats['det_mismatch'] += 1
    
    def _on_tracks(self, msg: Detection2DArray):
        """Handle tracks message."""
        age_ms, stamp_s = self._compute_age_and_log(
            'tracks', msg.header.stamp, len(msg.detections))
        
        with self._lock:
            self._stats['trk_count'] += 1
            self._stats['max_trk_age'] = max(self._stats['max_trk_age'], age_ms)
            
            # Check lineage
            if self._stamp_matches_recent_cam(stamp_s):
                self._stats['trk_match'] += 1
            else:
                self._stats['trk_mismatch'] += 1
    
    def _stamp_matches_recent_cam(self, stamp_s: float) -> bool:
        """Check if stamp matches any recent camera stamp within ±50ms."""
        for cam_stamp in self._recent_cam_stamps:
            if abs(stamp_s - cam_stamp) < 0.050:  # 50ms tolerance
                return True
        return False
    
    def write_summary(self):
        """Write summary statistics to file."""
        summary_path = os.path.join(self.output_dir, 'latency_probe_summary.txt')
        with self._lock:
            stats = self._stats.copy()
        
        with open(summary_path, 'w') as f:
            f.write("# Latency Probe Summary\n\n")
            f.write(f"Camera messages: {stats['camera_count']}\n")
            f.write(f"Detection messages: {stats['det_count']}\n")
            f.write(f"Track messages: {stats['trk_count']}\n")
            f.write("\n")
            f.write(f"Max camera age (sim): {stats['max_cam_age']:.1f} ms\n")
            f.write(f"Max detection age (sim): {stats['max_det_age']:.1f} ms\n")
            f.write(f"Max track age (sim): {stats['max_trk_age']:.1f} ms\n")
            f.write("\n")
            f.write("## Stamp Lineage Check\n\n")
            det_total = stats['det_match'] + stats['det_mismatch']
            trk_total = stats['trk_match'] + stats['trk_mismatch']
            if det_total > 0:
                det_rate = stats['det_mismatch'] / det_total * 100
                f.write(f"Detections: {stats['det_match']} match, {stats['det_mismatch']} mismatch ({det_rate:.1f}% mismatch)\n")
            if trk_total > 0:
                trk_rate = stats['trk_mismatch'] / trk_total * 100
                f.write(f"Tracks: {stats['trk_match']} match, {stats['trk_mismatch']} mismatch ({trk_rate:.1f}% mismatch)\n")
        
        self.get_logger().info(f'Summary written to: {summary_path}')
    
    def destroy_node(self):
        """Clean shutdown."""
        self.write_summary()
        self.csv_file.close()
        self.get_logger().info(f'LatencyProbe stopped')
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description='Pipeline Latency Probe (Fixed)')
    parser.add_argument('--output-dir', '-o', required=True,
                       help='Output directory for CSV and summary files')
    args = parser.parse_args()
    
    # Ensure output dir exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    rclpy.init()
    node = LatencyProbeNode(args.output_dir)
    
    # Handle SIGTERM/SIGINT gracefully
    def shutdown(sig, frame):
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
