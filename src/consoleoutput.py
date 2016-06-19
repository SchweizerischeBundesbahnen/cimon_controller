# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'u206123'
from output import AbstractBuildAmpel

def create(configuration, key=None):
    return ConsoleOutput()

class ConsoleOutput(AbstractBuildAmpel):
    """Mock for manual testing"""

    def signal(self, red, yellow, green):
        if red or yellow or green:
            signal = "signaling%s%s%s" % (" red" if red else "", " yellow" if yellow else "", " green" if green else "")
        else:
            signal = "signaling off"
        print(signal)

if  __name__ =='__main__':
    ConsoleOutput().self_check()