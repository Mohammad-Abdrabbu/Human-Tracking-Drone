#!/usr/bin/env python3
import math, time
from typing import List
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from .bytetrack_core import ByteTrackCore, Det, Track
from .bytetrack_adapters import DetAdapter, DetAdapterConfig, TrackAdapter

class IoUFallback:
    """Tiny degraded-mode tracker: greedy IoU across last output."""
    def __init__(self, match_thresh: float = 0.5, min_box_area_px: float = 400.0):
        self.match_thresh = float(match_thresh)
        self.min_box_area_px = float(min_box_area_px)
        self.prev: List[Track] = []

    @staticmethod
    def _iou(a, b):
        at, al, ab, ar = a
        bt, bl, bb, br = b
        inter_t, inter_l = max(at, bt), max(al, bl)
        inter_b, inter_r = min(ab, bb), min(ar, br)
        w, h = max(0.0, inter_r - inter_l), max(0.0, inter_b - inter_t)
        inter = w * h
        if inter <= 0: return 0.0
        area_a = (ab-at)*(ar-al); area_b = (bb-bt)*(br-bl)
        return inter / max(1e-6, (area_a+area_b-inter))

    def update(self, dets: List[Det]) -> List[Track]:
        # Filter tiny boxes
        dets = [d for d in dets if (d.ts and (max(0.0, d.tlbr[3]-d.tlbr[1]) * max(0.0, d.tlbr[2]-d.tlbr[0]) >= self.min_box_area_px))]
        if not self.prev:
            tracks = []
            nid = 1
            for d in dets:
                tracks.append(Track(id=nid, tlbr=d.tlbr, score=d.score, cls=d.cls, age=1, last_ts=d.ts, missed=0))
                nid += 1
            self.prev = tracks
            return tracks
        # Greedy match
        matched = set()
        out = []
        used_prev = set()
        for d in dets:
            best_iou, best_idx = 0.0, -1
            for i, t in enumerate(self.prev):
                iou = self._iou(t.tlbr, d.tlbr)
                if iou > best_iou:
                    best_iou, best_idx = iou, i
            if best_iou >= self.match_thresh:
                t = self.prev[best_idx]
                t.tlbr = d.tlbr
                t.score = d.score
                t.cls = d.cls
                t.age += 1
                t.last_ts = d.ts
                t.missed = 0
                out.append(t)
                used_prev.add(best_idx)
            else:
                # new id beyond current max
                nid = (max([t.id for t in self.prev], default=0) + 1)
                out.append(Track(id=nid, tlbr=d.tlbr, score=d.score, cls=d.cls, age=1, last_ts=d.ts, missed=0))
        # carry over unmatched with one miss
        for i, t in enumerate(self.prev):
            if i not in used_prev:
                t.missed += 1
                out.append(t)
        self.prev = out
        return out

