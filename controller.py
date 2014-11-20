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

import serial, time, collections, csv, msvcrt

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


    def closeSer(self):
        """ Close serial port when done.
        """
        
        self.send('STP') # Stop the pump
        self.dbF.writerow(['spSerial:: Signing Off!'])
        self.ser.close()


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
        row = 'spSerial:: Sent_Cmd: ', s, ' ||  Received:', r
        self.dbF.writerow(row)
    
    
    def basicCommand(self, vol, rate=1000):
        """ A basic command for the syringe pump, will infuse positive volumes
        and withdraw negative volumes.
        
        Note: if this function is called again before it completes it will
        interrupt the previous command.
        """
        
        if vol < 0: # With draw
            self.send('DIR WDR')
            vol = abs(vol)
        else:
            self.send('DIR INF')            
        
        self.send('RAT '+ str(rate) +' UM')
        self.send('VOL '+ str(vol))
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
        self.stx = '\x2a' # *
        self.etx = '\x0d' # CR
        self.ack = '\x5e' # ^
        self.adr = '00' # Always 00 for our TC

        # Open port
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up


    def closeSer(self):
        """ Close serial port when done.
        """
        
        # Send commands to turn off TC
        self.send('2d', data=self.tcformatData(0)) # Turn off TC        
        self.dbF.writerow(['tcSerial:: Signing Off!'])         
        self.ser.close()
        
        
    def formatData(self, temp):
        """Format temperature SP for TE Tech TC.
        Input: temp in celsius, float or int 
        Output: string formated for DDDDDDDDD value of TC cmds
        e.g. input 1 >> output 00000064
        e.g. input -1 >> output ffffff9c (2's complement)
        e.g. input 1.25 >> output 0000007d 
        """
        
        bits = 32 # Required for this protocol
        temp = int(temp*100) # Multiply by 100 to preserve decimal places
            
        if temp < 0:  # 2's complement for negatives
            temp = 2**bits + temp
            r = hex(temp)[:-1] # Remove trailing L for Long
        else:
            temph = hex(temp)
            r = '0x'+'0'*(10-len(temph)) + temph[2:]
            
        return r

    
    def getChecksum(self, s):
        """Get the 8bit (modulo 256) checksum of characters in s
        """
        
        chksum = 0
        for ch in s:
            chksum = chksum + ord(ch)
            
        return hex(chksum%256)[2:]


    def read(self, delay):
        """ Read chars from the serial port buffer well it is not empty.
        Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ACK>
        """
    
        buf = []
        seeking_sync = True;
        seeking_end = True;
    
        time.sleep(delay)
        # Read serial into buffer and then pop out to s for return
        while self.ser.inWaiting() > 0:
            ch = self.ser.read(1) #Read 1 BYTE
    
            if seeking_sync:
                if ch == self.stx: # <STX>
                    seeking_sync = False
            elif seeking_end:
                if ch == self.ack: # <ACK>
                    buf.append(self.ack)
                    seeking_end = False
                else:
                    buf.append(ch)
                    
        if not buf: # No reply received
            return False
        elif buf[-1] != self.ack: # Check for ACK character
            return False 
        else:
            return ''.join(buf[:-1])
    

    def send(self, cmd, data='00000000', delay=0.4, retries=10):
        """ String is written directly to serial port.
        00000000 = null data for TC expects for commands without data
        0.4s delay is the expected delay before a reply
        """
        
        cmd = self.adr + cmd + data
        s = self.stx + cmd + self.getChecksum(cmd) + self.etx
                
        for i in range(retries):
            self.ser.write(s)
            
            reply = self.read(delay)
            
            # If no reply re-send command
            if not reply:
                continue
            
            # If checksum invalid re-send command
            if self.getChecksum(reply[:-2]) != reply[-2:]:
                continue
    
        # Let the user know what happened, no error handling
        row = 'tcSerial:: Sent_Cmd: ', cmd, ' ||  Received:', reply
        self.dbF.writerow(row)
        
        return reply
      
        
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
        self.debugRow = ''
        buf = []

        # Open port, nominal baudrate = 19200, TC required 9600 though
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        
        while self.ser.inWaiting() > 0:
            ch = self.ser.read(1) #Read 1 BYTE
            buf.append(ch)
        self.debugRow = ''.join(buf) 
        print self.debugRow
        self.dbF.writerow([self.debugRow])        
        
    def closeSer(self):
        """ Close serial port when done.
        """      
        
        # Send commands to turn off the Arduino
        self.ard.send('F',data=[str(0)], delay=2) # Turn off fan
        self.ard.send('P',data=[str(0)], delay=2) # Turn off pump
        self.dbF.writerow(['arduinoSerial:: Signing Off!'])  
        self.ser.close()
    

    def read(self, delay):
        """ Read chars from the serial port buffer well it is not empty.
        Reply syntax: <STX> <CMD CHAR> <DATA1,DATA2,DATA3,etc.> <ACK>
        """
                
        buf = []
        seeking_sync = True;
        seeking_end = True;

        if DEBUG:
            time.sleep(delay)
            while self.ser.inWaiting() > 0:
                ch = self.ser.read(1) #Read 1 BYTE
                buf.append(ch)
            print 'Received: ', ''.join(buf)
        else:
            time.sleep(delay)
            # Read serial into buffer and then pop out to s for return
            while self.ser.inWaiting() > 0:
                ch = self.ser.read(1) #Read 1 BYTE
                
                if seeking_sync:
                    if ch == chr(2): # <STX>
                        seeking_sync = False
                elif seeking_end:
                    if ch == chr(6): # <ACK>
                        buf.append(chr(6))
                        seeking_end = False
                    else:
                        buf.append(ch)
        
        if not buf: # No reply received
            self.debugRow = self.debugRow + 'No reply!'
            self.dbF.writerow([self.debugRow])
            print self.debugRow
            return False
        elif buf[-1] != chr(6): # Check for ACK character
            self.debugRow = self.debugRow + 'ACK not found!'
            self.dbF.writerow([self.debugRow])
            print self.debugRow
            return False 
        else:
            cmd = buf[0] # First entry is command
            # Comma separated data stored in list
            data = ''.join(buf[1:-1]).split(',') 
            return cmd, data
    

    def send(self, cmd, data=[], delay=0.4, retries=10):
        """ Command is formatted and written to arduino serial port.
        Command syntax: <STX> <CMD CHAR> <DATA> <NULL> <ETX>
        """
            
        # Format output string, requires data members to be strings
        # chr(0) = <NULL>
        s = chr(2)+cmd+','.join(data)+chr(0)+chr(3)

        for i in range(retries):
            # Send command         
            self.ser.write(s)
            time.sleep(0.2) ### THIS IS CRAZY, without this delay it breaks...
            
            self.debugRow = 'arduinoSerial:: Sent_Cmd: ' + cmd
            self.debugRow = self.debugRow + ' || Received: '
            
            reply = self.read(delay)
            
            if not reply: # Try again if no reply received
                continue  
            
            ### Note no sequence byte or checksum implemented
            
            if DEBUG: # Return and do nothing with reply
                print '======================='
                print ''                    
                return 
            else: # Format reply and return
                rCmd, rData = reply
                # Let the user know what happened, no error handling
                self.debugRow = self.debugRow + rCmd+'_'+':'.join(rData)
                self.dbF.writerow([self.debugRow])
                print self.debugRow
                
                return reply
        
        
