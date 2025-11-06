#!/usr/bin/env python3
import rclpy, cv2, numpy as np, time
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
from cv_bridge import CvBridge

class DebugViz(Node):
    def __init__(self):
        super().__init__('debug_viz')
        self.bridge = CvBridge()
        self.last_tracks = None
        self.last_hud = ""
        self.sub_img = self.create_subscription(Image, '/camera/image_raw', self.on_img, 10)
        self.sub_det = self.create_subscription(Detection2DArray, '/perception/tracks', self.on_det, 10)
        self.sub_hud = self.create_subscription(String, '/gp2/follow/hud', self.on_hud, 10)
        self.pub_dbg = self.create_publisher(Image, '/perception/debug_image', 10)

    def on_det(self, msg):
        self.last_tracks = msg

    def on_hud(self, msg):
        self.last_hud = msg.data

    def on_img(self, msg):
        img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        h, w = img.shape[:2]
        # center crosshair
        cv2.line(img, (w//2, 0), (w//2, h), (0,255,0), 1)
        cv2.line(img, (0, h//2), (w, h//2), (0,255,0), 1)
        # draw detections
        if self.last_tracks:
            for d in self.last_tracks.detections:
                cx = int(d.bbox.center.x); cy = int(d.bbox.center.y)
                bw = int(d.bbox.size_x);   bh = int(d.bbox.size_y)
                x0 = cx - bw//2; y0 = cy - bh//2
                x1 = cx + bw//2; y1 = cy + bh//2
                cv2.rectangle(img, (x0,y0), (x1,y1), (255,0,0), 2)
                try: label = f"id={d.id}"
                except: label = "id=?"
                cv2.putText(img, label, (x0, max(0,y0-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1, cv2.LINE_AA)
        # HUD text
        if self.last_hud:
            cv2.putText(img, self.last_hud[:120], (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 3, cv2.LINE_AA)
            cv2.putText(img, self.last_hud[:120], (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 1, cv2.LINE_AA)

        self.pub_dbg.publish(self.bridge.cv2_to_imgmsg(img, encoding='bgr8'))

def main():
    rclpy.init()
    rclpy.spin(DebugViz())
    rclpy.shutdown()

if __name__ == "__main__":
    main()