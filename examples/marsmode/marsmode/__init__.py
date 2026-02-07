"""MarsMode - Tesla CAN bus automation for keeping the vehicle awake.

This package provides various modes for sending periodic CAN messages
to prevent a Tesla from going to sleep (Mars Mode).
"""

__version__ = "2.0.0"
__author__ = "MarsMode Contributors"

from marsmode.core import PandaController, Config, setup_logging
from marsmode.modes import (
    BaseMode,
    MediaVolumeBasicMode,
    MediaVolumeMode,
    SpeedBasicMode,
    SpeedMode,
    MediaBackMode,
    AdvancedMode,
)

__all__ = [
    "PandaController",
    "Config",
    "setup_logging",
    "BaseMode",
    "MediaVolumeBasicMode",
    "MediaVolumeMode",
    "SpeedBasicMode",
    "SpeedMode",
    "MediaBackMode",
    "AdvancedMode",
]
