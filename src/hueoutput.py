# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'ursbeeli'

"""Output for philips hue lamps"""
"""
This implements the output for PHILIPS HUE Lamps.

PREREQUISITES:
  You must have an ip connection from your raspi to the hue bridge
  The easiest way to acomplish this is to connect the raspi and hue bridge to a router, serving as dhcp server using ethernet
  However, as the raspi should not use the dhcp of the router but only dhcp provided by the sbbfree wlan, a few adjustments
  need to be made

  1) Modify /etc/dhcpcd.conf by adding the following lines at the end

     interface eth0

     static ip_address=192.168.1.3 # adjust for your ip address
     static routers=192.168.1.1    # adjust for your router

  2) Create /lib/dhcpcd/dhcpcd-hhoks/40-route
     /sbin/route del -net 0.0.0.0 gw 192.168.1.1       # might need to be adjusted for your router
     /sbin/route add 192.168.1.0 gw 192.168.1.1 eth0   # might need to be adjusted for your router

  3) verify routes using "netstat -rn", there should only be one "default" entry on the wlan port

  4) Install the hue python library

     sudo pip3 install phue

  5) Create the initial connection to your hue bridge

     /opt/cimon/controller/hue-connect

     Then enter the hue bridge's ip address, press the "pairing button" on the bridge and then press enter.
     This will write the "hue api user key" into ~/.python_hue

CONFIGURATION:
  Create the following block in your cimon.yaml file

  - implementation: hueoutput
    ipaddress: '<ip-address of hue bridge>'
    lamps: [<list-of-ids for your lamps>]
    unused: [<list-of-ids of unused lamps (i.e. lamps contained in "lamps" but not mapped below>]
    mappings:
      '<arbitrary group name 1>':
        builds: ['<jenkins-job-id1>','<jenkins-job-id2>', ...]
        lamps: [<lamp-id1>]
      '<arbitrary group name 2>':
        builds: ['<jenkins-job-id3>']
        lamps: [<lamp-id2>,<lamp-id3>,...]

  Note that each job can only be assigned to one group. A group can consist of one or more jobs. Each group can have
  one or more lamps assigned, but each lamp can only be assigned to one job.
"""

import logging.config
import time
import re
from output import NameFilter

from phue import Bridge

from cimon import RequestStatus, Health

# hue lamp colours, determined by experimentation, not all of them are used
COLOUR_WHITE = {'on': True, 'sat': 0, 'bri': 63, 'hue': 0}
COLOUR_RED = {'on': True, 'sat': 254, 'bri': 127, 'hue': 0}
COLOUR_ORANGE = {'on': True, 'sat': 254, 'bri': 255, 'hue': 5500}
COLOUR_YELLOW = {'on': True, 'sat': 254, 'bri': 127, 'hue': 17500}
COLOUR_GREEN = {'on': True, 'sat': 254, 'bri': 127, 'hue': 25500}
COLOUR_LIGHT_BLUE = {'on': True, 'sat': 254, 'bri': 127, 'hue': 40000}
COLOUR_DARK_BLUE = {'on': True, 'sat': 254, 'bri': 127, 'hue': 47000}
COLOUR_BLUE_VIOLET = {'on': True, 'sat': 254, 'bri': 127, 'hue': 50000}
COLOUR_VIOLET = {'on': True, 'sat': 254, 'bri': 127, 'hue': 55000}
COLOUR_PINK = {'on': True, 'sat': 254, 'bri': 127, 'hue': 60000}
FLASHING = {
    'alert': 'lselect'}  # will flash the lamp between two brightnesses with the current colour, only lasts 15 seconds
LAMP_OFF = {"on": False, "transitiontime": 0}

logger = logging.getLogger(__name__)


def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    return HueOutput(ipaddress=configuration.get("ipaddress", None),
                     lamps=configuration.get("lamps", []),
                     unused=configuration.get("unused", []),
                     mappings=configuration.get("mappings", []))


class Mapping():
    def __init__(self, name, builds, job_name_pattern, collector_pattern, lamps):
        self.name = name
        self.builds = builds
        self.filter = NameFilter(job_name_pattern, collector_pattern)
        self.lamps = lamps

    def matches(self, url, job):
        return job in self.builds or self.filter.matches(url, job)

