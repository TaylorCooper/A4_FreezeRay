"""
    Author:
        Taylor Cooper
    Description:
        Load and run recipes over serial interface
        Communication with NE-500, TC-36-25_RS232, Arduino            
    Date Created:
        October 22, 2014 2:16:50 PM
    
    ###TODO:
        SygPump
            Remove recipe functionality
        Arduino interface
        TC interface
        Controller / loop interface
            Recipe file definition
    
    Arguments and Inputs:
        Recipe File:
            ### TBD
    Outputs:
        Serial commands various interface devices
    Dependencies:
        pyserial (in cmdline: pip install pyserial)
                  
    History:                  
    --------------------------------------------------------------
    Date:    
    Author:    Taylor Cooper
    Modification:    
     --------------------------------------------------------------
"""

import serial, time, collections, csv

DEBUG = False

class spSerial():
    """
    Description:  Sends commands to pump over serial.
    Input: COM port and recipe file
    Output: Commands to syringe pump
    """
    
    def __init__(self, port, debugLogFile):
        """ Initialize syringe pump communication
        """
        
        self.port = port
        self.buffer = collections.deque() # Deques make nice buffers
        self.dbF = debugLogFile

        # Open port, nominal baudrate = 19200, TC required 9600 though
        ### May need to initialize Baud Rate with multiple py serial instances
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        
        # Initialize diameter
        self.send('*RESET',delay=1) # Reset pump, wait longer
        self.send('DIA'+str(self.diameter)) # Assign syringe diameter
              

    def read(self):
        """ Read chars from the serial port buffer well it is not empty.
        """        
        s = ""
        
        # Read serial into buffer and then pop out to s for return
        while self.ser.inWaiting() > 0:

            l = self.ser.read(1) #Read 1 BYTE
            self.buffer.append(l)
            
            while len(self.buffer) > 0:
                s = s + self.buffer.popleft()

        return s
    

    def send(self, s, delay=0.2):
        """ String is written directly to serial port.
        """
        
        # Send and receive cmd
        cmd = s + '\x0D' # Carriage return required
        self.ser.write(cmd)
        time.sleep(delay) # Delay in seconds before response
        r = self.read()
        
        # Let the user know what happened, no error handling
        row = 'Sent_Cmd: ', s, ' ||  Received:', r
        self.dbF.writerow(row)
    
    
    def flushLine(self, flushLength=200):
        """ Flush line to remove air
        """
        
        self.send('RAT 1000 UM')
        self.send('VOL '+ str(flushLength))
        self.send('DIR INF')
        self.send('RUN')



class tcSerial():
    """
    Description:  Wrapping and unwrapping of temperature controller messages
    Input: Recipe file command
    Output: Serial command with checksum for TC
    """
    
    def __init__(self, port, debugLogFile):
        """ Initialize syringe pump communication
        """
        
        self.port = port
        self.buffer = collections.deque() # Deques make nice buffers
        self.dbF = debugLogFile

        # Open port, nominal baudrate = 19200, TC required 9600 though
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        

    def read(self):
        """ Read chars from the serial port buffer well it is not empty.
        """        
        s = ""
        
        # Read serial into buffer and then pop out to s for return
        while self.ser.inWaiting() > 0:

            l = self.ser.read(1) #Read 1 BYTE
            self.buffer.append(l)
            
            while len(self.buffer) > 0:
                s = s + self.buffer.popleft()

        return s
    

    def send(self, s, delay=0.2):
        """ String is written directly to serial port.
        """
        
        # Send and receive cmd
        cmd = s + '\x0D' # Carriage return required
        self.ser.write(cmd)
        time.sleep(delay) # Delay in seconds before response
        r = self.read()
        
        # Let the user know what happened, no error handling
        row = 'Sent_Cmd: ', s, ' ||  Received:', r
        self.dbF.writerow(row)
      
        
class arduinoSerial():
    """
    Description:
    Input:
    Output:
    """
    
    def __init__(self, port, debugLogFile):
        """ Initialize syringe pump communication
        """
        
        self.port = port
        self.dbF = debugLogFile
        buf = []

        # Open port, nominal baudrate = 19200, TC required 9600 though
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        
        while self.ser.inWaiting() > 0:
            ch = self.ser.read(1) #Read 1 BYTE
            buf.append(ch)
        print ''.join(buf)
        

    def read(self, delay):
        """ Read chars from the serial port buffer well it is not empty.
        Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ETX>
        """
                
        buf = []
        seeking_sync = True;
        seeking_end = True;

        if DEBUG:
            time.sleep(delay)
            while self.ser.inWaiting() > 0:
                ch = self.ser.read(1) #Read 1 BYTE
                buf.append(ch)
            print ''.join(buf)
            print '======================='
        else:
            time.sleep(delay)
            # Read serial into buffer and then pop out to s for return
            while self.ser.inWaiting() > 0:
                ch = self.ser.read(1) #Read 1 BYTE
                
                if seeking_sync:
                    if ch == chr(2): # <STX>
                        seeking_sync = False
                elif seeking_end:
                    if ch == chr(3): # <ETX>
                        seeking_end = False
                    else:
                        buf.append(ch)
            
            # Command = first char, Data = comma separated values
            cmd = buf[0]
            data = ''.join(buf[1:]).split(',')
    
            return cmd, data
    

    def send(self, cmd, data=[], delay=0.4):
        """ Command is formatted and written to arduino serial port.
        Command syntax: <STX> <CMD CHAR> <DATA> <NULL> <ETX>
        """
            
        # Format output string, requires data members to be strings
        # chr(0) = <NULL>
        s = chr(2)+cmd+','.join(data)+chr(0)+chr(3)

        # Send command         
        self.ser.write(s)
        time.sleep(0.2) ### THIS IS CRAZY, without this delay it breaks...
        
        if DEBUG:
            print 'Sent: ', s
            self.read(delay) # Delay in seconds before response
        else:
            rCmd, rData = self.read(delay)
            # Let the user know what happened, no error handling
            row = 'Sent_Cmd: ' + cmd + ' || Received: ' 
            row = row + rCmd+'_'+'-'.join(rData)
            self.dbF.writerow([row])
            print row
        
        
