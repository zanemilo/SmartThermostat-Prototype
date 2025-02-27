#
# Thermostat - This is the Python code used to demonstrate
# the functionality of the thermostat that we have prototyped throughout
# the course. 
#
# This code works with the test circuit that was built for module 7.
#
# Functionality:
#
# The thermostat has three states: off, heat, cool
#
# The lights will represent the state that the thermostat is in.
#
# If the thermostat is set to off, the lights will both be off.
#
# If the thermostat is set to heat, the Red LED will be fading in 
# and out if the current temperature is below the set temperature;
# otherwise, the Red LED will be on solid.
#
# If the thermostat is set to cool, the Blue LED will be fading in 
# and out if the current temperature is above the set temperature;
# otherwise, the Blue LED will be on solid.
#
# One button will cycle through the three states of the thermostat.
#
# One button will raise the setpoint by a degree.
#
# One button will lower the setpoint by a degree.
#
# The LCD display will display the date and time on one line and
# alternate the second line between the current temperature and 
# the state of the thermostat along with its set temperature.
#
# The Thermostat will send a status update to the TemperatureServer
# over the serial port every 30 seconds in a comma delimited string
# including the state of the thermostat, the current temperature
# in degrees Fahrenheit, and the setpoint of the thermostat.
#
#------------------------------------------------------------------
# Change History
#------------------------------------------------------------------
# Version   |   Description
#------------------------------------------------------------------
#    1          Initial Development
#    2          Completed missing functionality per project requirements
#------------------------------------------------------------------

##
## Import necessary to provide timing in the main loop
##
from time import sleep
from datetime import datetime

##
## Imports required to allow us to build a fully functional state machine
##
from statemachine import StateMachine, State

##
## Imports necessary to provide connectivity to the 
## thermostat sensor and the I2C bus
##
import board
import adafruit_ahtx0

##
## These are the packages that we need to pull in so that we can work
## with the GPIO interface on the Raspberry Pi board and work with
## the 16x2 LCD display
##
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd

## This imports the Python serial package to handle communications over the
## Raspberry Pi's serial port. 
import serial

##
## Imports required to handle our Button, and our PWMLED devices
##
from gpiozero import Button, PWMLED

##
## This package is necessary so that we can delegate the blinking
## lights to their own thread so that more work can be done at the
## same time
##
from threading import Thread

##
## This is needed to get coherent matching of temperatures.
##
from math import floor

##
## DEBUG flag - boolean value to indicate whether or not to print 
## status messages on the console of the program
## 
DEBUG = True

##
## Create an I2C instance so that we can communicate with
## devices on the I2C bus.
##
i2c = board.I2C()

##
## Initialize our Temperature and Humidity sensor
##
thSensor = adafruit_ahtx0.AHTx0(i2c)

##
## Initialize our serial connection
##
ser = serial.Serial(
        port='/dev/ttyS0', # This would be /dev/ttyAM0 prior to Raspberry Pi 3
        baudrate = 115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
)

##
## Our two LEDs, utilizing GPIO 18, and GPIO 23
##
redLight = PWMLED(18)
blueLight = PWMLED(23)

##
## ManagedDisplay - Class intended to manage the 16x2 
## Display
##
class ManagedDisplay():
    def __init__(self):
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)
        self.lcd_columns = 16
        self.lcd_rows = 2 
        self.lcd = characterlcd.Character_LCD_Mono(self.lcd_rs, self.lcd_en, 
                    self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7, 
                    self.lcd_columns, self.lcd_rows)
        self.lcd.clear()

    def cleanupDisplay(self):
        self.lcd.clear()
        self.lcd_rs.deinit()
        self.lcd_en.deinit()
        self.lcd_d4.deinit()
        self.lcd_d5.deinit()
        self.lcd_d6.deinit()
        self.lcd_d7.deinit()
        
    def clear(self):
        self.lcd.clear()

    def updateScreen(self, message):
        self.lcd.clear()
        self.lcd.message = message

screen = ManagedDisplay()

