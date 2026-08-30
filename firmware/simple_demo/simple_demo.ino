// simple_demo.ino — calm bench demo, no loopy patterns, wires stay put.
// One axis at a time, small angles, steady speed:
//   pan: center -> left -> right -> center
//   tilt: center -> up -> down -> center
//   probe (MG90S): out and back
// Wiring as rover_motion v3. PCA9685 ch0 tilt, ch1 probe, ch2 pan.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH_TILT = 0, CH_PROBE = 1, CH_PAN = 2;

float pos[3] = {90, 0, 90};   // current deg per channel (probe stored as deg)

void writeDeg(uint8_t ch, float deg) {
  float us = 600.0 + deg * 10.0;
  pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
}

// steady move, ~60 deg/s, one channel at a time
void moveTo(uint8_t ch, float target) {
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
  Serial.println(F("SIMPLE DEMO: pan left/right, tilt up/down, probe in/out"));
  delay(1500);
}

void loop() {
  Serial.println(F("pan left"));    moveTo(CH_PAN, 55);   delay(600);
  Serial.println(F("pan right"));   moveTo(CH_PAN, 125);  delay(600);
  Serial.println(F("pan center"));  moveTo(CH_PAN, 90);   delay(800);

  Serial.println(F("tilt up"));     moveTo(CH_TILT, 115); delay(600);
  Serial.println(F("tilt down"));   moveTo(CH_TILT, 65);  delay(600);
  Serial.println(F("tilt center")); moveTo(CH_TILT, 90);  delay(800);

  Serial.println(F("probe out"));   moveTo(CH_PROBE, 75); delay(1000);
  Serial.println(F("probe back"));  moveTo(CH_PROBE, 0);  delay(800);

  Serial.println(F("--- loop ---"));
  delay(2000);
}
