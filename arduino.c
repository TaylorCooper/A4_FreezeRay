/*
Created By: Taylor Cooper
Created On: 2014.10.20

Last Modified By: Taylor Cooper
Last Modified: 2014.11.21

Board: Arduino Mega 2560 R3

Functionality:


Communication:
From PC: 	Serial.read(commands from python controller)
From PC:	Command syntax: <STX> <CMD CHAR> <DATA> <NULL> <ETX>
To PC:		Serial.write(result from processing command)
To PC:		Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ETX>

Issues:
1)
Serial Monitor Resets the board in Windows:
See this thread for details on how to fix it
http://playground.arduino.cc/Main/DisablingAutoResetOnSerialConnection
Ignoring this problem since the Laptop uses Linux and works, to send multiple
commands in windows the serial port must be opened and closed for each 
command, which really lengthens communication.
2)
Not making intelligent use of arrays
3)
Not making any effort to deal with new commands coming in before execution of
current command

*/

#include <Wire.h>
#include "Adafruit_MotorShield.h"
#include "Adafruit_PWMServoDriver.h"

// ===========
// DEBUGGING
// ===========
//#define DEBUG
#ifdef DEBUG
#define debugPrintln(x) Serial.println(x)
#define debugPrint(x) Serial.print(x)
#define debugWrite(x) Serial.write(x)
#else
#define debugPrintln(x)  //Blank line
#define debugPrint(x)  //Blank line
#define debugWrite(x)  //Blank line
#endif

// ===========
// COMMANDS AND STATIC VALUES
// ===========

#define NULL		0x00 // String end, Null
#define STX			0x02 // Start character
#define ETX			0x03 // End character
#define ACK			0x06 // Acknowledge
#define FALSE 		0
#define TRUE 		1
#define MAXSPD		255 // Max speed 255 = 100% duty cycle
#define MINSPD		0
#define RAMPRATE	10  // delay between PWM increments in milliseconds
#define NUM_CMDS 	3	// Number of commands, array declared in get_cmds
#define CMD_SIZE	10  // Max size of command in characters
const char cmds[NUM_CMDS] = {'F','P','Q'};

// ===========
// DATA
// ===========

// Create the motor shield object with the default I2C address
Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_DCMotor *fanM1 = AFMS.getMotor(4); // Fan motor pointer
Adafruit_DCMotor *pumpM3 = AFMS.getMotor(1);  // Pump motor pointer

// A struct for all the common data
struct arduino_t {
  uint8_t c_fanspd;
  uint8_t n_fanspd;
  uint8_t c_pumpspd;
  uint8_t n_pumpspd;
  int c_temp;
  bool cmd_pending;
  char cmd[CMD_SIZE];
  };

static arduino_t ard= {
  0, // current fan speed = off
  0, // new fan speed = off
  0, // current pump speed = off
  0, // new pump speed = off
  -30000, // temperature = something impossible
  FALSE, // no commands pending
  {0} // buffer for commands
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

	delay(50);

	// Check serial buffer if no unprocessed commands
	if (Serial.available() >= 2 && !ard.cmd_pending){
		debugPrintln("Command received!");
		get_cmd();
    }

	// Process command if received
	if ( ard.cmd_pending ){

		debugPrint("Command processing: ");
		debugWrite(ard.cmd[0]);
		debugPrint(&ard.cmd[1]);
		debugPrintln(' ');

		process_cmd();
	}

	// Get and overwrite current temperature, logging done in Python
	get_temperature();
}

