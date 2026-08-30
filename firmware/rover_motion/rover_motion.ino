// rover_motion.ino v3 — Field Triage Rover: wheels + servos on one Mega
//
// Target: Arduino Mega 2560. Wheels through TWO L298N modules (all 12 pins
// independent, LastMinuteEngineers-style); servos through a PCA9685 on the
// Mega's I2C (SDA 20, SCL 21) — the PCA9685 makes its own pulses, so the old
// Servo-library/Timer1 conflict does not exist here.
//
// Servo roster: ch0 probe = MG996R (force calc requires it),
//               ch1 pan   = MG90S  (thrust collar carries the camera moment),
//               ch2 tilt  = MG996R (holds the camera against gravity).
//
// Serial protocol (ASCII, newline-terminated), 115200 baud:
//   PING                  -> OK PONG
//   FWD <ms> <pwm>        -> OK FWD      auto-stops after <ms>
//   REV <ms> <pwm>        -> OK REV
//   SPIN <ms> <pwm> <L|R> -> OK SPIN
//   STOP                  -> OK STOP
//   PROBE <0-100>         -> OK PROBE    0 = retracted, 100 = inserted
//   PAN <deg> / TILT <deg>-> OK PAN|TILT
//   HOME                  -> OK HOME
//   STATUS -> OK <drive> <pwm> <probe> <pan> <tilt> <settled> <uptime>
//
// Safety: no untimed motion; 400 ms host watchdog; PROBE refused while
// driving; driving refused while the probe is deployed; ~83 deg/s servo slew.
// Rules: IN pins only digitalWrite, EN pins only analogWrite, stop = EN 0.

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// ---- wheels: two L298N modules ---------------------------------------------
//                       EN  IN-a IN-b
const uint8_t FL[3] = {  9,  8,   7 };   // front-left   board1 ENA/IN1/IN2
const uint8_t RL[3] = {  3,  5,   4 };   // rear-left    board1 ENB/IN3/IN4
const uint8_t FR[3] = { 10, 11,  12 };   // front-right  board2 ENA/IN1/IN2
const uint8_t RR[3] = {  6, 13,   2 };   // rear-right   board2 ENB/IN3/IN4
const uint8_t* MOTOR[4] = { FL, RL, FR, RR };

// Flip per motor if it runs backward — never touch the EN pins.
const bool FWD_HIGH[4] = { true, true, true, true };   // FL RL FR RR

// 3-6 V TT motors on a ~9 V rail (3S minus the L298 drop).
const uint8_t MAX_PWM = 160;
const unsigned long WATCHDOG_MS = 400;
const unsigned long MAX_DRIVE_MS = 10000;

// ---- servos: PCA9685 --------------------------------------------------------
Adafruit_PWMServoDriver pca;
const uint8_t CH_PROBE = 0, CH_PAN = 1, CH_TILT = 2;
const int US_MIN = 600, US_MAX = 2400;   // full range; the probe needs all of it
const float SLEW_US_PER_S = 1000.0;      // ~83 deg/s
const uint8_t SERVO_TICK_MS = 20;
const int HOME_US[3] = { US_MIN, 1500, 1500 };  // probe retracted, pan/tilt 90

float curUs[3], targetUs[3];

// ---- state ------------------------------------------------------------------
enum DriveState { IDLE, FWD, REV, SPINL, SPINR };
DriveState drive = IDLE;
uint8_t drivePwm = 0;
unsigned long driveStopAt = 0, lastRxMs = 0, lastServoTick = 0;

char lineBuf[48];
uint8_t lineLen = 0;
bool lineOverflow = false;

// ---- motors -----------------------------------------------------------------
void stopMotors() {
  for (uint8_t m = 0; m < 4; m++) analogWrite(MOTOR[m][0], 0);
  drive = IDLE;
  drivePwm = 0;
}

void setMotor(uint8_t m, bool fwd, uint8_t pwm) {
  bool h = (fwd == FWD_HIGH[m]);
  digitalWrite(MOTOR[m][1], h ? HIGH : LOW);
  digitalWrite(MOTOR[m][2], h ? LOW : HIGH);
  analogWrite(MOTOR[m][0], pwm);
}

void startDrive(DriveState d, unsigned long ms, uint8_t pwm) {
  if (pwm > MAX_PWM) pwm = MAX_PWM;
  bool leftFwd = (d == FWD || d == SPINR);
  bool rightFwd = (d == FWD || d == SPINL);
  setMotor(0, leftFwd, pwm);
  setMotor(1, leftFwd, pwm);
  setMotor(2, rightFwd, pwm);
  setMotor(3, rightFwd, pwm);
  drive = d;
  drivePwm = pwm;
  driveStopAt = millis() + ms;
}

// ---- servos -----------------------------------------------------------------
void writeServoUs(uint8_t ch, float us) {
  pca.setPWM(ch, 0, (int)(us * 4096.0 / 20000.0 + 0.5));  // 50 Hz frame
}

bool servosSettled() {
  for (uint8_t i = 0; i < 3; i++)
    if (fabs(curUs[i] - targetUs[i]) > 6.0) return false;
  return true;
}

bool probeRetracted() {
  return targetUs[CH_PROBE] <= US_MIN + 6 && curUs[CH_PROBE] <= US_MIN + 24;
}

void servoTick() {
  unsigned long now = millis();
  if (now - lastServoTick < SERVO_TICK_MS) return;
  float step = SLEW_US_PER_S * (now - lastServoTick) / 1000.0;
  lastServoTick = now;
  for (uint8_t i = 0; i < 3; i++) {
    float d = targetUs[i] - curUs[i];
    if (fabs(d) <= step) curUs[i] = targetUs[i];
    else curUs[i] += (d > 0 ? step : -step);
    writeServoUs(i, curUs[i]);
  }
}

