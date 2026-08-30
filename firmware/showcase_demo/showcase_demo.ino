// showcase_demo.ino — auto-looping demo for the whole rover.
// Cinematic eased motion for pan/tilt, plain steady motion for the probe,
// and a short wheel routine. Wheels OFF the ground, probe in open air.
//
// Same wiring as rover_motion v3:
//   L298N left:  ENA 9, IN1 8, IN2 7, IN3 5, IN4 4, ENB 3
//   L298N right: ENA 10, IN1 11, IN2 12, IN3 13, IN4 2, ENB 6
//   PCA9685 on I2C (Mega SDA 20 / SCL 21): ch0 tilt, ch1 probe, ch2 pan

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

//                       EN  IN-a IN-b
const uint8_t FL[3] = {  9,  8,   7 };
const uint8_t RL[3] = {  3,  5,   4 };
const uint8_t FR[3] = { 10, 11,  12 };
const uint8_t RR[3] = {  6, 13,   2 };
const uint8_t* MOTOR[4] = { FL, RL, FR, RR };
const uint8_t DEMO_PWM = 140;          // 3-6 V motors on a ~9-11 V rail

Adafruit_PWMServoDriver pca;
const uint8_t CH_TILT = 0, CH_PROBE = 1, CH_PAN = 2;

// ---------- servo primitives ----------
void servoDeg(uint8_t ch, float deg) {           // 0-180 over 600-2400 us
  float us = 600.0 + deg * 10.0;
  pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
}
void probePct(float pct) { servoDeg(CH_PROBE, pct * 1.5); }  // 0-100% = 0-150 deg

float easeInOut(float t) {               // 0..1 -> 0..1, slow-fast-slow
  return 0.5 - 0.5 * cos(t * PI);
}

// Cinematic: eased glide from one pose to another over move_ms.
void glideTo(float panFrom, float panTo, float tiltFrom, float tiltTo, int move_ms) {
  unsigned long t0 = millis();
  while (true) {
    float t = (millis() - t0) / (float)move_ms;
    if (t >= 1.0) break;
    float e = easeInOut(t);
    servoDeg(CH_PAN, panFrom + (panTo - panFrom) * e);
    servoDeg(CH_TILT, tiltFrom + (tiltTo - tiltFrom) * e);
    delay(20);
  }
  servoDeg(CH_PAN, panTo);
  servoDeg(CH_TILT, tiltTo);
}

// Normal: constant-rate probe move (~83 deg/s like the real firmware).
void probeMove(float fromPct, float toPct) {
  float fromDeg = fromPct * 1.5, toDeg = toPct * 1.5;
  float step = 83.0 * 0.02;                        // deg per 20 ms tick
  float pos = fromDeg;
  while (fabs(toDeg - pos) > step) {
    pos += (toDeg > pos) ? step : -step;
    servoDeg(CH_PROBE, pos);
    delay(20);
  }
  servoDeg(CH_PROBE, toDeg);
}

// ---------- motor primitives ----------
void allStop() {
  for (uint8_t m = 0; m < 4; m++) analogWrite(MOTOR[m][0], 0);
}
void setMotor(uint8_t m, bool fwd, uint8_t pwm) {
  digitalWrite(MOTOR[m][1], fwd ? HIGH : LOW);
  digitalWrite(MOTOR[m][2], fwd ? LOW : HIGH);
  analogWrite(MOTOR[m][0], pwm);
}
void driveRamped(bool leftFwd, bool rightFwd, int hold_ms) {
  for (int p = 0; p <= DEMO_PWM; p += 4) {         // soft launch
    setMotor(0, leftFwd, p);  setMotor(1, leftFwd, p);
    setMotor(2, rightFwd, p); setMotor(3, rightFwd, p);
    delay(15);
  }
  delay(hold_ms);
  for (int p = DEMO_PWM; p >= 0; p -= 4) {         // soft stop
    setMotor(0, leftFwd, p);  setMotor(1, leftFwd, p);
    setMotor(2, rightFwd, p); setMotor(3, rightFwd, p);
    delay(10);
  }
  allStop();
}

// ---------- the show ----------
void turretWakeUp() {
  Serial.println(F("turret: wake up"));
  glideTo(90, 90, 90, 55, 900);        // look down...
  glideTo(90, 90, 55, 90, 900);        // ...and back up
  glideTo(90, 35, 90, 80, 1100);       // glance left
  glideTo(35, 145, 80, 80, 1600);      // sweep right
  glideTo(145, 90, 80, 90, 1100);      // settle center
}

void turretScan() {
  Serial.println(F("turret: cinematic scan"));
  unsigned long t0 = millis();
  while (millis() - t0 < 9000) {       // smooth figure-pattern for 9 s
    float t = (millis() - t0) / 1000.0;
    servoDeg(CH_PAN,  90 + 52 * sin(2 * PI * 0.14 * t));
    servoDeg(CH_TILT, 85 + 22 * sin(2 * PI * 0.28 * t + PI / 2));
    delay(20);
  }
  glideTo(90, 90, 85, 90, 700);
}

void probeSample() {
  Serial.println(F("probe: insert, dwell, retract"));
  probeMove(0, 60);                    // steady descent
  delay(2000);                         // dwell (reading would happen here)
  probeMove(60, 0);                    // steady retract
}

void wheelRoutine() {
  Serial.println(F("wheels: forward, spin left, spin right"));
  driveRamped(true, true, 1200);       // forward
  delay(400);
  driveRamped(false, true, 800);       // spin left
  delay(400);
  driveRamped(true, false, 800);       // spin right
  delay(400);
}

void setup() {
  for (uint8_t m = 0; m < 4; m++)
    for (uint8_t k = 0; k < 3; k++) pinMode(MOTOR[m][k], OUTPUT);
  allStop();
  pca.begin();
  pca.setPWMFreq(50);
  servoDeg(CH_PAN, 90);
  servoDeg(CH_TILT, 90);
  probePct(0);
  Serial.begin(115200);
  Serial.println(F("SHOWCASE DEMO — wheels off the ground, probe in open air"));
  delay(1500);
}

void loop() {
  turretWakeUp();
  turretScan();
  probeSample();                       // probe only moves while wheels are stopped
  wheelRoutine();                      // wheels only move with the probe retracted
  Serial.println(F("--- loop ---"));
  delay(1500);
}
