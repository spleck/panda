"""Mode implementations for MarsMode."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from marsmode.core import (
    PandaController,
    Config,
    CAN_ID_STEERING_WHEEL,
    CAN_ID_TESLA_CLOCK,
    CAN_ID_GEAR,
    BUS_MAIN,
    BUS_VEHICLE,
    MSG_VOL_DOWN,
    MSG_VOL_UP,
    MSG_SPEED_DOWN,
    MSG_SPEED_UP,
    MSG_MEDIA_BACK,
    MSG_PLAY_PAUSE_PREFIX,
    MSG_LEFT_TILT_PREFIX,
)


class BaseMode(ABC):
    """Base class for all MarsMode implementations.
    
    Provides common functionality and interface for all modes.
    """
    
    def __init__(
        self,
        controller: PandaController,
        config: Optional[Config] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the mode.
        
        Args:
            controller: PandaController instance
            config: Configuration object
            logger: Logger instance
        """
        self.controller = controller
        self.config = config or Config()
        self.logger = logger or logging.getLogger(f"marsmode.{self.__class__.__name__}")
        self._running = False
    
    @abstractmethod
    def run(self) -> None:
        """Run the mode. This should be implemented by subclasses."""
        pass
    
    def stop(self) -> None:
        """Stop the mode."""
        self._running = False
        self.logger.info("Mode stopped")
    
    def _send_message(self, address: int, data: bytes, bus: int = BUS_MAIN) -> bool:
        """Send a CAN message through the controller."""
        return self.controller.send_can_message(address, data, bus)


class MediaVolumeBasicMode(BaseMode):
    """Basic media volume mode using blind sleep timers.
    
    Sends volume down/up commands at random intervals to keep the vehicle awake.
    This is the simplest mode with no synchronization to vehicle state.
    """
    
    def run(self) -> None:
        """Run the media volume basic mode."""
        self.logger.info("Starting Media Volume Basic mode")
        self._running = True
        
        def loop() -> bool:
            if not self._running or self.controller.shutdown_requested:
                return False
                
            # Send volume down
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.volume_delay)
            
            # Send volume up
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
            
            # Random interval
            interval = random.uniform(
                self.config.volume_interval_min,
                self.config.volume_interval_max
            )
            self.logger.debug(f"Sleeping for {interval:.2f}s")
            time.sleep(interval)
            
            return True
        
        self.controller.run_with_reconnect(loop)


class MediaVolumeMode(BaseMode):
    """Media volume mode synchronized to Tesla clock ticks.
    
    Listens for Tesla clock messages (0x528) and sends volume commands
    at specific tick counts for more reliable operation.
    """
    
    def run(self) -> None:
        """Run the media volume mode."""
        self.logger.info("Starting Media Volume mode")
        self._running = True
        step_count = 0
        
        def loop() -> bool:
            nonlocal step_count
            
            if not self._running or self.controller.shutdown_requested:
                return False
                
            can_recv = self.controller.receive_can_messages()
            for address, _, dat, bus in can_recv:
                if bus == BUS_MAIN and address == CAN_ID_TESLA_CLOCK:
                    step_count += 1
                    
                    # Parse car clock
                    try:
                        car_clock = datetime.fromtimestamp(int(dat.hex(), 16))
                        self.logger.debug(f"Car Clock: {car_clock}")
                    except (ValueError, OverflowError) as e:
                        self.logger.debug(f"Invalid clock data: {e}")
                    
                    # Send volume commands at specific steps
                    if step_count == self.config.clock_tick_steps - 1:
                        self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
                    elif step_count >= self.config.clock_tick_steps:
                        self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
                        self.logger.debug("Sent volume event")
                        step_count = 0
            
            return True
        
        self.controller.run_with_reconnect(loop)


