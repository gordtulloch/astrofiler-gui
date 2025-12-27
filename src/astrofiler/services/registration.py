from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# Hardcoded registration settings (per project decision)
REGISTRATION_ENABLED = True
REGISTRATION_HOST = "www.gordtulloch.com"
REGISTRATION_PORT = 5050
REGISTRATION_TIMEOUT_SECONDS = 2.0


def ping_once(host: str, port: int, timeout_seconds: float) -> None:
    """Open and close a TCP connection.

    The registration server counts a connection as a "use"; no payload is sent.
    Raises on failure.
    """

    with socket.create_connection((host, port), timeout=timeout_seconds):
        return


def start_startup_ping(
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Kick off a background registration ping.

    Never raises; intended to be safe to call during GUI startup.
    """

    def status(msg: str) -> None:
        if callable(status_callback):
            try:
                status_callback(msg)
            except Exception:
                pass

    def worker() -> None:
        try:
            if not REGISTRATION_ENABLED:
                logger.debug("Registration ping disabled (hardcoded)")
                return

            status("Pinging registration server...")
            ping_once(REGISTRATION_HOST, REGISTRATION_PORT, REGISTRATION_TIMEOUT_SECONDS)
            logger.info(
                "Registration ping succeeded (%s:%d)",
                REGISTRATION_HOST,
                REGISTRATION_PORT,
            )
        except Exception as e:
            # Intentionally quiet: registration must not impact startup.
            logger.info("Registration ping failed: %s", e)

    t = threading.Thread(target=worker, name="registration-ping", daemon=True)
    t.start()
