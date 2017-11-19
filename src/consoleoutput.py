# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'
from output import AbstractBuildAmpel
from datetime import datetime

def create(configuration, key=None):
    return ConsoleOutput(build_filter_pattern=configuration.get("buildFilterPattern", None),
                         collector_filter_pattern=configuration.get("collectorFilterPattern", None))

class ConsoleOutput(AbstractBuildAmpel):
    """Mock for manual testing"""
    def __init__(self, build_filter_pattern=None, collector_filter_pattern=None):
        super(ConsoleOutput, self).__init__(build_filter_pattern=build_filter_pattern, collector_filter_pattern=collector_filter_pattern)
        self.__current_signal__ = None

    def signal(self, red, yellow, green, flash=False):
        if self.__current_signal__ != (red, yellow, green, flash):
            if red or yellow or green:
                signal = "%s signaling%s%s%s%s" % (datetime.now().isoformat(), " red" if red else "", " yellow" if yellow else "", " green" if green else "", " flashing" if flash else "")
            else:
                signal = "%s signaling off" % datetime.now().isoformat()
            print(signal)
            self.__current_signal__ = (red, yellow, green, flash)

if  __name__ =='__main__':
    ConsoleOutput().self_check()