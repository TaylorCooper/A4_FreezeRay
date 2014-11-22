"""
    Author:
        Taylor Cooper
    Description:
        Load and run recipes over serial interface
        Communication with NE-500, TC-36-25_RS232, Arduino            
    Date Created:
        October 22, 2014 2:16:50 PM
        
    Arguments and Inputs:
        Recipe File
        Debug File
        Datalog File
    Outputs:
        Serial commands to syringe pump, temp controller and arduino
        Debug and datalog files populated
                  
    History:                  
    --------------------------------------------------------------
    Date:    
    Author:    Taylor Cooper
    Modification:    
     --------------------------------------------------------------
"""

import serial, time, collections, csv, msvcrt

# DEBUG MODE FROM ARDUINO
DEBUG = False

# Serial communication parameters, based on test run of 1000 logs
SP_DELAY=0.05 
TC_DELAY=0.05
ARD_DELAY_CMD=3 ### Something should be done about this...
ARD_DELAY_QRY=0.2
SP_RETRIES=10
TC_RETRIES=10
ARD_RETRIES=20

# Logging files and recipe
dbLP = "D:\\GitHub\\workspace\\A4_FreezeRay\\debugLog"
dtLP = "D:\\GitHub\\workspace\\A4_FreezeRay\\dataLog"
recipe = "D:\\GitHub\\workspace\\A4_FreezeRay\\recipe.csv"
LOG_RATE = 1 # Log data every X seconds by default
    
# SygPump, TC, Arduino (4 = COM5 in Windows)
# e.g. (None,None,'COM6') tries to open communication with Arduino on COM6 
# ports = (None,None,'COM6')
ports = ('COM5','COM7','COM6')

