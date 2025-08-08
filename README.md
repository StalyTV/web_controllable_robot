# Web Controllable Robot

A minimalistic web-controlled robot with live video streaming, optimized for Raspberry Pi.

## Features

- **Low-latency video streaming** using hardware JPEG encoding
- **Responsive web interface** with touch and keyboard controls
- **Minimal computation** - optimized for Raspberry Pi performance
- **Cross-platform development** - works on development machines with OpenCV fallback

## Hardware Requirements

- Raspberry Pi (3B+ or newer recommended)
- Raspberry Pi Camera Module (v1, v2, or HQ)
- Arduino Uno/Nano (for motor control)
- Robot chassis with motors
- Motor driver board (L298N, Adafruit Motor HAT, etc.)
- Jumper wires for serial connection (Pi TX → Arduino RX)
- Power supply for both Pi and motors

## Installation

### On Raspberry Pi

1. **Update system and install PiCamera2:**
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install python3-picamera2 python3-pip -y
```

2. **Clone and setup project:**
```bash
git clone <your-repo>
cd Web_Contrallable_Robot
python3 -m venv .venv
source .venv/bin/activate
pip install flask opencv-python
```

3. **Enable camera and serial:**
```bash
sudo raspi-config
# Navigate to Interface Options > Camera > Enable
# Navigate to Interface Options > Serial Port > 
#   - Would you like a login shell accessible over serial? > No
#   - Would you like the serial port hardware enabled? > Yes
sudo reboot
```

### For Development (Non-Pi systems)

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Hardware Connections

### Raspberry Pi to Arduino Serial Connection
- **Pi GPIO 14 (TX)** → **Arduino Pin 0 (RX)**
- **Pi GPIO 15 (RX)** → **Arduino Pin 1 (TX)** (optional, for debugging)
- **Pi GND** → **Arduino GND**

### Arduino Motor Driver Connections (L298N Example)
- **Arduino Pin 2** → **L298N IN1**
- **Arduino Pin 3** → **L298N IN2** 
- **Arduino Pin 4** → **L298N IN3**
- **Arduino Pin 5** → **L298N IN4**
- **Arduino Pin 9** → **L298N ENA** (PWM)
- **Arduino Pin 10** → **L298N ENB** (PWM)

## Usage

1. **Upload Arduino code:**
   - Open `arduino_robot_controller.ino` in Arduino IDE
   - Adjust motor pins for your hardware setup
   - Upload to your Arduino

2. **Start the server:**
```bash
python main.py
```

3. **Access the web interface:**
   - Local: http://localhost:8080
   - Network: http://[PI_IP_ADDRESS]:8080

4. **Controls:**
   - **Web buttons:** Hold down for continuous movement
   - **Keyboard:** Hold arrow keys or WASD for movement
   - **Auto-stop:** Robot stops when key/button is released
   - **Emergency stop:** Space bar or Escape key

## Robot Control Protocol

The system sends these commands to Arduino via serial:
- **"fo"** - Move forward
- **"ba"** - Move backward  
- **"le"** - Turn left
- **"ri"** - Turn right
- **"st"** - Stop motors

Commands are sent continuously while keys/buttons are pressed and "st" is sent immediately on release for responsive control.

## Robot Control Integration

The current code includes placeholders for robot control. To add actual motor control:

### Option 1: GPIO Control (Direct)
```python
import RPi.GPIO as GPIO

# Motor pins
MOTOR_LEFT_1 = 18
MOTOR_LEFT_2 = 19
MOTOR_RIGHT_1 = 20
MOTOR_RIGHT_2 = 21

def setup_motors():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([MOTOR_LEFT_1, MOTOR_LEFT_2, MOTOR_RIGHT_1, MOTOR_RIGHT_2], GPIO.OUT)

def move_forward():
    GPIO.output(MOTOR_LEFT_1, GPIO.HIGH)
    GPIO.output(MOTOR_LEFT_2, GPIO.LOW)
    GPIO.output(MOTOR_RIGHT_1, GPIO.HIGH)
    GPIO.output(MOTOR_RIGHT_2, GPIO.LOW)
```

### Option 2: Adafruit Motor HAT
```python
from adafruit_motor import motor
import board

motor_left = motor.DCMotor(board.MOTOR1_A, board.MOTOR1_B)
motor_right = motor.DCMotor(board.MOTOR2_A, board.MOTOR2_B)

def move_forward():
    motor_left.throttle = 0.8
    motor_right.throttle = 0.8
```

### Option 3: Serial/Arduino Control
```python
import serial

arduino = serial.Serial('/dev/ttyUSB0', 9600)

def send_command(cmd):
    arduino.write(f"{cmd}\n".encode())
```

## Performance Optimization

- **Hardware JPEG encoding** reduces CPU usage by ~70%
- **Threaded streaming** prevents blocking
- **Configurable quality** (adjust `q=70` in JpegEncoder)
- **Resolution optimization** (640x480 default, adjustable)

## Network Configuration

To access from other devices on your network:

1. **Find Pi's IP address:**
```bash
hostname -I
```

2. **Configure firewall (if needed):**
```bash
sudo ufw allow 5000
```

3. **Static IP (recommended):**
Edit `/etc/dhcpcd.conf`:
```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

## Troubleshooting

### Camera Issues
- Ensure camera is enabled: `sudo raspi-config`
- Check connection: `libcamera-hello --list-cameras`
- Verify permissions: Add user to `video` group

### Performance Issues
- Lower video quality: Reduce `q` parameter
- Decrease resolution: Modify camera configuration
- Optimize network: Use wired connection if possible

### Network Access Issues
- Check firewall settings
- Verify Pi's IP address
- Ensure devices are on same network

## Security Note

This is designed for local network use. For internet access, implement:
- Authentication system
- HTTPS encryption
- Rate limiting
- Input validation

## License

MIT License - Feel free to modify and distribute.
