# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from urllib.request import urlopen, HTTPError, Request, URLError
from datetime import datetime
from concurrent import futures
import json
import logging
import sys
from collector import HttpClient, create_http_client
from configutil import decrypt
from cimon import Health,RequestStatus,JobStatus
from urllib.parse import urlparse
import re

# Collect the status from new relic.
# will collect the status of the monitoring
#
# is collector type "monitoring" (only one collector of each type is allowed)
#
# returns a dict per application (name in new relic) and containing another dict of the actual buid_status
# the "request_status" allways has to be checked first, only if it is "ok" the further values are contained
# { <job_name_as_string> : {
#       "request_status" : "ok" | "error" ,
#       "result" : "success" | "unstable" | "failure" | "other", # only if status["request_status"] == "ok"
#       "number" : <build_number_within_job_as_integer>, # only if status["request_status"] == "ok"
#       "timestamp" :
# }
default_update_applications_every = 50

logger = logging.getLogger(__name__)

def create(configuration, key=None):
    return NewRelicCollector(base_url = configuration["url"],
                             api_key = configuration.get("apiKey", None) or decrypt(configuration.get("apiKeyEncyrpted", None), key),
                             application_name_pattern= configuration.get("applicationNamePattern", r'.*'),
                             refresh_applications_every=configuration.get("refreshApplicationsEvery",default_update_applications_every), # times
                             name = configuration.get("name", None),
                             verify_ssl=configuration.get("verifySsl", True))

class NewRelicCollector:

    # extract result and building state from the colors in the view
    health_status_to_cimon_health = {
                            "red" : Health.SICK,
                            "orange" : Health.UNWELL,
                            "yellow " : Health.UNWELL,
                            "green" : Health.HEALTHY,
                            "gray": Health.UNDEFINED,
                            "unknown" : Health.UNDEFINED}
    def __init__(self,
                 base_url,
                 api_key,
                 application_name_pattern=r'.*',
                 refresh_applications_every=default_update_applications_every,
                 name=None,
                 verify_ssl=True):
        self.new_relic_client = NewRelicClient(
            http_client=create_http_client(base_url=base_url,fixed_headers={'X-Api-Key':api_key},verify_ssl=verify_ssl),
            application_name_pattern=application_name_pattern,
            refresh_applications_every=refresh_applications_every)
        self.name = name if name else urlparse(base_url).netloc

    def collect(self):
        status=self.__collect_health__()
        logger.debug("Health status collected: %s", status)
        return status

    def __collect_health__(self):
        try:
            return {(self.name, app_name) : self.__to_job_status__(app_health) for app_name, app_health in self.new_relic_client.applications_health().items()}
        except HTTPError as e:
            # ignore...
            if(e.code == 404): # not found - its OK lets not crash
                logger.warning("No applications found in new relic: : %s" % e.msg)
                return {(self.name,"all") : JobStatus(RequestStatus.NOT_FOUND)}
            else:
                logger.exception("HTTP Error requesting status for job: %s" % e.msg)
                return {(self.name,"all") : JobStatus(RequestStatus.ERROR)}
        except URLError as e:
            logger.exception("URL Error requesting status for job %s" % e)
            return {(self.name,"all") : JobStatus(RequestStatus.ERROR)}

    def __to_job_status__(self, app_health):
        return JobStatus(request_status=RequestStatus.OK,
                         health=self.__to_cimon_health__(app_health))

    def __to_cimon_health__(self, app_health):
        if not app_health in self.health_status_to_cimon_health:
            logger.debug("Unknown health status: %s" % app_health)
            return Health.OTHER
        return self.health_status_to_cimon_health[app_health]

class NewRelicClient():
    def __init__(self, http_client, application_name_pattern, refresh_applications_every):
        self.http_client = http_client
        self.application_name_pattern = re.compile(application_name_pattern)
        self.refresh_applications_every = refresh_applications_every
        self.request_count=refresh_applications_every
        self.application_ids={}

    def applications_health(self):
        if(self.request_count >= (self.refresh_applications_every)):
            self.application_ids = self.__load_application_ids__()
            self.request_count=0
        result = self.__load_application_health_state__()
        self.request_count+=1
        return result

    def __load_application_ids__(self):
        result=self.__load_all_applications__()
        return [str(application['id']) for application in result['applications'] if self.application_name_pattern.match(application['name'])]

    def __load_all_applications__(self):
        return json.loads(self.http_client.open_and_read("/v2/applications.json"))

    def __load_application_health_state__(self):
        result = self.__load_applications_by_id__()
        return {application['name']:application['health_status'] for application in result['applications']}

    def __load_applications_by_id__(self):
        return json.loads(self.http_client.open_and_read("/v2/applications.json?filter[ids]=%s" % ','.join(self.application_ids)))


if  __name__ =='__main__':
    base_url = sys.argv[1]
    app_key = sys.argv[2]

    if not base_url or not app_key:
        print("Usage: python3 newreliccollector.py <base_url> <appKey>")
        exit(42)

    """smoke test"""
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    collector = NewRelicCollector(
                        base_url=base_url,
                        app_key=app_key)
    print(collector.collect())
