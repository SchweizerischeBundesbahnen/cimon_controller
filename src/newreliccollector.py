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
# requires a preferably encrypted API key for new relic.
#
default_update_applications_every = 50

logger = logging.getLogger(__name__)

def create(configuration, key=None):
    if "type" not in configuration or configuration["type"] == "alerts":
        return NewRelicAlertsCollector(base_url = configuration["url"],
                                       api_key = configuration.get("apiKey", None) or decrypt(configuration.get("apiKeyEncyrpted", None), key),
                                       policy_name_pattern=configuration.get("policyNamePattern", None),
                                       condition_name_pattern=configuration.get("conditionNamePattern", None),
                                       name = configuration.get("name", None),
                                       verify_ssl=configuration.get("verifySsl", True))
    elif configuration["type"] == "applications":
        return NewRelicApplicationsCollector(base_url = configuration["url"],
                                         api_key = configuration.get("apiKey", None) or decrypt(configuration.get("apiKeyEncyrpted", None), key),
                                         application_name_pattern= configuration.get("applicationNamePattern", None),
                                         refresh_applications_every=configuration.get("refreshApplicationsEvery", default_update_applications_every),  # times
                                         name = configuration.get("name", None),
                                         verify_ssl=configuration.get("verifySsl", True))
    else:
        raise ValueError("Unknown type of new relic collector: %s" % configuration["type"])

class NewRelicAlertsCollector:
    priority_to_cimon_health = {
        "critical" : Health.SICK,
        "warning" : Health.UNWELL,
        "info" : Health.HEALTHY}

    def __init__(self,
                 base_url,
                 api_key,
                 policy_name_pattern=None,
                 condition_name_pattern=None,
                 name=None,
                 verify_ssl=True):
        self.new_relic_client=BaseNewRelicClient(
            http_client=create_http_client(base_url=base_url,fixed_headers={'X-Api-Key':api_key},verify_ssl=verify_ssl))
        self.policy_name_pattern=re.compile(policy_name_pattern if policy_name_pattern  else r'.*')
        self.condition_name_pattern=re.compile(condition_name_pattern if condition_name_pattern else r'.*')
        self.name = name if name else urlparse(base_url).netloc
        logger.info("configured new relic collector %s", self.__dict__)

    def collect(self):
        status=self.__collect_alerts__()
        logger.debug("Alert status collected: %s", status)
        return status

    def __collect_alerts__(self):
        try:
            return self.__to_status__(self.__filter__(self.new_relic_client.open_alert_violations()))
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

    def __filter__(self, alert_violations):
        return [alert for alert in alert_violations
                      if self.policy_name_pattern.match(alert["policy_name"])
                      and self.condition_name_pattern.match(alert["condition_name"])]

    def __to_status__(self, alert_violations):
        status = {}
        for alert in alert_violations:
            key = (self.name, alert["condition_name"])
            job_status = self.__to_job_status__(alert)
            if key not in status or job_status.health > status[key].health or job_status.timestamp > status[key].timestamp:
                status[key] = job_status
        return status

    def __to_job_status__(self, alert):
        return JobStatus(request_status=RequestStatus.OK,
                         health=self.__to_cimon_health__(alert["priority"]),
                         timestamp=datetime.fromtimestamp(alert["opened_at"]/1000.0),
                         number=alert["id"])

    def __to_cimon_health__(self, priority):
        if not priority or priority.lower() not in self.priority_to_cimon_health:
            return Health.UNDEFINED
        return self.priority_to_cimon_health[priority.lower()]

class NewRelicApplicationsCollector:

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
                 application_name_pattern=None,
                 refresh_applications_every=default_update_applications_every,
                 name=None,
                 verify_ssl=True):
        http_client=create_http_client(base_url=base_url,fixed_headers={'X-Api-Key':api_key},verify_ssl=verify_ssl)
        if application_name_pattern and application_name_pattern != r'.*':
            self.new_relic_client = ApplicationNameFilterNewRelicClient(
                http_client=http_client,
                application_name_pattern=application_name_pattern,
                refresh_applications_every=refresh_applications_every)
        else:
            self.new_relic_client= BaseNewRelicClient(http_client=http_client)
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

class BaseNewRelicClient():
    def __init__(self, http_client):
        self.http_client = http_client

    def applications_health(self):
        return self.__extract_health_status__(self.__load_all_applications__())

    def open_alert_violations(self):
        return self.__extract_violations__(json.loads(self.http_client.open_and_read("/v2/alerts_violations.json?only_open=true")))

    def __load_all_applications__(self):
        return json.loads(self.http_client.open_and_read("/v2/applications.json"))

    def __extract_health_status__(self, result):
        return {application['name']:application['health_status'] for application in result['applications']}

    def __extract_violations__(self, alert_violations):
        return alert_violations["violations"] if "violations" in alert_violations else []

class ApplicationNameFilterNewRelicClient(BaseNewRelicClient):
    def __init__(self, http_client, application_name_pattern, refresh_applications_every):
        super().__init__(http_client=http_client)
        self.application_name_pattern = re.compile(application_name_pattern)
        self.refresh_applications_every = refresh_applications_every
        self.request_count=refresh_applications_every
        self.application_ids={}

    def applications_health(self):
        if self.request_count >= (self.refresh_applications_every):
            self.application_ids = self.__load_application_ids__()
            self.request_count=0
        result = self.__extract_health_status__(self.__load_applications_by_id__())
        self.request_count+=1
        return result

    def __load_application_ids__(self):
        result=self.__load_all_applications__()
        return [str(application['id']) for application in result['applications'] if self.application_name_pattern.match(application['name'])]

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
    collector = NewRelicApplicationsCollector(
                        base_url=base_url,
                        app_key=app_key)
    print(collector.collect())
