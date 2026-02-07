# Mars Mode Scripts

Scripts to simulate button inputs via CAN bus signals in your Tesla Model 3, Y, and newer S and X. Keeps the vehicle awake by sending periodic CAN messages via a comma.ai Panda device.

**📖 Full documentation:** See [examples/marsmode/README.md](examples/marsmode/README.md)

## Quick Links

- [Installation Guide](examples/marsmode/README.md#installation)
- [Usage Examples](examples/marsmode/README.md#usage)
- [Available Modes](examples/marsmode/README.md#available-modes)
- [Configuration](examples/marsmode/README.md#configuration)

## Bill of Materials

* 1x Raspberry Pi 4 + Case
* 1x USB-C to USB-A Cable
* 1x [USB-A to USB-A Cable](https://a.co/d/4NF5Dub) for flashing firmware
* 1x MicroSD Memory Card
* 1x [White Comma Panda](https://www.comma.ai/shop/panda)
* 1x [OBD Adapter Cable](https://enhauto.com/product/tesla-gen1-obd-cable)

## Quick Install (PiOS)

```bash
curl https://spleck.net/mars-mode-install | bash
```

For verbose output:
```bash
curl https://spleck.net/mars-mode-install | V=1 bash
```

## Quick Start

After installation:

```bash
# Run a mode directly
cd ~/panda/examples/marsmode
python -m marsmode --mode media-volume-basic

# Or use the wrapper
./scripts/marsmode.sh start media-volume-basic

# Enable auto-start on boot
sudo systemctl enable marsmode@media-volume-basic
```

## Project Structure

```
examples/marsmode/
├── marsmode/              # Python package
│   ├── __main__.py        # Entry point
│   ├── cli.py             # Command-line interface
│   ├── core.py            # Shared Panda controller
│   └── modes.py           # Mode implementations
├── scripts/               # Shell scripts
│   ├── install.sh         # System installer
│   └── marsmode.sh        # Wrapper script
├── config/
│   └── marsmode.yaml      # Configuration
├── systemd/
│   └── marsmode@.service  # Systemd service
└── README.md              # Full documentation
```

## Manual Installation

See [examples/marsmode/README.md](examples/marsmode/README.md#manual-install) for detailed manual install steps.

## Available Modes

| Mode | Description |
|------|-------------|
| `media-volume-basic` | Simple volume up/down every 4-8 seconds |
| `media-volume` | Volume control synced to Tesla clock ticks |
| `speed-basic` | AP speed adjust every 4-8 seconds |
| `speed` | Speed adjust synced to Tesla clock ticks |
| `media-back` | Media back button every 5 seconds (Streaming app only) |
| `advanced` | Full-featured with mode switching and park detection |

## Credits

- Original panda software by [comma.ai](https://github.com/commaai/panda)
- Mars Mode extensions by spleck

## License

panda software and mars mode scripting are released under the MIT license unless otherwise specified.