int probePct() { return (int)((curUs[0] - US_MIN) * 100.0 / (US_MAX - US_MIN) + 0.5); }
int panDeg()   { return (int)((curUs[1] - US_MIN) / 10.0 + 0.5); }
int tiltDeg()  { return (int)((curUs[2] - US_MIN) / 10.0 + 0.5); }

// ---- protocol ---------------------------------------------------------------
void err(const char* reason) {
  Serial.print(F("ERR "));
  Serial.println(reason);
}

bool parseLong(const char* s, long* out, long lo, long hi) {
  if (s == NULL || *s == '\0') return false;
  char* end;
  long v = strtol(s, &end, 10);
  if (*end != '\0' || v < lo || v > hi) return false;
  *out = v;
  return true;
}

void handleDriveCmd(DriveState d, const char* okName) {
  char* msTok = strtok(NULL, " ");
  char* pwmTok = strtok(NULL, " ");
  long ms, pwm;
  if (!parseLong(msTok, &ms, 1, MAX_DRIVE_MS) || !parseLong(pwmTok, &pwm, 0, 255)) {
    err("bad_args");
    return;
  }
  if (d == SPINL) {
    char* side = strtok(NULL, " ");
    if (side == NULL || side[1] != '\0' || (side[0] != 'L' && side[0] != 'R')) {
      err("bad_args");
      return;
    }
    if (side[0] == 'R') d = SPINR;
  }
  if (!probeRetracted()) {  // rolling with the probe down snaps the probe
    err("probe_deployed");
    return;
  }
  startDrive(d, (unsigned long)ms, (uint8_t)pwm);
  Serial.print(F("OK "));
  Serial.println(okName);
}

void handleLine(char* line) {
  char* cmd = strtok(line, " ");
  if (cmd == NULL) return;

  if (strcmp(cmd, "PING") == 0) {
    Serial.println(F("OK PONG"));

  } else if (strcmp(cmd, "FWD") == 0) {
    handleDriveCmd(FWD, "FWD");
  } else if (strcmp(cmd, "REV") == 0) {
    handleDriveCmd(REV, "REV");
  } else if (strcmp(cmd, "SPIN") == 0) {
    handleDriveCmd(SPINL, "SPIN");

  } else if (strcmp(cmd, "STOP") == 0) {
    stopMotors();
    Serial.println(F("OK STOP"));

  } else if (strcmp(cmd, "PROBE") == 0) {
    long pct;
    if (!parseLong(strtok(NULL, " "), &pct, 0, 100)) { err("bad_args"); return; }
    if (drive != IDLE) { err("moving"); return; }
    targetUs[CH_PROBE] = US_MIN + pct * (US_MAX - US_MIN) / 100.0;
    Serial.println(F("OK PROBE"));

  } else if (strcmp(cmd, "PAN") == 0 || strcmp(cmd, "TILT") == 0) {
    long deg;
    if (!parseLong(strtok(NULL, " "), &deg, 0, 180)) { err("bad_args"); return; }
    targetUs[cmd[0] == 'P' ? CH_PAN : CH_TILT] = US_MIN + deg * 10.0;
    Serial.println(cmd[0] == 'P' ? F("OK PAN") : F("OK TILT"));

  } else if (strcmp(cmd, "HOME") == 0) {
    if (drive != IDLE) { err("moving"); return; }
    for (uint8_t i = 0; i < 3; i++) targetUs[i] = HOME_US[i];
    Serial.println(F("OK HOME"));

  } else if (strcmp(cmd, "STATUS") == 0) {
    static const char* names[] = { "IDLE", "FWD", "REV", "SPINL", "SPINR" };
    Serial.print(F("OK "));
    Serial.print(names[drive]); Serial.print(' ');
    Serial.print(drivePwm);     Serial.print(' ');
    Serial.print(probePct());   Serial.print(' ');
    Serial.print(panDeg());     Serial.print(' ');
    Serial.print(tiltDeg());    Serial.print(' ');
    Serial.print(servosSettled() ? 1 : 0); Serial.print(' ');
    Serial.println(millis());

  } else {
    err("unknown_cmd");
  }
}

// ---- setup / loop -----------------------------------------------------------
void setup() {
  for (uint8_t m = 0; m < 4; m++)
    for (uint8_t k = 0; k < 3; k++) pinMode(MOTOR[m][k], OUTPUT);
  stopMotors();

  pca.begin();
  pca.setPWMFreq(50);
  for (uint8_t i = 0; i < 3; i++) {
    curUs[i] = targetUs[i] = HOME_US[i];
    writeServoUs(i, curUs[i]);
  }

  Serial.begin(115200);
  lastRxMs = millis();
  lastServoTick = millis();
  Serial.println(F("READY rover_motion 3.0"));
}

void loop() {
  unsigned long now = millis();
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    lastRxMs = now;
    if (c == '\n' || c == '\r') {
      if (lineOverflow) { err("line_too_long"); lineOverflow = false; lineLen = 0; }
      else if (lineLen > 0) { lineBuf[lineLen] = '\0'; handleLine(lineBuf); lineLen = 0; }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineOverflow = true;
    }
  }
  if (drive != IDLE) {
    if ((long)(now - driveStopAt) >= 0) stopMotors();
    else if (now - lastRxMs > WATCHDOG_MS) stopMotors();
  }
  servoTick();
}
