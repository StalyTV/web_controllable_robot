#!/bin/bash

# Quick setup script for Raspberry Pi
# Run with: curl -sSL https://raw.githubusercontent.com/your-repo/setup.sh | bash

echo "Setting up Web Controllable Robot on Raspberry Pi..."

# Update system
echo "Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "Installing dependencies..."
sudo apt install python3-picamera2 python3-pip python3-venv git -y

# Create project directory
echo "Setting up project..."
cd ~
git clone https://github.com/your-username/Web_Contrallable_Robot.git || {
    echo "Please update the git URL in this script"
    mkdir -p Web_Contrallable_Robot
    cd Web_Contrallable_Robot
}

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install flask opencv-python

# Enable camera if not already enabled
echo "Checking camera configuration..."
if ! grep -q "start_x=1" /boot/config.txt; then
    echo "Enabling camera..."
    echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
    echo "A reboot will be required after setup."
    REBOOT_REQUIRED=1
fi

# Create systemd service for auto-start (optional)
read -p "Do you want the robot to start automatically on boot? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo tee /etc/systemd/system/robot-server.service > /dev/null <<EOF
[Unit]
Description=Web Controllable Robot Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin
ExecStart=$(pwd)/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl enable robot-server.service
    echo "Service installed. Use 'sudo systemctl start robot-server' to start."
fi

echo "Setup complete!"
echo "Run the robot with: python main.py"
echo "Access at: http://$(hostname -I | awk '{print $1}'):5000"

if [ "$REBOOT_REQUIRED" = "1" ]; then
    echo ""
    echo "IMPORTANT: A reboot is required to enable the camera."
    read -p "Reboot now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    fi
fi
