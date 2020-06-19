# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4

__author__ = 'florianseidl'

import json
import logging
import re
import sys
from concurrent import futures
from datetime import datetime
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError

from cimon import JobStatus, RequestStatus, Health
from collector import create_http_client, configure_client_cert
from configutil import decrypt

# Collect the build status in jenins via rest requests.
# will request the status of the latestBuild of each job configured and each job in each view configured
# views will be updated periodically
#
# is collector type "build" (only one collector of each type is allowed)
#
# the result returned is transformed form the actual jenkins api (in order to encapsulate the jenkins specific things)
#
# returns a dict per job (job_name) and containing JobStatus objects
# the "request_status" allways has to be checked first, only if it is OK the further values are contained
# { (<hostname>, <job_name_as_string>) : JobStatus }
#
default_max_parallel_requests = 7
default_update_views_every = 50
default_view_depth = 0

logger = logging.getLogger(__name__)


def create(configuration, key=None):
    jenkins = JenkinsClient(http_client=create_http_client(base_url=configuration["url"],
                                                           username=configuration.get("user", None),
                                                           password=configuration.get("password", None) or decrypt(
                                                               configuration.get("passwordEncrypted", None), key),
                                                           jwt_login_url=configuration.get("jwtLoginUrl", None),
                                                           saml_login_url=configuration.get("samlLoginUrl", None),
                                                           verify_ssl=configuration.get("verifySsl", True),
                                                           client_cert=configure_client_cert(
                                                               configuration.get("clientCert", None), key), ),
                            view_depth=configuration.get("viewDepth", default_view_depth))
    return JenkinsCollector(jenkins=jenkins,
                            base_url=configuration["url"],
                            job_names=configuration.get("jobs", ()),
                            view_names=configuration.get("views", ()),
                            folder_names=configuration.get("folders", ()),
                            multibranch_pipeline_names=configuration.get("multibranch_pipelines", ()),
                            max_parallel_requests=configuration.get("maxParallelRequest",
                                                                    default_max_parallel_requests),
                            name=configuration.get('name', None),
                            job_name_from_url_pattern=configuration.get('jobNameFromUrlPattern', None),
                            job_name_from_url_pattern_match_group=configuration.get('jobNameFromUrlPatternMatchGroup',
                                                                                    1))


class JenkinsCollector:
    # extract result and building state from the colors in the view

    def __init__(self,
                 jenkins,
                 base_url,
                 job_names=(),
                 view_names=(),
                 folder_names=(),
                 multibranch_pipeline_names=(),
                 max_parallel_requests=default_max_parallel_requests,
                 name=None,
                 job_name_from_url_pattern=None,
                 job_name_from_url_pattern_match_group=1):
        self.job_names = tuple(job_names)
        self.view_names = tuple(view_names)
        self.folder_names = tuple(folder_names)
        self.multibranch_pipeline_names = tuple(multibranch_pipeline_names)
        self.max_parallel_requests = max_parallel_requests

        name = name if name else urlparse(base_url).netloc
        name_from_url_pattern_extractor = \
            NameFromUrlPatternExtractor(job_name_from_url_pattern,
                                        job_name_from_url_pattern_match_group) if job_name_from_url_pattern \
                else NoNameFromUrlPatternExtractor()
        self.job_reader = JobReader(
            name=name,
            jenkins=jenkins,
            name_from_url_pattern_extractor=name_from_url_pattern_extractor)
        self.view_reader = ViewReader(
            name=name,
            jenkins=jenkins,
            name_from_url_pattern_extractor=name_from_url_pattern_extractor)
        self.folder_reader = FolderAndMultibranchPipelineReader(
            name=name,
            jenkins=jenkins,
            name_from_url_pattern_extractor=name_from_url_pattern_extractor)
        logger.info("configured jenkins collector %s", self.__dict__)

    def collect(self):
        method_param = [(self.job_reader.collect_job, job_name) for job_name in self.job_names] + \
                       [(self.view_reader.collect_view, view_name) for view_name in self.view_names] + \
                       [(self.collect_folder, folder_name) for folder_name in self.folder_names] + \
                       [(self.folder_reader.collect_multibranch_pipeline_standalone, multibranch_pipeline_name) for
                        multibranch_pipeline_name in self.multibranch_pipeline_names]

        builds = self.collect_async(method_param)
        logger.debug("Build status collected: %s", builds)
        return builds

    def collect_folder(self, folder_name):
        folder = self.folder_reader.read_folder(folder_name)
        method_param = [(self.folder_reader.collect_multibranch_pipeline_in_folder, (folder_name, multibranch["name"]))
                        for
                        multibranch in folder["jobs"]]
        return self.collect_async(method_param)

    def collect_async(self, method_param):
        with futures.ThreadPoolExecutor(max_workers=self.max_parallel_requests) as executor:
            future_requests = {executor.submit(method, params):
                                   (method, params) for method, params in method_param}

        builds = {}
        for future_request in futures.as_completed(future_requests):
            builds.update(future_request.result())
        return builds