class HueOutput():
    def __init__(self, ipaddress, lamps, unused, mappings):
        self.ipaddress = ipaddress
        self.lamps = lamps
        self.unused = unused
        self.mappings = mappings
        self.mappings = self.createMappings(mappings)
        self.states = {}
        logger.debug("--- HueOutput.init() start ---")
        logger.debug(" - ipaddress: {}".format(ipaddress))
        logger.debug(" - lamps: {}".format(lamps))
        logger.debug(" - unused: {}".format(unused))
        logger.debug(" - mappings: {}".format(mappings))

        # initialise bridge connection
        self.bridge = Bridge(ipaddress)
        logger.debug("Connected to hue bridge")

        # turn off unused lamps, don't touch the others
        self.setLamps(unused, LAMP_OFF)
        logger.debug("Turned off unused lamps")
        logger.debug("--- HueOutput.init() done ---")

    def close(self):
        logger.debug("--- HueOutput.close() start ---")
        self.setLamps(self.lamps, LAMP_OFF)
        logger.debug("Turned off all lamps")
        logger.debug("--- HueOutput.close() done ---")

    """ maps jenkins job ids to mapping groups """

    def createMappings(self, configuredMappings):
        mappings = []
        for mappingName in configuredMappings:
            configuredMapping = configuredMappings[mappingName]
            mapping = Mapping(
                mappingName,
                configuredMapping["builds"] if "builds" in configuredMapping else [],
                configuredMapping["buildFilterPattern"] if "buildFilterPattern" in configuredMapping else None,
                configuredMapping["collectorFilterPattern"] if "collectorFilterPattern" in configuredMapping else None,
                configuredMapping["lamps"])
            mappings.append(mapping)
        return mappings

    """ sets the state for a list of lamps
        as the bridge can only handle a limited number of lamps (depending on the amount of "state" being sent)
        we will break down large lamp lists into lists of 6 lamps and then wait until the bridge has
        processed theses commands before sending the data for the next 6 lamps
    """

    def setLamps(self, lamps, state):
        if len(lamps) > 0:
            for i in range(0, len(lamps), 6):
                self.bridge.set_light(lamps[i:i + 6], state)
                time.sleep(0.5)

    """ handle the state of one single jenkinds build job
        this will also collate the "worst case" status if several jobs belong to one group
        the result will be written into the states dictionary for later output to the lamps
    """

    def treatBuild(self, url, job, jobStatus):
        mapping = self.mappingpForJob(url, job)
        if mapping:
            logger.debug("   - treating build: {}".format(job))
            logger.debug("     jobStatus: {}".format(jobStatus))
            logger.debug("     --> mapped build")
            status = jobStatus.request_status
            health = jobStatus.health
            active = jobStatus.active
            logger.debug("     request status: {}".format(status))
            logger.debug("     build health: {}".format(health))
            logger.debug("     build active: {}".format(active))
            builds = mapping["builds"]
            lamps = mapping["lamps"]
            logger.debug("     build belongs to mapping: {}".format(mapping.name))
            logger.debug("     mapping covers builds: {}".format(builds))
            logger.debug("     mapping controls lamps: {}".format(lamps))
            if mapping.name not in self.states:
                self.states[mapping.name] = {}
                self.states[mapping.name]["status"] = status
                self.states[mapping.name]["health"] = health
                self.states[mapping.name]["active"] = active
            # consolidate for "worst" value if multiple builds contribute to one group
            if status.value > self.states[mapping.name]["status"].value:
                self.states[mapping.name]["status"] = status
            if health.value > self.states[mapping.name]["health"].value:
                self.states[mapping.name]["health"] = health
            if active:
                self.states[mapping.name]["active"] = active

    def mappingpForJob(self, url, job):
        return next((mapping for mapping in self.mappings if mapping.matches(url, job)), None)

    """ determine lamp colour depending on request_status and health """
    def getColour(self, state):
        result = LAMP_OFF
        status = state["status"]
        health = state["health"]
        active = state["active"]
        if status == RequestStatus.ERROR:
            result = COLOUR_BLUE_VIOLET
        elif status == RequestStatus.NOT_FOUND:
            result = COLOUR_VIOLET
        elif status == RequestStatus.OK:
            if health == Health.HEALTHY:
                result = COLOUR_GREEN
            elif health == Health.UNWELL:
                result = COLOUR_YELLOW
            elif health == Health.SICK:
                result = COLOUR_RED
            elif health == Health.OTHER:
                result = COLOUR_LIGHT_BLUE
            elif health == Health.UNDEFINED:
                result = COLOUR_DARK_BLUE
            else:
                pass
        else:
            pass
        if active:
            result.update(FLASHING)
        return result

    """ iterate over the state of all groups and set the lamps accordingly """

    def updateLamps(self):
        treated = []
        logger.debug("   - lamps: {}".format(self.lamps))
        logger.debug("   - states: {}".format(self.states))
        for build in self.states:
            mapping = self.mappings[build]
            lamps = mapping["lamps"]
            logger.debug("   build: {}".format(build))
            state = self.states[build]
            logger.debug("   state: {}".format(state))
            logger.debug("   lamps: {}".format(lamps))
            colour = self.getColour(state)
            logger.debug("   colour: {}".format(colour))
            self.setLamps(lamps, colour)
            treated = treated + lamps
        untreated = [x for x in self.lamps if x not in self.unused and x not in treated]
        # logger.debug("   - set untreated lamps to white: {}".format(untreated))
        # self.setLamps(untreated, COLOUR_WHITE)
        logger.debug("   - set unused lamps off: {}".format(self.unused))
        self.setLamps(self.unused, LAMP_OFF)

    """ main method called by cimon.py when jenkins updates have been received """

    def on_update(self, status):
        """Display the given status.
        This information seems to no longer be correct:
        Status is a dict of status type, for instance { 'build' : {"<job_name_1>": {"request_status" : "error" | "not_found" | "ok", "result" : "failure" | "unstable" | "other" | "success"},
                                                                    "<job_name_2>": {...},
                                                                    ...}

        Instead, the following is delivered:
        Status is a dict of status type, for instance { ("<url>", "<job_name1>") : {"request_status" : <RequestStatus.OK: 1> | <RequestStatus.NOT_FOUND: 2> | <RequestStatus.ERROR: 3>,
                                                                                    "health" : <Healthy.HEALTHY: 1> | <Health.UNWELL: 2> | <Health:SICK: 3> | <Health.OTHER: 4> | <Health.UNDEFINED: 5>,
                                                                                    "active" : True | False,
                                                                                    ... },
                                                        ("<url>", "<job_name2>") : {...}
                                                       }
        """
        logger.debug("--- HueOutput.onUpdate start ---")
        logger.debug("- status contains {} entries".format(len(status)))
        self.states = {}
        items = status.items()
        logger.debug("-> Evaluating Jobs")
        for key, value in items:
            url = key[0]
            job = key[1]
            self.treatBuild(url, job, value)
        logger.debug("-> Updating Lamps")
        self.updateLamps()
        logger.debug("--- HueOutput.onUpdate done ---")
        logger.debug()
        pass


if __name__ == '__main__':
    HueOutput().on_update({})
