"""
logger.py — WebPulse Terminal Intelligence Logger

Provides a professional, colour-coded logging experience that prints
structured status updates to the terminal during an audit run.

Usage:
    from src.logger import pulse_logger
    pulse_logger.info("Successfully navigated to %s", url)
"""

import logging
import sys


class _PulseFormatter(logging.Formatter):
    """Custom formatter that prefixes every message with a branded tag
    and a status icon based on severity level."""

    # ANSI colour codes for terminal output
    _COLOURS = {
        logging.DEBUG:    "\033[90m",     # grey
        logging.INFO:     "\033[96m",     # cyan
        logging.WARNING:  "\033[93m",     # yellow
        logging.ERROR:    "\033[91m",     # red
        logging.CRITICAL: "\033[1;91m",   # bold red
    }
    _ICONS = {
        logging.DEBUG:    "…",
        logging.INFO:     "✔",
        logging.WARNING:  "⚠",
        logging.ERROR:    "✖",
        logging.CRITICAL: "‼",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        icon = self._ICONS.get(record.levelno, " ")
        tag = f"{colour}[WEBPULSE]{self._RESET}"
        body = super().format(record)
        return f"  {tag} {colour}{icon}{self._RESET} {body}"


def _build_pulse_logger() -> logging.Logger:
    """Construct and return the singleton WebPulse logger."""
    logger = logging.getLogger("webpulse")
    logger.setLevel(logging.DEBUG)

    # Force stdout to UTF-8 on Windows so icons print correctly without crashing
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(_PulseFormatter())
        logger.addHandler(console_handler)

    # Prevent propagation to the root logger to avoid duplicate messages
    logger.propagate = False
    return logger


# ── Public API ──────────────────────────────────────────────────────────
pulse_logger = _build_pulse_logger()
