#!/usr/bin/env python3
# follow_node.py (detect + rotate + advance; no strafe)
# Uses ByteTrack tracks for target selection and image-based forward control.
import asyncio, math, time, threading, re

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from std_msgs.msg import String, Int32, Empty
from geometry_msgs.msg import Twist, PoseStamped
from vision_msgs.msg import Detection2DArray
from mavsdk.telemetry import Health
from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed

# Import from new modular components
from .state.fsm import FollowState as S
from .state.zone_classifier import ZoneClassifier
from .utils.geometry import fov_ex
from .controllers.yaw_controller import YawController
from .controllers.range_controller import RangeController
from .controllers.altitude_controller import AltitudeController


# Note: S enum now imported from .state.fsm as FollowState


class FollowNode(Node):
    def __init__(self):
        super().__init__("gp2_follow")

        # --- core I/O ---
        self.declare_parameter('udp_url', 'udpin://0.0.0.0:14540')
        self.declare_parameter('det_topic', '/dev/null')            # keep raw detections off in selection mode
        self.declare_parameter('tracks_topic', '/perception/tracks')
        self.declare_parameter('target_id_topic', '/perception/target_select')
        self.declare_parameter('require_target_selection', True)
        self.declare_parameter('tracks_qos', 'reliable')            # 'reliable' | 'besteffort'

        # --- image geometry ---
        self.declare_parameter('img_w', 1280)
        self.declare_parameter('img_h', 960)
        self.declare_parameter('hfov_deg', 100.0)
        self.declare_parameter('invert_ex', False)

        # --- yaw control ---
        self.declare_parameter('k_yaw', 1.2)            # rad/s per rad
        self.declare_parameter('kd_yaw', 0.0)           # rad/s per rad/s
        self.declare_parameter('lpf_alpha', 0.20)       # 0..1
        self.declare_parameter('deadzone', 0.08)        # rad
        self.declare_parameter('center_hold_deg', 1.5)  # deg
        self.declare_parameter('yawrate_max', 0.5)      # rad/s (conservative)
        self.declare_parameter('rate_limit_yaw', 60.0)  # deg/s^2

        # --- forward control (new) ---
        # Stand-off is controlled by bbox height (pixels). Move forward when too small; stop when near target height.
        self.declare_parameter('stand_off_px', 300.0)   # desired bbox height at stand-off
        self.declare_parameter('max_close_px', 420.0)   # beyond this, never command positive vx
        self.declare_parameter('h_deadband_px', 10.0)   # no vx when |h - stand_off_px| <= deadband
        self.declare_parameter('kx', 0.012)             # m/s per pixel error
        self.declare_parameter('vx_max', 0.5)           # m/s
        self.declare_parameter('rate_limit_vx', 0.15)   # m/s^2 (slew limit) - increased for faster decel
        self.declare_parameter('gate_ex', 0.35)         # rad; only advance when |ex_f| <= gate_ex
        self.declare_parameter('h_lpf_alpha', 0.20)     # bbox height LPF (0..1)
        self.declare_parameter('allow_reverse', False)  # if False, never command negative vx

        # --- BBOX VELOCITY ESTIMATION (for stationary target detection) ---
        self.declare_parameter('h_velocity_lpf_alpha', 0.15)     # LPF for bbox velocity estimation
        self.declare_parameter('stationary_threshold_px_s', 8.0) # below this, target considered stationary
        self.declare_parameter('stationary_stand_off_boost', 80.0)  # extra stand-off (px) when target stationary

        # --- PROXIMITY BRAKE ZONE (force stop near stationary target) ---
        self.declare_parameter('prox_brake_enable', True)        # enable proximity braking
        self.declare_parameter('prox_brake_hf_thresh', 200.0)    # trigger when h_f > this (px)
        self.declare_parameter('prox_brake_vx_max', 0.10)        # max vx when in brake zone (m/s)
        self.declare_parameter('prox_brake_decel_rate', 0.50)    # emergency deceleration (m/s²) - INCREASED

        # --- PROGRESSIVE SPEED CONTROL (reduce speed as target gets closer) ---
        self.declare_parameter('progressive_speed_enable', True)  # enable progressive vx_max
        self.declare_parameter('progressive_hf_start', 80.0)      # h_f where speed reduction starts (px) - earlier taper
        self.declare_parameter('progressive_hf_full', 160.0)      # h_f where speed is minimum (px) - reach min speed earlier
        self.declare_parameter('progressive_vx_min', 0.08)        # minimum vx_max when very close (m/s) - safer approach

        # --- THREE-ZONE CONTROL (Step 1 - FAR/HOVER/NEAR) ---
        self.declare_parameter('zone_hover_lower_px', 150.0)      # Below this = FAR
        self.declare_parameter('zone_hover_upper_px', 185.0)      # Above this (but below near) = transition
        self.declare_parameter('zone_near_px', 220.0)             # Above this = NEAR (no positive vx)
        self.declare_parameter('zone_hover_yaw_deg', 4.0)         # Yaw error must be < this for HOVER
        self.declare_parameter('zone_hover_eR_thresh', 20.0)      # |eR| must be < this for HOVER

        # --- NEAR BACK-OFF (Step 3) ---
        self.declare_parameter('near_backoff_enable', True)       # Enable back-off when too close
        self.declare_parameter('near_backoff_vx', 0.15)           # Max back-off velocity (m/s)
        self.declare_parameter('near_backoff_kx', 0.006)          # Proportional gain (m/s per px overshoot)

        # --- timing / behavior ---
        self.declare_parameter('stale_s', 0.75)
        self.declare_parameter('lock_k', 3)
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('scan_when_no_target', False)
        self.declare_parameter('scan_rate_deg_s', 20.0)

        # --- takeoff + altitude guard ---
        self.declare_parameter('do_auto_takeoff', True)
        self.declare_parameter('auto_takeoff_alt_m', 2.5)
        self.declare_parameter('takeoff_mode', 'action')  # 'action' | 'offboard'
        self.declare_parameter('alt_guard_enable', True)
        self.declare_parameter('alt_max_m', 2.5)
        self.declare_parameter('alt_deadband_m', 0.05)
        self.declare_parameter('k_z_down', 0.8)
        self.declare_parameter('vz_down_max', 0.7)

        # --- altitude hold (new) ---
        self.declare_parameter('alt_hold_enable', True)
        self.declare_parameter('alt_hold_m', 3.0)      # desired altitude (m, AGL)
        self.declare_parameter('k_z_up', 0.8)          # m/s per m (up)
        self.declare_parameter('vz_up_max', 0.7)       # m/s (up)

        

        # --- state ---
        self._is_in_air = False
        self._rel_alt = 0.0
        self._alt_high = max(0.8, 0.5 * float(self.get_parameter('auto_takeoff_alt_m').value))

        self._ex_f = 0.0
        self._prev_ex_f = 0.0
        self._prev_yaw_deg = 0.0
        self._loop_dt_ema = 1/20

        self._lock = threading.Lock()
        self._fsm = S.GROUND
        self._last_det_ts = 0.0
        self._lock_score = 0

        # Track-derived latest center & height for the SELECTED id
        self._last_cx = None
        self._last_h  = None
        self._h_f     = 0.0       # LPF’d bbox height
        self._prev_vx = 0.0

        # Bbox velocity estimation state
        self._h_f_prev = 0.0              # previous filtered bbox height
        self._h_velocity = 0.0            # smoothed bbox height velocity (px/s)
        self._h_velocity_update_time = 0.0  # last time velocity was updated
        self._target_stationary = False   # is target considered stationary?
        self._prox_brake_active = False   # is proximity brake currently active?
        self._zone = "FAR"                # current zone: FAR, HOV, NEAR

        # Initialize zone classifier with default params (will be updated from ROS params)
        self._zone_classifier = ZoneClassifier(
            hover_lower_px=float(self.get_parameter('zone_hover_lower_px').value),
            hover_upper_px=float(self.get_parameter('zone_hover_upper_px').value),
            near_thresh_px=float(self.get_parameter('zone_near_px').value),
            hover_yaw_deg=float(self.get_parameter('zone_hover_yaw_deg').value),
            hover_eR_thresh=float(self.get_parameter('zone_hover_eR_thresh').value)
        )

        # Initialize yaw controller
        self._yaw_ctrl = YawController(
            k_yaw=float(self.get_parameter('k_yaw').value),
            kd_yaw=float(self.get_parameter('kd_yaw').value),
            lpf_alpha=float(self.get_parameter('lpf_alpha').value),
            deadzone=float(self.get_parameter('deadzone').value),
            center_hold_deg=float(self.get_parameter('center_hold_deg').value),
            yawrate_max=float(self.get_parameter('yawrate_max').value),
            rate_limit_deg_s2=float(self.get_parameter('rate_limit_yaw').value)
        )

        # Initialize range controller
        self._range_ctrl = RangeController(
            stand_off_px=float(self.get_parameter('stand_off_px').value),
            kx=float(self.get_parameter('kx').value),
            vx_max=float(self.get_parameter('vx_max').value),
            rate_limit_vx=float(self.get_parameter('rate_limit_vx').value),
            max_close_px=float(self.get_parameter('max_close_px').value),
            h_deadband_px=float(self.get_parameter('h_deadband_px').value),
            allow_reverse=bool(self.get_parameter('allow_reverse').value),
            progressive_enable=bool(self.get_parameter('progressive_speed_enable').value),
            progressive_hf_start=float(self.get_parameter('progressive_hf_start').value),
            progressive_hf_full=float(self.get_parameter('progressive_hf_full').value),
            progressive_vx_min=float(self.get_parameter('progressive_vx_min').value),
            prox_brake_enable=bool(self.get_parameter('prox_brake_enable').value),
            prox_brake_hf_thresh=float(self.get_parameter('prox_brake_hf_thresh').value),
            prox_brake_vx_max=float(self.get_parameter('prox_brake_vx_max').value),
            prox_brake_decel_rate=float(self.get_parameter('prox_brake_decel_rate').value),
            # NEAR back-off (Step 3)
            near_backoff_enable=bool(self.get_parameter('near_backoff_enable').value),
            near_backoff_vx=float(self.get_parameter('near_backoff_vx').value),
            near_backoff_kx=float(self.get_parameter('near_backoff_kx').value)
        )

        # Initialize altitude controller
        self._alt_ctrl = AltitudeController(
            alt_hold_m=float(self.get_parameter('alt_hold_m').value),
            k_z_up=float(self.get_parameter('k_z_up').value),
            k_z_down=float(self.get_parameter('k_z_down').value),
            vz_up_max=float(self.get_parameter('vz_up_max').value),
            vz_down_max=float(self.get_parameter('vz_down_max').value),
            alt_guard_enable=bool(self.get_parameter('alt_guard_enable').value),
            alt_max_m=float(self.get_parameter('alt_max_m').value),
            alt_deadband_m=float(self.get_parameter('alt_deadband_m').value)
        )
        self._alt_ctrl.alt_hold_enable = bool(self.get_parameter('alt_hold_enable').value)

        self._selected_id = None
        self._seen_ids = set()

        self._guard_state = 'NORMAL'
        qos_guard = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=1)
        qos_guard.durability = rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL
        self.create_subscription(String, '/gp2/guard/status', self._on_guard_status, qos_guard)



        # --- pubs/subs ---
        # Tracks QoS
        qos_tracks = QoSProfile(depth=20)
        qos_tracks.history = HistoryPolicy.KEEP_LAST
        tracks_qos_val = str(self.get_parameter('tracks_qos').value).lower()
        qos_tracks.reliability = ReliabilityPolicy.RELIABLE if tracks_qos_val != 'besteffort' else ReliabilityPolicy.BEST_EFFORT

        # Generic RELIABLE for in (we keep dets disabled by pointing to /dev/null)
        qos_in = QoSProfile(depth=20)
        qos_in.history = HistoryPolicy.KEEP_LAST
        qos_in.reliability = ReliabilityPolicy.RELIABLE

        # HUD + command
        self.cmd_pub = self.create_publisher(Twist, "/sahtd/follow/cmd_body", 10)
        self.hud_pub = self.create_publisher(String, "/sahtd/follow/hud", 10)
        self.seen_pub = self.create_publisher(String, "/sahtd/follow/seen_ids", 10)

        qos_pose = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.pose_pub = self.create_publisher(PoseStamped, '/gp2/vehicle/pose_local', qos_pose)

        self._last_pose_pub_time = self.get_clock().now()

        self.get_logger().info(
            'Republishing MAVSDK local pose as ENU → /gp2/vehicle/pose_local '
            '(frame_id=map). Mapping: x=east_m, y=north_m, z=-down_m'
        )

        # Selection
        self.create_subscription(Int32, self.get_parameter('target_id_topic').value, self._on_target_select, QoSProfile(depth=10))

        # Raw dets (disabled in practice by det_topic=/dev/null, but kept for completeness)
        self.create_subscription(Detection2DArray, self.get_parameter('det_topic').value, self._on_dets, qos_in)

        # Tracks
        self.create_subscription(Detection2DArray, self.get_parameter('tracks_topic').value, self._on_tracks, qos_tracks)

        # Reset subscription
        self.reset_sub = self.create_subscription(
            Empty,
            '/sahtd/follow/reset',
            self._on_follow_reset,
            10,
        )

        self.get_logger().info("FollowNode (rotate+advance) ready @20 Hz with altitude guard.")
        threading.Thread(target=self._mav_task, daemon=True).start()

    # (legacy det path; ignored because det_topic=/dev/null)
    def _on_dets(self, msg: Detection2DArray):
        pass

    def _extract_track_id(self, det) -> int | None:
        # Try explicit fields first
        for attr in ('tracking_id', 'id'):
            if hasattr(det, attr):
                try:
                    return int(getattr(det, attr))
                except Exception:
                    pass
        # Fallback: parse int from class_id string like "person#17"
        try:
            for r in det.results:
                s = getattr(r.hypothesis, 'class_id', '')
                m = re.search(r'(\d+)', str(s))
                if m:
                    return int(m.group(1))
        except Exception:
            pass
        return None

    def _on_target_select(self, msg: Int32):
        with self._lock:
            self._selected_id = int(msg.data)
            self._lock_score = 0
            self._last_cx = None
            self._last_h  = None
            self._h_f = 0.0
            self._last_det_ts = 0.0
            self.get_logger().info(f"[follow] selected_id={self._selected_id}")

    def _on_tracks(self, msg: Detection2DArray):
        cur_ids = set()
        sel = self._selected_id
        chosen_cx, chosen_h = None, None

        for d in msg.detections:
            tid = self._extract_track_id(d)
            if tid is not None:
                cur_ids.add(tid)
            if sel is not None and tid == sel:
                # center x
                try:
                    chosen_cx = float(d.bbox.center.x)
                except Exception:
                    chosen_cx = float(d.bbox.center.position.x)
                # height (px)
                try:
                    chosen_h = float(d.bbox.size_y)
                except Exception:
                    chosen_h = None



        # Publish seen IDs for HUD
        ids_str = ",".join(str(i) for i in sorted(cur_ids))
        self.seen_pub.publish(String(data=f"ids={ids_str}" if ids_str else "ids="))
        if sel is not None and chosen_cx is None:
            self.hud_pub.publish(String(data=f"selected={sel} not visible; seen=[{ids_str}]"))

        with self._lock:
            self._seen_ids = cur_ids
            if sel is not None and chosen_cx is not None and chosen_h is not None:
                self._last_cx = chosen_cx
                self._last_h  = max(0.0, chosen_h)
                self._last_det_ts = time.time()
                self._lock_score = min(int(self.get_parameter('lock_k').value), self._lock_score + 1)
            else:
                self._lock_score = max(0, self._lock_score - 1)

    def _on_guard_status(self, msg: String):
        self._guard_state = (msg.data or 'NORMAL').strip()

    def _on_follow_reset(self, msg: Empty):
        """Reset follower state without tearing down MAVSDK connection."""
        with self._lock:
            self._selected_id = None
            self._lock_score = 0
            self._last_cx = None
            self._last_h = None
            self._h_f = 0.0
            self._prev_vx = 0.0
            self._h_f_prev = 0.0
            self._h_velocity = 0.0
            self._h_velocity_update_time = 0.0
            self._target_stationary = False
            self._prox_brake_active = False
            self._zone = "FAR"
            self._ex_f = 0.0
            self._prev_ex_f = 0.0
            self._prev_yaw_deg = 0.0
            self._last_det_ts = 0.0
            self._fsm = S.SEARCH
        self.get_logger().warn('[reset] follow_node state reset to SEARCH; target history cleared')

    # --- NEW: Gate A helper (NED→ENU) ---
    def publish_pose_local_from_ned(self, north_m: float, east_m: float, down_m: float):
        now = self.get_clock().now()
        # (optional) throttle to ~10–20 Hz if your control loop runs faster
        if (now - self._last_pose_pub_time).nanoseconds < int(1e9 / 20):
            return
        self._last_pose_pub_time = now

        ps = PoseStamped()
        ps.header.stamp = now.to_msg()
        ps.header.frame_id = 'map'  # ENU world frame
        ps.pose.position.x = float(east_m)    # ENU X = East
        ps.pose.position.y = float(north_m)   # ENU Y = North
        ps.pose.position.z = float(-down_m)   # ENU Z = Up
        # orientation not required by guard; keep identity
        ps.pose.orientation.w = 1.0
        self.pose_pub.publish(ps)

    # ---- MAVSDK worker (async)
    async def _async_mav(self):
        url = self.get_parameter('udp_url').value
        if url.startswith("udpin://:"): url = url.replace("udpin://:", "udpin://0.0.0.0:")
        if url.startswith("udp://:"):   url = url.replace("udp://:",   "udp://0.0.0.0:")
        self.get_logger().info(f"Connecting MAVSDK @ {url}")

        drone = System()
        await drone.connect(system_address=url)

        async def _watch_in_air():
            async for ia in drone.telemetry.in_air():
                self._is_in_air = bool(ia)

        async def _watch_pos():
            async for p in drone.telemetry.position():
                self._rel_alt = float(p.relative_altitude_m)
        
        # --- NEW: local NED → ENU pose republisher (Gate A) ---
        async def _watch_pvn():
            async for pvn in drone.telemetry.position_velocity_ned():
                try:
                    n = float(pvn.position.north_m)
                    e = float(pvn.position.east_m)
                    d = float(pvn.position.down_m)
                except Exception:
                    continue
                self.publish_pose_local_from_ned(n, e, d)

        watcher_ia  = asyncio.create_task(_watch_in_air())
        watcher_pos = asyncio.create_task(_watch_pos())
        watcher_pvn = asyncio.create_task(_watch_pvn()) 

        # Wait connected
        async for s in drone.core.connection_state():
            if s.is_connected:
                self.get_logger().info("PX4 connected.")
                break

        # Minimal health gate
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

        # Arm
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
            for _ in range(20):
                await asyncio.sleep(0.05)
            t_wait = time.time()
            while not self._is_in_air and (time.time() - t_wait) < 8.0:
                await asyncio.sleep(0.2)
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
            # NEW: climb to the requested takeoff altitude (with small margin)
            target_alt = float(self.get_parameter('auto_takeoff_alt_m').value)
            climb_start = time.time()
            while (self._rel_alt < (target_alt - 0.10)) and (time.time() - climb_start) < 12.0:
                await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.7, 0.0))  # up (NED down negative)
                await asyncio.sleep(0.05)

        else:
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
            for _ in range(60):
                await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, -0.7, 0.0))
                await asyncio.sleep(0.05)

        # --- control loop ---
        rate_hz = float(self.get_parameter('publish_rate_hz').value)
        dt = 1.0 / max(1.0, rate_hz)

        hfov_rad       = math.radians(float(self.get_parameter('hfov_deg').value))
        invert         = bool(self.get_parameter('invert_ex').value)
        k_yaw          = float(self.get_parameter('k_yaw').value)
        kd_yaw         = float(self.get_parameter('kd_yaw').value)
        yaw_max        = float(self.get_parameter('yawrate_max').value)
        dead           = float(self.get_parameter('deadzone').value)
        alpha          = float(self.get_parameter('lpf_alpha').value)
        dead_deg_hold  = float(self.get_parameter('center_hold_deg').value)
        rate_limit_dps2= float(self.get_parameter('rate_limit_yaw').value)
        img_w          = int(self.get_parameter('img_w').value)
        stale_s        = float(self.get_parameter('stale_s').value)

        # forward params
        stand_off_px   = float(self.get_parameter('stand_off_px').value)
        max_close_px   = float(self.get_parameter('max_close_px').value)
        h_deadband_px  = float(self.get_parameter('h_deadband_px').value)
        kx             = float(self.get_parameter('kx').value)
        vx_max         = float(self.get_parameter('vx_max').value)
        rate_limit_vx  = float(self.get_parameter('rate_limit_vx').value)
        gate_ex        = float(self.get_parameter('gate_ex').value)
        h_alpha        = float(self.get_parameter('h_lpf_alpha').value)
        allow_reverse  = bool(self.get_parameter('allow_reverse').value)

        # altitude guard
        do_alt_guard   = bool(self.get_parameter('alt_guard_enable').value)
        alt_max_m      = float(self.get_parameter('alt_max_m').value)
        alt_db_m       = float(self.get_parameter('alt_deadband_m').value)
        k_z_down       = float(self.get_parameter('k_z_down').value)
        vz_down_max    = float(self.get_parameter('vz_down_max').value)

        req_sel        = bool(self.get_parameter('require_target_selection').value)

        self._fsm = S.SEARCH
        while rclpy.ok():
            t0 = time.time()
            # defaults
            vx, vy = 0.0, 0.0
            yaw_cmd = 0.0
            reason = "WAIT_NO_TARGET"

            # read shared state
            with self._lock:
                cx = self._last_cx
                h  = self._last_h
                age = t0 - self._last_det_ts
                l_th = int(self.get_parameter('lock_k').value)
                locked = (self._lock_score >= l_th)
                lock_score = self._lock_score
                sel_id = self._selected_id

            # altitude guard (NED down is +)
            vz_down = 0.0
            guard_on = False
            if do_alt_guard and (self._rel_alt > (alt_max_m + alt_db_m)):
                guard_on = True
                err_m = self._rel_alt - alt_max_m
                vz_down = min(vz_down_max, max(0.0, k_z_down * err_m))

            # selection gate
            if req_sel and (sel_id is None):
                yaw_cmd = 0.0
                ex_deg = float('nan')
                yaw_raw = 0.0
                reason = "WAIT_FOR_SELECTION"
                self._fsm = S.SEARCH
            else:
                # ---- YAW control using YawController ----
                if cx is not None and age <= stale_s:
                    ex_rad = fov_ex(cx, img_w, hfov_rad, invert=invert)
                    ex_deg = math.degrees(ex_rad)
                    ex_normalized = ex_rad / (hfov_rad * 0.5)  # Normalize to [-1, 1]

                    # Use YawController for filtered PD control
                    yaw_cmd = self._yaw_ctrl.compute(ex_normalized, dt)
                    
                    # Sync internal state for HUD/debug
                    self._ex_f = self._yaw_ctrl.filtered_error
                    
                    # Determine reason based on yaw command
                    if yaw_cmd == 0.0:
                        reason = "TRACK_CENTER_HOLD"
                    else:
                        reason = "TRACK_PD"
                    yaw_raw = yaw_cmd

                    self._prev_ex_f = self._ex_f
                    self._fsm = S.LOCKED if locked else S.SEARCH
                else:
                    if bool(self.get_parameter('scan_when_no_target').value) and (not req_sel or sel_id is not None):
                        yaw_cmd = math.radians(float(self.get_parameter('scan_rate_deg_s').value))
                        reason = "SCAN_NO_TARGET"
                    else:
                        yaw_cmd = 0.0
                        reason = "WAIT_NO_TARGET"
                    ex_deg = float('nan')
                    yaw_raw = yaw_cmd

                # ---- FORWARD control (gated by centering & visibility) ----
                if cx is not None and h is not None and age <= stale_s and locked:
                    # height LPF
                    self._h_f = (1.0 - h_alpha) * self._h_f + h_alpha * h

                    # --- BBOX VELOCITY ESTIMATION ---
                    # Compute time delta since last update
                    now_sec = time.time()
                    h_vel_dt = now_sec - self._h_velocity_update_time if self._h_velocity_update_time > 0 else dt
                    h_vel_dt = max(0.01, min(0.5, h_vel_dt))  # clamp to avoid crazy values

                    # Compute instantaneous bbox velocity (px/s)
                    if self._h_f_prev > 0:
                        h_velocity_raw = (self._h_f - self._h_f_prev) / h_vel_dt
                    else:
                        h_velocity_raw = 0.0

                    # LPF the velocity
                    h_vel_alpha = float(self.get_parameter('h_velocity_lpf_alpha').value)
                    self._h_velocity = (1.0 - h_vel_alpha) * self._h_velocity + h_vel_alpha * h_velocity_raw

                    # Update state for next iteration
                    self._h_f_prev = self._h_f
                    self._h_velocity_update_time = now_sec

                    # Determine if target is stationary
                    stationary_thresh = float(self.get_parameter('stationary_threshold_px_s').value)
                    self._target_stationary = abs(self._h_velocity) < stationary_thresh

                    # ADAPTIVE STAND-OFF: increase when target is stationary
                    if self._target_stationary:
                        boost = float(self.get_parameter('stationary_stand_off_boost').value)
                        effective_stand_off = stand_off_px + boost
                    else:
                        effective_stand_off = stand_off_px

                    eR = effective_stand_off - self._h_f

                    # --- THREE-ZONE CLASSIFICATION (using ZoneClassifier module) ---
                    ex_rad_for_zone = abs(self._ex_f * math.pi)  # _ex_f is normalized [-1,1]
                    self._zone = self._zone_classifier.classify(self._h_f, ex_rad_for_zone, eR)

                    centered_ok = abs(self._ex_f) <= gate_ex

                    # --- VX CONTROL using RangeController ---
                    # Controller handles zone-aware control, progressive speed, and proximity braking
                    vx_limited = self._range_ctrl.compute(
                        h_f=self._h_f,
                        zone=self._zone,
                        centered_ok=centered_ok,
                        effective_stand_off=effective_stand_off,
                        dt=dt
                    )
                    
                    # Sync proximity brake state for HUD
                    self._prox_brake_active = (
                        self._range_ctrl.prox_brake_enable and 
                        self._h_f > self._range_ctrl.prox_brake_hf_thresh
                    )

                    vx = vx_limited
                    self._prev_vx = vx_limited
                else:
                    # no target / not centered / not locked -> decay vx to 0 with slew
                    max_dv = rate_limit_vx * dt
                    vx_limited = self._prev_vx + max(-max_dv, min(max_dv, 0.0 - self._prev_vx))
                    if not allow_reverse:
                        vx_limited = max(0.0, vx_limited)
                    vx = vx_limited
                    self._prev_vx = vx_limited

            # yaw rate limit (deg/s^2) on final command
            yaw_cmd_deg = math.degrees(yaw_cmd)
            max_step = rate_limit_dps2 * dt
            yaw_limited_deg = self._prev_yaw_deg + max(-max_step, min(max_step, yaw_cmd_deg - self._prev_yaw_deg))
            self._prev_yaw_deg = yaw_limited_deg
            yaw_final = math.radians(yaw_limited_deg)

            # --- Geo-Guard clamp ---
            if self._guard_state in ('GEOGUARD_HOLD', 'GEOGUARD_VIOLATION'):
                vx = 0.0
                if self._guard_state == 'GEOGUARD_VIOLATION':
                    # optional: freeze slewing toward zero so we don't "spring" forward on release
                    self._prev_vx = 0.0

            # --- Vertical (altitude) control using AltitudeController ---
            # Controller returns positive = up, but MAVSDK uses NED (positive = down)
            vz_enu = self._alt_ctrl.compute(self._rel_alt)
            vz_cmd = -vz_enu  # Convert ENU (up+) to NED (down+)

            # Publish Twist (ROS) and send MAVSDK velocity (Body frame)
            tw = Twist()
            tw.linear.x = vx
            tw.linear.y = 0.0
            tw.linear.z = vz_cmd
            tw.angular.z = yaw_final
            self.cmd_pub.publish(tw)

            loop_dt = max(1e-3, time.time() - t0)
            self._loop_dt_ema = 0.9 * self._loop_dt_ema + 0.1 * loop_dt
            loop_hz = 1.0 / self._loop_dt_ema

            # Compute effective eR for HUD (with stationary boost if applicable)
            if self._target_stationary:
                boost = float(self.get_parameter('stationary_stand_off_boost').value)
                hud_eR = (stand_off_px + boost) - self._h_f
            else:
                hud_eR = stand_off_px - self._h_f

            stat_flag = 'S' if self._target_stationary else 'M'  # S=stationary, M=moving
            brake_flag = 'PB' if self._prox_brake_active else ''  # PB=proximity brake

            hud = (
                f"{self._fsm.name} ex_deg={'nan' if 'ex_deg' not in locals() else f'{ex_deg:+.1f}'} "
                f"yaw={yaw_limited_deg:+.1f}deg/s "
                f"h_f={self._h_f:.1f}px eR={hud_eR:+.1f}px vx={vx:+.2f}m/s "
                f"Z={self._zone} [{stat_flag}]{brake_flag} "
                f"lock={lock_score}/{l_th} age={age:.2f}s hz={loop_hz:.1f}"
                f" alt={self._rel_alt:.2f}m"
            )
            self.hud_pub.publish(String(data=hud))

            try:
                await drone.offboard.set_velocity_body(VelocityBodyYawspeed(vx, 0.0, 0.0, yaw_limited_deg))
            except OffboardError:
                for _ in range(6):
                    await drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await asyncio.sleep(0.05)
                try:
                    await drone.offboard.start()
                except OffboardError:
                    pass

            # loop pacing
            elapsed = time.time() - t0
            await asyncio.sleep(max(0.0, dt - elapsed))

    def _mav_task(self):
        try:
            asyncio.run(self._async_mav())
        except Exception as e:
            self.get_logger().error(f"MAV task error: {e}")


def main():
    rclpy.init()
    n = FollowNode()
    try:
        rclpy.spin(n)
    finally:
        n.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
