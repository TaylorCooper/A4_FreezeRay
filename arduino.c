/*
Created By: Andre Wild
Created On: 2010.05.01

Last Modified By: Taylor Cooper
Last Modified: 2014.05.01

Board: Arduino Mega ATmega128
Typical COM port: /dev/ttyUSB0


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

//#define DEBUG

// ===========
// COMMANDS AND STATIC VALUES
// ===========

#define STX			0x02 // Start character
#define ETX			0x03 // End character
#define NULL		0x00 // String end, Null
#define FALSE 		0
#define TRUE 		1
#define MAXSPD		255 // Max speed 255 = 100% duty cycle
#define MINSPD		0
#define RAMPRATE	10  // delay between PWM increments in milliseconds
#define NUM_CMDS 	3	// Number of commands, array declared in get_cmds
const char cmds[NUM_CMDS] = {'F','P','Q'};

// ===========
// DATA
// ===========

// Create the motor shield object with the default I2C address
Adafruit_MotorShield AFMS = Adafruit_MotorShield();
Adafruit_DCMotor *fanM1 = AFMS.getMotor(1); // Fan motor pointer
Adafruit_DCMotor *pumpM3 = AFMS.getMotor(3);  // Pump motor pointer

// A struct for all the common data
struct arduino_t {
  uint8_t c_fanspd;
  uint8_t n_fanspd;
  uint8_t c_pumpspd;
  uint8_t n_pumpspd;
  uint8_t c_temp;
  bool cmd_pending;
  char *cmd;
  };

static arduino_t ard= {
  0, // current fan speed = off
  0, // new fan speed = off
  0, // current pump speed = off
  0, // new pump speed = off
  0xFFFFFFFF, // temperature = something impossible
  FALSE, // no commands pending
  NULL // since we have no commands yet
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

//###
#ifdef DEBUG
#define debugPrint(x) Serial.println((x));
#else
#define debugPrint(x)
#endif

void loop(){

	delay(50);

	// Check serial buffer if no unprocessed commands
	if (Serial.available() >= 2 && !ard.cmd_pending){

		//debugPrint("com");

		#ifdef DEBUG
		Serial.println("Command received!");
		#endif



		get_cmd();
    }

	// Process command if received
	if ( ard.cmd_pending ){

		#ifdef DEBUG
		Serial.print("Command processing: ");
		Serial.write(ard.cmd[0]);
		Serial.print(&ard.cmd[1]);
		Serial.println(' ');
		#endif

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
	char buffer[100];  // Should be global###  releases stack and can be overwritten at end of function
	memset(buffer, 0x00, sizeof(buffer)); // Probably not needed###

	// Read about serial.read().... ###
	
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
				buffer[i] = ch;
				i++;
			}
		} else

	}//While Serial.available()

	#ifdef DEBUG
	Serial.print("Buffer=");
	Serial.write(buffer[0]);
	Serial.write(buffer[1]);
	Serial.println(' ');
	#endif

	// Check crudely if command is valid, if ETX found
	if ( !seeking_end ){
		for (int j = 0; j < NUM_CMDS; j++){
			if ( buffer[0] == cmds[j] ){
				ard.cmd = buffer;
				ard.cmd_pending = TRUE;
			}
		}
	}

	// Reset and return
	seeking_sync = TRUE;
	seeking_end = TRUE;
	return;
}

void process_cmd(){
	/*
	 * Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ETX>
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
			set_motors( ard.c_fanspd, ard.n_fanspd, fanM1 );
			ard.c_fanspd = ard.n_fanspd;
			ard.cmd_pending = FALSE;

			#ifdef DEBUG
			Serial.print("Fan set point changed!");
			Serial.print(ard.c_fanspd);
			Serial.print('_');
			Serial.print(ard.n_fanspd);
			Serial.println(' ');
			#endif
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
			set_motors( ard.c_pumpspd, ard.n_pumpspd, pumpM3 );
			ard.c_pumpspd = ard.n_pumpspd;
			ard.cmd_pending = FALSE;

			#ifdef DEBUG
			Serial.print("Pump set point changed!");
			Serial.print(ard.c_pumpspd);
			Serial.print('_');
			Serial.print(ard.n_pumpspd);
			Serial.println(' ');
			#endif
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

	Serial.write(ETX);

	ard.cmd_pending = FALSE;
}

void set_motors(uint8_t c_spd,uint8_t n_spd, Adafruit_DCMotor *motor){
	/*
	 * Ramp motors to new set points
	 */

	motor->run(FORWARD);  // Breaks without this

	if ( n_spd > c_spd ){  // Ramp up
		for (int i=0; i<255; i++) {
			motor->setSpeed(i);
			delay(RAMPRATE);
		}
	}
	else if ( n_spd < c_spd ){  // Ramp down
		for (int i=c_spd; i>n_spd; i--) {
			motor->setSpeed(i);
			delay(RAMPRATE);
		}
	}
	// ### deal with == case
}

void get_temperature(){
	/*
	 * ### Underconstruction
	 */
	ard.c_temp = 0xFFFFFFFF;
}
