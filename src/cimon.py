# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'u206123'

from rescheduler import ReScheduler
from configutil import find_config_file_path
import atexit
import logging
import logging.config
import sys
import os
import yaml
import signal
from datetime import datetime, timedelta, time
from argparse import ArgumentParser

# The Masterboxcontrolprogram of the ci monitor scripts.
#
# Will schedule a run ever polling_interval_sec seconds:
# - first collect all configured collectors
# - then output to all outputs
#
# In order to add a controller or output, add a python module (file) implementing the method
#   def create(configuration):
#       return MyCollectorOrOutputInstance()
#
# Any implementation of a Collector needs to implement the method
#   def collect(self): # collect
#       return current_status_as_collected_in_a_dict
# and the field
#   type = "foo" # the type of collection, for instance type = "build"
#
# Any implementations of an Output has to implement the method
#   def on_update(self, status):
#       display the status
#       the status is a dict of different status, for instance "build"
#       the format of that status inside is determined by the collector
# and can implement the method (optional):
#   def reset(self):
#       reset_the_output_here_if_required

# append the user home directory to sys.path
sys.path.append("%s/cimon/plugins" % os.path.expanduser("~"))

class Cimon():
    """ Start and configuration of the build monitor """

    def __init__(self,
                 polling_interval_sec=0,
                 collectors=tuple(),
                 outputs=tuple(),
                 operating_hours=tuple(range(0,24)),
                 operating_days=tuple(range(0,7))):
        self.rescheduler = None
        self.polling_interval_sec=int(polling_interval_sec)
        self.collectors=collectors
        self.outputs=outputs
        self.operating_hours=sorted(operating_hours)
        self.operating_days=sorted(operating_days)

    def reset(self):
        for output in self.outputs:
            if hasattr(output, "reset"):
                output.reset()

    def start(self):
        logging.info("Starting cimon...")
        self.rescheduler = ReScheduler(self.run, self.polling_interval_sec)
        self.reset()
        self.rescheduler.start()
        logging.debug("Started cimon")

    def stop(self,**kwargs): # has to accept extra params from signal (signal and frame)
        if self.rescheduler:
            logging.debug("Stopping cimon...")
            self.rescheduler.stop()
            self.rescheduler = None
            self.reset()
        logging.info("Stopped cimon")

    def run(self):
        if self.is_operating(datetime.now()):
            self.collect_and_output()
        else:
            self.reset() # reset all output before waiting
            return self.sec_to_next_operating(datetime.now())

    def is_operating(self, now):
        # check the current hour is configured
        # if the list is empty the function is disabled, we assume each day/hour is operating time
        return (not self.operating_hours or now.hour in self.operating_hours) and \
               (not self.operating_days or now.weekday() in self.operating_days)

    def collect_and_output(self):
        logging.debug("Running collection")
        # first collect the current status
        status = {}
        for collector in self.collectors:
            status[collector.type] = collector.collect()
        logging.debug("Collected status: %s", status)
        # then display the current status
        for output in self.outputs:
            output.on_update(status)
        logging.info("Collected status and updated outputs")

    def sec_to_next_operating(self, now):
        next_operating_hour = self.__find_same_or_next_day_or_hour__(self.operating_hours, now.hour)
        if next_operating_hour >= now.hour and (not self.operating_days or now.weekday() in self.operating_days):
            # some time today - distance to next operating hour (if operating hour is now return 0 since no distance)
            return int((datetime.combine(now.date(), time(hour=next_operating_hour)) - now).total_seconds()) if next_operating_hour > now.hour else 0
        else:
            # some other day - search next operating day and calculate distance to first operating hour that day
            next_operating_day = self.__find_same_or_next_day_or_hour__(self.operating_days, now.weekday() + 1)
            distance_to_next_operating_day = next_operating_day - now.weekday() if next_operating_day >= now.weekday() else next_operating_day + 6 - now.weekday()
            # absolute date next operating is at the next operating day
            next_operating_date = (now + timedelta(days=distance_to_next_operating_day)).date()
            next_operating = datetime.combine(next_operating_date, time(hour=self.__find_same_or_next_day_or_hour__(self.operating_hours, 0)))
            return int((next_operating - now).total_seconds())

    def __find_same_or_next_day_or_hour__(self, operating_days_or_hours, current_day_or_hour):
        # find the current day/hour or then next day/hour after
        # if the list is empty the function is disabled, we assume each day/hour is operating time
        for day_or_hour in operating_days_or_hours:
            if day_or_hour >= current_day_or_hour:
                return day_or_hour
        # may roll over - now use the first day/hour in the list
        return operating_days_or_hours[0] if operating_days_or_hours else current_day_or_hour