class controller():
    """
    Description:
    Input:
    Output:
    """
    
    def __init__(self, debugLogPath, dataLogPath, recipePath, ports):
        
        # Initial set up
        ts = str(time.time())[2:-3] # Repeats at about 100 weeks
        print 'Timestam: ', ts  ### Take this out later
        dtLP = dataLogPath + '.csv' #'_' + ts + '.csv'
        dbLP = debugLogPath + '.csv' #'_' + ts + '.csv'
        
        # Allocate class variables 
        self.dataLogFile = open(dtLP, 'wb')
        self.dtF = csv.writer(self.dataLogFile, delimiter=',', 
                                    escapechar='{', quoting=csv.QUOTE_NONE)
        self.debugLogFile = open(dbLP, 'wb')
        self.dbF = csv.writer(self.debugLogFile, delimiter=',', 
                                    escapechar='{', quoting=csv.QUOTE_NONE)

        self.recipePath = recipePath
        
        # Open communications
        #self.sp = spSerial(ports[0], self.dbF)
        #self.tc = tcSerial(ports[1], self.dbF)
        self.ard = arduinoSerial(ports[2], self.dbF)
        
        # Any initial parameters for the run
        runParams = [
                     'temp=',
                      ]
        # Any parameters for logging         
        headers = [ 
                  'Time_Stamp',
                  'SP_Temp',
                  'SP_SetPoint',
                  'HS_Temp',
                  'Ard_Temp',
                  'TC_Effort',
                  'Syg_Vol_Pumped',
                  'Air_Pump_Effort',
                  'Fan_Effort',
                  ]
        
        # Write initial comments
        self.dtF.writerow(runParams)    
        self.dtF.writerow(headers)
        self.dataLogFile.flush() 
        self.dbF.writerow(['Debug log path: ' + dbLP])
        self.dbF.writerow(['Data log path: ' + dtLP])
        self.dbF.writerow(['Recipe path: ' + self.recipePath])
        self.debugLogFile.flush()      

    def loadRecipe(self):
        """
        Description:
        Input:
        Output:
        """

        
    def run(self):
        """
        Description:
        Input:
        Output:
        """
        
        # Arduino Test here
        ### MINIMUM DELAY TO RAMP FROM 0-255 = 2.8 seconds
        self.ard.send('Q', delay=0.2)
        self.ard.send('F',data=[str(255)], delay=2.8)
        self.ard.send('Q', delay=0.2)
        self.ard.send('P',data=[str(255)], delay=2.8)
        self.ard.send('Q', delay=0.2)        
        
        self.dataLogFile.close()
        self.debugLogFile.close()

exampleRecipe = [
                 1, # Number of times commands are looped
                 7.0, # Inner diameter of syringe
                 
                 # Pre-formated commands
                 ['PHN 1', # Step 1
                 'FUN RAT', # Not sure what this is for..
                 'RAT 1000 UM', # Set pump rate in ul/min
                 'VOL 1000', # Set volume in ul
                 'DIR INF', # Set direction (infusion, depress syringe)
                 'PHN 2', # Step 2 executes after step 1 completes
                 'FUN RAT',
                 'RAT 1000 UM',
                 'VOL 1000',
                 'DIR WDR',
                 'PHN 3',
                 'FUN STP',
                 'RUN'] # Step 3 executes after step 1 completes
                 ]

recipePath = 'recipe.txt'

if __name__ == '__main__':
    # To change pump baud rate run "*ADR 0 B 9600" in Arduino serial monitor
    # this change will last through reset, 9600 required to match with TC
    
    # Syringe Pump Commands 
#     sp = spSerial(4, recipePath) # Port (4 = COM5), recipe, default BR = 9600
#     sp.flushLine() # Call this command to remove air at the end of tube
#     sp.runRecipe()

    dbLP = "D:\\GitHub\\workspace\\A4_FreezeRay\\debugLog"
    dtLP = "D:\\GitHub\\workspace\\A4_FreezeRay\\dataLog"
    recipe = "D:\\GitHub\\workspace\\A4_FreezeRay\\recipe.txt"
    ports = (6,7,5) # SygPump, TC, Arduino (4 = COM5 in Windows)
        
    ctrlr = controller(dbLP,dtLP, recipe, ports)
    ctrlr.run()





    