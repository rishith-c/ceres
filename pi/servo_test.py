#!/usr/bin/env python3
"""Bench test for the PCA9685 servo stack. Run ON THE PI:

    python3 servo_test.py

Commands:
    p <0-100>   probe: 0 retracted, 100 fully inserted (bench: no soil!)
    n <0-180>   pan   (SG90)
    t <0-180>   tilt  (MG996R)
    h           home everything (probe 0, pan 90, tilt 90)
    q           quit (homes first)

Servo V+ must come from the 5.5-6 V rail, never the Pi's 5 V pin.
"""

from actuators import ProbeTurret


def main():
    body = ProbeTurret()
    print(__doc__)
    while True:
        try:
            raw = input("> ").strip().lower().split()
        except (EOFError, KeyboardInterrupt):
            raw = ["q"]
        if not raw:
            continue
        cmd, arg = raw[0], (raw[1] if len(raw) > 1 else None)
        try:
            if cmd == "q":
                body.home()
                print("homed, bye")
                return
            elif cmd == "h":
                body.home()
                print("homed")
            elif cmd == "p" and arg is not None:
                body.probe(float(arg))
                print(f"probe at {arg}%")
            elif cmd == "n" and arg is not None:
                body.pan(float(arg))
                print(f"pan {arg} deg")
            elif cmd == "t" and arg is not None:
                body.tilt(float(arg))
                print(f"tilt {arg} deg")
            else:
                print("commands: p <0-100> | n <0-180> | t <0-180> | h | q")
        except ValueError as e:
            print(f"no: {e}")


if __name__ == "__main__":
    main()
