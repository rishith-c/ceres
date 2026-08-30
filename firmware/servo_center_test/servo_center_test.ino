// servo_center_test.ino — holds ch0/ch1/ch2 at exactly 1500 us forever.
// A normal positional servo: moves to its middle and STOPS dead.
// A continuous-rotation servo: 1500 us is its "stop" command, so it also
//   stops — but it NEVER held a position before, it was spinning.
// A servo with a stripped feedback pot: keeps creeping/spinning even now.
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
Adafruit_PWMServoDriver pca;

void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  for (uint8_t ch = 0; ch < 3; ch++)
    pca.setPWM(ch, 0, (int)(1500.0 * 4096.0 / 20000.0 + 0.5));
  Serial.begin(115200);
  Serial.println(F("CENTER TEST: all three channels held at 1500 us."));
  Serial.println(F("Now gently try to twist each servo horn by hand:"));
  Serial.println(F("  fights back and returns  -> healthy positional servo"));
  Serial.println(F("  turns freely, no fight   -> continuous-rotation type (bad for us)"));
  Serial.println(F("  creeps/spins on its own  -> stripped feedback, replace it"));
}
void loop() { delay(1000); }
