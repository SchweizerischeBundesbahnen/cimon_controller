# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from output import AbstractBuildAmpel, default_signal_error_threshold
from os import system
import logging

default_repeat_every = 15

default_colors={1 : "red", 2: "yellow", 3: "green", 4: "red"}

logger = logging.getLogger(__name__)

# output to the Energenie Power socket
# treats the Energenie as an Ampel, see AbstractBuildAmpel for the logic.
# uses the sispmctl command line tool (as user).
# The Energenie has 4 controllable outputs, 1-4.
# assignment is configurable, default is:
#   1: red
#   2: yellow
#   3: green
#   4: red (second red for instance for a rotating light)
# colors not assigned will not be switched
# both red will be switched together
def create(configuration, aesKey=None):
    return EnergenieBuildAmpel(device_nr=configuration.get("deviceNr", None),
                               signal_error_threshold=configuration.get("signalErrorThreshold", default_signal_error_threshold),
                               repeat_every=configuration.get("repeatEvery", default_repeat_every),
                               build_filter_pattern=configuration.get("buildFilterPattern", None),
                               colors=configuration.get("colors", default_colors))


class EnergenieBuildAmpel(AbstractBuildAmpel):
    """ control energenie according to build status """

    def __init__(self, device_nr=None, signal_error_threshold=default_signal_error_threshold, repeat_every=default_repeat_every, build_filter_pattern=None, colors=default_colors):
        super(EnergenieBuildAmpel, self).__init__(signal_error_threshold=signal_error_threshold, build_filter_pattern=build_filter_pattern)
        self.energenie = Energenie(device_nr=device_nr, repeat_every=repeat_every)
        self.colors=colors

    def signal(self, red, yellow, green, flash=False): # igonre flash, this feature is not supported
        signal=locals()
        self.energenie.switch([(k, signal[v]) for k,v in self.colors.items()])

class Energenie():
    """ control the energenie socket using the sispmctl script """

    def __init__(self, device_nr=None, repeat_every=default_repeat_every):
        self.__device_nr=device_nr
        self.__last_state=None
        self.repeat_every=repeat_every
        self.__repeat_count = 0

    def switch(self, socket_on):
        if socket_on:
            self.__switch_if_changed__(*socket_on)

    def __switch_if_changed__(self, *socket_on):
        if socket_on != self.__last_state or self.__repeat_count >= self.repeat_every:
            logger.debug("Change or time to repeat output to energenie: %s", str(socket_on))
            self.__last_state = socket_on
            self.__call_sispmctl__(*socket_on)
            self.__repeat_count = 1
        else:
            logger.debug("Ignoring repeated output to energenie")
            self.__repeat_count += 1

    def __call_sispmctl__(self, *socket_on):
        device_str = "-d %s" % self.__device_nr if self.__device_nr else ""
        switches = ""
        for socket, on in socket_on:
           switches += " %s %s" % ("-o" if on else "-f", socket)
        command = "sispmctl -q %s%s" % (device_str, switches)
        logger.debug(command)
        rc = system(command)
        if rc != 0:
            logger.warning("Energenie output: sispmctl returned %s", rc)

if  __name__ =='__main__':
    """smoke test"""
    e = Energenie()
    e.self_check()
