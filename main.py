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

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("PySerial not available, robot control disabled")

app = Flask(__name__)

class RobotController:
    """Serial communication controller for Arduino-based robot"""
    def __init__(self, port='/dev/ttyS0', baudrate=9600):
        self.serial_connection = None
        self.last_command = None
        self.command_lock = threading.Lock()
        
        if SERIAL_AVAILABLE:
            try:
                # Try common serial ports for Raspberry Pi
                ports_to_try = [port, '/dev/ttyAMA0', '/dev/ttyUSB0', '/dev/ttyACM0']
                for test_port in ports_to_try:
                    try:
                        self.serial_connection = serial.Serial(test_port, baudrate, timeout=1)
                        print(f"Robot controller connected on {test_port}")
                        break
                    except (serial.SerialException, FileNotFoundError):
                        continue
                
                if not self.serial_connection:
                    print("Warning: No serial connection found. Robot control disabled.")
            except Exception as e:
                print(f"Error initializing robot controller: {e}")
        else:
            print("Serial library not available. Robot control will be simulated.")
    
    def send_command(self, command):
        """Send command to Arduino via serial"""
        command_map = {
            'forward': 'fo',
            'backward': 'ba', 
            'left': 'le',
            'right': 'ri',
            'stop': 'st'
        }
        
        if command not in command_map:
            return False
            
        serial_cmd = command_map[command]
        
        with self.command_lock:
            if self.serial_connection:
                try:
                    self.serial_connection.write((serial_cmd + '\n').encode())
                    self.serial_connection.flush()
                    self.last_command = command
                    print(f"Sent to Arduino: {serial_cmd} ({command})")
                    return True
                except Exception as e:
                    print(f"Serial communication error: {e}")
                    return False
            else:
                # Simulate command for testing
                self.last_command = command
                print(f"Simulated robot command: {serial_cmd} ({command})")
                return True
    
    def emergency_stop(self):
        """Send immediate stop command"""
        return self.send_command('stop')
    
    def close(self):
        """Close serial connection"""
        if self.serial_connection:
            self.emergency_stop()
            time.sleep(0.1)  # Give time for stop command
            self.serial_connection.close()
            print("Robot controller disconnected")

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
            print("Using PiCamera2 for video capture...")
            # Use PiCamera2 for Raspberry Pi (most efficient)
            self.camera = Picamera2()
            # Configure for low latency streaming with 180-degree rotation
            config = self.camera.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                lores={"size": (320, 240), "format": "YUV420"},
                transform={"hflip": True}  # 180-degree rotation
            )
            self.camera.configure(config)
            
            # Use hardware JPEG encoder for minimal CPU usage
            self.encoder = JpegEncoder(q=70)  # Quality 70 for balance of size/quality
            self.camera.start_recording(self.encoder, FileOutput(self.output))
        else:
            print("Using OpenCV for video capture...")
            # Fallback to OpenCV (for development/testing)
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self._start_opencv_capture()

    def _start_opencv_capture(self):
        """Start OpenCV capture in separate thread"""
        print("Starting OpenCV video capture...")
        def capture_frames():
            while True:
                ret, frame = self.camera.read()
                if ret:
                    # Flip the frame upside down (rotate 180 degrees)
                    frame = cv2.flip(frame, -1)  # -1 flips both horizontally and vertically
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

# Initialize camera and robot controller
camera = VideoCamera()
robot = RobotController()

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
        
        
        <div class="status" id="status">Ready to control robot</div>
    </div>

    <script>
        let currentCommand = null;
        let isKeyPressed = false;
        
        function sendCommand(command) {
            if (currentCommand !== command) {
                currentCommand = command;
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
        }
        
        function stopRobot() {
            if (currentCommand !== 'stop') {
                currentCommand = 'stop';
                fetch('/control/stop', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status').innerHTML = 
                            'Command: STOP - ' + data.message;
                    });
            }
        }
        
        // Button event handlers for continuous press
        function setupButtonEvents() {
            const buttons = document.querySelectorAll('.control-btn');
            buttons.forEach(button => {
                const command = button.getAttribute('data-command');
                
                // Mouse events
                button.addEventListener('mousedown', () => {
                    if (command !== 'stop') {
                        sendCommand(command);
                    } else {
                        stopRobot();
                    }
                });
                
                button.addEventListener('mouseup', () => {
                    if (command !== 'stop') {
                        stopRobot();
                    }
                });
                
                button.addEventListener('mouseleave', () => {
                    if (command !== 'stop') {
                        stopRobot();
                    }
                });
                
                // Touch events for mobile
                button.addEventListener('touchstart', (e) => {
                    e.preventDefault();
                    if (command !== 'stop') {
                        sendCommand(command);
                    } else {
                        stopRobot();
                    }
                });
                
                button.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    if (command !== 'stop') {
                        stopRobot();
                    }
                });
            });
        }
        
        // Keyboard controls with continuous press
        let pressedKeys = new Set();
        
        document.addEventListener('keydown', function(event) {
            if (pressedKeys.has(event.key)) return; // Already pressed
            
            pressedKeys.add(event.key);
            isKeyPressed = true;
            
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
                    stopRobot(); break;
            }
        });
        
        document.addEventListener('keyup', function(event) {
            pressedKeys.delete(event.key);
            
            switch(event.key) {
                case 'ArrowUp': case 'w': case 'W':
                case 'ArrowDown': case 's': case 'S':
                case 'ArrowLeft': case 'a': case 'A':
                case 'ArrowRight': case 'd': case 'D':
                    stopRobot(); break;
            }
        });
        
        // Stop robot when window loses focus
        window.addEventListener('blur', function() {
            stopRobot();
            pressedKeys.clear();
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
        
        // Initialize button events when page loads
        document.addEventListener('DOMContentLoaded', setupButtonEvents);
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
    valid_commands = ['forward', 'backward', 'left', 'right', 'stop']
    
    if command in valid_commands:
        success = robot.send_command(command)
        if success:
            return {'status': 'success', 'message': f'Executing {command}'}
        else:
            return {'status': 'error', 'message': 'Serial communication failed'}, 500
    else:
        return {'status': 'error', 'message': 'Invalid command'}, 400

@app.route('/status')
def status():
    """Get system status"""
    return {
        'camera_active': True,
        'robot_connected': robot.serial_connection is not None if SERIAL_AVAILABLE else False,
        'serial_available': SERIAL_AVAILABLE,
        'last_command': robot.last_command,
        'timestamp': time.time()
    }

if __name__ == '__main__':
    try:
        print("Starting Web Controllable Robot Server...")
        print("Camera initialized successfully")
        print("Access the robot at: http://localhost:8080")
        print("Use arrow keys or WASD for control, Space/Esc to stop")
        
        # Run with minimal threads for better performance on Pi
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        robot.emergency_stop()
        robot.close()
        camera.close()
        print("Robot and camera closed. Goodbye!")