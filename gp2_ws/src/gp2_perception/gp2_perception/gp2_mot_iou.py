#!/usr/bin/env python3
import rclpy, time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from std_msgs.msg import Int32
from std_srvs.srv import Trigger

# ---------- Pose2D helpers (vision_msgs Pose2D uses position.{x,y} + theta) ----------
def get_center_xy(det: Detection2D) -> Tuple[float, float]:
    c = det.bbox.center
    if hasattr(c, "x"):                         # geometry_msgs/Pose2D layout
        return float(c.x), float(c.y)
    elif hasattr(c, "position"):                # vision_msgs/Pose2D layout
        return float(c.position.x), float(c.position.y)
    raise AttributeError("Unknown Pose2D layout in bbox.center")

def set_center_xy(det: Detection2D, x: float, y: float, theta: float = 0.0):
    c = det.bbox.center
    if hasattr(c, "x"):
        c.x, c.y, c.theta = float(x), float(y), float(theta)
    elif hasattr(c, "position"):
        c.position.x, c.position.y, c.theta = float(x), float(y), float(theta)
    else:
        raise AttributeError("Unknown Pose2D layout in bbox.center")

def det_to_xyxy(det: Detection2D) -> Tuple[float, float, float, float]:
    cx, cy = get_center_xy(det)
    w, h = float(det.bbox.size_x), float(det.bbox.size_y)
    x1, y1 = cx - w * 0.5, cy - h * 0.5
    x2, y2 = cx + w * 0.5, cy + h * 0.5
    return x1, y1, x2, y2

def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    if inter <= 0.0: return 0.0
    area_a = max(0.0, (ax2 - ax1)) * max(0.0, (ay2 - ay1))
    area_b = max(0.0, (bx2 - bx1)) * max(0.0, (by2 - by1))
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0

# ---------- simple track struct ----------
@dataclass
class Track:
    tid: int
    xyxy: Tuple[float,float,float,float]
    last_ts: float
    hits: int = 1
    misses: int = 0

# ---------- Node ----------
class MotNode(Node):
    def __init__(self):
        super().__init__('gp2_mot')

        # params
        self.declare_parameter('iou_threshold', 0.3)
        self.declare_parameter('max_missed',   15)
        self.declare_parameter('min_hits',     2)
        self.declare_parameter('class_id',     'person')

        self.iou_thr   = float(self.get_parameter('iou_threshold').value)
        self.max_missed= int(self.get_parameter('max_missed').value)
        self.min_hits  = int(self.get_parameter('min_hits').value)
        self.cls       = str(self.get_parameter('class_id').value)

        # QoS
        qos_in = QoSProfile(depth=20)
        qos_in.history = HistoryPolicy.KEEP_LAST
        qos_in.reliability = ReliabilityPolicy.RELIABLE

        qos_out = QoSProfile(depth=20)
        qos_out.history = HistoryPolicy.KEEP_LAST
        qos_out.reliability = ReliabilityPolicy.RELIABLE

        # I/O
        self.sub_dets = self.create_subscription(Detection2DArray, '/perception/detections', self.cb, qos_in)
        self.pub_trks = self.create_publisher(Detection2DArray, '/perception/tracks', qos_out)

        # target designate via topic + clear via service
        self.active_id = -1
        self.pub_target = self.create_publisher(Int32, '/perception/target_state', 1)
        self.sub_select = self.create_subscription(Int32, '/perception/target_select',
                                                   self._on_target_select, 10)
        self.srv_clear  = self.create_service(Trigger, '/perception/target_clear',
                                              self._on_target_clear)

        # tracker state
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}

        self.get_logger().info('MOT ready (IoU association). Use /perception/target_select (Int32).')

    # --- target handlers ---
    def _on_target_select(self, msg: Int32):
        self.active_id = int(msg.data)
        self.pub_target.publish(Int32(data=self.active_id))
        self.get_logger().info(f"Designated target_id={self.active_id}")

    def _on_target_clear(self, req, res):
        self.active_id = -1
        self.pub_target.publish(Int32(data=self.active_id))
        res.success = True
        res.message = "Cleared target"
        self.get_logger().info("Cleared target")
        return res

    # --- main callback ---
    def cb(self, msg: Detection2DArray):
        ts = self.get_clock().now().nanoseconds / 1e9
        dets = [d for d in msg.detections if any(r.hypothesis.class_id == self.cls for r in d.results)]

        track_ids = list(self.tracks.keys())
        track_boxes = [self.tracks[tid].xyxy for tid in track_ids]
        det_boxes = [det_to_xyxy(d) for d in dets]

        matches: List[Tuple[int,int]] = []
        unmatched_tracks = set(range(len(track_ids)))
        unmatched_dets = set(range(len(det_boxes)))

        if track_boxes and det_boxes:
            scored = []
            for ti, tb in enumerate(track_boxes):
                for di, db in enumerate(det_boxes):
                    scored.append((iou(tb, db), ti, di))
            scored.sort(key=lambda x: x[0], reverse=True)
            used_t, used_d = set(), set()
            for s, ti, di in scored:
                if s < self.iou_thr or ti in used_t or di in used_d:
                    continue
                matches.append((ti, di))
                used_t.add(ti); used_d.add(di)
            unmatched_tracks -= used_t
            unmatched_dets   -= used_d

        # update matched
        for ti, di in matches:
            tid = track_ids[ti]
            self.tracks[tid].xyxy = det_boxes[di]
            self.tracks[tid].last_ts = ts
            self.tracks[tid].hits += 1
            self.tracks[tid].misses = 0

        # age unmatched
        for ti in list(unmatched_tracks):
            tid = track_ids[ti]
            tr = self.tracks[tid]
            tr.misses += 1
            if tr.misses > self.max_missed:
                del self.tracks[tid]

        # create for unmatched detections
        for di in list(unmatched_dets):
            self.tracks[self.next_id] = Track(
                tid=self.next_id, xyxy=det_boxes[di], last_ts=ts, hits=1, misses=0
            )
            self.next_id += 1

        # publish as Detection2DArray with id=<track_id>
        out = Detection2DArray()
        out.header = msg.header
        for tid, tr in self.tracks.items():
            x1, y1, x2, y2 = tr.xyxy
            w, h = (x2 - x1), (y2 - y1)
            cx, cy = (x1 + 0.5*w), (y1 + 0.5*h)

            d = Detection2D()
            d.header = msg.header
            set_center_xy(d, cx, cy, 0.0)
            d.bbox.size_x = w
            d.bbox.size_y = h
            d.id = str(tid)

            hyp = ObjectHypothesisWithPose()
            hyp.hypothesis.class_id = self.cls
            hyp.hypothesis.score = 1.0
            d.results.append(hyp)

            out.detections.append(d)
        self.pub_trks.publish(out)

def main():
    rclpy.init()
    node = MotNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
