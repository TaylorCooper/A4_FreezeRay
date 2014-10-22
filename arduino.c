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

//#define DEBUGMODE 1

#define STX			0x02
#define ETX			0x03
#define SYNC		0xFF
#define SEQ			0b00000111
//#define DEBUGMODE

// ===========
// PUMP DATA
// ===========

bool cmd_pending = false;

struct pump_data_t {
  uint8_t address;
  uint8_t sequence;
  char *cmd;
  };

static pump_data_t pump_data = {
  '0', // pump 0
  0b00110111, // sequence byte is 7, evaluates to ascii7
  NULL, // command array is null
  };
 

void setup(){

  Serial.begin(9600); //communication with computer
  Serial1.begin(9600); //reply from the pump??
  Serial2.begin(9600); //communication with pumps
 
}

void loop(){

	delay(20);


	if (Serial.available() >= 2){
		
		#ifndef DEBUGMODE
		send_pump_cmd();
		#endif
		
		#ifdef DEBUGMODE
		get_cmd();
		
		if (cmd_pending){
			send_self();
		}
		
		#endif

    }
    
	#ifndef DEBUGMODE
	get_pump_reply();
	#endif
	
}


#ifdef DEBUGMODE
void get_cmd(){
	static bool seeking_sync = true;
	static bool seeking_end = true;
	static uint8_t checksum;
	static uint8_t bufptr;
	static uint8_t sequence;
	
	uint8_t ch;
	char buffer[100];  //Use dynamic array later
	
	while (Serial.available()) {
		ch = Serial.read();
		
		if (seeking_sync) {
			// Waiting for sync byte.
			if (ch == STX) {
				// Found sync byte. Wait for rest of packet.
				seeking_sync = false;
				checksum = STX; // STX first character gets ignored.
				bufptr = 0;
			}
		} 
		else if (seeking_end) {
			// Reading packet.
			
			checksum ^= ch;
			
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
				} else {
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

#endif


void send_pump_cmd(){
  
	while (Serial.available() > 0){

		Serial2.write(Serial.read());

	}
}

void get_pump_reply(){
  
	while(Serial1.available() > 0){

		Serial.write(Serial1.read());
		
	}
}
