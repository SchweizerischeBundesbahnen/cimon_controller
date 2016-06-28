# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from output import AbstractBuildAmpel, default_signal_error_threshold
from os import system
import logging

# controll the cleware usb ampel (http://www.cleware-shop.de/epages/63698188.sf/de_DE/?ObjectPath=/Shops/63698188/Products/43/SubProducts/43-1)
# uses the shell cleware tool (as user) as no python binding worked. Unfortunately this is kind of slow.
# Extends AbstractBuildAmpel. See AbstractBuildAmpel for explaination of the logic (when does which light turn on)
def create(configuration, key=None):
    return ClewareBuildAmpel(device=configuration.get("device", None),
                        signal_error_threshold=configuration.get("signalErrorThreshold", default_signal_error_threshold))


class ClewareBuildAmpel(AbstractBuildAmpel):

    """control the cleware ampel according to build status"""
    def __init__(self, device=None, signal_error_threshold=default_signal_error_threshold):
        super().__init__(signal_error_threshold=signal_error_threshold)
        self.cleware_ampel=ClewareAmpel(device)

    def signal(self, red, yellow, green):
        self.cleware_ampel.display(red=red, yellow=yellow, green=green)

class ClewareAmpel():
    """control the cleware ampel using the clewarecontrol shell command """

    def __init__(self, device=None):
        self.__device=device

    def display(self, red=False, yellow=False, green=False):
        self.__call_clewarecontrol__(0, red)
        self.__call_clewarecontrol__(1, yellow)
        self.__call_clewarecontrol__(2, green)

    def __call_clewarecontrol__(self, light, on):
        device_str = "-d %s" % self.__device if self.__device else ""
        command = "clewarecontrol %s -c 1 -as %s %s >> /dev/null" % (device_str, light, int(on))
        logging.debug(command)
        rc = system(command)
        if rc != 0:
            logging.warning("clewarecontrol returned %s", rc)

if  __name__ =='__main__':
    """smoke test"""
    a = ClewareAmpel()
    a.self_check()
