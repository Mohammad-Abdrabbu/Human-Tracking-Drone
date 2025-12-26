#!/usr/bin/env python3
"""
sahtd_event_logger_node.py - Committee-proof event logger for FR6/FR8.

Subscribes to:
  /gp2/guard/status   (String) - Guard state transitions
  /gp2/guard/reason   (String) - Reason for guard state
  /gp2/guard/debug    (String) - Debug info for context
  /perception/target_select (Int32) - Target selection events

Outputs:
  File: ~/sahtd/data/logs/events.jsonl (JSONL format)
  Terminal: print() + ROS log for live visibility
  Topic: /sahtd/events (String) for future UI integration

Non-blocking: Uses in-memory queue + timer flush to avoid blocking control loops.
"""
import json
import os
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import String, Int32


class EventLoggerNode(Node):
    def __init__(self):
        super().__init__('event_logger_node')

        # Compute default log path using SAHTD_ROOT or auto-detection
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
                _sahtd_root = os.path.expanduser('~') + '/sahtd'
        
        default_log_path = os.path.join(_sahtd_root, 'data/logs/events.jsonl')

        # --- Parameters ---
        self.declare_parameter('log_file', default_log_path)
        self.declare_parameter('flush_rate_hz', 10.0)
        self.declare_parameter('max_queue_size', 1000)

        log_path = self.get_parameter('log_file').get_parameter_value().string_value
        self.log_path = Path(os.path.expanduser(log_path))
        self.flush_rate = self.get_parameter('flush_rate_hz').get_parameter_value().double_value
        self.max_queue = self.get_parameter('max_queue_size').get_parameter_value().integer_value

        # --- Ensure log directory exists ---
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Open log file in append mode (line buffered) ---
        try:
            self._log_file = open(self.log_path, 'a', buffering=1)
        except Exception as e:
            self.get_logger().error(f'Failed to open log file: {e}')
            self._log_file = None

        # --- Event queue (non-blocking) ---
        self._event_queue = deque(maxlen=self.max_queue)

        # --- State tracking for transition detection ---
        self._last_guard_status: Optional[str] = None
        self._last_guard_reason: str = ''
        self._last_guard_debug: str = ''

        # --- QoS profiles ---
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        qos_status = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # --- Subscriptions ---
        self.create_subscription(
            String, '/gp2/guard/status', self._on_guard_status, qos_status)
        self.create_subscription(
            String, '/gp2/guard/reason', self._on_guard_reason, qos_reliable)
        self.create_subscription(
            String, '/gp2/guard/debug', self._on_guard_debug, 10)
        self.create_subscription(
            Int32, '/perception/target_select', self._on_target_select, qos_reliable)
        # FR7: Command acknowledgments
        self.create_subscription(
            String, '/sahtd/cmd_ack', self._on_cmd_ack, qos_reliable)
        # FR6: Target visibility status (lost/reacquired)
        self.create_subscription(
            String, '/sahtd/target_status', self._on_target_status, qos_reliable)

        # --- Publisher for live event stream ---
        self._events_pub = self.create_publisher(String, '/sahtd/events', 10)

        # --- Timer for non-blocking flush ---
        flush_period = 1.0 / self.flush_rate if self.flush_rate > 0 else 0.1
        self.create_timer(flush_period, self._flush_queue)

        # --- Startup banner ---
        self.get_logger().info('=' * 60)
        self.get_logger().info('EVENT LOGGER NODE STARTED')
        self.get_logger().info(f'  Log file: {self.log_path}')
        self.get_logger().info(f'  Flush rate: {self.flush_rate} Hz')
        self.get_logger().info('=' * 60)

        # Log startup event
        self._queue_event('LOGGER_START', 'event_logger', {
            'log_file': str(self.log_path),
            'flush_rate_hz': self.flush_rate
        })

    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp with milliseconds."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def _queue_event(self, event_name: str, source: str, data: dict):
        """Queue an event for non-blocking write."""
        event = {
            'ts': self._get_timestamp(),
            'event': event_name,
            'source': source,
            'data': data
        }
        self._event_queue.append(event)

        # Also print immediately for live terminal visibility
        data_str = ' '.join(f'{k}={v}' for k, v in data.items() if v)
        live_line = f"EVENT: {event['ts']} {event_name} [{source}] {data_str}"
        print(live_line, flush=True)
        self.get_logger().info(live_line)

        # Publish to topic for UI integration
        msg = String()
        msg.data = json.dumps(event)
        self._events_pub.publish(msg)

    def _flush_queue(self):
        """Timer callback: flush queued events to disk."""
        if not self._log_file or not self._event_queue:
            return

        try:
            while self._event_queue:
                event = self._event_queue.popleft()
                line = json.dumps(event, separators=(',', ':'))
                self._log_file.write(line + '\n')
            self._log_file.flush()
        except Exception as e:
            self.get_logger().error(f'Failed to write to log file: {e}')

    def _on_guard_status(self, msg: String):
        """Handle guard status - log on transitions only."""
        status = msg.data.strip() if msg.data else ''
        
        # Only log on state transitions
        if status and status != self._last_guard_status:
            # Map status to event name
            event_map = {
                'NORMAL': 'GUARD_NORMAL',
                'GEOGUARD_HOLD': 'GUARD_HOLD',
                'GEOGUARD_VIOLATION': 'GUARD_VIOLATION'
            }
            event_name = event_map.get(status, f'GUARD_{status}')

            self._queue_event(event_name, 'geo_guard', {
                'status': status,
                'reason': self._last_guard_reason,
                'debug': self._last_guard_debug
            })

            self._last_guard_status = status

    def _on_guard_reason(self, msg: String):
        """Cache guard reason for context."""
        self._last_guard_reason = msg.data.strip() if msg.data else ''

    def _on_guard_debug(self, msg: String):
        """Cache guard debug for context."""
        self._last_guard_debug = msg.data.strip() if msg.data else ''

    def _on_target_select(self, msg: Int32):
        """Handle target selection."""
        target_id = msg.data
        self._queue_event('TARGET_SELECTED', 'target_select', {
            'target_id': target_id
        })

    def _on_cmd_ack(self, msg: String):
        """Handle command acknowledgments from FR7 command executor."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f'[event_logger] Invalid CMD_ACK JSON: {msg.data}')
            return
        
        self._queue_event('CMD_ACK', 'command_executor', {
            'req_id': data.get('req_id', 'unknown'),
            'cmd': data.get('cmd', 'unknown'),
            'status': data.get('status', 'unknown'),
            'detail': data.get('detail', '')
        })

    def _on_target_status(self, msg: String):
        """Handle target lost/reacquired events from follow_node (FR6)."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(f'[event_logger] Invalid target_status JSON: {msg.data}')
            return
        
        event_type = data.get('type', 'UNKNOWN')
        selected_id = data.get('selected_id', -1)
        
        # Map to human-readable message
        if event_type == 'TARGET_LOST':
            message = f'Target {selected_id} lost - no detection for timeout period'
        elif event_type == 'TARGET_REACQUIRED':
            message = f'Target {selected_id} re-acquired after loss'
        else:
            message = f'Target status: {event_type}'
        
        self._queue_event(event_type, 'follow', {
            'selected_id': selected_id,
            'message': message
        })

    def destroy_node(self):
        """Clean up: flush remaining events and close file."""
        # Flush any remaining events
        if self._event_queue and self._log_file:
            try:
                while self._event_queue:
                    event = self._event_queue.popleft()
                    line = json.dumps(event, separators=(',', ':'))
                    self._log_file.write(line + '\n')
                self._log_file.flush()
            except Exception:
                pass

        # Close file
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = EventLoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
