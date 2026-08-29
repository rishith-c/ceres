// motor_test.ino — bench smoke test for 4 DC motors on the Inland L298P shield.
//
// NO Servo library here, so channels C/D (Timer1, D9/D10) keep PWM — all four
// channels test independently. Wheels OFF the ground.
//
// Serial monitor at 115200, then send:
//   a / b / c / d  -> test that one channel (fwd, pause, rev)
//   g              -> full sequence A -> B -> C -> D
//   s              -> stop everything now
//
// TEST_PWM 140/255: on a 3S pack (~11.1 V) minus the L298 bridge drop the
// motor rail is ~8.6 V, so 140/255 duty averages ~4.7 V at the motor —
// inside the TT motor's 3-6 V rating. Don't raise it on 3S.

const uint8_t DIR_PIN[4] = {3, 4, 7, 8};    // A B C D  (verified pinout)
const uint8_t PWM_PIN[4] = {6, 5, 10, 9};
const char NAME[4] = {'A', 'B', 'C', 'D'};
const uint8_t TEST_PWM = 140;

void allStop() {
  for (uint8_t i = 0; i < 4; i++) analogWrite(PWM_PIN[i], 0);
}

bool interrupted() {          // let 's' cut a test short
  if (Serial.available() && Serial.peek() == 's') { allStop(); return true; }
  return false;
}

bool run(uint8_t i, uint8_t dir, const char* label) {
  Serial.print(F("  channel ")); Serial.print(NAME[i]);
  Serial.print(' '); Serial.println(label);
  digitalWrite(DIR_PIN[i], dir);
  analogWrite(PWM_PIN[i], TEST_PWM);
  for (uint8_t t = 0; t < 12; t++) { delay(100); if (interrupted()) return false; }
  analogWrite(PWM_PIN[i], 0);
  delay(400);
  return true;
}

void testChannel(uint8_t i) {
  if (!run(i, HIGH, "forward")) return;
  if (!run(i, LOW, "reverse")) return;
  Serial.println(F("  done"));
}

void setup() {
  for (uint8_t i = 0; i < 4; i++) {
    pinMode(DIR_PIN[i], OUTPUT);
    pinMode(PWM_PIN[i], OUTPUT);
  }
  allStop();
  Serial.begin(115200);
  Serial.println(F("MOTOR TEST ready. Wheels off the ground!"));
  Serial.println(F("send a/b/c/d = one channel, g = all four, s = stop"));
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == 's') { allStop(); Serial.println(F("stopped")); }
  else if (c >= 'a' && c <= 'd') testChannel(c - 'a');
  else if (c == 'g') {
    for (uint8_t i = 0; i < 4; i++) testChannel(i);
    Serial.println(F("sequence complete"));
  }
}
