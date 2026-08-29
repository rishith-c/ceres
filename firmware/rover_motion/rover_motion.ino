// rover_motion.ino v2 — Field Triage Rover wheel controller
//
// Target: Arduino Uno R3 + TWO L298N modules, one per side, all 12 control
// pins wired independently (LastMinuteEngineers-style), one TT motor per
// L298 channel. The original Inland L298P shield died to reverse polarity.
//
// Board 1 = LEFT  (front-left OUT1/2, rear-left OUT3/4):  9 8 7 5 4 3
// Board 2 = RIGHT (front-right OUT1/2, rear-right OUT3/4): 10 12 13 A0 A1 11
//
// ARCHITECTURE CHANGE from v1: servos moved to a PCA9685 on the Pi (HANDOFF
// §3 resolution 2). This board is wheels-only; PROBE/PAN/TILT/HOME are gone
// from the protocol. The probe-vs-motion interlock therefore lives on the Pi
// now — the Pi must never command wheels while its probe is deployed.
//
// Serial protocol (ASCII, newline-terminated), 115200 baud:
//   PING                  -> OK PONG
//   FWD <ms> <pwm>        -> OK FWD     auto-stops after <ms>
//   REV <ms> <pwm>        -> OK REV
//   SPIN <ms> <pwm> <L|R> -> OK SPIN
//   STOP                  -> OK STOP
//   STATUS                -> OK <drive> <pwm> <uptime_ms>
//
// Rules kept from v1: IN pins only digitalWrite, EN pins only analogWrite,
// stop is analogWrite(EN, 0); no untimed motion; host watchdog.

//                       EN  IN-a IN-b        (per motor: one EN + an IN pair)
const uint8_t FL[3] = {  9,  8,   7 };   // front-left   board1 ENA/IN1/IN2
const uint8_t RL[3] = {  3,  5,   4 };   // rear-left    board1 ENB/IN3/IN4
const uint8_t FR[3] = { 10, 12,  13 };   // front-right  board2 ENA/IN1/IN2
const uint8_t RR[3] = { 11, A0,  A1 };   // rear-right   board2 ENB/IN3/IN4

// Flip per motor if it runs backward — never touch the EN pins.
const bool FWD_HIGH[4] = { true, true, true, true };   // FL RL FR RR

// 3-6 V TT motors on a ~9 V rail (3S minus the L298 drop): 160/255 duty
// averages ~5.6 V at the motor. On the 8.5 V buck rail this could rise, but
// leave it — speed is not the constraint on this rover.
const uint8_t MAX_PWM = 160;

const unsigned long WATCHDOG_MS = 400;
const unsigned long MAX_DRIVE_MS = 10000;

enum DriveState { IDLE, FWD, REV, SPINL, SPINR };
DriveState drive = IDLE;
uint8_t drivePwm = 0;
unsigned long driveStopAt = 0;
unsigned long lastRxMs = 0;

char lineBuf[48];
uint8_t lineLen = 0;
bool lineOverflow = false;

const uint8_t* MOTOR[4] = { FL, RL, FR, RR };

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
  setMotor(0, leftFwd, pwm);   // FL
  setMotor(1, leftFwd, pwm);   // RL
  setMotor(2, rightFwd, pwm);  // FR
  setMotor(3, rightFwd, pwm);  // RR
  drive = d;
  drivePwm = pwm;
  driveStopAt = millis() + ms;
}

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
  } else if (strcmp(cmd, "STATUS") == 0) {
    static const char* names[] = { "IDLE", "FWD", "REV", "SPINL", "SPINR" };
    Serial.print(F("OK "));
    Serial.print(names[drive]); Serial.print(' ');
    Serial.print(drivePwm);     Serial.print(' ');
    Serial.println(millis());
  } else {
    err("unknown_cmd");
  }
}

void setup() {
  for (uint8_t m = 0; m < 4; m++)
    for (uint8_t k = 0; k < 3; k++) pinMode(MOTOR[m][k], OUTPUT);
  stopMotors();
  Serial.begin(115200);
  lastRxMs = millis();
  Serial.println(F("READY rover_motion 2.1"));
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
}
