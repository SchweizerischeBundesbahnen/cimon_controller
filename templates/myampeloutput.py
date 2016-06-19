# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = '<your_userid_here>'
from output import AbstractBuildAmpel

# Template for an ampel-type output. Supports 3 signals (red-yellow-green) or less.
# copy and add your functionality

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    return MyAmpelOutput()

class MyAmpelOutput(AbstractBuildAmpel):
    """Template for your own Ampel-like output device. Currently only support build status"""

    def signal(self, red, yellow, green):
        """Display the given input (red=True means red light on, red=False red light off and so on) """
        pass

if  __name__ =='__main__':
    MyAmpelOutput().self_check()