// motor_test_l298n.ino — bench test, TWO L298N modules, all 12 pins wired
// independently (LastMinuteEngineers-style wiring). Uno or Mega.
//
// Board 1 = LEFT:  ENA->9  IN1->8  IN2->7  IN3->5  IN4->4  ENB->3
// Board 2 = RIGHT: ENA->10 IN1->11 IN2->12 IN3->13 IN4->2 ENB->6
// Front motors on each board's OUT1/OUT2, rear motors on OUT3/OUT4.
//
// Serial monitor at 115200, wheels OFF the ground:
//   1 / 2 / 3 / 4  -> one motor (FL, RL, FR, RR): forward, pause, reverse
//   l / r          -> that whole side
//   g              -> everything in order
//   s              -> stop now

//                       EN  IN-a IN-b
const uint8_t FL[3] = {  9,  8,   7 };
const uint8_t RL[3] = {  3,  5,   4 };
const uint8_t FR[3] = { 10, 11,  12 };
const uint8_t RR[3] = {  6, 13,   2 };
const uint8_t* MOTOR[4] = { FL, RL, FR, RR };
const char* NAME[4] = { "FRONT-LEFT", "REAR-LEFT", "FRONT-RIGHT", "REAR-RIGHT" };

const uint8_t TEST_PWM = 140;   // 3-6 V motors on an ~9 V rail: keep capped

void allStop() {
  for (uint8_t m = 0; m < 4; m++) analogWrite(MOTOR[m][0], 0);
}

void runMotor(uint8_t m, bool fwd) {
  Serial.print(NAME[m]);
  Serial.println(fwd ? " forward" : " reverse");
  digitalWrite(MOTOR[m][1], fwd ? HIGH : LOW);
  digitalWrite(MOTOR[m][2], fwd ? LOW : HIGH);
  analogWrite(MOTOR[m][0], TEST_PWM);
  delay(1200);
  allStop();
  delay(400);
}

void testMotor(uint8_t m) {
  runMotor(m, true);
  runMotor(m, false);
}

void setup() {
  for (uint8_t m = 0; m < 4; m++)
    for (uint8_t k = 0; k < 3; k++) pinMode(MOTOR[m][k], OUTPUT);
  allStop();
  Serial.begin(115200);
  Serial.println(F("L298N TEST ready: 1/2/3/4 = one motor, l/r = side, g = all, s = stop"));
  Serial.println(F("Wheels off the ground!"));
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == 's') { allStop(); Serial.println(F("stopped")); }
  else if (c >= '1' && c <= '4') testMotor(c - '1');
  else if (c == 'l') { testMotor(0); testMotor(1); }
  else if (c == 'r') { testMotor(2); testMotor(3); }
  else if (c == 'g') { for (uint8_t m = 0; m < 4; m++) testMotor(m); Serial.println(F("done")); }
}
