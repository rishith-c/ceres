"""Probe + turret servos on a PCA9685 hanging off the Pi's I2C bus.

Servo roster (HANDOFF §3 resolution 2, amended 2026-08-29):
  ch 0  probe  MG996R  600-2400 us  — the ONLY servo strong enough for the
                                      probe's calculated insertion force
  ch 1  pan    SG90    500-2400 us  — OK only because the printed thrust
                                      collar carries the camera's weight
  ch 2  tilt   MG996R  600-2400 us  — holds the C920 against gravity

Safety rules that used to live in the Arduino firmware and now live HERE,
because the Pi owns both the wheels (via rover.py) and the servos:
  - NEVER command wheels while the probe is deployed, and never deploy the
    probe while driving. Check `probe_deployed` before Rover.forward() etc.
  - Never park the probe loaded: insert, dwell, retract (HANDOFF §4).
  - Servos slew at ~83 deg/s instead of snapping.

Wiring: PCA9685 VCC->Pi 3.3V, SDA->GPIO2, SCL->GPIO3, GND->Pi GND.
V+ comes from the 5.5-6 V servo rail ONLY — never the Pi's 5 V pin.
Needs: sudo raspi-config -> enable I2C; pip3 install adafruit-circuitpython-servokit
"""

from __future__ import annotations

import time

PROBE_CH, PAN_CH, TILT_CH = 0, 1, 2
SLEW_DEG_S = 83.0
TICK_S = 0.02
PROBE_SWEEP_DEG = 150.0     # full 0-100% stroke, needs the 600-2400 us range


class ProbeTurret:
    def __init__(self, kit=None):
        """kit is injectable for tests; by default builds an adafruit ServoKit."""
        if kit is None:
            from adafruit_servokit import ServoKit  # lazy: hardware-only dep
            kit = ServoKit(channels=16)
        self._kit = kit
        for ch, (lo, hi, rng) in {PROBE_CH: (600, 2400, 150),
                                  PAN_CH: (500, 2400, 180),
                                  TILT_CH: (600, 2400, 180)}.items():
            self._kit.servo[ch].set_pulse_width_range(lo, hi)
            self._kit.servo[ch].actuation_range = rng
        # Assume nothing about physical position at boot: command home slowly.
        self._pos = {PROBE_CH: 0.0, PAN_CH: 90.0, TILT_CH: 90.0}
        for ch, a in self._pos.items():
            self._kit.servo[ch].angle = a

    # -- internals -----------------------------------------------------------

    def _slew(self, ch: int, target: float) -> None:
        """Move one channel at ~83 deg/s instead of letting it snap."""
        pos = self._pos[ch]
        step = SLEW_DEG_S * TICK_S
        while abs(target - pos) > step:
            pos += step if target > pos else -step
            self._kit.servo[ch].angle = pos
            time.sleep(TICK_S)
        self._kit.servo[ch].angle = target
        self._pos[ch] = target

    # -- probe ---------------------------------------------------------------

    @property
    def probe_deployed(self) -> bool:
        """True unless the probe is fully retracted. Callers must not drive
        the wheels while this is True."""
        return self._pos[PROBE_CH] > 2.0

    def probe(self, pct: float) -> None:
        """0 = retracted, 100 = fully inserted."""
        if not 0 <= pct <= 100:
            raise ValueError("probe pct must be 0-100")
        self._slew(PROBE_CH, pct / 100.0 * PROBE_SWEEP_DEG)

    def sample(self, read_fn, dwell_s: float = 3.0, depth_pct: float = 100):
        """One soil measurement, never parking the probe loaded:
        insert -> dwell (temperature die needs seconds) -> read -> retract.
        read_fn() is called at depth after the dwell; its result is returned.
        The probe retracts even if read_fn raises."""
        self.probe(depth_pct)
        try:
            time.sleep(dwell_s)
            return read_fn()
        finally:
            self.probe(0)

    # -- turret --------------------------------------------------------------

    def pan(self, deg: float) -> None:
        if not 0 <= deg <= 180:
            raise ValueError("pan deg must be 0-180")
        self._slew(PAN_CH, deg)

    def tilt(self, deg: float) -> None:
        if not 0 <= deg <= 180:
            raise ValueError("tilt deg must be 0-180")
        self._slew(TILT_CH, deg)

    def home(self) -> None:
        self.probe(0)
        self.pan(90)
        self.tilt(90)
