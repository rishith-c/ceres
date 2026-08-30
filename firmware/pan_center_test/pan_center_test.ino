// pan_center_test.ino — drives ONLY ch0 (pan) at exact center, forever.
// ch1 (probe) and ch2 (tilt) get NO pulses: limp, the rack is untouched.
//
// Now grab the pan servo's horn and gently twist:
//   snaps back and HOLDS center, quiet     -> healthy positional servo
//   spins on its own / turns freely,
//   smooth motor drag, never returns       -> continuous-rotation type
//   turns with CLICKING/ratcheting sounds  -> stripped gears, replace it
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
Adafruit_PWMServoDriver pca;
void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  pca.setPWM(1, 0, 0);   // probe: no pulses, limp
  pca.setPWM(2, 0, 0);   // tilt: no pulses, limp
  pca.setPWM(0, 0, (int)(1500.0 * 4096.0 / 20000.0 + 0.5));  // pan: hold center
  Serial.begin(115200);
  Serial.println(F("PAN CENTER TEST: ch0 held at 1500us. Twist the pan horn gently."));
  Serial.println(F("holds+springs back=healthy | spins/free=continuous | clicks=stripped gears"));
}
void loop() { delay(1000); }