class controller():
    """
    Description:
    Input:
    Output:
    """
    
    def __init__(self, debugLogPath, dataLogPath, recipePath, ports):
        
        # Initial set up
        self.ts = str(time.time())[2:-3] # Repeats at about 100 weeks
        print 'Timestamp: ', self.ts  ### Take this out later
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
        self.step = []*8 
        
        # Open communications
        self.sp = spSerial(ports[0], self.dbF)
        self.tc = tcSerial(ports[1], self.dbF)
        self.ard = arduinoSerial(ports[2], self.dbF)
        
        #### Any initial parameters for the run
        runParams = [
                     'temp=',
                      ]
        ### Any parameters for logging         
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

    def getSeconds(self, s):
        """ Convert stings of this format to seconds.
        10h-10m-10s
        3s
        7m-9s
        1h-5s
        """
        duration = 0
        
        for i in s.split('-'):
            if 'h' in i: duration = duration + int(i.split('h')[0])*3600
            if 'm' in i: duration = duration + int(i.split('m')[0])*60
            if 's' in i: duration = duration + int(i.split('s')[0])
                
        return duration

    def executeStep(self):
        """ Description: Executes steps for a single row
        Input: self.stepVars
        Output: commands to ard, sp, tc, delay / user resume
        """
        
        # Set Pump Effort
        self.ard.send('P', data=[str(int(255*self.step[4]/100.0))], delay=3)
        # Set Fan Effort
        self.ard.send('F', data=[str(int(255*self.step[3]/100.0))], delay=3)            
        # Set TC set point
        self.tc.send('1c', data=self.tc.formatData(float(self.step[2])))
        
        # Enable or disable TC
        if self.step[1] == 'Y':
            self.tc.send('2d', data=self.tcformatData(1)) # Turn on TC
        else:
            self.tc.send('2d', data=self.tcformatData(0)) # Turn off TC
        
        # Send SP volume and rate if volume != 0
        if self.step[5] != 0:
            self.sp.basicCommand(self.step[5], self.step[6])
        
        # Sleep (ideally this would be multi-threaded or something)
        time.sleep(self.getSeconds(self.step[0]))
        
        # Wait for user resume if required
        if self.step[7] == 'Y':
            print "Press Enter to continue..."
            waiting = True
            
            while waiting:
                if msvcrt.getch() == '\r': waiting = False
        
        
    def run(self):
        """Description: Reads and executes recipe row by row
        Input: Recipe path, spSerial, tcSerial, arduinoSerial
        Output: debugLog, dataLog, pause for user input
        """
        
        recipeFile = open(self.recipePath, 'rb')
        recipe = csv.reader(recipeFile)
        firstLine = True
        
        # Dur(s), TC On, SP Temp, Fan%, AirPump%, SygVol, SygRate, User Resume
        stepVars = [None]*8
        
        # Read & execute recipe
        ### Does not attempt to check for set point changes, just resends
        for row in recipe:
            
            if firstLine: # Skip header
                firstLine = False
                continue
            
            # Read instructions
            for idx,item in enumerate(row):
                if item[0] == '#': continue # Ignore comments
                if item != self.step[idx]: self.step[idx] = item
                
            row = 'controller:: self.step: ' + ' '.join(self.step)
            self.dbF.writerow([row])
            
            self.executeStep()
                

        
        
#         # Arduino Test here
#         ### MINIMUM DELAY TO RAMP FROM 0-255 = 2.8 seconds
#         self.ard.send('Q', delay=0.2)
#         self.ard.send('F',data=[str(255)], delay=3)
#         self.ard.send('Q', delay=0.2)
#         self.ard.send('P',data=[str(255)], delay=3)
#         self.ard.send('Q', delay=0.2)
#         self.ard.send('F',data=[str(128)], delay=2)
#         self.ard.send('Q', delay=0.2) 
#         self.ard.send('P',data=[str(128)], delay=2)
#         self.ard.send('Q', delay=0.2) 
#         self.ard.send('F',data=[str(0)], delay=2)
#         self.ard.send('Q', delay=0.2) 
#         self.ard.send('P',data=[str(0)], delay=2)
#         self.ard.send('Q', delay=0.2)                                  
#         
#         self.dataLogFile.close()
#         self.debugLogFile.close()

exampleSygPumpRecipe = [
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





    