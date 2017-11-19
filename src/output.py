# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from time import sleep
import logging
import re
from cimon import RequestStatus,Health

default_signal_error_threshold=3

logger = logging.getLogger(__name__)

# Generic Logic for any kind of build output and traffic light like signaling device output.
#
# AbstractBuildOutput: Generic Outupt for build result.
# Has to be extended, derived clas seeds to implement the methods:
#   - signal_error if an error occured (server not available,..)
#   - signal_health: if there is a result
#   - signal_off: if the device is to be turned off
#
# AbstractBuildAmpel: Ampel-like device (red, yellow, green signal)
# Has to be extended, derived clas seeds to implement the methods:
#   def signal(self, red, yellow, green):
#  parameters are boolean, if True the light  has to be switchend on, if false it has to be switched off
#
# Does currently only evaluate build output. Will
#   - signal red if at least one build failed
#   - signal yellow if at least one build is unstable or in any other status except failed and success or a job has no build or is not found
#   - signal green if at all buids are successfull
#   - signal all lights on if there is an error and (error_threshold is exceeded or there is no previous signal)
#
# Methods to handle the build status
def has_request_status(status, req_status):
    for name in status:
        if status[name].request_status == req_status:
            return True
    return False

def has_health(status, health):
    for name in status:        
        if status[name].request_status == RequestStatus.OK and \
           status[name].health == health:
            return True
    return False

def is_building(status):
    for name in status:
        if status[name].request_status == RequestStatus.OK and \
           status[name].active:
            return True
    return False

class NameFilter():

    def __init__(self, job_name_pattern=None, collector_pattern=None):
        self.job_name_pattern = re.compile(job_name_pattern) if job_name_pattern else None
        self.collector_pattern = re.compile(collector_pattern) if collector_pattern else None

    def filter_status(self, status):
        filtered = status
        if self.collector_pattern:
           filtered = self.filter_by_pattern(filtered, self.collector_pattern, 0)
        if self.job_name_pattern:
            filtered = self.filter_by_pattern(filtered, self.job_name_pattern, 1)
        return filtered

    def filter_by_pattern(self, status, pattern, index):
        return {k: v for k, v in status.items() if pattern.match(k[index])}

# Abstract base classes for outputs
class AbstractBuildOutput():
    """ Output for builds with error handling. Derived methods have to implement signal and on_status and set the last_signal after signaling non-error state """
    def __init__(self, signal_error_threshold=default_signal_error_threshold, build_filter_pattern=None, collector_filter_pattern=None):
        self.signal_error_threshold=signal_error_threshold
        self.build_filter = NameFilter(collector_pattern=collector_filter_pattern,job_name_pattern=build_filter_pattern)
        self.error_count=0
        self.last_status=None

    def on_update(self, status):
        self.on_update_filtered(self.build_filter.filter_status(status))

    def on_update_filtered(self, status):
        if has_request_status(status, RequestStatus.ERROR):
            self.on_error(status)
            self.error_count+=1
        else:
            self.error_count=0
            self.on_status(status)

    def on_error(self, status):
        # if there is at least one build in error
        # tolerate signal_error_threshold errors, then
        # signal by all lights on
        if self.error_count < self.signal_error_threshold and self.last_status:
            logger.debug("Tolerating error and signaling previous state, count is %d", self.error_count)
            self.signal_health(*self.last_status)
        else:
            logger.debug("Signaling an error")
            self.signal_error()

    def on_status(self, status):
        building = is_building((status))
        # if there is at least one build failed, signal red
        if has_health(status, Health.SICK):
            self.__signal_health_and_store__(Health.SICK, building)
            # if there is at least one build unstable in undefied state or not found, signal yellow
        elif has_health(status, Health.UNWELL):
            self.__signal_health_and_store__(Health.UNWELL, building)
        # if at least one in undefied state or not found, signal yellow
        elif has_health(status, Health.OTHER):
            self.__signal_health_and_store__(Health.OTHER, building)
        # elseif at least one build has success, all is OK, signal green
        # this include request_status == "ok" and result == "successs"
        # as well as   request_status == "not_found"
        # but only if at least one build had request_status == "ok" and result == "success"
        elif has_health(status, Health.HEALTHY):
            self.__signal_health_and_store__(Health.HEALTHY, building)
        # if all builds are request_status MOT_FOUND or result EMPTY, signal nothing
        elif self.last_status:
            logger.debug("No build found, repeating last stored signal")
            self.signal_health(*self.last_status)
        else:
            logger.info("No build found, no signal")

    def __signal_health_and_store__(self, result, building):
        logger.debug("Signaling %s, building=%s", result, building)
        self.signal_health(result=result, building=building)
        self.last_status = (result, building)

    def close(self):
        logger.info("Switching off")
        self.signal_off()
        self.last_status = None
        self.error_count = 0

    def self_check(self):
        logger.info("Self check initiated...")
        self.signal_health(result=Health.HEALTHY, building=False)
        sleep(1)
        self.signal_health(result=Health.HEALTHY, building=True)
        sleep(1)
        self.signal_health(result=Health.UNWELL, building=False)
        sleep(1)
        self.signal_health(result=Health.UNWELL, building=True)
        sleep(1)
        self.signal_health(result=Health.OTHER, building=False)
        sleep(1)
        self.signal_health(result=Health.OTHER, building=True)
        sleep(1)
        self.signal_health(result=Health.SICK, building=False)
        sleep(1)
        self.signal_health(result=Health.SICK, building=True)
        sleep(1)
        self.signal_error()
        sleep(1)
        self.signal_off()
        self.close()
        logger.info("Self check complete")

class AbstractBuildAmpel(AbstractBuildOutput):
    """base class for ampel kind output. ampel has to implement the signal method """

    def signal_health(self, result, building=False):
        if(result == Health.HEALTHY):
            self.signal(red=False, yellow=False, green=True, flash=building)
        elif(result == Health.UNWELL):
            self.signal(red=False, yellow=True, green=False, flash=building)
        elif(result == Health.SICK):
            self.signal(red=True, yellow=False, green=False, flash=building)
        else: # Health.OTHER or Health.EMPTY
            self.signal(red=False, yellow=True, green=False, flash=building)

    def signal_error(self):
        self.signal(red=True, yellow=True, green=True, flash=False)

    def signal_off(self):
        self.signal(red=False, yellow=False, green=False, flash=False)
