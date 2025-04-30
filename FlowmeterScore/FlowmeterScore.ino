#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

#define FLOW_SENSOR_PIN 18
volatile int pulseCount = 0;
float flowRate = 0.0;
float totalLitres = 0.0;
int score = 0;
const float calibrationFactor = 450.0;

String userId = "";
String userName = "";
int userScore = 0;
bool isLoggedIn = false;

// ฟังก์ชันนับพัลส์จาก Flow Meter
void IRAM_ATTR countPulse() {
    pulseCount++;
}

// ฟังก์ชันอ่านข้อมูลจาก Serial
void readSerialData() {
    if (Serial.available()) {
        String data = Serial.readStringUntil('\n');
        data.trim();

        int firstComma = data.indexOf(',');
        int secondComma = data.lastIndexOf(',');

        if (firstComma > 0 && secondComma > firstComma) {
            userId = data.substring(0, firstComma);
            userName = data.substring(firstComma + 1, secondComma);
            userScore = data.substring(secondComma + 1).toInt();
            isLoggedIn = true;

            updateLCD();
        }
    }
}

// ฟังก์ชันคำนวณค่าการไหลของน้ำ
void updateFlowRate() {
    flowRate = (pulseCount * 60.0) / calibrationFactor;
    totalLitres += (flowRate / 60.0);
    score = totalLitres * 5;
    pulseCount = 0;
}

// ฟังก์ชันอัปเดตข้อมูลบน LCD
void updateLCD() {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("User: " + userName);
    lcd.setCursor(0, 1);
    lcd.print("Score: " + String(userScore + score));
}

// ฟังก์ชันส่งข้อมูลกลับไปยัง Python
void sendDataToPython() {
    Serial.print(userId);
    Serial.print(",");
    Serial.print(userName);
    Serial.print(",");
    Serial.println(userScore + score);
}

void setup() {
    Serial.begin(115200);
    lcd.init();
    lcd.backlight();
    lcd.setCursor(0, 0);
    lcd.print("Scan Your ID");

    pinMode(FLOW_SENSOR_PIN, INPUT_PULLUP);
}

void loop() {
    static unsigned long lastTime = 0;
    unsigned long currentTime = millis();

    readSerialData();

    if (isLoggedIn) {
            // ถ้ามีคำสั่ง "restart" ให้รีสตาร์ท ESP32
        String data = Serial.readStringUntil('\n');
        if (data == "restart") {
            //Serial.println("ESP32 is restarting...");
            //delay(500);
            ESP.restart();
        }

        if (currentTime - lastTime >= 1000) {
            detachInterrupt(FLOW_SENSOR_PIN);
            updateFlowRate();
            updateLCD();
            sendDataToPython();
            lastTime = currentTime;
            attachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN), countPulse, RISING);
        }
    }
}
