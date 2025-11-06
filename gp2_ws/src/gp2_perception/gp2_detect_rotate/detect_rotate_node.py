# ~/gp2/ws/gp2_ws/src/gp2_perception/gp2_detect_rotate/detect_rotate_node.py
#!/usr/bin/env python3
import asyncio, math, time, threading
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from vision_msgs.msg import Detection2DArray
from mavsdk.telemetry import Health

from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed

def fov_ex(cx_px, img_w, hfov_rad, invert=False):
    # normalized pixel offset -> radians using FOV
    ex = (cx_px - 0.5 * img_w) / max(1.0, 0.5 * img_w)   # in [-1,1]
    if invert:
        ex = -ex
    return ex * (hfov_rad * 0.5)

class S(Enum):
    GROUND=0; TAKEOFF=1; SEARCH=2; LOCKED=3

class DetectRotate(Node):
    def __init__(self):
        super().__init__("gp2_detect_rotate")

        # --- params
        self.declare_parameter('udp_url', 'udpin://0.0.0.0:14540')
        self.declare_parameter('det_topic', '/perception/detections')  # or /perception/tracks
        self.declare_parameter('class_id', 'person')
        self.declare_parameter('img_w', 1280)
        self.declare_parameter('img_h', 960)
        self.declare_parameter('hfov_deg', 100.0)
        self.declare_parameter('k_yaw', 1.2)            # yaw rate gain
        self.declare_parameter('yawrate_max', 0.6)      # rad/s (clamp)
        self.declare_parameter('deadzone', 0.08)        # no yaw inside this |ex|
        self.declare_parameter('stale_s', 0.75)         # detection stale -> SEARCH
        self.declare_parameter('lock_k', 3)             # frames until LOCKED
        self.declare_parameter('publish_rate_hz', 20.0) # keep-alive
        self.declare_parameter('scan_rate_deg_s', 20.0) # SEARCH yaw rate (deg/s)
        self.declare_parameter('invert_ex', False)      # flip image X if needed
        self.declare_parameter('auto_takeoff_alt_m', 2.5)
        self.declare_parameter('do_auto_takeoff', True)
        self.declare_parameter('takeoff_mode','action') # 'action' or 'offboard'
        self.declare_parameter('scan_when_no_target', False)  # if False => yaw=0 until a human is seen

        # --- altitude guard ---
        self.declare_parameter('alt_guard_enable', True)
        self.declare_parameter('alt_max_m', 2.5)
        self.declare_parameter('alt_deadband_m', 0.05)  # margin before pushing down
        self.declare_parameter('k_z_down', 0.8)         # m/s per m of error (NED down +)
        self.declare_parameter('vz_down_max', 0.7)      # cap down speed (m/s, NED down +)

        # --- yaw smoothing / damping ---
        self.declare_parameter('lpf_alpha', 0.20)       # 0..1, higher = snappier
        self.declare_parameter('kd_yaw', 0.0)           # derivative gain (optional)
        self.declare_parameter('rate_limit_yaw', 120.0) # deg/s^2, limits change per second
        self.declare_parameter('center_hold_deg', 1.5)  # if |ex_deg| <= this → force yaw=0


        # state used by priming
        self._is_in_air = False
        self._rel_alt = 0.0
        self._alt_high = max(0.8, 0.5 * float(self.get_parameter('auto_takeoff_alt_m').value))
        self._alt_low  = max(0.2, self._alt_high - 0.20)

        self._ex_f = 0.0          # filtered ex (rad)
        self._prev_ex_f = 0.0
        self._prev_yaw_deg = 0.0  # last sent yaw rate (deg/s)
        self._loop_dt_ema = 1/20  # for HUD Hz estimate
        
        # --- state
        self._lock = threading.Lock()
        self._last_det_ts = 0.0
        self._last_cx = None
        self._lock_score = 0
        self._fsm = S.GROUND
        self._in_air = False
        self._rel_alt = 0.0

        # --- pubs/subs
        qos_in = QoSProfile(depth=20)
        qos_in.history = HistoryPolicy.KEEP_LAST
        qos_in.reliability = ReliabilityPolicy.RELIABLE  # match YOLO/MOT
        self.create_subscription(Detection2DArray,
                                 self.get_parameter('det_topic').value,
                                 self._on_dets, qos_in)

        self.cmd_pub = self.create_publisher(Twist, "/gp2/rotate/cmd_body", 10)
        self.hud_pub = self.create_publisher(String, "/gp2/rotate/hud", 10)

        self.get_logger().info("DetectRotate ready (yaw-only Offboard @20 Hz).")
        threading.Thread(target=self._mav_task, daemon=True).start()

    # ---- detection callback
    def _on_dets(self, msg: Detection2DArray):
        img_w = int(self.get_parameter('img_w').value)
        cls = str(self.get_parameter('class_id').value)
        # pick largest 'person'
        best = None
        best_area = 0.0
        for d in msg.detections:
            try:
                if not any(r.hypothesis.class_id == cls for r in d.results):
                    continue
                w = float(d.bbox.size_x); h = float(d.bbox.size_y)
                area = w*h
                if area > best_area:
                    best, best_area = d, area
            except Exception:
                continue
        if best is not None:
            try:
                cx = float(best.bbox.center.x)
            except Exception:
                cx = float(best.bbox.center.position.x)
            with self._lock:
                self._last_cx = cx
                self._last_det_ts = time.time()
                self._lock_score = min(int(self.get_parameter('lock_k').value),
                                       self._lock_score + 1)
        else:
            with self._lock:
                self._lock_score = max(0, self._lock_score - 1)

    # ---- MAVSDK worker (async)
    async def _async_mav(self):
        # --- BEGIN: robust offboard-priming lifted from follow_node (trimmed) ---
        url = self.get_parameter('udp_url').value
        if url.startswith("udpin://:"): url = url.replace("udpin://:", "udpin://0.0.0.0:")
        if url.startswith("udp://:"):   url = url.replace("udp://:",   "udp://0.0.0.0:")

        self.get_logger().info(f"Connecting MAVSDK @ {url}")
        drone = System()
        await drone.connect(system_address=url)

        # watchers (update _is_in_air and _rel_alt)
        async def _watch_in_air():
            async for ia in drone.telemetry.in_air():
                self._is_in_air = bool(ia)

        async def _watch_pos():
            async for p in drone.telemetry.position():
                self._rel_alt = float(p.relative_altitude_m)

        watcher_ia  = asyncio.create_task(_watch_in_air())
        watcher_pos = asyncio.create_task(_watch_pos())

        # wait until connected
        async for s in drone.core.connection_state():
            if s.is_connected:
                self.get_logger().info("PX4 connected.")
                break

        # health gate (timeout 10s)
        self.get_logger().info("Waiting for local position & IMU health…")
        t0 = time.time()
        while True:
            h: Health = await drone.telemetry.health().__anext__()
            if h.is_local_position_ok and h.is_gyrometer_calibration_ok:
                self.get_logger().info("IMU + Local position OK.")
                break
            if time.time() - t0 > 10.0:
                self.get_logger().warn("Health wait timed out, continuing anyway.")
                break
            await asyncio.sleep(0.2)

        # arm
        self.get_logger().info("Arming…")
        await drone.action.arm()

        zero = VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)

        do_auto_takeoff = bool(self.get_parameter('do_auto_takeoff').value)
        takeoff_alt     = float(self.get_parameter('auto_takeoff_alt_m').value)
        takeoff_mode    = str(self.get_parameter('takeoff_mode').value).lower()

        if do_auto_takeoff and takeoff_mode == "action":
            await drone.action.set_takeoff_altitude(takeoff_alt)
            self.get_logger().info(f"Takeoff (Action) to ~{takeoff_alt:.1f} m…")
            await drone.action.takeoff()

            # give PX4 time to switch in-air
            for _ in range(20):
                await asyncio.sleep(0.05)
            t_wait = time.time()
            while not self._is_in_air and (time.time() - t_wait) < 8.0:
                await asyncio.sleep(0.2)

            # prime offboard with zeros, then start (3 retries)
            for _ in range(15):
                await drone.offboard.set_velocity_body(zero)
                await asyncio.sleep(0.05)

            started = False
            for _ in range(3):
                try:
                    await drone.offboard.start()
                    started = True
                    break
                except OffboardError:
                    for _ in range(10):
                        await drone.offboard.set_velocity_body(zero)
                        await asyncio.sleep(0.05)
                    await asyncio.sleep(0.2)
            if not started:
                self.get_logger().error("Offboard start failed after retries.")
                return

            # climb inside Offboard to safe band
            climb_start = time.time()
            while self._rel_alt < self._alt_high and (time.time() - climb_start) < 6.0:
                await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.7, 0.0))
                await asyncio.sleep(0.05)
        else:
            # no action takeoff; start offboard then climb gently
            for _ in range(15):
                await drone.offboard.set_velocity_body(zero)
                await asyncio.sleep(0.05)

            started = False
            for _ in range(3):
                try:
                    await drone.offboard.start()
                    started = True
                    break
                except OffboardError:
                    for _ in range(10):
                        await drone.offboard.set_velocity_body(zero)
                        await asyncio.sleep(0.05)
                    await asyncio.sleep(0.2)
            if not started:
                self.get_logger().error("Offboard start failed after retries.")
                return

            # gentle climb ~3 s (60 * 50ms) to get clear of ground
            for _ in range(60):
                await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.7, 0.0))
                await asyncio.sleep(0.05)
        # --- END: robust offboard-priming ---

        rate_hz = float(self.get_parameter('publish_rate_hz').value)
        dt = 1.0 / max(1.0, rate_hz)
        scan_when_no = bool(self.get_parameter('scan_when_no_target').value)
        
        scan_deg_s = float(self.get_parameter('scan_rate_deg_s').value)
        hfov_rad   = math.radians(float(self.get_parameter('hfov_deg').value))
        k_yaw      = float(self.get_parameter('k_yaw').value)
        kd_yaw     = float(self.get_parameter('kd_yaw').value)
        yaw_max    = float(self.get_parameter('yawrate_max').value)               # rad/s
        dead       = float(self.get_parameter('deadzone').value)
        stale_s    = float(self.get_parameter('stale_s').value)
        invert     = bool(self.get_parameter('invert_ex').value)
        img_w      = int(self.get_parameter('img_w').value)
        scan_when_no = bool(self.get_parameter('scan_when_no_target').value)

        # altitude guard params
        do_alt_guard  = bool(self.get_parameter('alt_guard_enable').value)
        alt_max_m     = float(self.get_parameter('alt_max_m').value)
        alt_db_m      = float(self.get_parameter('alt_deadband_m').value)
        k_z_down      = float(self.get_parameter('k_z_down').value)
        vz_down_max   = float(self.get_parameter('vz_down_max').value)

        # yaw smoothing params
        alpha         = float(self.get_parameter('lpf_alpha').value)
        rate_hz       = float(self.get_parameter('publish_rate_hz').value)
        dt            = 1.0 / max(1.0, rate_hz)
        rate_limit_dps2 = float(self.get_parameter('rate_limit_yaw').value)  # deg/s^2
        center_hold_deg = float(self.get_parameter('center_hold_deg').value)

        self._fsm = S.SEARCH
        while rclpy.ok():
            t0 = time.time()

            with self._lock:
                cx   = self._last_cx
                age  = t0 - self._last_det_ts
                l_th = int(self.get_parameter('lock_k').value)
                locked = (self._lock_score >= l_th)
                lock_score = self._lock_score

            # --- default command (keep Offboard alive) ---
            vx, vy = 0.0, 0.0
            yaw    = 0.0   # rad/s
            reason = "WAIT_NO_TARGET"

            # --- altitude guard (NED down is +) ---
            vz_down = 0.0
            guard_on = False
            if do_alt_guard and (self._rel_alt > (alt_max_m + alt_db_m)):
                guard_on = True
                err_m = self._rel_alt - alt_max_m
                vz_down = min(vz_down_max, max(0.0, k_z_down * err_m))  # push down

            # --- yaw control ---
            if cx is not None and age <= stale_s:
                ex_rad = fov_ex(cx, img_w, hfov_rad, invert=invert)  # error (rad)
                ex_deg = math.degrees(ex_rad)

                # LPF on error
                self._ex_f = (1.0 - alpha) * self._ex_f + alpha * ex_rad
                dex_dt = (self._ex_f - self._prev_ex_f) / max(1e-3, dt)

                # PD yaw (raw), then deadzones/holds
                yaw_raw = k_yaw * self._ex_f + kd_yaw * dex_dt       # rad/s
                if abs(ex_rad) < dead or abs(ex_deg) <= center_hold_deg:
                    yaw_cmd = 0.0
                    reason  = "TRACK_CENTER_HOLD"
                else:
                    yaw_cmd = max(-yaw_max, min(yaw_max, yaw_raw))
                    reason  = "TRACK_PD"

                self._prev_ex_f = self._ex_f
                self._fsm = S.LOCKED if locked else S.SEARCH

            else:
                # no valid target
                if scan_when_no:
                    yaw_cmd = math.radians(scan_deg_s)
                    reason  = "SCAN_NO_TARGET"
                else:
                    yaw_cmd = 0.0
                    reason  = "WAIT_NO_TARGET"
                ex_deg = float('nan')  # not available
                yaw_raw = yaw_cmd

            # --- rate limit yaw (deg/s) for extra damping ---
            yaw_cmd_deg = math.degrees(yaw_cmd)
            max_step = rate_limit_dps2 * dt
            yaw_limited_deg = (
                self._prev_yaw_deg +
                max(-max_step, min(max_step, yaw_cmd_deg - self._prev_yaw_deg))
            )
            self._prev_yaw_deg = yaw_limited_deg
            yaw = math.radians(yaw_limited_deg)  # final yaw (rad/s)

            # --- publish HUD + Twist ---
            # Note: vz_down is NED down (+). For Twist, we show up-positive for human readability.
            tw = Twist()
            tw.linear.x = vx
            tw.linear.y = vy
            tw.linear.z = -vz_down  # up-positive in Twist
            tw.angular.z = yaw
            self.cmd_pub.publish(tw)

            # loop Hz estimate for HUD
            loop_dt = max(1e-3, time.time() - t0)
            self._loop_dt_ema = 0.9 * self._loop_dt_ema + 0.1 * loop_dt
            loop_hz = 1.0 / self._loop_dt_ema

            hud = (
                f"{self._fsm.name} reason={reason} "
                f"age={age:.2f}s cx={'none' if cx is None else f'{cx:.1f}'} "
                f"ex_deg={'nan' if cx is None else f'{ex_deg:+.1f}'} "
                f"yaw_raw={math.degrees(yaw_raw):+.1f} yaw={yaw_limited_deg:+.1f}deg/s "
                f"alt={self._rel_alt:.2f}m guard={int(guard_on)} vz_d={vz_down:.2f}m/s "
                f"lock={lock_score}/{l_th} hz={loop_hz:.1f}"
            )
            self.hud_pub.publish(String(data=hud))

            # --- MAVSDK send (VelocityBodyYawspeed: vx, vy, NED_down, yaw_deg/s) ---
            try:
                await drone.offboard.set_velocity_body(
                    VelocityBodyYawspeed(vx, vy, +vz_down, yaw_limited_deg)
                )
            except OffboardError:
                # keep alive and retry start
                for _ in range(6):
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await asyncio.sleep(0.05)
                try:
                    await drone.offboard.start()
                except OffboardError:
                    pass

            # keep the actual loop at ~rate_hz
            elapsed = time.time() - t0
            await asyncio.sleep(max(0.0, dt - elapsed))


    def _mav_task(self):
        try:
            asyncio.run(self._async_mav())
        except Exception as e:
            self.get_logger().error(f"MAV task error: {e}")

def main():
    rclpy.init()
    n = DetectRotate()
    try:
        rclpy.spin(n)
    finally:
        n.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
