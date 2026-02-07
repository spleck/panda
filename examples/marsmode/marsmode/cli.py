"""Command-line interface for MarsMode."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from marsmode.core import Config, PandaController, setup_logging
from marsmode.modes import MODE_REGISTRY, BaseMode


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for MarsMode CLI."""
    parser = argparse.ArgumentParser(
        prog="marsmode",
        description="Tesla CAN bus automation for keeping the vehicle awake (Mars Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available modes:
  media-volume-basic  Basic media volume control with random timing
  media-volume        Media volume synchronized to Tesla clock ticks
  speed-basic         Basic AP max speed adjustment with random timing
  speed               AP max speed adjustment synchronized to clock ticks
  media-back          Media back button for Streaming app (clock-based)
  advanced            Multi-mode with gesture controls and park detection

Examples:
  python -m marsmode media-volume-basic
  python -m marsmode advanced --verbose
  python -m marsmode media-volume --config /etc/marsmode.yaml --dry-run
  python -m marsmode status
        """,
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        choices=list(MODE_REGISTRY.keys()) + ["status", "list"],
        default="media-volume-basic",
        help="Operating mode (default: media-volume-basic)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Run without sending CAN messages (for testing)",
    )
    
    parser.add_argument(
        "-c", "--config",
        metavar="FILE",
        help="Load configuration from YAML file",
    )
    
    parser.add_argument(
        "--save-config",
        metavar="FILE",
        help="Save current configuration to YAML file and exit",
    )
    
    parser.add_argument(
        "--can-speed",
        type=int,
        default=500,
        metavar="KBPS",
        help="CAN bus speed in kbps (default: 500)",
    )
    
    parser.add_argument(
        "--safety-mode",
        choices=["alloutput", "silent"],
        default="alloutput",
        help="Panda safety mode (default: alloutput)",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
    )
    
    return parser


def list_modes() -> None:
    """List all available modes."""
    print("Available MarsMode modes:")
    print()
    
    descriptions = {
        "media-volume-basic": "Basic media volume control with random sleep timing",
        "media-volume": "Media volume synchronized to Tesla clock ticks (0x528)",
        "speed-basic": "Basic AP max speed adjustment with random timing",
        "speed": "AP max speed adjustment synchronized to Tesla clock ticks",
        "media-back": "Media back button for Streaming app (clock-based)",
        "advanced": "Multi-mode with gesture controls and park detection",
    }
    
    for mode_name, mode_class in MODE_REGISTRY.items():
        desc = descriptions.get(mode_name, "No description available")
        print(f"  {mode_name:20} - {desc}")
    
    print()
    print("Use 'python -m marsmode <mode>' to run a mode.")


def check_status() -> int:
    """Check the status of MarsMode/Panda.
    
    Returns:
        Exit code (0 for OK, 1 for error)
    """
    print("MarsMode Status Check")
    print("=" * 40)
    
    # Check if panda module is available
    try:
        from panda import Panda
        print("✓ panda module available")
    except ImportError:
        print("✗ panda module not found")
        print("  Install with: pip install -e ~/panda")
        return 1
    
    # Try to connect to Panda
    try:
        p = Panda()
        print("✓ Panda device connected")
        
        # Try to get some info
        try:
            serial = p.get_serial()
            print(f"  Serial: {serial}")
        except Exception:
            pass
            
    except Exception as e:
        print(f"✗ Panda device not found: {e}")
        print("  Check USB connection and udev rules")
        return 1
    
    print()
    print("System is ready for MarsMode operation.")
    return 0


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for MarsMode CLI.
    
    Args:
        args: Command line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    # Handle special commands
    if parsed_args.mode == "list":
        list_modes()
        return 0
    
    if parsed_args.mode == "status":
        return check_status()
    
    # Create configuration
    config = Config.from_args(parsed_args)
    
    # Override with CLI options
    config.can_speed_kbps = parsed_args.can_speed
    config.safety_mode = parsed_args.safety_mode
    
    # Save config if requested
    if parsed_args.save_config:
        save_path = Path(parsed_args.save_config)
        config.to_file(save_path)
        print(f"Configuration saved to {save_path}")
        return 0
    
    # Set up logging
    log_level = logging.DEBUG if config.verbose else logging.INFO
    logger = setup_logging(log_level)
    
    logger.info(f"Starting MarsMode v2.0.0 in '{config.mode}' mode")
    
    if config.dry_run:
        logger.info("[DRY RUN MODE] No CAN messages will be sent")
    
    # Get the mode class
    mode_class = MODE_REGISTRY.get(config.mode)
    if mode_class is None:
        logger.error(f"Unknown mode: {config.mode}")
        return 1
    
    # Create controller and run mode
    try:
        controller = PandaController(config=config, logger=logger)
        mode = mode_class(controller, config, logger)
        mode.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=config.verbose)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
