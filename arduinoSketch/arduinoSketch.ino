/*
Created By: Taylor Cooper
Created On: 2014.10.22

Last Modified By: 
Last Modified: 

Board: Arduino Mega ATmega128 
Controls air pump, fan and reads thermistor using motoshield.

From PC:   Serial.read(commands formatted for PSD8 syringe pump)
To Motoshield: ???

Maybe Issues:
Serial Monitor Resets the board in Windows:
See this thread for details on how to fix it
http://playground.arduino.cc/Main/DisablingAutoResetOnSerialConnection
Ignoring this problem since the Laptop uses Linux and works, to send multiple
commands in windows the serial port must be opened and closed for each 
command, which really lengthens communication.

*/

#include <Wire.h>
#include "Adafruit_MotorShield.h"
#include "Adafruit_PWMServoDriver.h"

// Create the motor shield object with the default I2C address
Adafruit_MotorShield AFMS = Adafruit_MotorShield();

// Select which 'port' M1, M2, M3 or M4. In this case, M1
Adafruit_DCMotor *myMotor = AFMS.getMotor(1);


bool cmd_pending = false;

// ===========
// AIR PUMP DATA
// ===========

struct pump_state_t {
  uint8_t dir;
  uint8_t pwm;
  uint8_t dirPin;
  uint8_t pwmPin;
  };

void setup(){

  Serial.begin(9600); //communication with computer @ 9600 bps
  Serial.println("Adafruit Motorshield v2 - DC Motor test!");

  AFMS.begin();  // create with the default frequency 1.6KHz
  //AFMS.begin(1000);  // OR with a different frequency, say 1KHz
  
  // Set the speed to start, from 0 (off) to 255 (max speed)
  myMotor->setSpeed(150);
  myMotor->run(FORWARD);
  // turn on motor
  myMotor->run(RELEASE);
}

void loop() {
  uint8_t i;
  
  Serial.print("tick");

  myMotor->run(FORWARD);
  for (i=127; i<255; i++) {
    myMotor->setSpeed(i);  
    delay(50);
  }
  for (i=255; i!=127; i--) {
    myMotor->setSpeed(i);  
    delay(50);
  }
  
  Serial.print("tock");

//  myMotor->run(BACKWARD);
//  for (i=0; i<255; i++) {
//    myMotor->setSpeed(i);  
//    delay(10);
//  }
//  for (i=255; i!=0; i--) {
//    myMotor->setSpeed(i);  
//    delay(10);
//  }
//
//  Serial.print("tech");
  myMotor->run(RELEASE);
  delay(1000);
}
