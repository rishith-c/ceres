// rover_motion.ino — Field Triage Rover motion controller
//
// Target: Arduino Uno R3 + Inland L298P 4-channel motor shield.
// Serial slave: the Pi owns sequencing, vision and triage; this board owns
// anything with a deadline. Protocol per HANDOFF.md §4 (ASCII, newline-terminated).
//
// REBUILT 2026-08-28 from the HANDOFF.md §4 spec — the original file was lost.
// Wiring assumed: resolution 1 from HANDOFF §3 (wheels paired: left pair on
// channel A, right pair on channel B; channels C/D empty; servos on the Uno).
//
// Hard rules from HANDOFF §3, kept here:
//  - DIR pins only ever digitalWrite; PWM pins only ever analogWrite.
//  - Motor stop is analogWrite(pin, 0).
//  - Servo library owns Timer1, so D9/D10 (channels C/D) have no PWM. Unused.

#include <Servo.h>

// ---- Motor shield (verified pinout, HANDOFF §3) -----------------------------
const uint8_t DIR_A = 3;   // left pair direction
const uint8_t PWM_A = 6;   // left pair speed (Timer0)
const uint8_t DIR_B = 4;   // right pair direction
const uint8_t PWM_B = 5;   // right pair speed (Timer0)

// Flip these if a pair runs backward after wiring — never swap PWM/DIR roles.
const uint8_t A_FORWARD = HIGH;
const uint8_t B_FORWARD = HIGH;

// Two TT motors share one 2 A L298 channel (~1.2 A stall each at ~6 V).
// Capping PWM at 200/255 keeps a worst-case stall under the channel rating.
const uint8_t MAX_PWM = 200;

// ---- Servos (free pins after shield: D2, D11, D12) --------------------------
const uint8_t PIN_PROBE = 11;
const uint8_t PIN_PAN   = 12;
const uint8_t PIN_TILT  = 2;

// Probe rack needs ~150° of sweep for the 47 mm stroke, which requires the
// full 600–2400 µs pulse range (HANDOFF §5, graceful degradation note).
const int SERVO_US_MIN = 600;
const int SERVO_US_MAX = 2400;

// ~83 °/s slew (HANDOFF §4): ≈1000 µs/s on a servo sweeping ~150° over the range.
const float SLEW_US_PER_S = 1000.0;
const uint8_t SERVO_TICK_MS = 20;

const int HOME_PROBE_US = SERVO_US_MIN;  // pct 0 = retracted
const int HOME_PAN_US   = 1500;          // 90°
const int HOME_TILT_US  = 1500;          // 90°

// ---- Safety timing ----------------------------------------------------------
const unsigned long WATCHDOG_MS = 400;    // host silence while driving -> stop
const unsigned long MAX_DRIVE_MS = 10000; // longer would be untimed in practice

// ---- State ------------------------------------------------------------------
enum DriveState { IDLE, FWD, REV, SPINL, SPINR };
DriveState drive = IDLE;
uint8_t drivePwm = 0;
unsigned long driveStopAt = 0;
unsigned long lastRxMs = 0;
unsigned long lastServoTick = 0;

Servo servoProbe, servoPan, servoTilt;
float curUs[3];     // probe, pan, tilt — actual commanded pulse, slewed
float targetUs[3];
Servo* servos[3] = { &servoProbe, &servoPan, &servoTilt };

char lineBuf[48];
uint8_t lineLen = 0;
bool lineOverflow = false;

// ---- Motors -----------------------------------------------------------------
void stopMotors() {
  analogWrite(PWM_A, 0);
  analogWrite(PWM_B, 0);
  drive = IDLE;
  drivePwm = 0;
}

void startDrive(DriveState d, unsigned long ms, uint8_t pwm) {
  if (pwm > MAX_PWM) pwm = MAX_PWM;
  switch (d) {
    case FWD:
      digitalWrite(DIR_A, A_FORWARD);
      digitalWrite(DIR_B, B_FORWARD);
      break;
    case REV:
      digitalWrite(DIR_A, !A_FORWARD);
      digitalWrite(DIR_B, !B_FORWARD);
      break;
    case SPINL:  // left pair back, right pair forward
      digitalWrite(DIR_A, !A_FORWARD);
      digitalWrite(DIR_B, B_FORWARD);
      break;
    case SPINR:
      digitalWrite(DIR_A, A_FORWARD);
      digitalWrite(DIR_B, !B_FORWARD);
      break;
    default:
      return;
  }
  analogWrite(PWM_A, pwm);
  analogWrite(PWM_B, pwm);
  drive = d;
  drivePwm = pwm;
  driveStopAt = millis() + ms;
}

