# Minimal, dependency-light ByteTrack-style core with ego-motion robustness.
# Contract unchanged: List[Det] -> List[Track].
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Det:
    tlbr: Tuple[float, float, float, float]  # (top,left,bottom,right) in px
    score: float
    cls: int
    ts: float  # monotonic seconds

@dataclass
class Track:
    id: int
    tlbr: Tuple[float, float, float, float]
    score: float
    cls: int
    age: int
    last_ts: float
    missed: int
    # Internal helpers for tiny motion prediction (safe defaults):
    last_cx: float = 0.0
    last_cy: float = 0.0
    prev_cx: float = 0.0
    prev_cy: float = 0.0

def iou_tlbr(a, b) -> float:
    at, al, ab, ar = a
    bt, bl, bb, br = b
    inter_t, inter_l = max(at, bt), max(al, bl)
    inter_b, inter_r = min(ab, bb), min(ar, br)
    w, h = max(0.0, inter_r - inter_l), max(0.0, inter_b - inter_t)
    inter = w * h
    if inter <= 0:
        return 0.0
    area_a = max(0.0, (ab - at)) * max(0.0, (ar - al))
    area_b = max(0.0, (bb - bt)) * max(0.0, (br - bl))
    denom = max(1e-6, (area_a + area_b - inter))
    return inter / denom

def tlbr_center_wh(tlbr):
    t, l, b, r = tlbr
    w = max(0.0, r - l)
    h = max(0.0, b - t)
    cx = l + 0.5 * w
    cy = t + 0.5 * h
    return cx, cy, w, h

def center_wh_to_tlbr(cx, cy, w, h):
    t = cy - 0.5 * h
    l = cx - 0.5 * w
    b = cy + 0.5 * h
    r = cx + 0.5 * w
    return (t, l, b, r)

def expand_tlbr(tlbr, frac: float):
    """Expand bbox by frac (e.g., 0.1 -> +10%) for matching only."""
    cx, cy, w, h = tlbr_center_wh(tlbr)
    w2 = w * (1.0 + frac)
    h2 = h * (1.0 + frac)
    return center_wh_to_tlbr(cx, cy, w2, h2)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

