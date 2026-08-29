"""Serial driver for rover_motion.ino v2 (wheels only — servos live on the
Pi's PCA9685, see actuators.py).

Connection handling only — no sequencing logic. The firmware is a serial
slave: every drive command is timed and auto-stops, and a 400 ms host
watchdog cuts the motors if we go silent while the wheels turn. That means
the caller MUST keep talking during motion — use wait_for_stop(), which
polls STATUS and doubles as the watchdog keepalive.

SAFETY (interlock moved here from the v1 firmware): never call forward/
reverse/spin while actuators.ProbeTurret.probe_deployed is True.

Opening the serial port resets the MCU. connect() absorbs that by waiting
for the READY banner instead of guessing with a sleep.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


class RoverError(Exception):
    """Base class for driver failures."""


class RoverTimeout(RoverError):
    """No (or no complete) reply within the deadline."""


class RoverCommandError(RoverError):
    """Firmware replied ERR <reason>; .reason carries the reason token."""

    def __init__(self, reason: str):
        super().__init__(f"rover replied ERR {reason}")
        self.reason = reason


@dataclass
class RoverStatus:
    drive: str        # IDLE | FWD | REV | SPINL | SPINR
    pwm: int
    uptime_ms: int


class Rover:
    def __init__(self, port: str | None = None, *, baud: int = 115200,
                 ready_timeout: float = 6.0, cmd_timeout: float = 2.0,
                 transport=None):
        """transport: pre-opened pyserial-like object (write/readline/close),
        used by tests. Give either port or transport."""
        self.port = port
        self.baud = baud
        self.ready_timeout = ready_timeout
        self.cmd_timeout = cmd_timeout
        self._ser = transport

    # -- connection ----------------------------------------------------------

    def connect(self) -> None:
        if self._ser is None:
            import serial  # lazy: not needed for tests
            # Short read timeout so readline() never blocks past our deadlines.
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
        self._wait_for_ready()

    def _wait_for_ready(self) -> None:
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            line = self._read_line()
            if line is not None and line.startswith("READY"):
                return
        raise RoverTimeout("no READY banner — is the firmware flashed?")

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def __enter__(self) -> "Rover":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self._ser is not None:
                self._command("STOP")
        except RoverError:
            pass
        self.close()

    # -- wire ----------------------------------------------------------------

    def _read_line(self) -> str | None:
        raw = self._ser.readline()
        if not raw:
            return None
        return raw.decode("ascii", errors="replace").strip()

    def _command(self, cmd: str, timeout: float | None = None) -> str:
        """Send one command, return the payload after 'OK '."""
        if self._ser is None:
            raise RoverError("not connected")
        self._ser.write((cmd + "\n").encode("ascii"))
        deadline = time.monotonic() + (timeout or self.cmd_timeout)
        while time.monotonic() < deadline:
            line = self._read_line()
            if line is None or line == "":
                continue
            if line.startswith("OK"):
                return line[2:].strip()
            if line.startswith("ERR"):
                raise RoverCommandError(line[3:].strip() or "unknown")
            if line.startswith("READY"):
                # Unsolicited READY mid-conversation = the MCU reset on us.
                raise RoverError("controller reset unexpectedly")
            # Anything else is line noise; keep reading.
        raise RoverTimeout(f"no reply to {cmd.split()[0]}")

    # -- commands (HANDOFF §4) ----------------------------------------------

    def ping(self) -> None:
        self._command("PING")

    def forward(self, ms: int, pwm: int) -> None:
        self._command(f"FWD {self._ms(ms)} {self._pwm(pwm)}")

    def reverse(self, ms: int, pwm: int) -> None:
        self._command(f"REV {self._ms(ms)} {self._pwm(pwm)}")

    def spin(self, ms: int, pwm: int, side: str) -> None:
        if side not in ("L", "R"):
            raise ValueError("side must be 'L' or 'R'")
        self._command(f"SPIN {self._ms(ms)} {self._pwm(pwm)} {side}")

    def stop(self) -> None:
        self._command("STOP")

    def status(self) -> RoverStatus:
        payload = self._command("STATUS")
        parts = payload.split()
        if len(parts) != 3:
            raise RoverError(f"malformed STATUS reply: {payload!r}")
        try:
            return RoverStatus(drive=parts[0], pwm=int(parts[1]),
                               uptime_ms=int(parts[2]))
        except ValueError as e:
            raise RoverError(f"malformed STATUS reply: {payload!r}") from e

    # -- helpers -------------------------------------------------------------

    def wait_for_stop(self, timeout: float = 15.0, poll: float = 0.1) -> RoverStatus:
        """Poll STATUS until the drive is IDLE. The polling itself is the
        watchdog keepalive — call this after every drive command."""
        deadline = time.monotonic() + timeout
        while True:
            st = self.status()
            if st.drive == "IDLE":
                return st
            if time.monotonic() > deadline:
                raise RoverTimeout("drive did not stop in time")
            time.sleep(poll)

    @staticmethod
    def _ms(ms: int) -> int:
        if not 1 <= ms <= 10000:
            raise ValueError("ms must be 1-10000")
        return ms

    @staticmethod
    def _pwm(pwm: int) -> int:
        if not 0 <= pwm <= 255:
            raise ValueError("pwm must be 0-255 (firmware caps at 160)")
        return pwm