def configure_from_yaml_file(file, keypath=None):
    print("Configuring cimon from yaml file: " + file)
    # read the yaml config file
    with open(file, "r") as f:
        cfg = yaml.load(f)
    # read the secret key on the device
    if keypath and os.path.isfile(keypath):
        with open(keypath, "rb") as k:
            key = k.read()
    else:
        key = None
    return configure_from_dict(cfg, key)

def configure_from_dict(configuration, key=None):
    try:
        logging.config.dictConfig(configuration["logging"])
    except: # default config: log all to console
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logging.exception("Configuration of logging failed, using default configuration")
    polling_interval_sec = int(configuration["pollingIntervalSec"])
    collectors=tuple(__configure_dynamic__(configuration["collector"], key))
    outputs=tuple(__configure_dynamic__(configuration["output"], key))
    operating_hours = __parse_hours_or_days__(configuration.get("operatingHours", "*"), "0-23")
    operating_days = __parse_hours_or_days__(configuration.get("operatingDays", "*"), "0-6")
    logging.info("Read configuration: %s", configuration)
    return Cimon(polling_interval_sec = polling_interval_sec,
                 collectors = collectors,
                 outputs=outputs,
                 operating_hours=operating_hours,
                 operating_days=operating_days)

def __configure_dynamic__(config, key=None):
    # a tiny bit of hand-made logic to allow dynamic addition of collecrs and output
    # will read the implementation from the yaml, then load "<implmementation>.py"
    # and then call the create(configuration) method that has to exist in each
    # output or collector
    objects = []
    for element_config in config:
        # load the module...
        module =__import__(element_config["implementation"])
        objects.append(module.create(element_config, key))
    return objects

def __parse_hours_or_days__(periodstring, default):
    if type(periodstring) is int:
        return (int(periodstring),)
    elif periodstring and not "*" in periodstring:
        result = []
        periods = periodstring.split(",")
        for period in periods:
            if "-" in period:
                fromTo = period.split("-")
                values = tuple(range(int(fromTo[0]), int(fromTo[1]) + 1)) if len(fromTo) == 2 else None
                if not values: # not 2 elements in range (1-2-3,...) or inverse (22-3) and so on
                    raise ValueError("Invalid range %s" % (period))
                result.extend(values)
            else:
                result.append(int(period))
        return tuple(set(result))
    elif default:
        return __parse_hours_or_days__(default, None)

if  __name__ =='__main__':
    """the actual start of the cimon masterboxcontrolprogram"""
    # config file location may be provided via command line arg
    parser = ArgumentParser(description="Run the cimon masterboxcontrolprogram")
    parser.add_argument("-c",  "--config", help="The cimon yaml config file with its path")
    parser.add_argument("-k",  "--key", help="The password key file with its path")
    args = parser.parse_args()
    # read yaml config file (mandatory)
    configfilepath = args.config or find_config_file_path("cimon.yaml")
    keypath = args.key or find_config_file_path("key.bin", True)
    masterboxcontrolprogram = configure_from_yaml_file(configfilepath, keypath)
    # register for proper exit
    atexit.register(masterboxcontrolprogram.stop) # listens to SIGINT, also works on windows....
    if hasattr(signal, "SIGHUP"): # linux only
        signal.signal(signal.SIGHUP, masterboxcontrolprogram.stop)
    if hasattr(signal, "SIGTERM"): # linux only
        signal.signal(signal.SIGTERM, masterboxcontrolprogram.stop)
    # now start
    masterboxcontrolprogram.start()



