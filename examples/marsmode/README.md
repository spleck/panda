# Mars Mode for Tesla

Scripts to simulate button inputs via CAN bus signals in your Tesla Model 3, Y, and newer S and X. Keeps the vehicle awake ("Mars Mode") by periodically sending CAN messages.

## Quick Start

```bash
# Install dependencies and setup
cd ~/panda/examples/marsmode
./scripts/install.sh

# Run a mode directly
python -m marsmode --mode media-volume-basic

# Or use the wrapper script
./scripts/marsmode.sh start media-volume-basic
```

## Project Structure

```
examples/marsmode/
├── marsmode/              # Python package
│   ├── __init__.py
│   ├── __main__.py        # Entry point: python -m marsmode
│   ├── cli.py             # Command-line interface
│   ├── core.py            # Shared Panda controller, logging, config
│   └── modes.py           # All mode implementations
├── scripts/               # Shell scripts
│   ├── install.sh         # System installer for PiOS
│   └── marsmode.sh        # Wrapper/launcher script
├── config/
│   └── marsmode.yaml      # Configuration file
├── systemd/
│   └── marsmode@.service  # Systemd service template
└── README.md              # This file
```

## Installation

### Automated Install for PiOS

```bash
curl https://spleck.net/mars-mode-install | bash
```

For verbose output:
```bash
curl https://spleck.net/mars-mode-install | V=1 bash
```

### Manual Install

1. **System dependencies:**
```bash
sudo apt-get update
sudo apt-get install -y dfu-util gcc-arm-none-eabi python3-pip python3-venv libffi-dev git scons screen
```

2. **Clone and setup:**
```bash
git clone https://github.com/spleck/panda.git ~/panda
python3 -m venv ~/panda/
source ~/panda/bin/activate
cd ~/panda
pip install -r requirements.txt
python setup.py install
```

3. **Install MarsMode:**
```bash
cd ~/panda/examples/marsmode
./scripts/install.sh
```

## Usage

### Command Line

```bash
# List available modes
python -m marsmode --list

# Run a specific mode
python -m marsmode --mode media-volume-basic

# Run with custom config
python -m marsmode --mode advanced --config config/marsmode.yaml

# Verbose logging
python -m marsmode --mode advanced -v

# Dry run (no actual CAN messages)
python -m marsmode --mode media-volume-basic --dry-run
```

### Available Modes

| Mode | Description |
|------|-------------|
| `media-volume-basic` | Simple volume up/down every 4-8 seconds |
| `media-volume` | Volume control synced to Tesla clock ticks |
| `speed-basic` | AP speed adjust every 4-8 seconds |
| `speed` | Speed adjust synced to Tesla clock ticks |
| `media-back` | Media back button every 5 seconds (Streaming app only) |
| `advanced` | Full-featured with mode switching, enable/disable, park detection |

### Wrapper Script

```bash
# Start a mode
./scripts/marsmode.sh start media-volume-basic

# Stop the service
./scripts/marsmode.sh stop

# Check status
./scripts/marsmode.sh status

# Set default mode (for auto-start)
./scripts/marsmode.sh set-default media-volume-basic
```

### Systemd Service

```bash
# Enable auto-start on boot
sudo systemctl enable marsmode@media-volume-basic

# Start/stop/restart
sudo systemctl start marsmode@media-volume-basic
sudo systemctl stop marsmode@media-volume-basic
sudo systemctl restart marsmode@media-volume-basic

# View logs
sudo journalctl -u marsmode@media-volume-basic -f
```

## Configuration

Edit `config/marsmode.yaml` to customize:

```yaml
can:
  speed_kbps: 500
  bus_main: 0
  bus_vehicle: 1

messages:
  can_id_steering_wheel: 0x3C2
  can_id_tesla_clock: 0x528
  can_id_gear: 0x118

timing:
  reconnect_delay: 1.2
  max_exception_count: 5

modes:
  media_volume_basic:
    interval_min: 4.0
    interval_max: 8.0
    
  media_volume:
    step_count_trigger: 7
```

## Bill of Materials

* 1x Raspberry Pi 4 + Case
* 1x USB-C to USB-A Cable
* 1x [USB-A to USB-A Cable](https://a.co/d/4NF5Dub) (for flashing)
* 1x MicroSD Memory Card
* 1x [White Comma Panda](https://www.comma.ai/shop/panda)
* 1x [OBD Adapter Cable](https://enhauto.com/product/tesla-gen1-obd-cable)

## Hardware Setup

1. Flash Raspberry Pi OS Lite (64-bit) to MicroSD
2. Enable SSH and configure WiFi in Raspberry Pi Imager
3. Boot the Pi and connect the White Comma Panda via USB
4. SSH into the Pi and run the install script
5. Connect the Panda to your Tesla's OBD port

## Development

```bash
# Activate the virtual environment
source ~/panda/bin/activate

# Run tests (if available)
python -m pytest tests/

# Type checking
mypy marsmode/

# Linting
ruff check marsmode/
```

## Troubleshooting

### Panda not detected
```bash
# Check USB connection
lsusb | grep -i panda

# Check udev rules
cat /etc/udev/rules.d/11-panda.rules

# Reload rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### Permission denied
```bash
# Ensure your user is in the dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Recovery mode
If the Panda needs recovery:
```bash
cd ~/panda/board
./recover.py
./flash.py
```

## Safety Notes

- These scripts send CAN messages to your vehicle. Use at your own risk.
- The advanced mode automatically disables when the vehicle is in park.
- Always test new modes in a safe environment.
- The media-back mode is only compatible with Tesla's Streaming app.

## License

Mars Mode scripts are released under the MIT license.

## Credits

- Original panda software by [comma.ai](https://github.com/commaai/panda)
- Mars Mode extensions by spleck
