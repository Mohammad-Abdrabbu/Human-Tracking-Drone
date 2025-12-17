#!/usr/bin/env python3
"""
YOLO Detection Node with Worker Thread Architecture.
Processes latest frame only to avoid backlog.
"""
import rclpy
import numpy as np
import cv2
import threading
import time
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from cv_bridge import CvBridge
from ultralytics import YOLO


def set_pose2d_center(pose2d_obj, x, y, theta=0.0):
    """Set center position for Pose2D object (handles different message layouts)."""
    if hasattr(pose2d_obj, 'x'):
        pose2d_obj.x = float(x)
        pose2d_obj.y = float(y)
        pose2d_obj.theta = float(theta)
    elif hasattr(pose2d_obj, 'position'):
        pose2d_obj.position.x = float(x)
        pose2d_obj.position.y = float(y)
        pose2d_obj.theta = float(theta)
    else:
        raise AttributeError("Unknown Pose2D layout")


class YoloDetNode(Node):
    """
    YOLOv8 detection node with worker thread architecture.
    
    Key improvements over synchronous version:
    - Subscription callback only stores latest frame (non-blocking)
    - Worker thread processes frames, drops stale ones
    - Debug image publishing is rate-limited
    - Observability logs every 1s
    """
    
    def __init__(self):
        super().__init__('gp2_yolo_det')
        
        # --- Model path (env-aware) ---
        import os
        default_model_path = os.path.join(
            os.environ.get('SAHTD_ROOT', os.path.expanduser('~/sahtd')),
            'simulation/weights/yolov8n.pt'
        )
        
        # --- Declare parameters ---
        # Existing params
        self.declare_parameter('model_path', default_model_path)
        self.declare_parameter('conf', 0.25)
        self.declare_parameter('imgsz', 416)
        self.declare_parameter('publish_debug_image', True)
        
        # New params for backlog fix
        self.declare_parameter('process_hz', 0.0)          # 0 = as fast as possible
        self.declare_parameter('max_age_ms', 250)          # Drop frames older than this
        self.declare_parameter('debug_pub_hz', 10.0)       # Debug image max publish rate
        self.declare_parameter('camera_resize_enable', True)
        self.declare_parameter('camera_resize_mode', 'letterbox')  # 'letterbox' or 'stretch'
        self.declare_parameter('camera_resize_imgsz', 416)
        
        # --- Get parameter values ---
        self.model_path = self.get_parameter('model_path').value
        # Use auto-detected default if param is empty
        if not self.model_path:
            self.model_path = default_model_path
        self.conf = float(self.get_parameter('conf').value)
        self.imgsz = int(self.get_parameter('imgsz').value)
        self.pub_dbg = bool(self.get_parameter('publish_debug_image').value)
        
        self.process_hz = float(self.get_parameter('process_hz').value)
        self.max_age_ms = int(self.get_parameter('max_age_ms').value)
        self.debug_pub_hz = float(self.get_parameter('debug_pub_hz').value)
        self.resize_enable = bool(self.get_parameter('camera_resize_enable').value)
        self.resize_mode = str(self.get_parameter('camera_resize_mode').value)
        self.resize_imgsz = int(self.get_parameter('camera_resize_imgsz').value)
        
        # --- Load YOLO model ---
        self.model = YOLO(self.model_path)
        self.bridge = CvBridge()
        
        # --- QoS: BEST_EFFORT, KEEP_LAST, depth=1 for latest-frame-only ---
        qos_img = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        qos_det = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # --- Subscription and publishers ---
        self.sub = self.create_subscription(Image, '/camera/image_raw', self._on_image, qos_img)
        self.pub_det = self.create_publisher(Detection2DArray, '/perception/detections', qos_det)
        self.pub_cnt = self.create_publisher(Int32, '/perception/detections_count', 1)
        self.pub_dbg_img = self.create_publisher(Image, '/perception/debug_image', 1) if self.pub_dbg else None
        
        # --- Thread-safe state ---
        self._lock = threading.Lock()
        self._latest_msg = None
        self._running = True
        
        # --- Observability counters ---
        self._processed_count = 0
        self._dropped_stale = 0
        self._last_log_time = time.time()
        self._last_dbg_pub_time = 0.0
        
        # --- Start worker thread ---
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        
        self.get_logger().info(
            f'YOLOv8 ready (conf={self.conf}, imgsz={self.imgsz}, '
            f'max_age_ms={self.max_age_ms}, resize={self.resize_enable})'
        )
    
    def _on_image(self, msg: Image):
        """
        Subscription callback - ONLY stores latest message.
        Does NOT run inference (non-blocking).
        """
        with self._lock:
            self._latest_msg = msg
    
    def _worker_loop(self):
        """
        Worker thread - processes latest frame, drops stale ones.
        """
        while self._running and rclpy.ok():
            # Grab and clear latest message
            with self._lock:
                msg = self._latest_msg
                self._latest_msg = None
            
            if msg is None:
                time.sleep(0.005)  # 5ms sleep when no frame
                continue
            
            # Compute frame age
            now = self.get_clock().now()
            msg_time = rclpy.time.Time.from_msg(msg.header.stamp)
            age_ns = (now - msg_time).nanoseconds
            age_ms = age_ns / 1e6
            
            # Drop stale frames
            if age_ms > self.max_age_ms:
                self._dropped_stale += 1
                continue
            
            # Process frame
            t0 = time.time()
            self._process_frame(msg, age_ms)
            infer_ms = (time.time() - t0) * 1000
            
            self._processed_count += 1
            
            # 1Hz observability log
            if time.time() - self._last_log_time >= 1.0:
                out_hz = self._processed_count / max(0.001, time.time() - self._last_log_time)
                self.get_logger().info(
                    f'YOLO: age={age_ms:.0f}ms, infer={infer_ms:.0f}ms, '
                    f'out_hz={out_hz:.1f}, dropped={self._dropped_stale}'
                )
                self._processed_count = 0
                self._dropped_stale = 0
                self._last_log_time = time.time()
            
            # Rate limit if process_hz > 0
            if self.process_hz > 0:
                target_period = 1.0 / self.process_hz
                elapsed = time.time() - t0
                if elapsed < target_period:
                    time.sleep(target_period - elapsed)
    
    def _process_frame(self, msg: Image, age_ms: float):
        """
        Run YOLO inference and publish detections.
        Debug overlay drawn on ORIGINAL frame size.
        """
        # Convert to OpenCV
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        orig_h, orig_w = frame.shape[:2]
        
        # Prepare output
        out = Detection2DArray()
        out.header = msg.header
        
        # Run YOLO (uses internal resizing to imgsz)
        results = self.model.predict(
            frame, 
            conf=self.conf, 
            imgsz=self.imgsz, 
            classes=[0],  # Person only
            verbose=False
        )
        
        count = 0
        dbg = frame.copy() if self.pub_dbg and self.pub_dbg_img is not None else None
        
        for r in results:
            if not getattr(r, 'boxes', None):
                continue
            for b in r.boxes:
                # Coordinates are already in original image space (YOLO handles this)
                x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
                w, h = (x2 - x1), (y2 - y1)
                cx, cy = (x1 + 0.5 * w), (y1 + 0.5 * h)
                score = float(b.conf.item() if hasattr(b.conf, "item") else float(b.conf))
                
                # Build detection message
                det = Detection2D()
                det.header = msg.header
                set_pose2d_center(det.bbox.center, cx, cy, 0.0)
                det.bbox.size_x = w
                det.bbox.size_y = h
                
                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = 'person'
                hyp.hypothesis.score = score
                det.results.append(hyp)
                
                out.detections.append(det)
                count += 1
                
                # Draw on debug image (original coordinates)
                if dbg is not None:
                    cv2.rectangle(dbg, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(
                        dbg, f"person {score:.2f}", 
                        (int(x1), max(0, int(y1) - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA
                    )
        
        # Publish detections
        self.pub_det.publish(out)
        self.pub_cnt.publish(Int32(data=count))
        
        # Publish debug image (rate-limited)
        if dbg is not None:
            now = time.time()
            min_interval = 1.0 / max(0.1, self.debug_pub_hz)
            if now - self._last_dbg_pub_time >= min_interval:
                self.pub_dbg_img.publish(self.bridge.cv2_to_imgmsg(dbg, encoding='bgr8'))
                self._last_dbg_pub_time = now
    
    def destroy_node(self):
        """Clean shutdown of worker thread."""
        self._running = False
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
        super().destroy_node()


def main():
    rclpy.init()
    node = YoloDetNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