class SpeedBasicMode(BaseMode):
    """Basic speed adjustment mode using blind sleep timers.
    
    Sends AP max speed down/up commands at random intervals.
    """
    
    def run(self) -> None:
        """Run the speed basic mode."""
        self.logger.info("Starting Speed Basic mode")
        self._running = True
        
        def loop() -> bool:
            if not self._running or self.controller.shutdown_requested:
                return False
                
            # Send speed down
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_DOWN)
            time.sleep(self.config.speed_delay)
            
            # Send speed up
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_UP)
            
            # Random interval
            interval = random.uniform(
                self.config.speed_interval_min,
                self.config.speed_interval_max
            )
            self.logger.debug(f"Sleeping for {interval:.2f}s")
            time.sleep(interval)
            
            return True
        
        self.controller.run_with_reconnect(loop)


class SpeedMode(BaseMode):
    """Speed adjustment mode synchronized to Tesla clock ticks.
    
    Listens for Tesla clock messages (0x528) and sends speed commands
    at specific tick counts.
    """
    
    def run(self) -> None:
        """Run the speed mode."""
        self.logger.info("Starting Speed mode")
        self._running = True
        step_count = 0
        
        def loop() -> bool:
            nonlocal step_count
            
            if not self._running or self.controller.shutdown_requested:
                return False
                
            can_recv = self.controller.receive_can_messages()
            for address, _, dat, _ in can_recv:
                if address == CAN_ID_TESLA_CLOCK:
                    step_count += 1
                    
                    # Parse car clock
                    try:
                        car_clock = datetime.fromtimestamp(int(dat.hex(), 16))
                        self.logger.debug(f"Car Clock: {car_clock}")
                    except (ValueError, OverflowError) as e:
                        self.logger.debug(f"Invalid clock data: {e}")
                    
                    # Send speed commands at specific steps
                    if step_count == self.config.clock_tick_steps - 1:
                        self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_DOWN)
                    elif step_count >= self.config.clock_tick_steps:
                        self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_UP)
                        self.logger.debug("Sent speed event")
                        step_count = 0
            
            return True
        
        self.controller.run_with_reconnect(loop)


class MediaBackMode(BaseMode):
    """Media back button mode for Tesla Streaming app.
    
    Sends media back commands at specific clock tick intervals.
    Note: This mode should only be used with the Streaming app as it
    does not have a back function that would interfere.
    """
    
    def run(self) -> None:
        """Run the media back mode."""
        self.logger.info("Starting Media Back mode")
        self._running = True
        step_count = 0
        
        def loop() -> bool:
            nonlocal step_count
            
            if not self._running or self.controller.shutdown_requested:
                return False
                
            can_data = self.controller.receive_can_messages()
            for ev_id, _, ev_data, _ in can_data:
                if ev_id == CAN_ID_TESLA_CLOCK:
                    step_count += 1
                    
                    if step_count >= self.config.media_back_steps:
                        self._send_message(CAN_ID_STEERING_WHEEL, MSG_MEDIA_BACK)
                        self.logger.debug("Sent media back")
                        step_count = 0
            
            return True
        
        self.controller.run_with_reconnect(loop)


