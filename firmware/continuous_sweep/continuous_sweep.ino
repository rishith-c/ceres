// continuous_sweep.ino — endless gentle sweeps, one axis at a time.
//   MG90S  (ch1): 30 right, 30 left of center
//   MG996R pan  (ch2): 45 right, 45 left
//   MG996R tilt (ch0): 45 up, 45 down
// Wiring as rover_motion v3. PCA9685 ch0 tilt, ch1 MG90S, ch2 pan.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH_TILT = 0, CH_MG90 = 1, CH_PAN = 2;

float pos[3] = {90, 90, 90};

void writeDeg(uint8_t ch, float deg) {
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
  Serial.println(F("CONTINUOUS SWEEP: mg90 +/-30, pan +/-45, tilt +/-45"));
  delay(1500);
}

void loop() {
  Serial.println(F("mg90 right 30"));  moveTo(CH_MG90, 120); delay(400);
  Serial.println(F("mg90 left 30"));   moveTo(CH_MG90, 60);  delay(400);
  moveTo(CH_MG90, 90);                 delay(600);

  Serial.println(F("pan right 45"));   moveTo(CH_PAN, 135);  delay(400);
  Serial.println(F("pan left 45"));    moveTo(CH_PAN, 45);   delay(400);
  moveTo(CH_PAN, 90);                  delay(600);

  Serial.println(F("tilt up 45"));     moveTo(CH_TILT, 135); delay(400);
  Serial.println(F("tilt down 45"));   moveTo(CH_TILT, 45);  delay(400);
  moveTo(CH_TILT, 90);                 delay(600);
}
