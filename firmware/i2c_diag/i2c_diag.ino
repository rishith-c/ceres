// i2c_diag.ino — is the PCA9685 wired right? Scans I2C, then wiggles ch0-2.
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
bool found = false;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(300);
  Serial.println(F("I2C scan (SDA=20, SCL=21 on Mega):"));
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("  device at 0x"));
      Serial.println(a, HEX);
      if (a == 0x40) found = true;
    }
  }
  if (found) {
    Serial.println(F("PCA9685 FOUND at 0x40 — I2C wiring is good."));
    Serial.println(F("Wiggling ch0/ch1/ch2 forever. If servos still don't move,"));
    Serial.println(F("the problem is servo POWER: buck 6V into V+ screw, common ground."));
    pca.begin();
    pca.setPWMFreq(50);
  } else {
    Serial.println(F("NO PCA9685 on the bus. Check: SDA->pin20, SCL->pin21,"));
    Serial.println(F("VCC->Mega 5V, GND->Mega GND. (V+ alone does not power the chip.)"));
  }
}

void loop() {
  if (!found) { delay(2000); Serial.println(F("still no PCA9685...")); return; }
  for (int us = 1200; us <= 1800; us += 600) {
    for (uint8_t ch = 0; ch < 3; ch++)
      pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
    Serial.print(F("all channels -> ")); Serial.print(us); Serial.println(F(" us"));
    delay(1200);
  }
}