class BaseReader():
    colors_to_result = {"red": Health.SICK,
                        "yellow": Health.UNWELL,
                        "blue": Health.HEALTHY,
                        "notbuilt": Health.UNDEFINED,
                        "aborted": Health.UNDEFINED}

    def __init__(self, name, jenkins, name_from_url_pattern_extractor):
        self.name = name
        self.jenkins = jenkins
        self.name_from_url_pattern_extractor = name_from_url_pattern_extractor

    def qualified_job_name(self, job_name, url):
        name_from_url = self.name_from_url_pattern_extractor.extract_name(url)
        return self.name, name_from_url if name_from_url else job_name

    def status_from_color(self, job):
        if "color" in job:
            color_status_building = job["color"].split("_") if job["color"] else (None,)
            if color_status_building[0] == "disabled":
                return JobStatus(request_status=RequestStatus.NOT_FOUND)
            elif color_status_building[0] in self.colors_to_result:
                return JobStatus(
                    health=self.colors_to_result[color_status_building[0]],
                    active=len(color_status_building) > 1 and color_status_building[1] == "anime")
        logger.warning('Missing attribute "color" in job description %s' % job)
        return JobStatus(health=Health.OTHER)


class JobReader(BaseReader):
    def __init__(self, name, jenkins, name_from_url_pattern_extractor):
        super().__init__(name, jenkins, name_from_url_pattern_extractor)
        self.last_results = {}

    jenkins_result_to_result = {"SUCCESS": Health.HEALTHY,
                                "UNSTABLE": Health.UNWELL,
                                "FAILURE": Health.SICK}

    def collect_job(self, job_name):
        job_name, req_status, jenkins_build = self.__latest_build__(job_name)
        job_url = jenkins_build["url"] if jenkins_build and "url" in jenkins_build else None
        if req_status == RequestStatus.OK:
            return {self.qualified_job_name(job_name, job_url): self.__convert_build__(job_name, jenkins_build)}
        else:
            return {self.qualified_job_name(job_name, job_url): JobStatus(request_status=req_status)}

    def __latest_build__(self, job_name):
        try:
            return (job_name, RequestStatus.OK, self.jenkins.latest_build(job_name))
        except HTTPError as e:
            # ignore...
            if (e.code == 404):  # not found - its OK lets not crash
                logger.warning("No build found for job %s" % job_name)
                return (job_name, RequestStatus.NOT_FOUND, None)
            else:
                logger.exception("HTTP Error requesting status for job %s" % job_name)
                return (job_name, RequestStatus.ERROR, None)
        except URLError as e:
            logger.exception("URL Error requesting status for job %s" % job_name)
            return (job_name, RequestStatus.ERROR, None)

    def __convert_build__(self, job_name, jenkins_build_result):
        if "actions" in jenkins_build_result and len(jenkins_build_result["actions"]) > 0 and "causes" in \
                jenkins_build_result["actions"][0] and len(jenkins_build_result["actions"][0]["causes"]) > 0:
            cause = jenkins_build_result["actions"][0]["causes"][0]["shortDescription"]
        else:
            cause = None
        status = JobStatus(
            health=self.__convert_store_fill_job_result__(job_name, jenkins_build_result["result"]),
            active=jenkins_build_result["building"],
            timestamp=datetime.fromtimestamp(jenkins_build_result["timestamp"] / 1000.0),
            number=jenkins_build_result["number"],
            names=[culprit["fullName"] for culprit in
                   jenkins_build_result["culprits"]] if "culprits" in jenkins_build_result else [],
            duration=jenkins_build_result["duration"] if "duration" in jenkins_build_result else None,
            fullDisplayName=jenkins_build_result["fullDisplayName"],
            url=jenkins_build_result["url"],
            builtOn=jenkins_build_result["builtOn"] if "builtOn" in jenkins_build_result else None,
            cause=cause)
        logger.debug("Converted Build result: %s", str(status))
        return status

    def __convert_store_fill_job_result__(self, job_name, jenkins_result):
        if jenkins_result:
            result = self.jenkins_result_to_result[
                jenkins_result] if jenkins_result in self.jenkins_result_to_result else Health.OTHER
            self.last_results[job_name] = result
            return result
        else:
            return self.last_results[job_name] if job_name in self.last_results else Health.OTHER


