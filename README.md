#A4_SyringePump#

Software to control and run the A4_FreezeRay.  Sends and receives 
serial commands and queries for NE-500 syringe pump,
TC-36-25_RS232 temperature controller and an Arduino mega.

__controller.py__:

_Input_: Recipe file or recipe parameters
_Output_: Forwards commands to NE-500, TC-36-25_RS232 and 
Arduino Mega over COM port
 
 
 __arduino.c____:

_Input_: Serial communication from controller.py
_Output_: Controls fan and pump driver circuits, monitors 
independent thermistor
 

__recipe.txt__:

_Input_: Contains all configurable commands used in a typical run
_Output_: None
