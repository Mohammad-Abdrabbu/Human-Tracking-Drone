#!/usr/bin/env python3
import math
import time
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped


class ActorPoseStubNode(Node):
    """
    Simple stub node that publishes a PoseStamped approximating the
    Gazebo actor trajectory defined in:

      ~/gp2/assets/models/actor_violate/model.sdf

    It does *not* read from Gazebo. Instead, it replays the same
    waypoint / time schedule as in the SDF, driven by wall-clock time.
    This is good enough for the Scene B playground demo where we only
    need to know when the human leaves the square.

    If you change the actor's SDF trajectory, you must update this node
    to match.
    """

    def __init__(self):
        super().__init__('actor_pose_stub')

        # Parameters
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('publish_topic', '/gp2/actor/person_A/pose')
        self.declare_parameter('rate_hz', 20.0)
        # how long the actor waits before starting to walk (see delay_start in SDF)
        self.declare_parameter('delay_start_s', 10.0)

        self.frame_id = str(self.get_parameter('frame_id').value)
        self.topic = str(self.get_parameter('publish_topic').value)
        self.rate_hz = float(self.get_parameter('rate_hz').value)
        self.delay_start_s = float(self.get_parameter('delay_start_s').value)

        self.pub = self.create_publisher(PoseStamped, self.topic, 10)

        # Copy of the SDF trajectory waypoints (time [s], x, y, z, yaw)
        # Times are relative to the start of the trajectory (not including delay_start_s).
        self._traj: List[Tuple[float, float, float, float, float]] = [
            (0.0, 3.0, 0.0, 0.02, 0.0),
            (10.0, 8.0, 0.0, 0.02, 0.0),
            (20.0, 13.0, -1.0, 0.02, -0.35),
            (30.0, 18.0, -2.0, 0.02, -0.79),
            (40.0, 23.0, -1.0, 0.02, -0.35),
            (50.0, 28.0, 0.0, 0.02, -0.10),
            (60.0, 33.0, 0.0, 0.02, 0.0),
            (80.0, 43.0, 0.0, 0.02, 0.0),
        ]
        self._traj_duration = self._traj[-1][0]

        self._t0 = time.monotonic()

        period = 1.0 / max(1e-3, self.rate_hz)
        self._timer = self.create_timer(period, self._on_timer)

        self.get_logger().info(
            f'ActorPoseStub: publishing to {self.topic} at {self.rate_hz:.1f} Hz, '
            f'delay_start_s={self.delay_start_s}, traj_duration={self._traj_duration}s'
        )

    # --- Trajectory sampling helpers ---

    def _sample_traj(self, t_rel: float) -> Tuple[float, float, float, float]:
        """
        Sample the trajectory at time t_rel (seconds since start of trajectory),
        with looping.
        """
        if self._traj_duration <= 0.0:
            # degenerate: stay at first waypoint
            _, x, y, z, yaw = self._traj[0]
            return x, y, z, yaw

        # loop
        t = t_rel % self._traj_duration

        # find segment
        for i in range(len(self._traj) - 1):
            t0, x0, y0, z0, yaw0 = self._traj[i]
            t1, x1, y1, z1, yaw1 = self._traj[i + 1]
            if t <= t1:
                if t1 <= t0 + 1e-6:
                    return x0, y0, z0, yaw0
                alpha = (t - t0) / (t1 - t0)
                x = x0 + alpha * (x1 - x0)
                y = y0 + alpha * (y1 - y0)
                z = z0 + alpha * (z1 - z0)
                yaw = yaw0 + alpha * (yaw1 - yaw0)
                return x, y, z, yaw

        # fallback (should not happen due to loop)
        _, x, y, z, yaw = self._traj[-1]
        return x, y, z, yaw

    @staticmethod
    def _yaw_to_quat(yaw: float):
        """
        Convert yaw (rad, about +Z) to a unit quaternion.
        """
        cy = math.cos(0.5 * yaw)
        sy = math.sin(0.5 * yaw)
        # roll=pitch=0
        return 0.0, 0.0, sy, cy

    # --- Timer callback ---

    def _on_timer(self):
        now = time.monotonic()
        t_since_start = now - self._t0

        if t_since_start < self.delay_start_s:
            # before actor starts walking: keep at first waypoint
            _, x, y, z, yaw = self._traj[0]
        else:
            t_rel = t_since_start - self.delay_start_s
            x, y, z, yaw = self._sample_traj(t_rel)

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.pose.position.x = float(x)
        msg.pose.position.y = float(y)
        msg.pose.position.z = float(z)
        qx, qy, qz, qw = self._yaw_to_quat(yaw)
        msg.pose.orientation.x = qx
        msg.pose.orientation.y = qy
        msg.pose.orientation.z = qz
        msg.pose.orientation.w = qw

        self.pub.publish(msg)


def main():
    rclpy.init()
    node = ActorPoseStubNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
