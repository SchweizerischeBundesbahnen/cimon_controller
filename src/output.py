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

# Abstract base classes for outputs
class AbstractBuildOutput():
    """ Output for builds with error handling. Derived methods have to implement signal and on_status and set the last_signal after signaling non-error state """
    def __init__(self, signal_error_threshold=default_signal_error_threshold):
        self.signal_error_threshold=signal_error_threshold
        self.error_count=0
        self.last_signal=None

    def on_update(self, status):
        if "build" not in status:
            logging.debug("No build status found in given status, ignoring %s", status)
        elif has_request_status(status, "error"):
            self.on_eror(status)
            self.error_count+=1
        else:
            self.error_count=0
            self.on_status(status)

    def on_eror(self, status):
        # if there is at least one build in error
        # tolerate signal_error_threshold errors, then
        # signal by all lights on
        if self.error_count < self.signal_error_threshold and self.last_signal:
            logging.debug("Tolerating error and signaling previous state, count is %d", self.error_count)
            self.last_signal()
        else:
            logging.debug("Signaling an error")
            self.signal_error()

    def on_status(self, status):
        # if there is at least one build failed, signal red
        if has_result(status, "failure"):
            logging.debug("Signaling failure")
            self.signal_failure()
            self.last_signal = self.signal_failure
        # if there is at least one build unstable in undefied state or not found, signal yellow
        elif has_result(status, "unstable"):
            logging.debug("Signaling unstable")
            self.signal_unstable()
            self.last_signal = self.signal_unstable
        # if at least one in undefied state or not found, signal yellow
        elif has_result(status, "other"):
            logging.debug("Signaling other")
            self.signal_other()
            self.last_signal = self.signal_other
            # elseif at least one build has success, all is OK, signal green
        # this include request_status == "ok" and result == "successs"
        # as well as   request_status == "not_found"
        # but only if at least one build had request_status == "ok" and result == "success"
        elif has_result(status, "success"):
            logging.debug("Signaling success")
            self.signal_success()
            self.last_signal = self.signal_success
        # if all builds are request_status == "not_found", signal nothing
        elif self.last_signal:
            logging.debug("No build found, repeating last stored signal")
            self.last_signal()
        else:
            logging.info("No build found, no signal")

    def reset(self):
        logging.debug("Reset called, switching off")
        self.signal_off()
        self.last_signal = None
        self.error_count = 0

    def self_check(self):
        logging.info("Self check initiated...")
        self.reset()
        self.signal_success()
        sleep(1)
        self.signal_unstable()
        sleep(1)
        self.signal_other()
        sleep(1)
        self.signal_failure()
        sleep(1)
        self.signal_error()
        sleep(1)
        self.signal_off()
        logging.info("Self check complete")


class AbstractBuildAmpel(AbstractBuildOutput):
    """base class for ampel kind output. ampel has to implement the signal method """

    def signal_error(self):
        self.signal(red=True, yellow=True, green=True)

    def signal_success(self):
        self.signal(red=False, yellow=False, green=True)

    def signal_unstable(self):
        self.signal(red=False, yellow=True, green=False)

    def signal_other(self):
        self.signal(red=False, yellow=True, green=False)

    def signal_failure(self):
        self.signal(red=True, yellow=False, green=False)

    def signal_off(self):
        self.signal(red=False, yellow=False, green=False)