class spSerial():
    """
    Description:  Sends commands to pump over serial.
    Input: COM port and recipe file
    Output: Commands to syringe pump
    """
    
    def __init__(self, port, debugLogFile, diameter=7.0):
        """ Initialize syringe pump communication
        """
        
        self.port = port
        self.buffer = collections.deque() # Deques make nice buffers
        self.dbF = debugLogFile

        # Open port, nominal baudrate = 19200, TC required 9600 though
        # To change pump baud rate run "*ADR 0 B 9600" in Arduino serial 
        # monitor. This change will last through reset.
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        
        beginMsg = 'NE-500 Syringe pump communication established!'
        print beginMsg
        self.dbF.writerow([beginMsg])
        
        # Initialize diameter
        self.send('*RESET',delay=1) # Reset pump, wait longer
        self.send('DIA'+str(diameter)) # Assign syringe diameter


    def closeSer(self):
        """ Close serial port when done.
        """
        
        # Stop pumping
        self.send('STP') # Stop the pump
        
        # Say good bye
        endMsg = 'spSerial:: Signing Off!'
        if DEBUG: print endMsg
        self.dbF.writerow([endMsg])    
        
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
    

    def send(self, s, delay = SP_DELAY, retries=SP_RETRIES):
        """ String is written directly to serial port.
        """
        
        # Send and receive cmd
        cmd = s + '\x0D' # Carriage return required
        spMsg = 'spSerial:: Sent_Cmd: ' + s + ' ||  Received:'
        
        for i in range(retries):
            self.ser.write(cmd)
            time.sleep(delay) # Delay in seconds before response
            
            r = self.read()
            
            if not r: # Basically just check if you get a reply
                self.dbF.writerow([self.spMsg+'Sent invalid checksum!'])
                if DEBUG: print self.spMsg+'Sent invalid checksum!'
                continue
            
            if r[-1] != '\x03': # Make sure message finished
                self.dbF.writerow([self.spMsg+'Did not receive ETX!'])
                if DEBUG: print self.spMsg+'Did not receive ETX!'
                continue
            else:
                break
        
        # Let the user know what happened, no error handling
        row = spMsg + r
        self.dbF.writerow([row])
        if DEBUG: print row
        
        return r
    
    
    def basicCommand(self, vol, rate=1000):
        """ A basic command for the syringe pump, will infuse positive volumes
        and withdraw negative volumes.
        
        Note: if this function is called again before it completes it will
        interrupt the previous command.
        """
        
        if vol == 0: # Do nothing
            return 
        elif vol < 0: # Withdraw
            self.send('DIR WDR')
            vol = abs(vol)
        else:
            self.send('DIR INF')            
        
        self.send('RAT '+ str(rate) +' UM')
        self.send('VOL '+ str(vol))
        self.send('RUN')

    def dispensed(self):
        """ Input: nothing
        Output: infused vol, withdrawn vol, units
        """
        
        r = self.send('DIS')
        
        init = r.split('I')[-1:][0].split('W')
        I = init[0]
        W = init[-1:][0][:5]
        units = init[-1:][0][5:7]
                
        return float(I),float(W),units

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
        
        beginMsg = 'TC-36-25_RS232 Temperature controller'
        beginMsg = beginMsg + ' communication established!'
        print beginMsg
        self.dbF.writerow([beginMsg])


    def closeSer(self):
        """ Close serial port when done.
        """
        
        # Send commands to turn off TC
        self.send('2d', data=self.formatData(0)) # Turn off TC  
        
        # Say good bye
        endMsg = 'tcSerial:: Signing Off!'
        if DEBUG: print endMsg
        self.dbF.writerow([endMsg])       
        
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
        
        if temp == 0:
            r ='0x00000000'
        elif temp < 0:  # 2's complement for negatives
            temp = 2**bits + temp
            r = hex(temp)[:-1] # Remove trailing L for Long
        else:
            temph = hex(temp)
            r = '0x'+'0'*(10-len(temph)) + temph[2:]
            
        return r[2:]

        
    def formatResponse(self, r):
        """ Format data from TC reply into 2 decimal floats
        """
        
        # Convert from hex and get decimal
        r = int(r[:-2],16)/100.0
        # If negative convert 2's complement
        if r > 1000: r = (r*100 - 2**32)/100.0
        return round(r,2)
    
    
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
    

    def send(self, cmd, data='00000000', delay=TC_DELAY, retries=TC_RETRIES):
        """ String is written directly to serial port.
        00000000 = null data for TC expects for commands without data
        1ms delay is the expected delay before a reply
        """
        
        cmd = self.adr + cmd + data
        s = self.stx + cmd + self.getChecksum(cmd) + self.etx
        tcMsg = 'tcSerial:: Sent_Cmd: ' + cmd + ' ||  Received:'
                
        for i in range(retries):
            self.ser.write(s)
            
            reply = self.read(delay)
                        
            # If no reply re-send command
            if not reply:
                self.dbF.writerow([tcMsg+'No reply!'])
                if DEBUG: print tcMsg+'No reply!'
                continue
            
            # If my checksum failed TC replies XXXXXXXXc0, so try again
            if 'X' in reply:
                self.dbF.writerow([tcMsg+'Sent invalid checksum!'])
                if DEBUG: print tcMsg+'Sent invalid checksum!'
                continue
            
            # If checksum invalid re-send command
            if self.getChecksum(reply[:-2]) != reply[-2:]:
                self.dbF.writerow([tcMsg+'Received invalid checksum!'])
                if DEBUG: print tcMsg+'Received invalid checksum!'
                continue
            else:
                break

        # Let the user know what happened, no error handling
        row = tcMsg + reply
        if DEBUG: print row
        self.dbF.writerow([row])
        
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
        debugRow = ''
        buf = []

        # Open port, nominal baudrate = 19200, TC required 9600 though
        self.ser = serial.Serial(self.port, baudrate=9600, timeout=1)
        time.sleep(1) # Give serial port time to set up
        
        # Clearing serial buffer
        while self.ser.inWaiting() > 0:
            ch = self.ser.read(1) #Read 1 BYTE
            buf.append(ch)
        debugRow = ''.join(buf) 
        print debugRow
        self.dbF.writerow([debugRow])        
        
    def closeSer(self):
        """ Close serial port when done.
        """      
        
        # Send commands to turn off the Arduino
        self.send('F',data=[str(0)], delay=ARD_DELAY_CMD) # Turn off fan
        self.send('P',data=[str(0)], delay=ARD_DELAY_CMD) # Turn off pump
        
        endMsg = 'arduinoSerial:: Signing Off!'
        if DEBUG: print endMsg
        self.dbF.writerow([endMsg])  
        self.ser.close()
    

    def read(self, delay, cmd):
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
                if ch == chr(2): # <STX>
                    seeking_sync = False
            elif seeking_end:
                if ch == chr(6): # <ACK>
                    buf.append(chr(6))
                    seeking_end = False
                else:
                    buf.append(ch)
        
        ### These checks should be moved to send like the other serial classes
        if not buf: # No reply received
            debugRow = 'arduinoSerial:: Sent_Cmd: ' + cmd + ' No reply!'
            self.dbF.writerow([debugRow])
            if DEBUG: print debugRow
            return False
        elif buf[-1] != chr(6): # Check for ACK character
            debugRow = 'arduinoSerial:: Sent_Cmd: ' + cmd + ' ACK not found!'
            self.dbF.writerow([debugRow])
            if DEBUG: print debugRow
            return False 
        else:
            cmd = buf[0] # First entry is command
            # Comma separated data stored in list
            data = ''.join(buf[1:-1]).split(',') 
            return cmd, data
    

    def send(self, cmd, data=[], delay=0.1, retries=ARD_RETRIES):
        """ Command is formatted and written to arduino serial port.
        Command syntax: <STX> <CMD CHAR> <DATA> <NULL> <ETX>
        """
            
        # Format output string, requires data members to be strings
        # chr(0) = <NULL>
        s = chr(2)+cmd+','.join(data)+chr(0)+chr(3)

        for i in range(retries):
            # Send command         
            self.ser.write(s)
            #time.sleep(0.2) ### THIS IS CRAZY, without this delay it breaks...
            
            self.ardMsg = 'arduinoSerial:: Sent_Cmd: ' + cmd
            self.ardMsg = self.ardMsg + ' || Received: '
            
            reply = self.read(delay, cmd)
            
            if not reply: # Try again if no reply received
                continue  
            else:
                break
                 
        ### Note no sequence byte or checksum implemented
        # Format reply and return
        rCmd, rData = reply
        # Let the user know what happened, no error handling
        self.ardMsg = self.ardMsg + rCmd+'_'+':'.join(rData)
        self.dbF.writerow([self.ardMsg])
        if DEBUG: print self.ardMsg
        
        return reply
    

        
