// Four TT motors, two L298Ns, Uno or Mega. Wheels OFF the ground.
// Runs by itself: each motor forward then reverse, then an all-wheels ramp.
// LastMinuteEngineers demo style, extended to both boards — with one change:
// speed is capped at TEST_PWM because full duty on an 11.1 V pack overdrives
// 3-6 V TT motors (the original demo assumed a 7 V supply).

// LEFT board (board 1)
int enA_L = 9;  int in1_L = 8;  int in2_L = 7;   // front-left
int enB_L = 3;  int in3_L = 5;  int in4_L = 4;   // rear-left
// RIGHT board (board 2)
int enA_R = 10; int in1_R = 11; int in2_R = 12;  // front-right
int enB_R = 6;  int in3_R = 13; int in4_R = 2;   // rear-right

int TEST_PWM = 140;   // ~5 V at the motor from an 11.1 V pack. Don't raise.

void motorOff(int en, int a, int b) {
  analogWrite(en, 0); digitalWrite(a, LOW); digitalWrite(b, LOW);
}
void allOff() {
  motorOff(enA_L, in1_L, in2_L); motorOff(enB_L, in3_L, in4_L);
  motorOff(enA_R, in1_R, in2_R); motorOff(enB_R, in3_R, in4_R);
}

void oneMotor(const char* name, int en, int a, int b) {
  Serial.print(name); Serial.println(" forward");
  digitalWrite(a, HIGH); digitalWrite(b, LOW); analogWrite(en, TEST_PWM);
  delay(2000); allOff(); delay(400);
  Serial.print(name); Serial.println(" reverse");
  digitalWrite(a, LOW); digitalWrite(b, HIGH); analogWrite(en, TEST_PWM);
  delay(2000); allOff(); delay(400);
}

void directionControl() {
  oneMotor("FRONT-LEFT ", enA_L, in1_L, in2_L);
  oneMotor("REAR-LEFT  ", enB_L, in3_L, in4_L);
  oneMotor("FRONT-RIGHT", enA_R, in1_R, in2_R);
  oneMotor("REAR-RIGHT ", enB_R, in3_R, in4_R);
}

void speedControl() {
  Serial.println("all wheels forward, ramp up/down");
  digitalWrite(in1_L, HIGH); digitalWrite(in2_L, LOW);
  digitalWrite(in3_L, HIGH); digitalWrite(in4_L, LOW);
  digitalWrite(in1_R, HIGH); digitalWrite(in2_R, LOW);
  digitalWrite(in3_R, HIGH); digitalWrite(in4_R, LOW);
  for (int i = 0; i <= TEST_PWM; i++) {
    analogWrite(enA_L, i); analogWrite(enB_L, i);
    analogWrite(enA_R, i); analogWrite(enB_R, i);
    delay(20);
  }
  for (int i = TEST_PWM; i >= 0; --i) {
    analogWrite(enA_L, i); analogWrite(enB_L, i);
    analogWrite(enA_R, i); analogWrite(enB_R, i);
    delay(20);
  }
  allOff();
}

void setup() {
  int pins[12] = { enA_L, in1_L, in2_L, enB_L, in3_L, in4_L,
                   enA_R, in1_R, in2_R, enB_R, in3_R, in4_R };
  for (int i = 0; i < 12; i++) pinMode(pins[i], OUTPUT);
  allOff();
  Serial.begin(115200);
  Serial.println("4-motor demo: direction test, then speed ramp. Wheels up!");
}

void loop() {
  directionControl();
  delay(1000);
  speedControl();
  delay(1000);
}
