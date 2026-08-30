// spin_tracker.ino — interactive control of the CONTINUOUS servo on ch2.
// It spins right; type 1 -> print estimated angle, reverse to left;
// type 2 -> print estimated angle, spin right again; s -> stop; z -> zero.
//
// HONESTY NOTE: a continuous-rotation servo has no position sensor. The
// "angle" printed is DEAD-RECKONED (speed x time) and drifts over minutes.
// Calibrate SPIN_DEG_PER_S: let it spin exactly 10 s, count the turns,
// then SPIN_DEG_PER_S = turns * 360 / 10.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH = 2;

const int US_STOP = 1500;      // trim screw on the servo fine-tunes true stop
const int US_OFFSET = 120;     // small offset = slow spin = better estimate
float SPIN_DEG_PER_S = 200.0;  // CALIBRATE ME (see note above)

int dir = +1;                  // +1 spinning right, -1 left, 0 stopped
float angle = 0;               // estimated, degrees (can exceed 360)
unsigned long lastMs = 0;

void writeUs(int us) { pca.setPWM(CH, 0, (int)(us * 4096.0 / 20000.0 + 0.5)); }

void applyDir() {
  writeUs(US_STOP + dir * US_OFFSET);
}

void report(const char* what) {
  float wrapped = fmod(fmod(angle, 360.0) + 360.0, 360.0);
  Serial.print(what);
  Serial.print(F(" at estimated angle "));
  Serial.print(wrapped, 1);
  Serial.print(F(" deg (total "));
  Serial.print(angle, 1);
  Serial.println(F(" deg from start) [dead-reckoned, not measured]"));
}

void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  Serial.begin(115200);
  Serial.println(F("SPIN TRACKER (ch2 continuous servo)"));
  Serial.println(F("1 = report + spin LEFT   2 = report + spin RIGHT"));
  Serial.println(F("s = report + STOP        z = zero the angle counter"));
  delay(1500);
  lastMs = millis();
  dir = +1;
  applyDir();
  Serial.println(F("spinning RIGHT..."));
}

void loop() {
  // integrate the estimate
  unsigned long now = millis();
  angle += dir * SPIN_DEG_PER_S * (now - lastMs) / 1000.0;
  lastMs = now;

  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == '1')      { report("[1]"); dir = -1; applyDir(); Serial.println(F("spinning LEFT...")); }
  else if (c == '2') { report("[2]"); dir = +1; applyDir(); Serial.println(F("spinning RIGHT...")); }
  else if (c == 's') { report("[s]"); dir = 0;  applyDir(); Serial.println(F("stopped")); }
  else if (c == 'z') { angle = 0; Serial.println(F("angle counter zeroed")); }
}
