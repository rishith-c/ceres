// rover_motion.ino v2 — Field Triage Rover wheel controller
//
// Target: Arduino Uno R3 + TWO L298N modules (one per side, channels jumped:
// each board's IN1<->IN3, IN2<->IN4, ENA<->ENB tied together), one TT motor
// per L298 channel. The original Inland L298P shield died to reverse polarity.
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

const uint8_t L_IN1 = 3, L_IN2 = 4, L_EN = 6;   // left board  (both left motors)
const uint8_t R_IN1 = 7, R_IN2 = 8, R_EN = 5;   // right board (both right motors)

// Flip per side if that side runs backward — never touch the EN pins.
const bool L_FWD_HIGH = true;
const bool R_FWD_HIGH = true;

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

void stopMotors() {
  analogWrite(L_EN, 0);
  analogWrite(R_EN, 0);
  drive = IDLE;
  drivePwm = 0;
}

void setSide(bool left, bool fwd) {
  bool h = left ? (fwd == L_FWD_HIGH) : (fwd == R_FWD_HIGH);
  digitalWrite(left ? L_IN1 : R_IN1, h ? HIGH : LOW);
  digitalWrite(left ? L_IN2 : R_IN2, h ? LOW : HIGH);
}

void startDrive(DriveState d, unsigned long ms, uint8_t pwm) {
  if (pwm > MAX_PWM) pwm = MAX_PWM;
  setSide(true, d == FWD || d == SPINR);
  setSide(false, d == FWD || d == SPINL);
  analogWrite(L_EN, pwm);
  analogWrite(R_EN, pwm);
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
  const uint8_t pins[] = { L_IN1, L_IN2, L_EN, R_IN1, R_IN2, R_EN };
  for (uint8_t i = 0; i < 6; i++) pinMode(pins[i], OUTPUT);
  stopMotors();
  Serial.begin(115200);
  lastRxMs = millis();
  Serial.println(F("READY rover_motion 2.0"));
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
