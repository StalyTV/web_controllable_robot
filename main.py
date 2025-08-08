#!/usr/bin/env python3
"""
Minimalistic Web-Controllable Robot with Video Streaming
Optimized for Raspberry Pi with low latency and minimal computation
"""

import io
import time
import threading
from flask import Flask, render_template_string, Response
try:
    from picamera2 import Picamera2
    from picamera2.encoders import JpegEncoder
    from picamera2.outputs import FileOutput
    PICAMERA_AVAILABLE = True
except ImportError:
    import cv2
    PICAMERA_AVAILABLE = False
    print("PiCamera2 not available, using OpenCV as fallback")

app = Flask(__name__)

class StreamingOutput(io.BufferedIOBase):
    """Thread-safe streaming output for camera frames"""
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class VideoCamera:
    """Minimalistic video camera handler"""
    def __init__(self):
        self.output = StreamingOutput()
        
        if PICAMERA_AVAILABLE:
            # Use PiCamera2 for Raspberry Pi (most efficient)
            self.camera = Picamera2()
            # Configure for low latency streaming
            config = self.camera.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                lores={"size": (320, 240), "format": "YUV420"}
            )
            self.camera.configure(config)
            
            # Use hardware JPEG encoder for minimal CPU usage
            self.encoder = JpegEncoder(q=70)  # Quality 70 for balance of size/quality
            self.camera.start_recording(self.encoder, FileOutput(self.output))
        else:
            # Fallback to OpenCV (for development/testing)
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self._start_opencv_capture()

    def _start_opencv_capture(self):
        """Start OpenCV capture in separate thread"""
        def capture_frames():
            while True:
                ret, frame = self.camera.read()
                if ret:
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    self.output.write(buffer.tobytes())
                time.sleep(0.033)  # ~30 FPS
        
        thread = threading.Thread(target=capture_frames, daemon=True)
        thread.start()

    def get_frame(self):
        """Get latest frame for streaming"""
        with self.output.condition:
            self.output.condition.wait()
            frame = self.output.frame
        return frame

    def close(self):
        """Clean up camera resources"""
        if PICAMERA_AVAILABLE:
            self.camera.stop_recording()
            self.camera.close()
        else:
            self.camera.release()

# Initialize camera
camera = VideoCamera()

def generate_frames():
    """Generator function for video streaming"""
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    """Main control interface"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Web Controllable Robot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: #f0f0f0;
            text-align: center;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .video-container { 
            margin: 20px 0; 
            border: 2px solid #ddd; 
            border-radius: 10px; 
            overflow: hidden;
        }
        #videoStream { 
            width: 100%; 
            height: auto; 
            display: block;
        }
        .controls { 
            margin: 20px 0; 
        }
        .control-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            max-width: 300px;
            margin: 20px auto;
        }
        .control-btn {
            padding: 15px;
            font-size: 18px;
            border: none;
            border-radius: 5px;
            background: #007bff;
            color: white;
            cursor: pointer;
            transition: background 0.2s;
        }
        .control-btn:hover { background: #0056b3; }
        .control-btn:active { background: #003d82; }
        .status { 
            margin: 10px 0; 
            padding: 10px; 
            background: #e9f7ef; 
            border-radius: 5px; 
        }
        h1 { color: #333; margin-bottom: 10px; }
        .info { color: #666; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Web Controllable Robot</h1>
        <p class="info">Live video stream with robot controls</p>
        
        <div class="video-container">
            <img id="videoStream" src="{{ url_for('video_feed') }}" alt="Robot Camera Feed">
        </div>
        
        <div class="controls">
            <h3>Robot Controls</h3>
            <div class="control-grid">
                <div></div>
                <button class="control-btn" onclick="sendCommand('forward')">↑ Forward</button>
                <div></div>
                
                <button class="control-btn" onclick="sendCommand('left')">← Left</button>
                <button class="control-btn" onclick="sendCommand('stop')">⏹ Stop</button>
                <button class="control-btn" onclick="sendCommand('right')">→ Right</button>
                
                <div></div>
                <button class="control-btn" onclick="sendCommand('backward')">↓ Backward</button>
                <div></div>
            </div>
        </div>
        
        <div class="status" id="status">Ready to control robot</div>
    </div>

    <script>
        function sendCommand(command) {
            fetch('/control/' + command, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').innerHTML = 
                        'Command: ' + command.toUpperCase() + ' - ' + data.message;
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = 
                        'Error: ' + error.message;
                });
        }
        
        // Add keyboard controls
        document.addEventListener('keydown', function(event) {
            switch(event.key) {
                case 'ArrowUp': case 'w': case 'W':
                    sendCommand('forward'); break;
                case 'ArrowDown': case 's': case 'S':
                    sendCommand('backward'); break;
                case 'ArrowLeft': case 'a': case 'A':
                    sendCommand('left'); break;
                case 'ArrowRight': case 'd': case 'D':
                    sendCommand('right'); break;
                case ' ': case 'Escape':
                    sendCommand('stop'); break;
            }
        });
        
        // Connection status indicator
        setInterval(function() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    if (!data.camera_active) {
                        document.getElementById('status').innerHTML = 
                            'Warning: Camera not responding';
                    }
                });
        }, 5000);
    </script>
</body>
</html>
    """)

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control/<command>', methods=['POST'])
def control_robot(command):
    """Handle robot control commands"""
    # This is where you would add actual robot control logic
    # For now, just acknowledge the command
    
    valid_commands = ['forward', 'backward', 'left', 'right', 'stop']
    
    if command in valid_commands:
        # TODO: Add actual motor control here
        # Examples:
        # - GPIO control for motor drivers
        # - Serial communication to Arduino
        # - I2C communication to motor controller
        
        print(f"Robot command received: {command}")
        return {'status': 'success', 'message': f'Executing {command}'}
    else:
        return {'status': 'error', 'message': 'Invalid command'}, 400

@app.route('/status')
def status():
    """Get system status"""
    return {
        'camera_active': True,
        'robot_connected': True,
        'timestamp': time.time()
    }

if __name__ == '__main__':
    try:
        print("Starting Web Controllable Robot Server...")
        print("Camera initialized successfully")
        print("Access the robot at: http://localhost:5000")
        print("Use arrow keys or WASD for control, Space/Esc to stop")
        
        # Run with minimal threads for better performance on Pi
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        camera.close()
        print("Camera closed. Goodbye!")