#!/usr/bin/env python3
"""
command_executor.py - FR7 Manual Override Command Executor

Subscribes to /sahtd/cmd and executes pause/resume/rtl/land commands using
the follow_node's MAVSDK drone connection. Publishes ACKs to /sahtd/cmd_ack.

Commands:
  pause  - Set paused flag, follow_node sends zero velocity but keeps offboard alive
  resume - Clear paused flag, follow_node resumes normal control
  rtl    - Queue return-to-launch action (stops offboard)
  land   - Queue land action (stops offboard)
"""
import json
import threading
from datetime import datetime, timezone
from typing import Callable, Optional, Any

from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String


class CommandExecutor:
    """
    Handles manual override commands from the web backend.
    
    Designed to be instantiated by follow_node after MAVSDK drone is connected.
    Uses the node's ROS infrastructure for subscriptions/publications.
    """
    
    def __init__(self, node: Node, drone_getter: Callable[[], Any]):
        """
        Initialize the command executor.
        
        Args:
            node: The ROS node to use for subscriptions/publications
            drone_getter: Callable that returns the MAVSDK drone object
        """
        self._node = node
        self._drone_getter = drone_getter
        self._lock = threading.Lock()
        
        # State
        self._paused = False
        self._pending_action: Optional[str] = None  # 'rtl' or 'land'
        
        # QoS for command topics
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribe to commands
        self._cmd_sub = node.create_subscription(
            String,
            '/sahtd/cmd',
            self._on_cmd,
            qos
        )
        
        # Publisher for ACKs
        self._ack_pub = node.create_publisher(String, '/sahtd/cmd_ack', qos)
        
        node.get_logger().info('[CommandExecutor] Initialized - listening on /sahtd/cmd')
    
    @property
    def paused(self) -> bool:
        """True if pause is active (follow_node should send zero velocity)."""
        with self._lock:
            return self._paused
    
    @property
    def pending_action(self) -> Optional[str]:
        """Returns 'rtl' or 'land' if an action is queued, None otherwise."""
        with self._lock:
            return self._pending_action
    
    def clear_pending_action(self) -> Optional[str]:
        """Clear and return the pending action (called after execution)."""
        with self._lock:
            action = self._pending_action
            self._pending_action = None
            return action
    
    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp with milliseconds."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def _publish_ack(self, req_id: str, cmd: str, status: str, detail: str = ''):
        """Publish command acknowledgment."""
        ack = {
            'req_id': req_id,
            'cmd': cmd,
            'status': status,
            'detail': detail,
            'ts': self._get_timestamp()
        }
        msg = String()
        msg.data = json.dumps(ack)
        self._ack_pub.publish(msg)
        self._node.get_logger().info(f'[CommandExecutor] ACK: {cmd} -> {status}')
    
    def _on_cmd(self, msg: String):
        """Handle incoming command message."""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self._node.get_logger().warn(f'[CommandExecutor] Invalid JSON: {e}')
            return
        
        req_id = data.get('req_id', 'unknown')
        cmd = data.get('cmd', '').lower()
        user = data.get('user', 'unknown')
        
        self._node.get_logger().info(f'[CommandExecutor] Received: cmd={cmd} req_id={req_id} user={user}')
        
        if cmd == 'pause':
            with self._lock:
                self._paused = True
            self._publish_ack(req_id, cmd, 'executed', 'Follow paused')
            
        elif cmd == 'resume':
            with self._lock:
                self._paused = False
            self._publish_ack(req_id, cmd, 'executed', 'Follow resumed')
            
        elif cmd == 'rtl':
            with self._lock:
                self._pending_action = 'rtl'
                self._paused = True  # Also pause while RTL is pending
            self._publish_ack(req_id, cmd, 'executed', 'RTL queued')
            
        elif cmd == 'land':
            with self._lock:
                self._pending_action = 'land'
                self._paused = True  # Also pause while land is pending
            self._publish_ack(req_id, cmd, 'executed', 'Land queued')
            
        else:
            self._publish_ack(req_id, cmd, 'failed', f'Unknown command: {cmd}')
