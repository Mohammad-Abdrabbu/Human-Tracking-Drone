#!/usr/bin/env python3
import rclpy, numpy as np, cv2
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from cv_bridge import CvBridge
from ultralytics import YOLO

def set_pose2d_center(pose2d_obj, x, y, theta=0.0):
    if hasattr(pose2d_obj, 'x'):
        pose2d_obj.x = float(x); pose2d_obj.y = float(y); pose2d_obj.theta = float(theta)
    elif hasattr(pose2d_obj, 'position'):
        pose2d_obj.position.x = float(x); pose2d_obj.position.y = float(y); pose2d_obj.theta = float(theta)
    else:
        raise AttributeError("Unknown Pose2D layout")

class YoloDetNode(Node):
    def __init__(self):
        super().__init__('gp2_yolo_det')
        # params
        self.declare_parameter('model_path', '/home/ramadan/gp2/models/yolov8n.pt')
        self.declare_parameter('conf', 0.25)
        self.declare_parameter('imgsz', 416)
        self.declare_parameter('publish_debug_image', True)

        self.model_path = self.get_parameter('model_path').value
        self.conf = float(self.get_parameter('conf').value)
        self.imgsz = int(self.get_parameter('imgsz').value)
        self.pub_dbg = bool(self.get_parameter('publish_debug_image').value)

        self.model = YOLO(self.model_path)
        self.bridge = CvBridge()

        # QoS
        qos_img = QoSProfile(depth=5); qos_img.reliability = ReliabilityPolicy.BEST_EFFORT
        qos_det = QoSProfile(depth=10); qos_det.reliability = ReliabilityPolicy.RELIABLE

        self.sub = self.create_subscription(Image, '/camera/image_raw', self.cb, qos_img)
        self.pub_det = self.create_publisher(Detection2DArray, '/perception/detections', qos_det)
        self.pub_cnt = self.create_publisher(Int32, '/perception/detections_count', 1)
        self.pub_dbg_img = self.create_publisher(Image, '/perception/debug_image', 1) if self.pub_dbg else None

        self.get_logger().info(f'YOLOv8 ready (conf={self.conf}, imgsz={self.imgsz}).')

    def cb(self, msg: Image):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        out = Detection2DArray(); out.header = msg.header

        # Only class 0 (person)
        results = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz, classes=[0], verbose=False)
        count = 0

        # draw on a copy if publishing debug image
        dbg = frame.copy() if self.pub_dbg and self.pub_dbg_img is not None else None

        for r in results:
            if not getattr(r, 'boxes', None):
                continue
            for b in r.boxes:
                x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
                w, h = (x2 - x1), (y2 - y1)
                cx, cy = (x1 + 0.5*w), (y1 + 0.5*h)
                score = float(b.conf.item() if hasattr(b.conf, "item") else float(b.conf))

                det = Detection2D(); det.header = msg.header
                set_pose2d_center(det.bbox.center, cx, cy, 0.0)
                det.bbox.size_x = w; det.bbox.size_y = h

                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = 'person'; hyp.hypothesis.score = score
                det.results.append(hyp)

                out.detections.append(det)
                count += 1

                if dbg is not None:
                    cv2.rectangle(dbg, (int(x1),int(y1)), (int(x2),int(y2)), (0,255,0), 2)
                    cv2.putText(dbg, f"person {score:.2f}", (int(x1), max(0,int(y1)-5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)

        self.pub_det.publish(out)
        self.pub_cnt.publish(Int32(data=count))
        if dbg is not None:
            self.pub_dbg_img.publish(self.bridge.cv2_to_imgmsg(dbg, encoding='bgr8'))

def main():
    rclpy.init()
    node = YoloDetNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