class ByteTrackCore:
    """
    Simplified ByteTrack logic + ego-motion robustness:
      1) High-conf match (IoU) using a slightly expanded track box.
      2) Salvage unmatched tracks with low-conf detections.
      3) New-ID suppression: if a new detection is near an unmatched track, re-attach.
      4) Duplicate removal: if two tracks overlap strongly, keep the older.
      5) Tiny center-motion prediction (1-step) to buy IoU under ego-motion.
      6) Single-target guard: with one track & one det, force-match.
    No external libs, no KF.
    """
    def __init__(self,
                 track_thresh: float = 0.5,
                 conf_low: float = 0.1,
                 match_thresh: float = 0.8,
                 track_buffer: int = 30,
                 max_age_without_det: int = 30,
                 min_box_area_px: float = 400.0,
                 # New, safe defaults (tunable, but fine as-is):
                 match_expand_frac: float = 0.10,
                 new_id_nearby_iou: float = 0.30,
                 new_id_nearby_center_frac: float = 0.15,   # fraction of prev box diag
                 duplicate_merge_iou: float = 0.70,
                 ego_pred_gain: float = 1.0,                # 1-step velocity gain
                 ego_shift_px_max_frac: float = 0.15,       # max shift fraction of box size
                 single_target_force_match: bool = True):
        self._next_id = 1
        self.active: List[Track] = []
        self.track_thresh = float(track_thresh)
        self.conf_low = float(conf_low)
        self.match_thresh = float(match_thresh)
        self.track_buffer = int(track_buffer)
        self.max_age_without_det = int(max_age_without_det)
        self.min_box_area_px = float(min_box_area_px)

        self.match_expand_frac = float(match_expand_frac)
        self.new_id_nearby_iou = float(new_id_nearby_iou)
        self.new_id_nearby_center_frac = float(new_id_nearby_center_frac)
        self.duplicate_merge_iou = float(duplicate_merge_iou)
        self.ego_pred_gain = float(ego_pred_gain)
        self.ego_shift_px_max_frac = float(ego_shift_px_max_frac)
        self.single_target_force_match = bool(single_target_force_match)

    def _new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    @staticmethod
    def _box_area(tlbr) -> float:
        t, l, b, r = tlbr
        return max(0.0, b - t) * max(0.0, r - l)

    def _gate(self, det: Det) -> bool:
        return self._box_area(det.tlbr) >= self.min_box_area_px

    def _iou(self, a, b) -> float:
        return iou_tlbr(a, b)

    def _predicted_tlbr(self, trk: Track) -> Tuple[float,float,float,float]:
        """
        Tiny 1-step center velocity prediction, clamped relative to box size.
        """
        cx, cy, w, h = tlbr_center_wh(trk.tlbr)
        # Initialize history if zeros
        if trk.last_cx == 0.0 and trk.last_cy == 0.0 and trk.prev_cx == 0.0 and trk.prev_cy == 0.0:
            trk.prev_cx = cx; trk.prev_cy = cy
            trk.last_cx = cx; trk.last_cy = cy

        vx = (trk.last_cx - trk.prev_cx) * self.ego_pred_gain
        vy = (trk.last_cy - trk.prev_cy) * self.ego_pred_gain

        # Clamp shift by fraction of box size (avoids overshoot)
        max_dx = max(1.0, self.ego_shift_px_max_frac * max(w, 1.0))
        max_dy = max(1.0, self.ego_shift_px_max_frac * max(h, 1.0))
        dx = clamp(vx, -max_dx, max_dx)
        dy = clamp(vy, -max_dy, max_dy)

        cx_p = cx + dx
        cy_p = cy + dy
        return center_wh_to_tlbr(cx_p, cy_p, w, h)

    def _center_dist(self, a, b) -> float:
        acx, acy, _, _ = tlbr_center_wh(a)
        bcx, bcy, _, _ = tlbr_center_wh(b)
        return ((acx - bcx)**2 + (acy - bcy)**2) ** 0.5

    def _merge_duplicates(self):
        """Keep older track when two overlap strongly."""
        survivors: List[Track] = []
        used = set()
        for i, ti in enumerate(self.active):
            if i in used:
                continue
            keep = ti
            for j, tj in enumerate(self.active):
                if j <= i or j in used:
                    continue
                if self._iou(ti.tlbr, tj.tlbr) >= self.duplicate_merge_iou:
                    # Prefer older (higher age), then lower id
                    if (tj.age > keep.age) or (tj.age == keep.age and tj.id < keep.id):
                        used.add(i)
                        keep = tj
                    else:
                        used.add(j)
            survivors.append(keep)
        self.active = survivors

    def update(self, dets: List[Det]) -> List[Track]:
        # Pre-filter supported class + area
        dets = [d for d in dets if self._gate(d)]
        # Partition by conf
        high = [d for d in dets if d.score >= self.track_thresh]
        low  = [d for d in dets if (self.conf_low <= d.score < self.track_thresh)]

        # Single-target guard: 1 track & 1 det -> force match
        if self.single_target_force_match and len(self.active) == 1 and len(high) == 1:
            trk = self.active[0]
            det = high[0]
            # Update track with det directly
            trk.prev_cx, trk.prev_cy = trk.last_cx, trk.last_cy
            cx, cy, w, h = tlbr_center_wh(det.tlbr)
            trk.last_cx, trk.last_cy = cx, cy
            trk.tlbr = det.tlbr
            trk.score = det.score
            trk.cls = det.cls
            trk.age += 1
            trk.last_ts = det.ts
            trk.missed = 0
            return list(self.active)

        # Build IoU matrix against active (using predicted & expanded boxes)
        pred_boxes = []
        exp_boxes  = []
        for trk in self.active:
            pred = self._predicted_tlbr(trk)
            exp  = expand_tlbr(pred, self.match_expand_frac)
            pred_boxes.append(pred)
            exp_boxes.append(exp)

        iou_mat = {}
        for i, trk in enumerate(self.active):
            iou_mat[i] = {}
            for j, d in enumerate(high):
                iou_mat[i][j] = self._iou(exp_boxes[i], d.tlbr)

        # Stage 1: match high-conf (greedy)
        tracks_idx = list(range(len(self.active)))
        dets_idx = list(range(len(high)))
        matched, u_tracks, u_high = self._greedy_match(tracks_idx, dets_idx, iou_mat, self.match_thresh)

        # Apply matches
        for i, j in matched:
            trk = self.active[i]
            det = high[j]
            # Update history for tiny prediction
            trk.prev_cx, trk.prev_cy = trk.last_cx, trk.last_cy
            cx, cy, w, h = tlbr_center_wh(det.tlbr)
            trk.last_cx, trk.last_cy = cx, cy

            trk.tlbr = det.tlbr
            trk.score = det.score
            trk.cls = det.cls
            trk.age += 1
            trk.last_ts = det.ts
            trk.missed = 0

        # Stage 2: salvage with low-conf for unmatched tracks
        if u_tracks and low:
            iou_mat2 = {}
            for i in u_tracks:
                iou_mat2[i] = {}
                # Use expanded box against low-conf dets too
                for j, d in enumerate(low):
                    iou_mat2[i][j] = self._iou(exp_boxes[i], d.tlbr)
            matched2, u_tracks2, _u_low = self._greedy_match(u_tracks, list(range(len(low))), iou_mat2, self.match_thresh)
            for i, j in matched2:
                trk = self.active[i]
                det = low[j]
                trk.prev_cx, trk.prev_cy = trk.last_cx, trk.last_cy
                cx, cy, w, h = tlbr_center_wh(det.tlbr)
                trk.last_cx, trk.last_cy = cx, cy

                trk.tlbr = det.tlbr
                trk.score = det.score
                trk.cls = det.cls
                trk.age += 1
                trk.last_ts = det.ts
                trk.missed = 0
            u_tracks = u_tracks2

        # Stage 3: new-ID suppression near unmatched tracks
        # If a high-conf det is near any unmatched track (IoU or center distance), attach to that track (reuse ID) instead of minting a new one.
        if u_tracks and u_high:
            # Precompute unmatched track gates
            gate_info = []
            for i in u_tracks:
                tb = self.active[i].tlbr
                cx, cy, w, h = tlbr_center_wh(tb)
                diag = (w**2 + h**2) ** 0.5
                gate_info.append((i, tb, self.new_id_nearby_iou, self.new_id_nearby_center_frac * max(10.0, diag)))

            still_unmatched_high = []
            for j in u_high:
                det = high[j]
                attached = False
                for (i, tb, iou_gate, dist_gate) in gate_info:
                    iou = self._iou(tb, det.tlbr)
                    if iou >= iou_gate or self._center_dist(tb, det.tlbr) <= dist_gate:
                        # Attach to track i
                        trk = self.active[i]
                        trk.prev_cx, trk.prev_cy = trk.last_cx, trk.last_cy
                        cx, cy, w, h = tlbr_center_wh(det.tlbr)
                        trk.last_cx, trk.last_cy = cx, cy

                        trk.tlbr = det.tlbr
                        trk.score = det.score
                        trk.cls = det.cls
                        trk.age += 1
                        trk.last_ts = det.ts
                        trk.missed = 0
                        attached = True
                        # Mark this unmatched track as handled so we don't reuse it again
                        u_tracks = [k for k in u_tracks if k != i]
                        break
                if not attached:
                    still_unmatched_high.append(j)
            u_high = still_unmatched_high

        # Stage 3b: any remaining unmatched high-conf become new tracks
        for j in u_high:
            d = high[j]
            cx, cy, w, h = tlbr_center_wh(d.tlbr)
            self.active.append(Track(
                id=self._new_id(), tlbr=d.tlbr, score=d.score, cls=d.cls,
                age=1, last_ts=d.ts, missed=0, last_cx=cx, last_cy=cy, prev_cx=cx, prev_cy=cy
            ))

        # Stage 4: age unmatched tracks; prune by buffer/age
        survivors: List[Track] = []
        matched_track_indices = set(i for (i, _) in matched)
        for idx, trk in enumerate(self.active):
            if idx in matched_track_indices:
                survivors.append(trk)
                continue
            # If not matched this frame, we already may have attached via suppression; check missed status.
            trk.missed += 1
            trk.age += 1
            if trk.missed <= max(self.track_buffer, self.max_age_without_det):
                survivors.append(trk)
        self.active = survivors

        # Stage 5: duplicate removal (keep older ID)
        if len(self.active) >= 2:
            self._merge_duplicates()

        return list(self.active)

    def _greedy_match(self, tracks_idx, dets_idx, iou_mat, iou_thr):
        matched, u_tracks, u_dets = [], set(tracks_idx), set(dets_idx)
        # Flatten & sort by IoU desc
        pairs = []
        for i in tracks_idx:
            for j in dets_idx:
                pairs.append((iou_mat[i][j], i, j))
        pairs.sort(reverse=True, key=lambda x: x[0])
        taken_t, taken_d = set(), set()
        for val, i, j in pairs:
            if val < iou_thr:
                break
            if i in taken_t or j in taken_d:
                continue
            matched.append((i, j))
            taken_t.add(i); taken_d.add(j)
        u_tracks -= taken_t
        u_dets -= taken_d
        return matched, list(u_tracks), list(u_dets)
