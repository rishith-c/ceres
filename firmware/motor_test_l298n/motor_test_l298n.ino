// motor_test_l298n.ino — paired-wheel bench test on TWO L298N modules
// (one per side, each board's IN1<->IN3, IN2<->IN4, ENA<->ENB jumped together).
//
// Serial monitor at 115200: l = left pair, r = right pair, g = both, s = stop.
// Wheels OFF the ground.

const uint8_t L_IN1 = 3, L_IN2 = 4, L_EN = 6;   // left board
const uint8_t R_IN1 = 7, R_IN2 = 8, R_EN = 5;   // right board
const uint8_t TEST_PWM = 140;   // 3-6 V motors on an ~9 V rail: keep capped

void allStop() { analogWrite(L_EN, 0); analogWrite(R_EN, 0); }

void run(bool left, bool fwd, const char* label) {
  Serial.println(label);
  digitalWrite(left ? L_IN1 : R_IN1, fwd ? HIGH : LOW);
  digitalWrite(left ? L_IN2 : R_IN2, fwd ? LOW : HIGH);
  analogWrite(left ? L_EN : R_EN, TEST_PWM);
  delay(1200);
  allStop();
  delay(400);
}

void testSide(bool left) {
  run(left, true,  left ? "LEFT forward" : "RIGHT forward");
  run(left, false, left ? "LEFT reverse" : "RIGHT reverse");
}

void setup() {
  const uint8_t pins[] = { L_IN1, L_IN2, L_EN, R_IN1, R_IN2, R_EN };
  for (uint8_t i = 0; i < 6; i++) pinMode(pins[i], OUTPUT);
  allStop();
  Serial.begin(115200);
  Serial.println(F("L298N TEST ready: l / r / g / s  (wheels off the ground)"));
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == 's') allStop();
  else if (c == 'l') testSide(true);
  else if (c == 'r') testSide(false);
  else if (c == 'g') { testSide(true); testSide(false); Serial.println(F("done")); }
}
