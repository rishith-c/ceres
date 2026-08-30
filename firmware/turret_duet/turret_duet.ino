// turret_duet.ino — standalone kinematic pan/tilt show. NO USB needed once
// flashed: unplug and let it run. Wheels untouched.
//
// tilt (ch0, MG996R): smooth sine 62-118 deg, 5 s period
// pan  (ch2, continuous): 300 ms alternating nudges, fired ONLY while the
//   tilt passes near center — big servos take turns, so the 6 V rail never
//   sees both peaks at once (the intermittent-hammer fix).
// probe (ch1): untouched, no pulses.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH_TILT = 0, CH_PROBE = 1, CH_PAN = 2;
const int PAN_L = 1250, PAN_R = 1750;

unsigned long t0, lastNudge = 0, panOffAt = 0;
bool panOn = false, nudgeRight = true;

void writeUs(uint8_t ch, float us) {
  pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
}

void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  pca.setPWM(CH_PROBE, 0, 0);          // probe limp
  pca.setPWM(CH_PAN, 0, 0);            // pan off until first nudge
  writeUs(CH_TILT, 1500);              // tilt level
  delay(1500);
  t0 = millis();
}

void loop() {
  unsigned long now = millis();
  float t = (now - t0) / 1000.0;

  float tilt = 90.0 + 28.0 * sin(2 * PI * t / 5.0);   // 62..118
  writeUs(CH_TILT, 600.0 + tilt * 10.0);

  if (!panOn && fabs(tilt - 90.0) < 8.0 && now - lastNudge > 2000) {
    writeUs(CH_PAN, nudgeRight ? PAN_R : PAN_L);
    nudgeRight = !nudgeRight;
    panOn = true;
    panOffAt = now + 300;
    lastNudge = now;
  }
  if (panOn && (long)(now - panOffAt) >= 0) {
    pca.setPWM(CH_PAN, 0, 0);          // cut pan pulses: coast to stop
    panOn = false;
  }
  delay(20);
}