class controller():
    """
    Description:
    Input:
    Output:
    """
    
    def __init__(self, debugLogPath, dataLogPath, recipePath, ports):
        
        # Initial set up
        ts = str(time.time())[2:-3] # Repeats at about 100 weeks
        print 'Timestamp: ', ts  ### Take this out later
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
        self.t0 = time.time() # Time the run starts
        
        # Open communications
        if ports[0]:
            self.sp = spSerial(ports[0], self.dbF)
        if ports[1]:
            self.tc = tcSerial(ports[1], self.dbF)
        if ports[2]:
            self.ard = arduinoSerial(ports[2], self.dbF)
        
        #### Any initial parameters for the run
        runParams = [
                     'temp=',
                      ]
        # Logging parameters        
        self.headers = [ 
                  'Time(s)',
                  'SP_Temp(C)',
                  'SP_SetPoint(C)',
                  'HS_Temp(C)',
                  'TC_Effort(%)',
                  'Alarm_State',
                  'Ard_Temp(C)',
                  'Fan_Effort(%)',
                  'Pump_Effort(%)',
                  'Volume_Infused',
                  'Volume_Withdrawn',
                  'Volume_Units'
                  ]
        
        # Write initial comments
        self.dtF.writerow(runParams)
        self.dtF.writerow(self.headers)
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
    
    def quit(self):
        """ Exit controller in a sensible way.
        """
        
        # Close serial connections
        self.sp.closeSer()
        self.tc.closeSer()
        self.ard.closeSer()
        
        # Say good bye
        endMsg = 'controller:: Signing Off!'
        print endMsg
        self.dbF.writerow([endMsg]) 
        
        # Close log files
        self.dataLogFile.close()
        self.debugLogFile.close()

    
    def log(self, delay, rate=LOG_RATE):
        """ Description: Log data for sleep duration
        Input: datalogFile for writing 
        Outputs: populated datalog
        """
        
        for i in range(delay/rate):

            row = []

            # Log time
            row.append(int(time.time() - self.t0))
            
            # Log spreader plate temperature (C)
            spTemp = self.tc.send('01')
            row.append(self.tc.formatResponse(spTemp))
            
            # Log spreader plate set point temperature (C)
            setPoint = self.tc.send('03')
            row.append(self.tc.formatResponse(setPoint))
            
            # Log heatsink temp (C)
            hsTemp = self.tc.send('06')
            row.append(self.tc.formatResponse(hsTemp))

            # Log TC effort (%)
            tcEffort = self.tc.send('04')
            tcEffort = self.tc.formatResponse(tcEffort)
            row.append(tcEffort*100)
            
            # Log Alarm state
            ### Potentially could do something with this information
            ### Could call pause function for error states
            alarm = self.tc.send('05')
            alarm = bin(int(alarm[:-2],16))[2:]
            alarm = (8-len(alarm))*'0'+ alarm
            row.append(str(' '+alarm+' '))

            # Arduino thermistor temperature (C), fan and pump effort (%)
            r = self.ard.send('Q', delay=ARD_DELAY_QRY)
            row.append('-')  ### Thermistor not yet implemented
            row.append(round(100*int(r[1][0])/255.0,2)) # Fan % effort
            row.append(round(100*int(r[1][1])/255.0,2)) # Pump % effort
            
            # Syringe pump vol infuse, vol withdrawn, vol units
            r = self.sp.dispensed()
            row.append(r[0]) # Infused
            row.append(r[1]) # Withdrawn
            row.append(r[2]) # Units
            
            # Write and flush rows in case of hang up
            if DEBUG: print row
            self.dtF.writerow(row)
            self.dataLogFile.flush()
            self.debugLogFile.flush() 
            
            # Sleep for rate
            time.sleep(rate)
                  
                  
    def pause(self):
        """ A simple pause function that requires user to resume.
        """
        
        print "Press Enter to continue..."
        waiting = True
        
        while waiting:
            if msvcrt.getch() == '\r': waiting = False


    def executeStep(self, step):
        """ Description: Executes steps for a single row
        Input: self.stepVars
        Output: commands to ard, sp, tc, delay / user resume
        """
        
        ### Arduino delay may screw up logging
        # Set Pump Effort
        self.ard.send('P', data=[str(int(255*step[4]/100.0))],
                      delay=ARD_DELAY_CMD)
        # Set Fan Effort
        self.ard.send('F', data=[str(int(255*step[3]/100.0))],
                      delay=ARD_DELAY_CMD)
                    
        # Set TC set point
        self.tc.send('1c', data=self.tc.formatData(float(step[2])))
        # Enable or disable TCi
        if step[1] == 'Y':
            self.tc.send('2d', data=self.tc.formatData(1)) # TC on
        else:
            self.tc.send('2d', data=self.tc.formatData(0)) # TC off
        
        # Send SP volume and rate if volume != 0
        if step[5] != 0:
            self.sp.basicCommand(step[5], step[6])
        
        # Sleep (ideally this would be multi-threaded or something)
        self.log(self.getSeconds(step[0]))
        
        # Wait for user resume if required
        if step[7] == 'Y':
            self.pause()
        
        
    def run(self):
        """Description: Reads and executes recipe row by row
        Input: Recipe path, spSerial, tcSerial, arduinoSerial
        Output: debugLog, dataLog, pause for user input
        """
        
        recipeFile = open(self.recipePath, 'rb')
        recipe = csv.reader(recipeFile)
        firstLine = True
        step = []*8 
        
        self.t0 = time.time()
        
        # Read & execute recipe
        ### Does not attempt to check for set points changes, just resends
        for row in recipe:
            
            if firstLine: # Skip header
                firstLine = False
                continue
            
            # Read instructions in this order:
            # dur(s), tcOn, spTemp, Fan%, AirPump%, SygVol, SygRate, userResume
            for idx,item in enumerate(row):
                if item[0] == '#': continue # Ignore comments
                if item != step[idx]: step[idx] = item
                
            row = 'controller:: self.step: ' + ' '.join(self.step)
            self.dbF.writerow([row])
            
            self.executeStep(step)
            
       
        self.dataLogFile.close()
        self.debugLogFile.close()

