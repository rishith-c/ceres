// probe_limit_finder.ino — find the rack-and-pinion's safe travel limits
// on ch1 (MG90S probe servo) WITHOUT ever stalling it.
//
// It crawls slowly (12 deg/s). Watch the carriage:
//   press 1  -> the INSTANT it reaches an end: reverses + notes the angle
//   press 2  -> same at the other end: reverses + notes the angle
//   s = hold still, g = crawl again, c = print noted limits
// It also auto-reverses at the hard fence (30-150 deg) if you press nothing.
// Rack pitch: ~0.314 mm per servo degree (module 2, z=18 pinion).

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca;
const uint8_t CH = 1;
const float FENCE_LO = 30.0, FENCE_HI = 150.0;
const float CRAWL_DEG_S = 12.0;

float pos = 90.0;
int dir = +1;          // +1 toward 150, -1 toward 30
bool moving = true;
float notedLo = -1, notedHi = -1;
unsigned long lastTick = 0, lastPrint = 0;

void writeDeg(float deg) {
  if (deg < FENCE_LO) deg = FENCE_LO;
  if (deg > FENCE_HI) deg = FENCE_HI;
  float us = 600.0 + deg * 10.0;
  pca.setPWM(CH, 0, (int)(us * 4096.0 / 20000.0 + 0.5));
}

void note() {
  Serial.print(F(">>> LIMIT NOTED at "));
  Serial.print(pos, 1);
  Serial.println(F(" deg"));
  if (dir > 0) notedHi = pos; else notedLo = pos;
  summary();
}

void summary() {
  Serial.print(F("    noted so far: low="));
  if (notedLo < 0) Serial.print(F("?")); else Serial.print(notedLo, 1);
  Serial.print(F(" deg, high="));
  if (notedHi < 0) Serial.print(F("?")); else Serial.print(notedHi, 1);
  Serial.println(F(" deg  (tell Claude these two numbers)"));
}

void setup() {
  pca.begin();
  pca.setPWMFreq(50);
  writeDeg(pos);
  Serial.begin(115200);
  Serial.println(F("PROBE LIMIT FINDER (ch1, crawling 12 deg/s)"));
  Serial.println(F("1 = end reached, reverse+note | 2 = other end, reverse+note"));
  Serial.println(F("s = hold | g = go | c = show noted limits"));
  delay(2000);
  lastTick = millis();
  Serial.println(F("crawling toward 150..."));
}

void loop() {
  unsigned long now = millis();
  if (moving && now - lastTick >= 20) {
    pos += dir * CRAWL_DEG_S * (now - lastTick) / 1000.0;
    lastTick = now;
    if (pos >= FENCE_HI) { pos = FENCE_HI; dir = -1; Serial.println(F("(fence 150 — auto-reversing)")); }
    if (pos <= FENCE_LO) { pos = FENCE_LO; dir = +1; Serial.println(F("(fence 30 — auto-reversing)")); }
    writeDeg(pos);
    if (now - lastPrint > 1500) { Serial.print(F("at ")); Serial.print(pos, 0); Serial.println(F(" deg")); lastPrint = now; }
  } else if (!moving) {
    lastTick = now;
  }

  if (!Serial.available()) return;
  char c = Serial.read();
  if (c == '1' || c == '2') { note(); dir = -dir; moving = true;
    Serial.println(dir > 0 ? F("reversing: toward 150...") : F("reversing: toward 30...")); }
  else if (c == 's') { moving = false; Serial.print(F("holding at ")); Serial.println(pos, 1); }
  else if (c == 'g') { moving = true; Serial.println(F("crawling...")); }
  else if (c == 'c') summary();
}
