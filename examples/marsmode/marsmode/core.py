"""Core module for MarsMode - shared functionality for Panda CAN control."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

try:
    from panda import Panda
except ImportError as e:
    raise ImportError(
        "panda module not found. Please install the panda package: "
        "pip install -e ~/panda"
    ) from e


# CAN message constants
CAN_ID_STEERING_WHEEL = 0x3C2
CAN_ID_TESLA_CLOCK = 0x528
CAN_ID_GEAR = 0x118

# Bus constants
BUS_MAIN = 0
BUS_VEHICLE = 1

# Timing constants
DEFAULT_CAN_SPEED_KBPS = 500
RECONNECT_DELAY = 1.2
MAX_EXCEPTION_COUNT = 5

# Media volume messages
MSG_VOL_DOWN = bytes([0x29, 0x55, 0x3F, 0x00, 0x00, 0x00, 0x00, 0x00])
MSG_VOL_UP = bytes([0x29, 0x55, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])

# Speed messages
MSG_SPEED_DOWN = bytes([0x29, 0x55, 0x00, 0x3F, 0x00, 0x00, 0x00, 0x00])
MSG_SPEED_UP = bytes([0x29, 0x55, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])

# Media back message
MSG_MEDIA_BACK = bytes([0x29, 0x95, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

# Play/pause message detection
MSG_PLAY_PAUSE_PREFIX = bytes([0x49, 0x55])

# Left tilt detection
MSG_LEFT_TILT_PREFIX = bytes([0x29, 0x95])


def setup_logging(
    level: int = logging.INFO,
    format_str: Optional[str] = None,
) -> logging.Logger:
    """Set up logging with the specified level.
    
    Args:
        level: Logging level (default: INFO)
        format_str: Optional custom format string
        
    Returns:
        Configured logger instance
    """
    if format_str is None:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("marsmode")


@dataclass
class Config:
    """Configuration for MarsMode operation.
    
    Attributes:
        mode: Operating mode (media-volume-basic, media-volume, speed-basic, speed, media-back, advanced)
        can_speed_kbps: CAN bus speed in kbps
        safety_mode: Panda safety mode (alloutput, silent)
        verbose: Enable verbose logging
        dry_run: Run without sending CAN messages
        config_file: Path to YAML configuration file
    """
    mode: str = "media-volume-basic"
    can_speed_kbps: int = DEFAULT_CAN_SPEED_KBPS
    safety_mode: str = "alloutput"
    verbose: bool = False
    dry_run: bool = False
    config_file: Optional[Path] = None
    
    # Mode-specific settings
    volume_interval_min: float = 4.0
    volume_interval_max: float = 8.0
    volume_delay: float = 0.3
    speed_interval_min: float = 4.0
    speed_interval_max: float = 8.0
    speed_delay: float = 0.3
    clock_tick_steps: int = 8
    media_back_steps: int = 5
    
    # Advanced mode settings
    startup_signal_count: int = 4
    startup_signal_delay: float = 0.5
    double_tap_min: float = 0.20
    double_tap_max: float = 0.75
    tickle_interval: int = 5
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Config:
        """Create Config from command line arguments."""
        config = cls()
        
        if args.mode:
            config.mode = args.mode
        if args.verbose:
            config.verbose = True
        if args.dry_run:
            config.dry_run = True
        if args.config:
            config.config_file = Path(args.config)
            config.load_from_file(config.config_file)
            
        return config
    
    @classmethod
    def from_file(cls, path: Path) -> Config:
        """Load configuration from YAML file."""
        config = cls()
        config.config_file = path
        config.load_from_file(path)
        return config
    
    def load_from_file(self, path: Path) -> None:
        """Load configuration from YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
            
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
            
        if data is None:
            return
            
        # Update settings from YAML
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_file(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = {
            k: v for k, v in self.__dict__.items()
            if k != 'config_file' and v is not None
        }
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)


