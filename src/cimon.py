# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

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
from copy import deepcopy

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

logger = logging.getLogger(__name__)

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

    def close(self):
        for target in self.outputs + self.collectors:
            if hasattr(target, "close"):
                target.close()

    def start(self):
        logger.info("Starting cimon...")
        self.rescheduler = ReScheduler(self.run, self.polling_interval_sec)
        self.rescheduler.start()
        logger.debug("Started cimon")

    def stop(self,**kwargs): # has to accept extra params from signal (signal and frame)
        if self.rescheduler:
            logger.debug("Stopping cimon...")
            self.rescheduler.stop()
            self.rescheduler = None
            self.close()
        logger.info("Stopped cimon")

    def run(self):
        if self.is_operating(datetime.now()):
            self.collect_and_output()
        else:
            logging.info("Outside operating hours, switching off and waiting for operating hours")
            self.close() # reset all output before waiting
            sec_to_next_operating = self.sec_to_next_operating(datetime.now())
            logging.info("Waiting for %d seconds", sec_to_next_operating)
            return max(sec_to_next_operating, 60) # make sure to wait at least a minute

    def is_operating(self, now):
        # check the current hour is configured
        # if the list is empty the function is disabled, we assume each day/hour is operating time
        return (not self.operating_hours or now.hour in self.operating_hours) and \
               (not self.operating_days or now.weekday() in self.operating_days)

    def collect_and_output(self):
        logger.debug("Running collection")
        # first collect the current status
        status = {}
        for collector in self.collectors:
            status[collector.type] = status[collector.type] if collector.type in status else {}
            status[collector.type].update(collector.collect())
        logger.debug("Collected status: %s", status)
        # then display the current status
        for output in self.outputs:
            output.on_update(deepcopy(status))
        logger.info("Collected status and updated outputs")

    def sec_to_next_operating(self, now):
        next_operating_hour = self.__find_same_or_next_day_or_hour__(self.operating_hours, now.hour)
        if next_operating_hour >= now.hour and (not self.operating_days or now.weekday() in self.operating_days):
            # some time today - distance to next operating hour (if operating hour is now return 0 since no distance)
            return int((datetime.combine(now.date(), time(hour=next_operating_hour)) - now).total_seconds()) if next_operating_hour > now.hour else 0
        else:
            # some other day - search next operating day and calculate distance to first operating hour that day
            next_operating_day = self.__find_same_or_next_day_or_hour__(self.operating_days, now.weekday() + 1)
            distance_to_next_operating_day = next_operating_day - now.weekday() if next_operating_day >= now.weekday() else next_operating_day + 7 - now.weekday()
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

def read_yaml_file(file):
    # read the yaml config file
    with open(file, "r") as f:
        cfg = yaml.load(f)
    return cfg

def read_key_file(keypath):
    # read the secret key on the device
    if keypath and os.path.isfile(keypath):
        with open(keypath, "rb") as k:
            return k.read()

def configure_from_yaml_file(file, keypath=None, dry_run=False):
    print("Configuring cimon from yaml file: " + file)
    return configure_from_dict(read_yaml_file(file), read_key_file(keypath))

def configure_from_dict(configuration, key):
    try:
        __configure_logging__(configuration)
        polling_interval_sec = int(configuration["pollingIntervalSec"])
        if not configuration["collector"]:
            raise ValueError("No collectors configured")
        collectors=tuple(__configure_dynamic__(configuration["collector"], key))
        __check_all_implement_method__(collectors, "collect")
        if not configuration["output"]:
            raise ValueError("No outputs configured")
        outputs=tuple(__configure_dynamic__(configuration["output"], key))
        __check_all_implement_method__(outputs, "on_update")
        operating_hours = __parse_hours_or_days__(configuration.get("operatingHours", "*"), "0-23")
        operating_days = __parse_hours_or_days__(configuration.get("operatingDays", "*"), "0-6")
        logger.info("Read configuration: %s", configuration)
        return Cimon(polling_interval_sec = polling_interval_sec,
                     collectors = collectors,
                     outputs=outputs,
                     operating_hours=operating_hours,
                     operating_days=operating_days)
    except Exception:
        logger.exception("Configuration failed, invalid configuration: %s", configuration)
        raise

def __configure_logging__(configuration):
    try:
        if "logging" in configuration:
            logging_cfg = configuration["logging"]
            logging_cfg["disable_existing_loggers"] = False # required in order to configure loggers at module level
            logging.config.dictConfig(logging_cfg)
        else:
            logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    except: # default config: log all to console
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger.exception("Configuration of logging failed, using default configuration")

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

def __check_all_implement_method__(objects, method_name):
    for object in objects:
        if not hasattr(object, method_name):
            raise AttributeError("%s does not implmement the method '%s', maybe did API is not correctly implemented or confused collector and output?" % (object, method_name))

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

def __start__(masterboxcontrolprogram):
    # register for proper exit
    atexit.register(masterboxcontrolprogram.stop) # listens to SIGINT, also works on windows....
    if hasattr(signal, "SIGHUP"): # linux only
        signal.signal(signal.SIGHUP, masterboxcontrolprogram.stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, masterboxcontrolprogram.stop)
    # now start
    masterboxcontrolprogram.start()

def __validate_config__(configfilepath, keypath):
    cfg = read_yaml_file(configfilepath)
    cfg.pop("logging", None) # do not use logging
    configure_from_dict(cfg, read_key_file(keypath))

if  __name__ =='__main__':
    """the actual start of the cimon masterboxcontrolprogram"""
    # config file location may be provided via command line arg
    parser = ArgumentParser(description="Run the cimon masterboxcontrolprogram")
    parser.add_argument("-c",  "--config", help="The cimon yaml config file with its path")
    parser.add_argument("-k",  "--key", help="The password key file with its path")
    parser.add_argument("--validate", action="store_true", help="Just validate the config file, do not run cimoon")
    args = parser.parse_args()
    # read yaml config file (mandatory)
    configfilepath = args.config or find_config_file_path("cimon.yaml")
    keypath = args.key or find_config_file_path("key.bin", True)
    if args.validate:
        __validate_config__(configfilepath, keypath)
        sys.exit(0) # just validate the config, do not start. If an exception was raised it will exit with 1
    else:
        __start__(configure_from_yaml_file(configfilepath, keypath))