void get_cmd(){
	/*
	 * Command syntax: <STX> <CMD CHAR> <DATA> <NULL> <ETX>
	 * NULL termination for easy use of atoi()
	 */
	static bool seeking_sync = TRUE;
	static bool seeking_end = TRUE;
	static uint8_t i;

	uint8_t ch;
	//memset(buffer, 0x00, sizeof(buffer)); // Probably not needed
	// Read about serial.read()....
	
	while (Serial.available()) {
		ch = Serial.read();
		
		if (seeking_sync) {
			// Waiting for sync byte.
			if (ch == STX) {
				// Found sync byte. Wait for rest of packet.
				seeking_sync = FALSE;
				i = 0;
			}
		} 
		else if (seeking_end) {
			// Reading packet.
			if (ch == ETX){
				seeking_end = FALSE;
			}
			else {
				ard.cmd[i] = ch;
				i++;
			}
		}

	}//While Serial.available()

	// Check crudely if command is valid, once ETX found
	if ( !seeking_end ){
		for (int j = 0; j < NUM_CMDS; j++){
			if ( ard.cmd[0] == cmds[j] ){
				ard.cmd_pending = TRUE;
			}
		}
	}

	debugPrint("ard.cmd=");
	debugWrite(ard.cmd[0]);
	debugWrite(ard.cmd[1]);
	debugPrint(':');
	debugPrint(ard.cmd_pending);
	debugPrint(':');
	debugPrint(seeking_end);
	debugPrintln(' ');

	// Reset and return
	seeking_sync = TRUE;
	seeking_end = TRUE;
	return;
}

void process_cmd(){
	/*
	 * Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ACK>
	 */

	uint8_t spd;
	char cmd = ard.cmd[0]; // First character should be cmd character
	char *data = ard.cmd + 1; // Trim first character

	Serial.write(STX);

	// Process command
	switch ( cmd ) {

	case 'F': // Set fan speed command

		// Read speed value
		spd = atoi(data);
		Serial.write(cmd);
		if ( MINSPD < spd < MAXSPD ){ //check speed is valid
			ard.n_fanspd = spd; // Set new fan speed set point
		} else {
			Serial.write('E');
			Serial.write(',');
		}
		Serial.print(spd);

		// Adjust fan set point if required
		if( ard.c_fanspd != ard.n_fanspd ){

			debugPrint("Fan C_N:");
			debugPrint(ard.c_fanspd);
			debugPrint('_');
			debugPrint(ard.n_fanspd);
			debugPrint(' ');

			set_motors( ard.c_fanspd, ard.n_fanspd, fanM1 );
			ard.c_fanspd = ard.n_fanspd;
			ard.cmd_pending = FALSE;
		}

		break;

	case 'P': // Set pump speed command

		// Read speed value
		spd = atoi(data);
		Serial.write(cmd);
		if ( MINSPD < spd < MAXSPD ){ //check speed is valid
			ard.n_pumpspd = spd; // Set new pump speed set point
		} else {
			Serial.write('E');
			Serial.write(',');
		}
		Serial.print(spd);

		// Adjust pump set point if  required
		if( ard.c_pumpspd != ard.n_pumpspd ){

			debugPrint("Pump C_N:");
			debugPrint(ard.c_pumpspd);
			debugPrint('_');
			debugPrint(ard.n_pumpspd);
			debugPrint(' ');

			set_motors( ard.c_pumpspd, ard.n_pumpspd, pumpM3 );
			ard.c_pumpspd = ard.n_pumpspd;
			ard.cmd_pending = FALSE;
		}

		break;

	case 'Q': // Query set points and temperature
		Serial.write( cmd );
		Serial.print( ard.c_fanspd );
		Serial.write(',');
		Serial.print( ard.c_pumpspd );
		Serial.write(',');
		Serial.print( ard.c_temp );
	}

	Serial.write(ACK);

	ard.cmd_pending = FALSE;
}

void set_motors(uint8_t c_spd,uint8_t n_spd, Adafruit_DCMotor *motor){
	/*
	 * Ramp motors to new set points
	 */

	motor->run(FORWARD);  // Breaks without this

	if ( n_spd > c_spd ){  // Ramp up
		for (int i=c_spd; i<n_spd; i++) {
			motor->setSpeed(i);
			delay(RAMPRATE);
		}
	}
	else if ( n_spd < c_spd ){  // Ramp down
		for (int i=c_spd; i>n_spd; i--) {
			motor->setSpeed(i);
			delay(RAMPRATE);
		}
	} else {
		return;
	}
}

void get_temperature(){
	/*
	 * ### Under construction
	 */
	ard.c_temp = -30000;
}