##
## TemperatureMachine - StateMachine implementation class for the thermostat
##
class TemperatureMachine(StateMachine):
    "A state machine designed to manage our thermostat"

    off = State(initial=True)
    heat = State()
    cool = State()

    setPoint = 72

    cycle = (
        off.to(heat) |
        heat.to(cool) |
        cool.to(off)
    )

    # on_enter_heat: update lights on entering Heat state
    def on_enter_heat(self):
        self.updateLights()  # update LED status based on heat mode
        if DEBUG:
            print("* Changing state to heat")

    # on_exit_heat: turn off red LED on exiting Heat state
    def on_exit_heat(self):
        redLight.off()

    # on_enter_cool: update lights on entering Cool state
    def on_enter_cool(self):
        self.updateLights()  # update LED status based on cool mode
        if DEBUG:
            print("* Changing state to cool")
    
    # on_exit_cool: turn off blue LED on exiting Cool state
    def on_exit_cool(self):
        blueLight.off()

    # on_enter_off: turn off both LEDs in Off state
    def on_enter_off(self):
        redLight.off()
        blueLight.off()
        if DEBUG:
            print("* Changing state to off")
    
    # processTempStateButton: cycle through thermostat states (off -> heat -> cool -> off)
    def processTempStateButton(self):
        if DEBUG:
            print("Cycling Temperature State")
        self.cycle()

    # processTempIncButton: increase setPoint by one degree and update lights
    def processTempIncButton(self):
        if DEBUG:
            print("Increasing Set Point")
        self.setPoint += 1
        self.updateLights()

    # processTempDecButton: decrease setPoint by one degree and update lights
    def processTempDecButton(self):
        if DEBUG:
            print("Decreasing Set Point")
        self.setPoint -= 1
        self.updateLights()

    # updateLights: update LED indicators based on current state and temperature
    def updateLights(self):
        temp = floor(self.getFahrenheit())
        redLight.off()
        blueLight.off()
    
        if DEBUG:
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint}")
            print(f"Temp: {temp}")

        if self.current_state.id == 'heat':
            if temp < self.setPoint:
                redLight.pulse()
            else:
                redLight.on()
        elif self.current_state.id == 'cool':
            if temp > self.setPoint:
                blueLight.pulse()
            else:
                blueLight.on()
        else:  # off state
            redLight.off()
            blueLight.off()

    def run(self):
        myThread = Thread(target=self.manageMyDisplay)
        myThread.start()

    # Get the temperature in Fahrenheit
    def getFahrenheit(self):
        t = thSensor.temperature
        return (((9/5) * t) + 32)
    
    # setupSerialOutput: create comma-delimited output for the Thermostat Server
    def setupSerialOutput(self):
        tempF = floor(self.getFahrenheit())
        output = f"{self.current_state.id},{tempF},{self.setPoint}"
        return output
    
    endDisplay = False

    # manageMyDisplay: update LCD display and send periodic UART updates
    def manageMyDisplay(self):
        counter = 1
        altCounter = 1
        while not self.endDisplay:
            if DEBUG:
                print("Processing Display Info...")
    
            current_time = datetime.now()
            # Setup display line 1 with current date and time
            lcd_line_1 = current_time.strftime("%m/%d %H:%M:%S") + "\n"
    
            # Setup display line 2: alternate between current temperature and state/setpoint
            if altCounter < 6:
                tempF = floor(self.getFahrenheit())
                lcd_line_2 = f"Temp: {tempF}F"
                altCounter += 1
            else:
                lcd_line_2 = f"{self.current_state.id.capitalize()} {self.setPoint}F"
                altCounter += 1
                if altCounter >= 11:
                    self.updateLights()
                    altCounter = 1
    
            # Update the LCD display with both lines
            screen.updateScreen(lcd_line_1 + lcd_line_2)
    
            if DEBUG:
                print(f"Counter: {counter}")
            # Send update over UART every 30 seconds
            if (counter % 30) == 0:
                ser.write((self.setupSerialOutput() + "\n").encode())
                counter = 1
            else:
                counter += 1
            sleep(1)
    
        screen.cleanupDisplay()

tsm = TemperatureMachine()
tsm.run()

##
## Bind buttons to their respective event handlers
##
greenButton = Button(24)
greenButton.when_pressed = tsm.processTempStateButton

redButton = Button(25)
redButton.when_pressed = tsm.processTempIncButton

blueButton = Button(12)
blueButton.when_pressed = tsm.processTempDecButton

##
## Main loop: wait until keyboard interrupt to exit cleanly
##
repeat = True
while repeat:
    try:
        sleep(30)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        tsm.endDisplay = True
        sleep(1)
