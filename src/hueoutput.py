# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'ursbeeli'

"""Output for philips hue lamps"""
"""
TODO: config options with example
"""

from cimon import RequestStatus,Health
from output import has_request_status,has_health,is_building
from phue import Bridge
import time

STATE_SUCCESS = "success"
STATE_FAILURE = "failure"
STATE_UNSTABLE = "unstable"
STATE_OTHER = "other"
STATE_ERROR = "error"
STATE_OK = "ok"
STATE_NOT_FOUND = "not_found"

COLOR_RED         = {'on':True, 'sat': 254, 'bri': 127, 'hue': 0}
COLOR_ORANGE      = {'on':True, 'sat': 254, 'bri': 255, 'hue': 5500}
COLOR_YELLOW      = {'on':True, 'sat': 254, 'bri': 127, 'hue': 12500}
COLOR_GREEN       = {'on':True, 'sat': 254, 'bri': 127, 'hue': 25500}
COLOR_LIGHT_BLUE  = {'on':True, 'sat': 254, 'bri': 127, 'hue': 40000}
COLOR_DARK_BLUE   = {'on':True, 'sat': 254, 'bri': 127, 'hue': 47000}
COLOR_BLUE_VIOLET = {'on':True, 'sat': 254, 'bri': 127, 'hue': 49000}
COLOR_VIOLET      = {'on':True, 'sat': 254, 'bri': 127, 'hue': 55000}
COLOR_PINK        = {'on':True, 'sat': 254, 'bri': 127, 'hue': 60000}

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    return HueOutput(ipaddress=configuration.get("ipaddress", None),
                    lamps=configuration.get("lamps", []),
                    mappings=configuration.get("mappings", []))

class HueOutput():
    def __init__(self, ipaddress, lamps, mappings):
        self.ipaddress = ipaddress
        self.lamps = lamps
        self.mappings = mappings
        self.groups = self.createGroupsFromMappings(mappings)
        self.states = {}
        print("--- HueOutput.init() ---")
        print(" - ipaddress: {}".format(ipaddress))
        print(" - lamps: {}".format(lamps))
        print(" - mappings: {}".format(mappings))
        print(" - groups: {}".format(self.groups))

        # initialise bridge connection
        self.bridge = Bridge(ipaddress)

        # turn off all lamps
        self.bridge.set_light(lamps, 'on', False)
        self.hue = 0

    def createGroupsFromMappings(self, mappings):
        groups = {}
        for key in mappings:
            mapping = mappings[key]
            builds = mapping["builds"]
            for b in builds:
               groups[b] = key
        return groups

    def getWorstOf(state1, state2):
       if state1 == STATE_ERROR or state2 == STATE_ERROR:
          return STATE_ERROR
       elif state1 == STATE_NOT_FOUND or state2 == STATE_NOT_FOUND:
          return STATE_NOT_FOUND
       elif state1 == STATE_OK:
          return state2
       elif state2 == STATE_OK:
          return state1
       elif state1 == STATE_OTHER or state2 == STATE_OTHER: # assuming this means "building"
          return STATE_OTHER
       elif state1 == STATE_FAILURE or state2 == STATE_FAILURE:
          return STATE_FAILURE
       elif state1 == STATE_UNSTABLE or state2 == STATE_UNSTABLE:
          return STATE_UNSTABLE
       elif state1 == STATE_SUCCESS:
          return state2
       elif state2 == STATE_SUCCESS:
          return state1
       else:
          return state2

    def treatBuild(self, buildName, buildInfo):
       print("   - treating build: {}".format(buildName))
       if buildName in self.groups:
          status = buildInfo["request_status"]
          result = buildInfo["result"]
          mappingName = self.groups[buildName]
          mapping = self.mappings[mappingName]
          builds = mapping["builds"]
          lamps = mapping["lamps"]
          print("     request status: {}".format(status))
          print("     build result: {}".format(result))
          print("     build belongs to mapping: {}".format(mappingName))
          print("     mapping covers builds: {}".format(builds))
          print("     mapping controls lamps: {}".format(lamps))
          if mappingName not in self.states:
             self.states[mappingName] = STATE_SUCCESS
          print("     state before merge: {}".format(self.states[mappingName]))
          self.states[mappingName] = getWorstOf(status, self.states[mappingName])
          self.states[mappingName] = getWorstOf(result, self.states[mappingName])
          print("     state after merge: {}".format(self.states[mappingName]))
       else:
          print("     --> not interested")

    def on_update(self, status):
        """Display the given status.
        Status is a dict of status type, for instance { 'build' : {"<job_name_1>": {"request_status" : "error" | "not_found" | "ok", "result" : "failure" | "unstable" | "other" | "success"},
                                                                    "<job_name_2>": {...},
                                                                    ...}
                                                       }
        """
        print("--- HueOutput.onUpdate ---")
        print(" - status: {}".format(status))
        print(" - mappings: {}".format(self.mappings))
        print(" - groups: {}".format(self.groups))
        print(" - lamps: {}".format(self.lamps))
        self.states = {}
        if "build" in status:
           builds = status["build"]
           for build in builds:
              treatBuild(self, build, builds[build])
        else:
           print("   no build information in status")
        print("   Done")
        print()
        pass

if  __name__ =='__main__':
    HueOutput().on_update({})

