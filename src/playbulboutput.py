# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'baehlerth'

import logging
import os

from output import AbstractBuildAmpel, default_signal_error_threshold

default_flash_interval_sec = 46
default_absoulte_every_sec = 300
default_flash_reg = '0x0019'
default_color_reg = '0x001b'
default_flash = '01000404'
default_yellow_color = '00ffff00'
default_red_color = '00ff0000'
default_green_color = '0000ff00'

logger = logging.getLogger(__name__)

def create(configuration, aesKey=None):
    return PlaybulbBuildAmpel(device=configuration.get("device", None),
                              signal_error_threshold=configuration.get("signalErrorThreshold",
                                                                       default_signal_error_threshold),
                              color_reg=configuration.get("colorReg",
                                                                  default_color_reg),
                              flash_reg=configuration.get("flashReg",
                                                                  default_flash_reg),
                              flash=configuration.get("flash", default_flash),
                              red_color=configuration.get("redColor", default_red_color),
                              green_color=configuration.get("greenColor", default_green_color),
                              yellow_color=configuration.get("yellowColor", default_yellow_color),
                              build_filter_pattern=configuration.get("buildFilterPattern", None),
                              collector_filter_pattern=configuration.get("collectorFilterPattern", None))


class PlaybulbBuildAmpel(AbstractBuildAmpel):
    
    def __init__(self, device,
                 signal_error_threshold=default_signal_error_threshold,
                 color_reg=default_color_reg,
                 flash_reg=default_flash_reg,
                 flash=default_flash,
                 red_color=default_red_color,
                 green_color=default_green_color,
                 yellow_color=default_yellow_color,
                 build_filter_pattern=None,
                 collector_filter_pattern=None):

        super().__init__(signal_error_threshold=signal_error_threshold,
                         build_filter_pattern=build_filter_pattern,
                         collector_filter_pattern=collector_filter_pattern)
        self.playbulb = PlaybulbAmpel(device, color_reg, flash_reg, flash, red_color, green_color, yellow_color)

    def signal(self, red, yellow, green, flash=False):
        self.playbulb.display(red, yellow, green, flash)

    def close(self):
        super().close()


class PlaybulbAmpel():
    def __init__(self, device, color_reg, flash_reg, flash, red_color, green_color, yellow_color):
        self.device = device
        self.color_reg = color_reg
        self.flash_reg = flash_reg
        self.flash = flash
        self.red_color = red_color
        self.green_color = green_color
        self.yellow_color = yellow_color

    def display(self, red=False, yellow=False, green=False, flash=False):
        register = self.color_reg
        color = "00000000"

        if red:
            color = self.red_color
        if green:
            color = self.green_color
        if yellow:
            color = self.yellow_color

        if flash:
            register = self.flash_reg
            color += self.flash

        command = "gatttool -b %s --char-write -a %s -n %s" % (self.device, register, color)
        return self.__call_gatttool__(command)

    def __call_gatttool__(self, command):
        logger.debug(command)
        rc = os.system(command)
        if rc != 0:
            logger.warning("gattool returned %s", rc)
            return False
        return True


if __name__ == '__main__':
    """smoke test"""
    a = PlaybulbBuildAmpel(device='device_smoke')
    a.self_check()