class ViewReader(BaseReader):
    def collect_view(self, view_name):
        # separate method because default parameter does not work easily with future
        return self.__collect_view_recursive__(view_name, set())

    def __collect_view_recursive__(self, view_name, allready_visited):
        if view_name in allready_visited:  # guard against infinite loops
            return {}
        allready_visited.add(view_name)

        view = self.__view__(view_name)
        if view:
            # add the builds to the existing ones (from recursion)
            builds = self.__extract_job__status__(view)
            if "views" in view:
                nested_views = self.__extract_nested_view_names__(view)
                for nested_view in nested_views:
                    # recurse for all nested views
                    builds.update(self.__collect_view_recursive__(nested_view, allready_visited))
            return builds
        else:
            return {self.qualified_job_name(view_name, None): JobStatus(request_status=RequestStatus.ERROR)}

    def __extract_job__status__(self, view):
        builds = {}
        for job in view["jobs"]:
            jobname = self.qualified_job_name(job["name"], job["url"])
            status = self.__status_from_color__(job)
            if "builds" in job:  # requires depth 2
                latest_build = self.__latest_build_in_view__(job)
                if "number" in latest_build:
                    status.number = latest_build["number"]
                if "timestamp" in latest_build:
                    status.timestamp = datetime.fromtimestamp(latest_build["timestamp"] / 1000)
                if "culprits" in latest_build:
                    status.names = [culprit["fullName"] for culprit in latest_build["culprits"]]
            builds[jobname] = status
        return builds

    def __status_from_color__(self, job):
        if "color" in job:
            color_status_building = job["color"].split("_") if job["color"] else (None,)
            if color_status_building[0] == "disabled":
                return JobStatus(request_status=RequestStatus.NOT_FOUND)
            elif color_status_building[0] in self.colors_to_result:
                return JobStatus(
                    health=self.colors_to_result[color_status_building[0]],
                    active=len(color_status_building) > 1 and color_status_building[1] == "anime")
        logger.warning('Missing attribute "color" in job description %s' % job)
        return JobStatus(health=Health.OTHER)

    def __latest_build_in_view__(self, job):
        latest = {}
        for build in job["builds"]:  # sort by number
            if not latest or "number" in build and latest["number"] < build["number"]:
                latest = build
        return latest

    def __extract_nested_view_names__(self, view):
        views = []
        for v in view["views"]:
            # "url":"https://ci.sbb.ch/view/mvp/view/zvs-drittgeschaeft/view/vermittler-westernunion/
            url = v["url"]  # extract name with path from url
            name_with_path = url.partition("view")[2]
            if name_with_path.endswith("/"):
                name_with_path = name_with_path[:-1]
            if name_with_path:
                views.append(name_with_path)
        return set(views)

    def __view__(self, view_name):
        try:
            return self.jenkins.view(view_name)
        except:
            # ignore...
            logger.exception("Error occured requesting info for view %s" % view_name)


