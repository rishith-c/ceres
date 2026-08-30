// continuous_sweep.ino — endless gentle sweeps, one axis at a time.
//   ch1 MG90S : 30 right, 30 left of center — HARD-CLAMPED to 30..150 deg,
//               it can NEVER be commanded to 0 (or past 150), even by mistake.
//   ch0 MG996R pan : 45 right, 45 left
//   ch2 MG996R tilt: 45 up, 45 down

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH_996 = 0, CH_MG90 = 1, CH_TILT = 2;

const float MG90_MIN = 30.0, MG90_MAX = 150.0;   // the safety fence

float pos[3] = {90, 90, 90};

void writeDeg(uint8_t ch, float deg) {
  if (ch == CH_MG90) {                 // fence enforced at the lowest level
    if (deg < MG90_MIN) deg = MG90_MIN;
    if (deg > MG90_MAX) deg = MG90_MAX;
  }
  float us = 600.0 + deg * 10.0;
  pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
}

void moveTo(uint8_t ch, float target) {   // steady ~60 deg/s
  float step = 60.0 * 0.02;
  while (fabs(target - pos[ch]) > step) {
    pos[ch] += (target > pos[ch]) ? step : -step;
    writeDeg(ch, pos[ch]);
    delay(20);
  }
  pos[ch] = target;
  writeDeg(ch, target);
}

void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  for (uint8_t ch = 0; ch < 3; ch++) writeDeg(ch, pos[ch]);
  Serial.begin(115200);
  Serial.println(F("SWEEP: ch1 mg90 +/-30 (fenced 30-150), ch0 pan +/-45, ch2 tilt +/-45"));
  delay(1500);
}

void loop() {
  Serial.println(F("mg90 right 30"));  moveTo(CH_MG90, 120); delay(400);
  Serial.println(F("mg90 left 30"));   moveTo(CH_MG90, 60);  delay(400);
  moveTo(CH_MG90, 90);                 delay(600);

  Serial.println(F("pan right 45"));   moveTo(CH_996, 135);  delay(400);
  Serial.println(F("pan left 45"));    moveTo(CH_996, 45);   delay(400);
  moveTo(CH_996, 90);                  delay(600);

  Serial.println(F("tilt up 45"));     moveTo(CH_TILT, 135); delay(400);
  Serial.println(F("tilt down 45"));   moveTo(CH_TILT, 45);  delay(400);
  moveTo(CH_TILT, 90);                 delay(600);
}
