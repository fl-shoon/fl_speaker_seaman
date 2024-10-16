import cv2
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import time

class CameraStream:
    def __init__(self):
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.frame = None
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()

    def _capture_loop(self):
        while True:
            ret, self.frame = self.camera.read()
            if not ret:
                break
            time.sleep(0.01)

    def get_frame(self):
        return self.frame

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                <head>
                    <title>Raspberry Pi Camera Stream</title>
                </head>
                <body>
                    <h1>Raspberry Pi Camera Stream</h1>
                    <img src="/stream" width="640" height="480" />
                </body>
                </html>
            ''')
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    frame = camera_stream.get_frame()
                    if frame is not None:
                        _, jpeg = cv2.imencode('.jpg', frame)
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', len(jpeg))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                    else:
                        time.sleep(0.1)
            except Exception as e:
                print(f"Removed streaming client: {str(e)}")
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

camera_stream = CameraStream()

def run_server():
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    print(f'Starting server on port 8000')
    server.serve_forever()

if __name__ == '__main__':
    run_server()