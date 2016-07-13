# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from time import sleep
import logging

default_signal_error_threshold=3

# Generic Logic for any kind of build output and traffic light like signaling device output.
#
# AbstractBuildOutput: Generic Outupt for build result.
# Has to be extended, derived clas seeds to implement the methods:
#   - signal_error if an error occured (server not available,..)
#   - signal_success if all builds are green
#   - signal_unstable if at least one build is unstable
#   - signal_other: if at least one build is in an other state
#   - signal_failure: if at least one build is in failed state
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
    builds = status["build"]
    for build in builds:
        if builds[build]["request_status"] == req_status:
            return True
    return False

def has_result(status, result):
    builds = status["build"]
    for build in builds:
        if builds[build]["request_status"] == "ok" and \
                        builds[build]["result"] == result:
            return True
    return False

def is_building(status):
    builds = status["build"]
    for build in builds:
        if builds[build]["request_status"] == "ok" and \
                "building" in builds[build] and \
                builds[build]["building"]:
            return True
    return False

# Abstract base classes for outputs
class AbstractBuildOutput():
    """ Output for builds with error handling. Derived methods have to implement signal and on_status and set the last_signal after signaling non-error state """
    def __init__(self, signal_error_threshold=default_signal_error_threshold):
        self.signal_error_threshold=signal_error_threshold
        self.error_count=0
        self.last_status=None

    def on_update(self, status):
        if "build" not in status:
            logging.debug("No build status found in given status, ignoring %s", status)
        elif has_request_status(status, "error"):
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
            logging.debug("Tolerating error and signaling previous state, count is %d", self.error_count)
            self.signal_status(*self.last_status)
        else:
            logging.debug("Signaling an error")
            self.signal_error()

    def on_status(self, status):
        building = is_building((status))
        # if there is at least one build failed, signal red
        if has_result(status, "failure"):
            self.__signal_status_and_store__("failure", building)
            # if there is at least one build unstable in undefied state or not found, signal yellow
        elif has_result(status, "unstable"):
            self.__signal_status_and_store__("unstable", building)
        # if at least one in undefied state or not found, signal yellow
        elif has_result(status, "other"):
            self.__signal_status_and_store__("other", building)
        # elseif at least one build has success, all is OK, signal green
        # this include request_status == "ok" and result == "successs"
        # as well as   request_status == "not_found"
        # but only if at least one build had request_status == "ok" and result == "success"
        elif has_result(status, "success"):
            self.__signal_status_and_store__("success", building)
        # if all builds are request_status == "not_found", signal nothing
        elif self.last_status:
            logging.debug("No build found, repeating last stored signal")
            self.signal_status(*self.last_status)
        else:
            logging.info("No build found, no signal")

    def __signal_status_and_store__(self, status, building):
        logging.debug("Signaling %s, building=%s", status, building)
        self.signal_status(status=status, building=building)
        self.last_status = (status, building)

    def close(self):
        logging.debug("Switching off")
        self.signal_off()
        self.last_status = None
        self.error_count = 0

    def self_check(self):
        logging.info("Self check initiated...")
        self.signal_status(status="success", building=False)
        sleep(1)
        self.signal_status(status="success", building=True)
        sleep(1)
        self.signal_status(status="unstable", building=False)
        sleep(1)
        self.signal_status(status="unstable", building=True)
        sleep(1)
        self.signal_status(status="other", building=False)
        sleep(1)
        self.signal_status(status="other", building=True)
        sleep(1)
        self.signal_status(status="failure", building=False)
        sleep(1)
        self.signal_status(status="failure", building=True)
        sleep(1)
        self.signal_error()
        sleep(1)
        self.signal_off()
        self.close()
        logging.info("Self check complete")


class AbstractBuildAmpel(AbstractBuildOutput):
    """base class for ampel kind output. ampel has to implement the signal method """

    def signal_status(self, status, building=False):
        if(status == "success"):
            self.signal(red=False, yellow=False, green=True, flash=building)
        elif(status == "unstable"):
            self.signal(red=False, yellow=True, green=False, flash=building)
        elif(status == "failure"):
            self.signal(red=True, yellow=False, green=False, flash=building)
        else: # status == "other"
            self.signal(red=False, yellow=True, green=False, flash=building)

    def signal_error(self):
        self.signal(red=True, yellow=True, green=True, flash=False)

    def signal_off(self):
        self.signal(red=False, yellow=False, green=False, flash=False)

