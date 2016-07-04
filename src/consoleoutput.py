# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'
from output import AbstractBuildAmpel

def create(configuration, key=None):
    return ConsoleOutput()

class ConsoleOutput(AbstractBuildAmpel):
    """Mock for manual testing"""

    def signal(self, red, yellow, green, flash=False):
        if red or yellow or green:
            signal = "signaling%s%s%s%s" % (" red" if red else "", " yellow" if yellow else "", " green" if green else "", " flashing" if flash else "")
        else:
            signal = "signaling off"
        print(signal)

if  __name__ =='__main__':
    ConsoleOutput().self_check()