class AdvancedMode(BaseMode):
    """Advanced mode with multiple sub-modes and gesture controls.
    
    Features:
    - Multiple modes: volume, speed, media back
    - Enable/disable with double-tap play/pause (left scroll wheel button)
    - Cycle modes with double-tap left tilt
    - Auto-disable when vehicle is parked
    """
    
    MODE_VOLUME = 0
    MODE_SPEED = 1
    MODE_MEDIA_BACK = 2
    
    def __init__(
        self,
        controller: PandaController,
        config: Optional[Config] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(controller, config, logger)
        self.mode_enabled = True
        self.mode_signal = self.MODE_VOLUME
        self.boot_init = False
        self.parked = False
        self.step_count = 0
        self.last_p_ts = 0.0
        self.last_d_ts = 0.0
        self.last_lt = 0.0
        self.last_rt = 0.0
    
    def run(self) -> None:
        """Run the advanced mode."""
        self.logger.info("Starting Advanced mode")
        self._running = True
        
        # Set initial safety mode
        if self.mode_enabled:
            self.controller.set_safety_mode("alloutput")
        else:
            self.controller.set_safety_mode("silent")
        
        def loop() -> bool:
            if not self._running or self.controller.shutdown_requested:
                return False
                
            can_data = self.controller.receive_can_messages()
            for ev_id, _, ev_data, ev_bus in can_data:
                if ev_bus == BUS_MAIN:
                    self._process_message(ev_id, ev_data)
            
            return True
        
        self.controller.run_with_reconnect(loop, reconnect_on_error=True)
    
    def _process_message(self, ev_id: int, ev_data: bytes) -> None:
        """Process a single CAN message."""
        if ev_id == CAN_ID_TESLA_CLOCK:
            self._handle_clock_tick()
        elif ev_id == CAN_ID_STEERING_WHEEL:
            self._handle_steering_wheel(ev_data)
        elif ev_id == CAN_ID_GEAR:
            self._handle_gear(ev_data)
    
    def _handle_clock_tick(self) -> None:
        """Handle Tesla clock tick message."""
        # Reset exception count on successful receive
        # Note: This is handled by the controller now
        
        # Display startup sequence on first tick detect after boot
        if not self.boot_init:
            self._do_startup_sequence()
        
        # Standard tickle when enabled
        if self.mode_enabled:
            self.step_count += 1
            if self.step_count >= self.config.tickle_interval:
                self.step_count = 0
                self._send_tickle_signal()
    
    def _do_startup_sequence(self) -> None:
        """Perform the startup sequence."""
        self.boot_init = True
        self.controller.set_safety_mode("alloutput")
        self.logger.info("Boot sequence: Startup detected")
        
        # Flag startup with volume adjustments
        for _ in range(self.config.startup_signal_count // 2):
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.startup_signal_delay)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
            time.sleep(self.config.startup_signal_delay)
        
        if not self.mode_enabled:
            self.controller.set_safety_mode("silent")
    
    def _send_tickle_signal(self) -> None:
        """Send the appropriate tickle signal based on current mode."""
        time.sleep(random.uniform(0, 2))
        
        if self.mode_signal == self.MODE_VOLUME:
            self.logger.debug("Media vol signals SENT")
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.volume_delay)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
        elif self.mode_signal == self.MODE_SPEED:
            self.logger.debug("Speed signal SENT")
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_DOWN)
            time.sleep(self.config.speed_delay)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_SPEED_UP)
        else:
            self.logger.debug("Media back signal SENT")
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_MEDIA_BACK)
    
    def _handle_steering_wheel(self, ev_data: bytes) -> None:
        """Handle steering wheel control messages."""
        # Check for play/pause (double tap to enable/disable)
        if len(ev_data) >= 2 and ev_data[:2] == MSG_PLAY_PAUSE_PREFIX:
            self._handle_play_pause()
        # Check for left tilt (double tap to cycle modes)
        elif len(ev_data) >= 2 and ev_data[:2] == MSG_LEFT_TILT_PREFIX:
            self._handle_left_tilt()
    
    def _handle_play_pause(self) -> None:
        """Handle play/pause button press."""
        self.logger.debug("Play/pause detected")
        self.step_count = 0
        
        delta_lt = time.time() - self.last_lt
        if self.config.double_tap_min < delta_lt < self.config.double_tap_max:
            # Double tap detected, toggle mode
            self.logger.info(f"Double tap detected ({delta_lt:.3f}s)")
            self._toggle_mode()
        else:
            self.logger.debug(f"Single click ({delta_lt:.3f}s)")
        
        self.last_lt = time.time()
    
    def _toggle_mode(self) -> None:
        """Toggle the mode on/off."""
        if self.mode_enabled:
            self.logger.info("--> DEACTIVATING")
            self.mode_enabled = False
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
            time.sleep(self.config.volume_delay + 0.2)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.volume_delay + 0.2)
            self.controller.set_safety_mode("silent")
        else:
            self.logger.info("--> ACTIVATING")
            self.mode_enabled = True
            self.controller.set_safety_mode("alloutput")
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.volume_delay + 0.2)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
    
    def _handle_left_tilt(self) -> None:
        """Handle left tilt of scroll wheel."""
        self.logger.debug("Left tilt detected")
        self.step_count = 0
        
        delta_rt = time.time() - self.last_rt
        if self.config.double_tap_min < delta_rt < self.config.double_tap_max:
            # Double tap detected, cycle mode
            self.last_rt = 0
            self.mode_signal = (self.mode_signal + 1) % 3
            mode_names = ["volume", "speed", "media_back"]
            self.logger.info(f"--> MODE SWAP to {mode_names[self.mode_signal]}")
            
            if not self.mode_enabled:
                self.controller.set_safety_mode("alloutput")
            
            # Flag change with volume adjustments
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_DOWN)
            time.sleep(self.config.volume_delay + 0.2)
            self._send_message(CAN_ID_STEERING_WHEEL, MSG_VOL_UP)
            time.sleep(self.config.volume_delay + 0.2)
            
            if not self.mode_enabled:
                self.controller.set_safety_mode("silent")
        else:
            self.logger.debug(f"Single tilt ({delta_rt:.3f}s)")
        
        self.last_rt = time.time()
    
    def _handle_gear(self, ev_data: bytes) -> None:
        """Handle gear position messages."""
        if len(ev_data) < 3:
            return
            
        gear_value = ev_data[2]
        
        # Check for park (values <= 50 or >= 240 typically indicate park)
        if gear_value <= 50 or gear_value >= 240:
            self.last_p_ts = time.time()
        else:
            self.last_d_ts = time.time()
        
        # Update parked state
        if not self.parked and (self.last_p_ts > self.last_d_ts):
            self.parked = True
            self.logger.info("Changing to PARK mode")
            if self.mode_enabled:
                self.controller.set_safety_mode("silent")
        elif self.parked and (self.last_d_ts > self.last_p_ts):
            self.parked = False
            self.logger.info(f"Changing to NON-PARK mode (gear: {gear_value})")
            if self.mode_enabled:
                self.controller.set_safety_mode("alloutput")


