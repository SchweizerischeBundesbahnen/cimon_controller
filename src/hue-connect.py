#!/usr/bin/python3
__author__ = 'ursbeeli'

""" auxiliary program needed for first time connection between hue bridge and raspi
    see hueoutput.py for more information
"""
import os,sys
from phue import Bridge

def wait_key():
    ''' Wait for a key press on the console and return it. '''
    result = None
    if os.name == 'nt':
        import msvcrt
        result = msvcrt.getch()
    else:
        import termios
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return result

ip = input("Enter the IP address of the hue bridge: ")

print("Press the connect button on your hue controller and then press enter.")
wait_key()

b = Bridge(ip)

# If the app is not registered and the button is not pressed, press the button and call connect() (this only needs to be run a single time)
b.connect()

print("Configuration has succesfully been written to ~/.python_hue")
