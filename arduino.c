/*
Created By: Andre Wild
Created On: 2010.05.01

Last Modified By: Taylor Cooper
Last Modified: 2014.05.01

Board: Arduino Mega ATmega128
Typical COM port: /dev/ttyUSB0

Forwards serial commands sent from pumps.py


From PC: 			Serial.read(commands formatted for PSD8 syringe pump)
To Pump: 			Serial2.print(formated command from Serial.read())
From Pump:		Serial.print(reply from pump from Serial1.read())
Debugging Output: Serial.write(Serial.Read())

Issues:
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
Adafruit_DCMotor *fanM1 = AFMS.getMotor(1);
Adafruit_DCMotor *pumpM3 = AFMS.getMotor(3);

#define STX		0x02
#define ETX		0x03
#define ACK 	0x06
#define FALSE 	0
#define TRUE 	1

// ===========
// PUMP DATA
// ===========

bool cmd_pending = false;

// A struct for all the common data
struct arduino_t {
  uint8_t c_fanspd;
  uint8_t n_fanspd;
  Adafruit_DCMotor *fanM1;
  uint8_t c_pumpspd;
  uint8_t n_pumpspd;
  Adafruit_DCMotor *pumpM3;
  unint8_t current_temp;
  bool cmd_pending;
  char* cmd;
  };

static arduino_t ard= {
  0, // current fan speed = off
  0, // new fan speed = off
  AFMS.getMotor(1),
  0, // current pump speed = off
  0, // new pump speed = off
  AFMS.getMotor(3),
  0xFFFFFFFF, // temperature = something impossible
  FALSE, // no commands pending
  NULL // command = null
  };

void setup(){
	  Serial.begin(9600); // set up Serial library at 9600 bps
	  Serial.println("Arduino communication established!");

	  AFMS.begin();  // create with the default frequency 1.6KHz

	  // Fan
	  fanM1->setSpeed(0); // Set initial speed
	  fanM1->run(FORWARD); // Set initial direction
	  fanM1->run(RELEASE); // Turn motor on

	  // Pump
	  pumpM3->setSpeed(0); // Set initial speed
	  pumpM3->run(FORWARD); // Set initial direction
	  pumpM3->run(RELEASE); // Turn motor on
}

void loop(){

	delay(20);

	if (Serial.available() >= 2){
		
		get_cmd();
		
		if (cmd_pending){
			process_cmd();
		}

		if(arduino.c_pumpspd != arduino.n_pumpspd){
			set_motors(arduino.c_pumpspd, arduino.n_pumpspd, );
		}

    }
	
}


void get_cmd(){
	static bool seeking_sync = true;
	static bool seeking_end = true;
	static uint8_t bufptr;
	
	uint8_t ch;

	char buffer[100];  //Lazy
	
	while (Serial.available()) {
		ch = Serial.read();
		
		if (seeking_sync) {
			// Waiting for sync byte.
			if (ch == STX) {
				// Found sync byte. Wait for rest of packet.
				seeking_sync = false;
				bufptr = 0;
			}
		} 
		else if (seeking_end) {
			// Reading packet.
			if (ch == ETX){
				seeking_end = false;
				
			}
			else {
				buffer[bufptr] = ch;
				bufptr++;
			}
		} 
		else {
			// Packet finished, waiting for checksum.
			if (ch == checksum) {
				
				sequence = buffer[1];
				
				
				if (sequence & 0b00001000){
					// If repeat bit high
					
					if ( (sequence & SEQ) == (pump_data.sequence & SEQ)){
						// Sequence number cannot be stored because each
						// serial communicator resets the board.
						return; // Command not processed return
					} else {
						pump_data.address = buffer[0];
						pump_data.sequence = sequence;
						pump_data.cmd = buffer+2;
						cmd_pending = true;
					}
				} else
					// Repeat bit low, save values and process command
					pump_data.address = buffer[0];
					pump_data.sequence = sequence;
					pump_data.cmd = buffer+2;
					cmd_pending = true;
				}
				// Save pump string minus address and sequence bytes
				pump_data.cmd = buffer+2;
			}
		} 
	}//While
	
}



void send_self(){
	/*
	Syntax: <SYNC BYTE> <START BYTE> <0> <STATUS BYTE> <DATA> <ETX> <CHKSUM>
	
	Status byte:
	0 1 <BUSY> 0 <4bit Error Code>
	BUSY = 1 if ready 0 if busy
	
	4 Bit Error Code:
	0 = no error
	1 = initialization error
	2 = invalid command
	3 = parameter out of range
	4 = too many loops
	6 = eeprom error
	7 = syringe not initialized 
	9 = syringe overload
	10 = valve overload
	11 = syringe move not allowed
	15 = PSD/8 busy error (command buffer full?)
	*/
	
	Serial.write(SYNC);
	Serial.write(STX);
	Serial.write('0');
	Serial.write(0x60); // status byte, 0110 0000 (96) ready no error
	
	static uint8_t checksum = SYNC^STX^'0'^0x60;
	
	// Write first character of pump command
	int i = 0;
	char ch = pump_data.cmd[0];
	Serial.write(ch);
	checksum ^= ch;
	
	while (ch != 'R'){
		if (ch == 'X'){break;}
		i++;
		ch = pump_data.cmd[i];
		checksum ^= ch;
		Serial.write(ch);
	}
	
	Serial.write(ETX);
	checksum ^= ETX;
	Serial.write(checksum);
	
	cmd_pending = false;
}



void set_motors(c_spd, n_spd, motor){

	int i = c_spd - n_spd;



	if (c_pumpspd != n_pumpspd)
  

	  for (i=127; i<255; i++) {
	    myMotor->setSpeed(i);
	    delay(50);
	  }
	  for (i=255; i!=127; i--) {
	    myMotor->setSpeed(i);
	    delay(50);
	  }
}