class PandaController:
    """Controller for Panda CAN interface with automatic reconnection.
    
    This class wraps the Panda device and provides:
    - Automatic connection setup with proper CAN speeds
    - Graceful error handling with reconnection logic
    - Signal handlers for clean shutdown
    - Safety mode management
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the Panda controller.
        
        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config or Config()
        self.logger = logger or logging.getLogger("marsmode")
        self.panda: Optional[Panda] = None
        self._connected = False
        self._shutdown_requested = False
        self._exception_count = 0
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        self.logger.info(f"Received {sig_name}, shutting down...")
        self._shutdown_requested = True
    
    def connect(self) -> bool:
        """Connect to the Panda device.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.config.dry_run:
            self.logger.info("[DRY RUN] Would connect to Panda")
            self._connected = True
            return True
            
        try:
            self.logger.debug("Connecting to Panda device...")
            self.panda = Panda()
            
            # Set up CAN speeds
            self.panda.set_can_speed_kbps(BUS_MAIN, self.config.can_speed_kbps)
            self.panda.set_can_speed_kbps(BUS_VEHICLE, self.config.can_speed_kbps)
            
            # Set safety mode
            safety = getattr(Panda, f"SAFETY_{self.config.safety_mode.upper()}")
            self.panda.set_safety_mode(safety)
            
            self._connected = True
            self._exception_count = 0
            self.logger.info("Panda connected successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Panda: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the Panda device."""
        if self.panda is not None:
            try:
                self.panda.set_safety_mode(Panda.SAFETY_SILENT)
                self.logger.debug("Panda disconnected")
            except Exception as e:
                self.logger.debug(f"Error during disconnect: {e}")
        self._connected = False
    
    def reconnect(self) -> bool:
        """Reconnect to the Panda device.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        self.disconnect()
        time.sleep(RECONNECT_DELAY)
        return self.connect()
    
    def send_can_message(
        self,
        address: int,
        data: bytes,
        bus: int = BUS_MAIN,
    ) -> bool:
        """Send a CAN message.
        
        Args:
            address: CAN message ID
            data: Message payload (up to 8 bytes)
            bus: CAN bus number
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if self.config.dry_run:
            self.logger.debug(f"[DRY RUN] Would send 0x{address:03X}: {data.hex()}")
            return True
            
        if not self._connected or self.panda is None:
            self.logger.error("Not connected to Panda")
            return False
            
        try:
            self.panda.can_send(address, data, bus)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send CAN message: {e}")
            return False
    
    def receive_can_messages(self) -> list[tuple[int, int, bytes, int]]:
        """Receive CAN messages.
        
        Returns:
            List of (address, _, data, bus) tuples
        """
        if self.config.dry_run:
            return []
            
        if not self._connected or self.panda is None:
            return []
            
        try:
            return self.panda.can_recv()
        except Exception as e:
            self.logger.error(f"Failed to receive CAN messages: {e}")
            return []
    
    def set_safety_mode(self, mode: str) -> bool:
        """Set the Panda safety mode.
        
        Args:
            mode: Safety mode (alloutput, silent)
            
        Returns:
            True if mode set successfully, False otherwise
        """
        if self.config.dry_run:
            self.logger.debug(f"[DRY RUN] Would set safety mode to {mode}")
            return True
            
        if not self._connected or self.panda is None:
            return False
            
        try:
            safety = getattr(Panda, f"SAFETY_{mode.upper()}")
            self.panda.set_safety_mode(safety)
            self.logger.debug(f"Safety mode set to {mode}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set safety mode: {e}")
            return False
    
    def run_with_reconnect(
        self,
        loop_func: Callable[[], bool],
        reconnect_on_error: bool = True,
    ) -> None:
        """Run a loop function with automatic reconnection on errors.
        
        Args:
            loop_func: Function to call in the main loop, returns False to exit
            reconnect_on_error: Whether to reconnect on errors
        """
        if not self.connect():
            self.logger.error("Initial connection failed")
            return
            
        try:
            while not self._shutdown_requested:
                try:
                    if not loop_func():
                        break
                    self._exception_count = 0
                    
                except Exception as e:
                    self._exception_count += 1
                    self.logger.error(
                        f"Exception in main loop (count: {self._exception_count}): {e}"
                    )
                    
                    if reconnect_on_error and self._exception_count > MAX_EXCEPTION_COUNT:
                        self.logger.warning("Too many exceptions, reconnecting...")
                        if not self.reconnect():
                            self.logger.error("Reconnection failed")
                            break
                    else:
                        time.sleep(RECONNECT_DELAY)
                        
        finally:
            self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Panda."""
        return self._connected and self.panda is not None
    
    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested
