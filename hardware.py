import RPi.GPIO as GPIO
import time
from typing import Callable

#GPIO 17 = LED
#GPIO 27 = Button
#GPIO 22 = Vibration

def run_conversation(end_conversation: Callable):
    #to stay in loop
    global a
    a = True

    #callback function for button pressed
    def button_callback(channel):
        global a
        print("Button pressed")
        a = False

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)
    GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(22, GPIO.OUT)

    #set callback function for button
    GPIO.add_event_detect(27,GPIO.RISING,callback=button_callback)

    #until button pressed LED blinking and vibration on/off
    try:
        while(a):
            GPIO.output(17, True)
            GPIO.output(22, True)
            time.sleep(1)
            GPIO.output(17, False)
            GPIO.output(22, False)
            time.sleep(1)

        #Vibration off
        GPIO.output(22, False)
        a = True

        #until button pressed led on
        while(a):
            GPIO.output(17, True)
        
        GPIO.output(17, False)
    except KeyboardInterrupt:
        print("quit")
    except:
        print("unknown error")
    finally:
        GPIO.cleanup()
    end_conversation()