class ByteTrackNode(Node):
    def __init__(self):
        super().__init__('bytetrack_node')

        # --- Params ---
        self.declare_parameter('detections_topic', '/perception/detections')
        self.declare_parameter('tracks_topic', '/perception/tracks')
        self.declare_parameter('seen_ids_topic', '/perception/seen_ids')
        self.declare_parameter('diagnostics_topic', '/perception/diagnostics')
        self.declare_parameter('mot_classes', ['person'])
        self.declare_parameter('conf_thres', 0.30)
        self.declare_parameter('track_thresh', 0.50)
        self.declare_parameter('match_thresh', 0.80)
        self.declare_parameter('track_buffer', 30)
        self.declare_parameter('max_age_without_det', 30)
        self.declare_parameter('min_box_area_px', 400.0)
        self.declare_parameter('fps_min', 10.0)
        self.declare_parameter('debug_image_enable', False)  # quarantined

        self.detections_topic = self.get_parameter('detections_topic').get_parameter_value().string_value
        self.tracks_topic = self.get_parameter('tracks_topic').get_parameter_value().string_value
        self.seen_ids_topic = self.get_parameter('seen_ids_topic').get_parameter_value().string_value
        self.diagnostics_topic = self.get_parameter('diagnostics_topic').get_parameter_value().string_value

        mot_classes = [str(s) for s in self.get_parameter('mot_classes').get_parameter_value().string_array_value]
        conf_thres = float(self.get_parameter('conf_thres').value)
        track_thresh = float(self.get_parameter('track_thresh').value)
        match_thresh = float(self.get_parameter('match_thresh').value)
        track_buffer = int(self.get_parameter('track_buffer').value)
        max_age_without_det = int(self.get_parameter('max_age_without_det').value)
        min_box_area_px = float(self.get_parameter('min_box_area_px').value)
        self.fps_min = float(self.get_parameter('fps_min').value)

        # --- QoS profiles ---
        qos_sub = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST)
        qos_pub_rel = QoSProfile(depth=20, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
        qos_pub_rel_latched = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
        qos_pub_rel_latched.durability = DurabilityPolicy.TRANSIENT_LOCAL  # diagnostics latch

        # --- Adapters & cores ---
        self.det_adapter = DetAdapter(DetAdapterConfig(mot_classes=mot_classes, conf_thres=conf_thres))
        self.track_adapter = TrackAdapter()
        self.core = ByteTrackCore(track_thresh=track_thresh,
                                  conf_low=0.10,
                                  match_thresh=match_thresh,
                                  track_buffer=track_buffer,
                                  max_age_without_det=max_age_without_det,
                                  min_box_area_px=min_box_area_px)
        self.fallback = IoUFallback(match_thresh=max(0.5, match_thresh*0.8), min_box_area_px=min_box_area_px)

        # --- Publishers/Subscribers ---
        self.pub_tracks = self.create_publisher(Detection2DArray, self.tracks_topic, qos_pub_rel)
        self.pub_seen = self.create_publisher(String, self.seen_ids_topic, qos_pub_rel)
        self.pub_diag = self.create_publisher(String, self.diagnostics_topic, qos_pub_rel_latched)
        self.sub = self.create_subscription(Detection2DArray, self.detections_topic, self._cb_dets, qos_sub)

        # --- State ---
        self.mode = "CORE"  # "CORE" or "DEGRADED"
        self._ema_fps = None
        self._last_ts = None
        self._printed_schema = False
        self._health("GREEN", "ByteTrack: initialized (Ultralytics-agnostic core).")

    def _health(self, level: str, msg: str):
        s = String()
        s.data = f"[{level}] {msg}"
        self.pub_diag.publish(s)
        if level in ("YELLOW", "RED"):
            self.get_logger().warn(s.data)
        else:
            self.get_logger().info(s.data)

    def _update_fps(self, ts: float):
        if self._last_ts is None:
            self._last_ts = ts
            return
        dt = max(1e-6, ts - self._last_ts)
        fps = 1.0 / dt
        self._ema_fps = fps if self._ema_fps is None else (0.9*self._ema_fps + 0.1*fps)
        self._last_ts = ts
        # Mode switch
        if self._ema_fps is not None and self._ema_fps < self.fps_min:
            if self.mode != "DEGRADED":
                self.mode = "DEGRADED"
                self._health("YELLOW", f"Detector FPS low ({self._ema_fps:.1f} < {self.fps_min}); switching to IoU fallback.")
        else:
            if self.mode != "CORE" and self._ema_fps and self._ema_fps >= self.fps_min:
                self.mode = "CORE"
                self._health("GREEN", f"Detector FPS recovered ({self._ema_fps:.1f} >= {self.fps_min}); returning to ByteTrack core.")

    def _cb_dets(self, msg: Detection2DArray):
        dets: List[Det] = self.det_adapter.msg_to_contract(msg)
        ts = float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9 if msg and msg.header else time.monotonic()
        self._update_fps(ts)

        # Run chosen mode
        if self.mode == "CORE":
            tracks = self.core.update(dets)
        else:
            tracks = self.fallback.update(dets)

        # Convert & publish
        out = self.track_adapter.contract_to_msg(tracks, frame_id=msg.header.frame_id, stamp=msg.header)
        self.pub_tracks.publish(out)

        # Seen IDs (HUD/debug)
        ids = ",".join(str(t.id) for t in tracks if t.missed == 0)
        s = String()
        s.data = f"ids={ids}" if ids else "ids="
        self.pub_seen.publish(s)

        # One-time schema log
        if not self._printed_schema and self.track_adapter.bbox_path != "unprobed":
            self._printed_schema = True
            self._health("GREEN", f"Publisher bbox path: {self.track_adapter.bbox_path}; QoS out: RELIABLE depth=20; mode={self.mode}")

def main():
    rclpy.init()
    node = ByteTrackNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
