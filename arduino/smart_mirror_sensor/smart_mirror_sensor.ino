/*
 * Smart Mirror - 아두이노 센서 노드 (DHT11 + HC-SR04 + 버저 + LED)
 *
 * 하는 일
 *   1) DHT11 로 실내 온습도 측정
 *   2) HC-SR04 로 거울 앞 거리(cm) 측정 → 사람이 서 있는지 판단하는 데 사용
 *   3) 2초마다 USB 시리얼로 JSON 한 줄 전송 →  {"t":23.0,"h":45.0,"d":87}
 *        d = 지난 2초 중 가장 가까웠던 거리(cm), 아무것도 없으면 필드 생략
 *   4) 라즈베리파이가 "ALERT\n" 을 보내면 버저 + LED 를 3초간 깜빡임 (우산 알림)
 *
 * 배선 (Uno 기준)
 *   DHT11   VCC -> 5V, GND -> GND, DATA -> D2   (낱개 4핀 제품은 DATA-VCC 사이 10kΩ 풀업 필요,
 *                                                 모듈형 3핀 제품은 저항이 내장되어 있음)
 *   HC-SR04 VCC -> 5V, GND -> GND, TRIG -> D4, ECHO -> D5
 *   버저    (+) -> D8, (-) -> GND
 *   LED     애노드(긴 다리) -> 220Ω -> D9, 캐소드(짧은 다리) -> GND
 *
 * 라이브러리 (Arduino IDE → 라이브러리 관리자)
 *   "DHT sensor library" (Adafruit), "Adafruit Unified Sensor"
 *
 * 설계 포인트
 *   - delay() 대신 millis() 로 시간을 재서 센서 읽기·명령 수신·알림 깜빡임이 서로를 막지 않음
 *   - HC-SR04 는 pulseIn 타임아웃을 짧게(최대 약 4m) 잡아서 측정이 루프를 오래 막지 않게 함
 */
#include <DHT.h>

#define DHT_PIN     2
#define DHT_TYPE    DHT11     // DHT22 로 바꾸면 DHT22
#define TRIG_PIN    4
#define ECHO_PIN    5
#define BUZZER_PIN  8
#define LED_PIN     9

// 능동(Active) 버저는 0, 수동(Passive) 버저는 1
#define BUZZER_PASSIVE 1

const unsigned long SEND_INTERVAL_MS  = 2000;
const unsigned long RANGE_INTERVAL_MS = 200;    // 거리 측정 주기
const unsigned long ECHO_TIMEOUT_US   = 25000;  // 약 4m 까지
const unsigned long ALERT_DURATION_MS = 3000;
const unsigned long BLINK_PERIOD_MS   = 250;

DHT dht(DHT_PIN, DHT_TYPE);

unsigned long lastSend = 0;
unsigned long lastRange = 0;
unsigned long alertStart = 0;
bool alerting = false;
int minDistance = -1;      // 전송 주기 동안 가장 가까웠던 거리 (-1 = 측정 없음)
String rx = "";

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  dht.begin();
}

void loop() {
  if (millis() - lastRange >= RANGE_INTERVAL_MS) {
    lastRange = millis();
    int d = readDistanceCm();
    if (d > 0 && (minDistance < 0 || d < minDistance)) minDistance = d;
  }

  readCommands();
  updateAlert();

  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    sendSensors();
  }
}

// HC-SR04: TRIG 에 10µs 펄스 → ECHO 가 HIGH 로 유지된 시간 = 초음파 왕복 시간
// 거리(cm) = 시간(µs) × 0.0343 / 2  ≈ 시간 / 58
int readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return -1;   // 타임아웃: 범위 안에 물체 없음
  return (int)(duration / 58);
}

void sendSensors() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  Serial.print("{");
  bool first = true;
  if (!isnan(t)) { Serial.print("\"t\":"); Serial.print(t, 1); first = false; }
  if (!isnan(h)) { if (!first) Serial.print(","); Serial.print("\"h\":"); Serial.print(h, 1); first = false; }
  if (minDistance > 0) { if (!first) Serial.print(","); Serial.print("\"d\":"); Serial.print(minDistance); first = false; }
  if (first) Serial.print("\"ok\":1");   // 빈 JSON 방지
  Serial.println("}");
  minDistance = -1;
}

void readCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      rx.trim();
      if (rx == "ALERT") startAlert();
      rx = "";
    } else if (c != '\r' && rx.length() < 20) {
      rx += c;
    }
  }
}

void startAlert() {
  alerting = true;
  alertStart = millis();
}

void buzzerOn()  { if (BUZZER_PASSIVE) tone(BUZZER_PIN, 1000); else digitalWrite(BUZZER_PIN, HIGH); }
void buzzerOff() { if (BUZZER_PASSIVE) noTone(BUZZER_PIN);     else digitalWrite(BUZZER_PIN, LOW); }

void updateAlert() {
  if (!alerting) return;
  unsigned long elapsed = millis() - alertStart;
  if (elapsed >= ALERT_DURATION_MS) {
    alerting = false;
    digitalWrite(LED_PIN, LOW);
    buzzerOff();
    return;
  }
  bool on = (elapsed / BLINK_PERIOD_MS) % 2 == 0;
  digitalWrite(LED_PIN, on);
  if (on) buzzerOn(); else buzzerOff();
}