class AsyncAdvancedMode(AdvancedMode):
    """Asyncio-based version of the Advanced mode.
    
    Uses asyncio for cleaner event loop handling.
    """
    
    async def run_async(self) -> None:
        """Run the advanced mode using asyncio."""
        self.logger.info("Starting Async Advanced mode")
        self._running = True
        
        if self.mode_enabled:
            self.controller.set_safety_mode("alloutput")
        else:
            self.controller.set_safety_mode("silent")
        
        while self._running and not self.controller.shutdown_requested:
            try:
                can_data = self.controller.receive_can_messages()
                for ev_id, _, ev_data, ev_bus in can_data:
                    if ev_bus == BUS_MAIN:
                        self._process_message(ev_id, ev_data)
                
                # Small yield to prevent busy-waiting
                await asyncio.sleep(0.001)
                
            except Exception as e:
                self.logger.error(f"Exception in async loop: {e}")
                await asyncio.sleep(RECONNECT_DELAY)


# Import reconnect delay for async mode
from marsmode.core import RECONNECT_DELAY

# Mode registry for CLI
MODE_REGISTRY: dict[str, type[BaseMode]] = {
    "media-volume-basic": MediaVolumeBasicMode,
    "media-volume": MediaVolumeMode,
    "speed-basic": SpeedBasicMode,
    "speed": SpeedMode,
    "media-back": MediaBackMode,
    "advanced": AdvancedMode,
}