// ---- Servos -----------------------------------------------------------------
bool servosSettled() {
  for (uint8_t i = 0; i < 3; i++)
    if (fabs(curUs[i] - targetUs[i]) > 6.0) return false;  // ~0.5°
  return true;
}

bool probeRetracted() {
  return targetUs[0] <= SERVO_US_MIN + 6 && curUs[0] <= SERVO_US_MIN + 24;
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
    servos[i]->writeMicroseconds((int)curUs[i]);
  }
}

int probePct() { return (int)((curUs[0] - SERVO_US_MIN) * 100.0 / (SERVO_US_MAX - SERVO_US_MIN) + 0.5); }
int panDeg()   { return (int)((curUs[1] - SERVO_US_MIN) / 10.0 + 0.5); }
int tiltDeg()  { return (int)((curUs[2] - SERVO_US_MIN) / 10.0 + 0.5); }

// ---- Protocol ---------------------------------------------------------------
void reply(const char* s) { Serial.println(s); }

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
  if (d == SPINL) {  // SPIN carries a third argument, L or R
    char* side = strtok(NULL, " ");
    if (side == NULL || side[1] != '\0' || (side[0] != 'L' && side[0] != 'R')) {
      err("bad_args");
      return;
    }
    if (side[0] == 'R') d = SPINR;
  }
  if (!probeRetracted()) {  // reciprocal of the PROBE-while-moving guard
    err("probe_deployed");
    return;
  }
  startDrive(d, (unsigned long)ms, (uint8_t)pwm);
  Serial.print(F("OK "));
  Serial.println(okName);
}

void handleLine(char* line) {
  char* cmd = strtok(line, " ");
  if (cmd == NULL) return;  // blank line

  if (strcmp(cmd, "PING") == 0) {
    reply("OK PONG");

  } else if (strcmp(cmd, "FWD") == 0) {
    handleDriveCmd(FWD, "FWD");

  } else if (strcmp(cmd, "REV") == 0) {
    handleDriveCmd(REV, "REV");

  } else if (strcmp(cmd, "SPIN") == 0) {
    handleDriveCmd(SPINL, "SPIN");

  } else if (strcmp(cmd, "STOP") == 0) {
    stopMotors();
    reply("OK STOP");

  } else if (strcmp(cmd, "PROBE") == 0) {
    long pct;
    if (!parseLong(strtok(NULL, " "), &pct, 0, 100)) { err("bad_args"); return; }
    if (drive != IDLE) { err("moving"); return; }  // rolling probe = snapped probe
    targetUs[0] = SERVO_US_MIN + pct * (SERVO_US_MAX - SERVO_US_MIN) / 100.0;
    reply("OK PROBE");

  } else if (strcmp(cmd, "PAN") == 0 || strcmp(cmd, "TILT") == 0) {
    long deg;
    if (!parseLong(strtok(NULL, " "), &deg, 0, 180)) { err("bad_args"); return; }
    uint8_t i = (cmd[0] == 'P') ? 1 : 2;
    targetUs[i] = SERVO_US_MIN + deg * 10.0;
    reply(i == 1 ? "OK PAN" : "OK TILT");

  } else if (strcmp(cmd, "HOME") == 0) {
    if (drive != IDLE) { err("moving"); return; }
    targetUs[0] = HOME_PROBE_US;
    targetUs[1] = HOME_PAN_US;
    targetUs[2] = HOME_TILT_US;
    reply("OK HOME");

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

// ---- Setup / loop -----------------------------------------------------------
void setup() {
  pinMode(DIR_A, OUTPUT);
  pinMode(DIR_B, OUTPUT);
  pinMode(PWM_A, OUTPUT);
  pinMode(PWM_B, OUTPUT);
  stopMotors();

  curUs[0] = targetUs[0] = HOME_PROBE_US;
  curUs[1] = targetUs[1] = HOME_PAN_US;
  curUs[2] = targetUs[2] = HOME_TILT_US;
  servoProbe.attach(PIN_PROBE, SERVO_US_MIN, SERVO_US_MAX);
  servoPan.attach(PIN_PAN, SERVO_US_MIN, SERVO_US_MAX);
  servoTilt.attach(PIN_TILT, SERVO_US_MIN, SERVO_US_MAX);
  for (uint8_t i = 0; i < 3; i++) servos[i]->writeMicroseconds((int)curUs[i]);

  Serial.begin(115200);
  lastRxMs = millis();
  lastServoTick = millis();
  // Opening the port resets the MCU; the Pi syncs on this instead of guessing.
  Serial.println(F("READY rover_motion 1.1"));
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
    if ((long)(now - driveStopAt) >= 0) stopMotors();          // timed motion expiry
    else if (now - lastRxMs > WATCHDOG_MS) stopMotors();       // host went silent
  }

  servoTick();
}
