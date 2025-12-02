from typing import List, Tuple
from dataclasses import dataclass
import time

from std_msgs.msg import Header
from vision_msgs.msg import Detection2DArray, Detection2D, BoundingBox2D, ObjectHypothesisWithPose
from .bytetrack_core import Det, Track

# --- Utilities & schema-safe bbox helpers ---

def _tlbr_from_center(cx: float, cy: float, w: float, h: float) -> Tuple[float,float,float,float]:
    t = cy - 0.5*h
    l = cx - 0.5*w
    b = cy + 0.5*h
    r = cx + 0.5*w
    return (t,l,b,r)

def _center_from_tlbr(tlbr) -> Tuple[float,float,float,float]:
    t,l,b,r = tlbr
    w = max(0.0, r-l)
    h = max(0.0, b-t)
    cx = l + 0.5*w
    cy = t + 0.5*h
    return cx, cy, w, h

def _set_bbox_safe(bbox: BoundingBox2D, cx: float, cy: float, w: float, h: float) -> str:
    """
    Try the common generated layout first (Humble): bbox.center.x/y exist.
    If that fails on a user's machine, attempt alternative attribute paths.
    Returns a short string describing the chosen path for logging.
    """
    try:
        bbox.center.x = float(cx)
        bbox.center.y = float(cy)
        bbox.size_x = float(w)
        bbox.size_y = float(h)
        return "bbox.center.xy"
    except Exception:
        # Fallback (rare): some non-standard generators expose center.position.x/y
        try:
            bbox.center.position.x = float(cx)  # type: ignore[attr-defined]
            bbox.center.position.y = float(cy)  # type: ignore[attr-defined]
            bbox.size_x = float(w)
            bbox.size_y = float(h)
            return "bbox.center.position.xy"
        except Exception:
            # Last resort: raise a clear error; node will publish health=RED instead of crashing
            raise RuntimeError("Unable to write BoundingBox2D center; schema mismatch")

# --- Adapters ---

@dataclass
class DetAdapterConfig:
    mot_classes: List[str]
    conf_thres: float

class DetAdapter:
    def __init__(self, cfg: DetAdapterConfig):
        self.cfg = cfg
        self._last_ts = None

    @staticmethod
    def _stamp_to_float(h: Header) -> float:
        return float(h.stamp.sec) + float(h.stamp.nanosec) * 1e-9

    def msg_to_contract(self, msg: Detection2DArray) -> List[Det]:
        ts_ros = self._stamp_to_float(msg.header) if msg and msg.header else time.monotonic()
        # Enforce monotonic ts; if not monotonic, gently extrapolate
        if self._last_ts is None:
            ts = ts_ros
        else:
            ts = ts_ros if ts_ros >= self._last_ts else (self._last_ts + 1e-3)
        self._last_ts = ts

        dets: List[Det] = []
        for det in msg.detections:
            if not det.results:
                continue
            hyp = det.results[0].hypothesis
            cls_name = str(hyp.class_id) if hyp.class_id is not None else ""
            score = float(hyp.score) if hyp.score is not None else 0.0
            if self.cfg.mot_classes and (cls_name not in self.cfg.mot_classes):
                continue
            if score < self.cfg.conf_thres:
                continue

            # center->tlbr robustly
            try:
                cx = float(det.bbox.center.x)
                cy = float(det.bbox.center.y)
            except Exception:
                # Some generators might require 'position'
                cx = float(getattr(det.bbox.center, "position", getattr(det.bbox.center, "pose", None)).x)  # type: ignore
                cy = float(getattr(det.bbox.center, "position", getattr(det.bbox.center, "pose", None)).y)  # type: ignore

            w = float(det.bbox.size_x)
            h = float(det.bbox.size_y)
            tlbr = _tlbr_from_center(cx, cy, w, h)
            dets.append(Det(tlbr=tlbr, score=score, cls=0, ts=ts))  # cls=0 for 'person'
        return dets

class TrackAdapter:
    def __init__(self):
        self._bbox_path = None  # for logging once

    def contract_to_msg(self, tracks: List[Track], frame_id: str, stamp: Header) -> Detection2DArray:
        arr = Detection2DArray()
        arr.header = stamp
        arr.header.frame_id = frame_id
        arr.detections = []
        for trk in tracks:
            det = Detection2D()
            det.header = stamp
            det.header.frame_id = frame_id
            det.bbox = BoundingBox2D()
            cx, cy, w, h = _center_from_tlbr(trk.tlbr)
            if self._bbox_path is None:
                # Probe once; cache path string (used for startup log)
                self._bbox_path = _set_bbox_safe(det.bbox, cx, cy, w, h)
            else:
                _set_bbox_safe(det.bbox, cx, cy, w, h)
            oh = ObjectHypothesisWithPose()
            oh.hypothesis.class_id = f"person#{trk.id}"
            oh.hypothesis.score = float(trk.score)
            det.results.append(oh)
            arr.detections.append(det)
        return arr

    @property
    def bbox_path(self) -> str:
        return self._bbox_path or "unprobed"
