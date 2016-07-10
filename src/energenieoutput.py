# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from output import AbstractBuildAmpel, default_signal_error_threshold
from os import system
import logging

# output to the Energenie Power socket
# treats the Energenie as an Ampel, see AbstractBuildAmpel for the logic.
# uses the sispmctl command line tool (as user).
# The Energenie has 4 controllable outputs, 1-4.
#   1: red
#   2: yellow
#   3: green
#   4: red (second red for instance for a rotating light)
# both red will be switched together
def create(configuration, aesKey=None):
    return EnergenieBuildAmpel(device_nr=configuration.get("deviceNr", None),
                               signal_error_threshold=configuration.get("signalErrorThreshold", default_signal_error_threshold))


class EnergenieBuildAmpel(AbstractBuildAmpel):
    """ control energenie according to build status """

    def __init__(self, device_nr=None, signal_error_threshold=default_signal_error_threshold):
        super(EnergenieBuildAmpel, self).__init__(signal_error_threshold=signal_error_threshold)
        self.energenie = Energenie(device_nr)

    def signal(self, red, yellow, green, flash=False): # igonre flash, this feature is not supported
        self.energenie.switch(socket_1=red, socket_2=yellow, socket_3=green, socket_4=red)

class Energenie():
    """ control the energenie socket using the sispmctl script """

    def __init__(self, device_nr=None):
        self.__device_nr=device_nr

    def switch(self, socket_1=False, socket_2=False, socket_3=False, socket_4=False):
        self.__call_sispmctl__((1, socket_1), (2, socket_2), (3, socket_3), (4, socket_4))

    def __call_sispmctl__(self, *socket_on):
        device_str = "-d %s" % self.__device_nr if self.__device_nr else ""
        switches = ""
        for socket, on in socket_on:
           switches += " %s %s" % ("-o" if on else "-f", socket)
        command = "sispmctl -q %s%s" % (device_str, switches)
        logging.debug(command)
        rc = system(command)
        if rc != 0:
            logging.warning("sispmctl returned %s", rc)

if  __name__ =='__main__':
    """smoke test"""
    e = Energenie()
    e.self_check()