if __name__ == '__main__':
        
    ctrlr = controller(dbLP, dtLP, recipe, ports)
    
    #ctrlr.log(20,1)  ## Current minimum rate = 6-7 seconds
    
    # Example steps and logging
    # dur(s), tcOn, spTemp, Fan%, AirPump%, SygVol, SygRate, userResume
    step1 = ['8s','N',25,0,0,0,0,'N', '# Comment']
    ctrlr.executeStep(step1)
    step2 = ['8s','Y',30,50,50,500,1900,'N','# Comment']
    ctrlr.executeStep(step2)
    step3 = ['8s','Y',-10.51,0,0,-500,1900,'N','# Comment']
    ctrlr.executeStep(step3)
    step4 = ['8s','Y',25,0,0,0,0,'N','# Comment']
    ctrlr.executeStep(step3)
    step4 = ['8s','N',25,0,0,0,0,'N','# Comment']
    ctrlr.executeStep(step4)
    
    ctrlr.quit()

#     # Arduino Test here
#     ### MINIMUM DELAY TO RAMP FROM 0-255 = 2.8 seconds
#     print ctrlr.ard.send('Q', delay=ARD_DELAY_QRY)
#     print ctrlr.ard.send('F',data=[str(255)], delay=ARD_DELAY_CMD)
#     print ctrlr.ard.send('Q', delay=ARD_DELAY_QRY)                            




    