class FolderAndMultibranchPipelineReader(BaseReader):
    def collect_multibranch_pipeline_in_folder(self, folder_multibranch_pipeline_name):
        return self.map_multibranch_pipeline(
            self.__pipeline_name__(*folder_multibranch_pipeline_name),
            self.__multibranch_pipeline_in_folder__(*folder_multibranch_pipeline_name))

    def collect_multibranch_pipeline_standalone(self, pipeline_name):
        return self.map_multibranch_pipeline(
            pipeline_name,
            self.__multibranch_pipeline_standalone__(pipeline_name))

    def map_multibranch_pipeline(self, pipeline_name, pipeline):
        if not pipeline:
            logger.debug("No builds in pipeline %s" % (pipeline_name))
            return {}
        builds = {}
        for job in pipeline["jobs"]:
            status = self.__status_multibranch_job__(job)
            builds[(self.name,
                    self.__pipeline_job_name__(pipeline_name, job["url"]))] = status
            logger.debug("Converted Mulitbranch pipeline build result: %s", str(status))
        return builds

    def __pipeline_name__(self, folder_name, multibranch_pipeline_name):
        return "%s/%s" % (folder_name, multibranch_pipeline_name)

    def __pipeline_job_name__(self, pipeline_name, url):
        return "%s/%s" % (pipeline_name, self.__branch_from_url__(url))

    def __branch_from_url__(self, url):
        return url.split("/")[-2].replace('%252F', '/')

    def read_folder(self, folder_name):
        try:
            return self.jenkins.folder(folder_name)
        except:
            # ignore...
            logger.exception("Error occured requesting info for folder %s" % folder_name)

    def __status_multibranch_job__(self, job):
        statusFromColor = self.status_from_color(job)
        if statusFromColor.request_status == RequestStatus.NOT_FOUND:
            return statusFromColor
        return JobStatus(
            health=statusFromColor.health,
            active=statusFromColor.active,
            timestamp=self.__get_timestamp_from_job__(job),
            number=self.__get_number_from_job__(job),
            names=self.__get_culprits_from_job__(job),
            duration=self.__get_duration_from_job__(job),
            fullDisplayName=self.__get_name_from_job__(job),
            url=job["url"] if "url" in job else None,
            builtOn=None,  # not available on job
            cause=self.__get_cause_from_job__(job)
        )

    def __get_cause_from_job__(self, job):
        if self.__last_build_contains__(job, "actions") and \
                "causes" in job["lastBuild"]["actions"][0] and job["lastBuild"]["actions"][0]["causes"]:
            return job["lastBuild"]["actions"][0]["causes"][0]["shortDescription"]

    def __get_culprits_from_job__(self, job):
        if self.__last_build_contains__(job, "culprits"):
            return [culprit["fullName"] for culprit in job["lastBuild"]["culprits"]]
        return []

    def __get_number_from_job__(self, job):
        if self.__last_build_contains__(job, "number"):
            return job["lastBuild"]["number"]

    def __get_name_from_job__(self, job):
        if self.__last_build_contains__(job, "fullDisplayName"):
            return job["lastBuild"]["fullDisplayName"]
        if "fullDisplayName" in job and job["fullDisplayName"]:
            return job["fullDisplayName"]

    def __get_duration_from_job__(self, job):
        if self.__last_build_contains__(job, "duration"):
            return job["lastBuild"]["duration"]

    def __get_timestamp_from_job__(self, job):
        if self.__last_build_contains__(job, "timestamp"):
            return datetime.fromtimestamp(job["lastBuild"]["timestamp"] / 1000.0)

    def __last_build_contains__(self, job, key):
        return "lastBuild" in job and job["lastBuild"] and key in job["lastBuild"] and job["lastBuild"][key]

    def __multibranch_pipeline_in_folder__(self, folder_name, multibranch_pipeline_name):
        try:
            return self.jenkins.multibranch_pipeline_in_folder(folder_name, multibranch_pipeline_name)
        except:
            # ignore...
            logger.exception(
                "Error occured requesting info for pipeline in folder %s" % self.__pipeline_name__(folder_name,
                                                                                                   multibranch_pipeline_name))

    def __multibranch_pipeline_standalone__(self, multibranch_pipeline_name):
        try:
            return self.jenkins.multibranch_pipeline_standalone(multibranch_pipeline_name)
        except:
            # ignore...
            logger.exception("Error occured requesting info for pipeline standalone %s" % multibranch_pipeline_name)


class JenkinsClient():
    """ copied and simplifed from jenkinsapi by Willow Garage in order to ensure singe requests for latest build
        as oposed to multiple requests and local status"""

    def __init__(self, http_client, view_depth=default_view_depth):
        self.http_client = http_client
        self.view_depth = view_depth

    def latest_build(self, job_name):
        return json.loads(self.http_client.open_and_read("/job/%s/lastBuild/api/json?depth=0" % job_name))

    def view(self, view_name):
        return json.loads(self.http_client.open_and_read("/view/%s/api/json?depth=%d" % (view_name, self.view_depth)))

    def folder(self, folder_name):
        return json.loads(self.http_client.open_and_read("/job/%s/api/json?tree=jobs[name]" % (folder_name)))

    def multibranch_pipeline_in_folder(self, folder_name, multibranch_pipeline_name):
        return json.loads(self.http_client.open_and_read(
            "/job/%s/job/%s/api/json?depth=2" % (folder_name, multibranch_pipeline_name)))

    def multibranch_pipeline_standalone(self, multibranch_pipeline_name):
        return json.loads(self.http_client.open_and_read("/job/%s/api/json" % (multibranch_pipeline_name)))


class NameFromUrlPatternExtractor():
    def __init__(self,
                 name_from_url_pattern,
                 name_from_url_pattern_match_group):
        self.name_from_url_pattern = name_from_url_pattern
        self.name_from_url_pattern_match_group = name_from_url_pattern_match_group

    def extract_name(self, url):
        if not url:
            return None
        matcher = re.search(self.name_from_url_pattern, url)
        if not matcher or len(matcher.groups()) < self.name_from_url_pattern_match_group:
            return None
        return matcher.group(self.name_from_url_pattern_match_group)


class NoNameFromUrlPatternExtractor():
    def extract_name(self, url):
        return None


if __name__ == '__main__':
    base_url = sys.argv[1]
    build = sys.argv[2]

    if not base_url or not build:
        print("Usage: python3 jenkinscollectory.py <base_url> <build>")
        exit(42)

    """smoke test"""
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    collector = JenkinsCollector(
        JenkinsClient(http_client=create_http_client(base_url=base_url)),
        base_url,
        job_names=[build],
        view_names=[])
    print(collector.collect())
