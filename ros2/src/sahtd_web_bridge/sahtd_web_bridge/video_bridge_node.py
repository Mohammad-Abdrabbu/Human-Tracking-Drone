#!/usr/bin/env python3
"""
video_bridge_node.py - MJPEG video bridge for web dashboard

Subscribes to a ROS Image topic and serves it as an MJPEG stream over HTTP.
This allows the web frontend to display live video feed without a full WebRTC setup.

HTTP Endpoint: http://0.0.0.0:8001/video
"""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class MJPEGHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MJPEG streaming."""
    
    # Shared reference to the node (set by VideoBridgeNode)
    node: Optional['VideoBridgeNode'] = None
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass
    
    def do_GET(self):
        if self.path == '/video':
            self._stream_mjpeg()
        elif self.path == '/snapshot':
            self._send_snapshot()
        elif self.path == '/':
            self._send_info()
        else:
            self.send_error(404)
    
    def _send_info(self):
        """Send simple info page."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        html = b'''<html><body>
<h1>SAHTD Video Bridge</h1>
<p><a href="/video">MJPEG Stream</a></p>
<p><a href="/snapshot">Snapshot (JPEG)</a></p>
<p><img src="/video" style="max-width:100%;"></p>
</body></html>'''
        self.wfile.write(html)
    
    def _send_snapshot(self):
        """Send current frame as JPEG."""
        if not self.node or self.node.latest_jpeg is None:
            self.send_error(503, 'No frame available')
            return
        
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(self.node.latest_jpeg)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(self.node.latest_jpeg)
    
    def _stream_mjpeg(self):
        """Stream MJPEG to client."""
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        
        try:
            while self.node and self.node.running:
                if self.node.latest_jpeg is not None:
                    frame = self.node.latest_jpeg
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                    self.wfile.flush()
                
                # Target ~15 FPS for streaming
                import time
                time.sleep(0.067)
        except (BrokenPipeError, ConnectionResetError):
            pass


class VideoBridgeNode(Node):
    """ROS node that bridges Image topic to HTTP MJPEG stream."""
    
    def __init__(self):
        super().__init__('video_bridge_node')
        
        # Parameters
        self.declare_parameter('image_topic', '/perception/debug_image_tracks')
        self.declare_parameter('http_port', 8001)
        self.declare_parameter('jpeg_quality', 70)
        
        self.image_topic = self.get_parameter('image_topic').value
        self.http_port = self.get_parameter('http_port').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value
        
        # State
        self.bridge = CvBridge()
        self.latest_jpeg: Optional[bytes] = None
        self.running = True
        self.frame_count = 0
        
        # QoS for image subscription (BEST_EFFORT to match typical image topics)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribe to image topic
        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self._on_image,
            qos
        )
        
        # Start HTTP server in background thread
        self._start_http_server()
        
        self.get_logger().info(
            f'[VideoBridge] Started:\n'
            f'  Image topic: {self.image_topic}\n'
            f'  HTTP port: {self.http_port}\n'
            f'  MJPEG stream: http://0.0.0.0:{self.http_port}/video'
        )
    
    def _on_image(self, msg: Image):
        """Convert ROS Image to JPEG and store for streaming."""
        try:
            # Convert to OpenCV BGR
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Encode to JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
            success, jpeg = cv2.imencode('.jpg', cv_image, encode_params)
            
            if success:
                self.latest_jpeg = jpeg.tobytes()
                self.frame_count += 1
                
                # Log every 100 frames
                if self.frame_count % 100 == 0:
                    self.get_logger().debug(f'[VideoBridge] Processed {self.frame_count} frames')
                    
        except Exception as e:
            self.get_logger().warn(f'[VideoBridge] Image conversion error: {e}')
    
    def _start_http_server(self):
        """Start HTTP server in background thread."""
        MJPEGHandler.node = self
        
        def run_server():
            server = HTTPServer(('0.0.0.0', self.http_port), MJPEGHandler)
            server.timeout = 1.0
            while self.running:
                server.handle_request()
        
        self.http_thread = threading.Thread(target=run_server, daemon=True)
        self.http_thread.start()
    
    def destroy_node(self):
        self.running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VideoBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
