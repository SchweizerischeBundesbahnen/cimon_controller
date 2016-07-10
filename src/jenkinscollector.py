# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from urllib.request import urlopen, HTTPError, Request, URLError
from datetime import datetime
from concurrent import futures
import json
import logging
import sys
from collector import HttpClient, BasicAuthenticationHandler, SamlAuthenticationHandler, create_http_client
from configutil import decrypt

# Collect the build status in jenins via rest requests.
# will request the status of the latestBuild of each job configured and each job in each view configured
# views will be updated periodically
#
# is collector type "build" (only one collector of each type is allowed)
#
# the result returned is transformed form the actual jenkins api (in order to encapsulate the jenkins specific things)
#
# returns a dict per job (job_name) and containing another dict of the actual buid_status
# the "request_status" allways has to be checked first, only if it is "ok" the further values are contained
# { <job_name_as_string> : {
#       "request_status" : "ok" | "not_found" | "error" ,
#       "building" : True | False, # only if status["request_status"] == "ok"
#       "result" : "success" | "unstable" | "failure" | "other", # only if status["request_status"] == "ok"
#       "number" : <build_number_within_job_as_integer>, # only if status["request_status"] == "ok"
#       "timestamp" : <build_timestamp_as_datetime>
# }
default_max_parallel_requests=7
default_update_views_every = 50

def create(configuration, key=None):
    return JenkinsCollector(base_url = configuration["url"],
                            username = configuration.get("user", None),
                            password = configuration.get("password", None) or decrypt(configuration.get("passwordEncrypted", None), key),
                            saml_login_url = configuration.get("samlLoginUrl", None),
                            job_names= configuration.get("jobs", ()),
                            view_names = configuration.get("views", ()),
                            max_parallel_requests = configuration.get("maxParallelRequest", default_max_parallel_requests),
                            verify_ssl = configuration.get("verifySsl", True))


class JenkinsCollector:
    type = "build"

    # extract result and building state from the colors in the view
    colors_to_result = {"red" : "failure",
                        "yellow" : "unstable",
                        "blue" : "success",
                        "disabled" : "other"}

    def __init__(self, base_url, username = None, password = None, job_names =(), view_names = (), max_parallel_requests=default_max_parallel_requests, saml_login_url=None, verify_ssl=True):
        self.jenkins = JenkinsClient(http_client=create_http_client(base_url=base_url,
                                                                    username=username,
                                                                    password=password,
                                                                    saml_login_url=saml_login_url,
                                                                    verify_ssl=verify_ssl))

        self.job_names = tuple(job_names)
        self.view_names = tuple(view_names)
        self.max_parallel_requests = max_parallel_requests
        self.last_results={}

    def collect(self):
        method_param = [(self.collect_job, job_name) for job_name in self.job_names] + \
                       [(self.collect_view, view_name) for view_name in self.view_names]

        with futures.ThreadPoolExecutor(max_workers=self.max_parallel_requests) as executor:
            future_requests = ({executor.submit(method, param):
                                    (method, param) for method, param in method_param})

        builds = {}
        for future_request in futures.as_completed(future_requests):
            builds.update(future_request.result())

        logging.debug("Build status collected: %s", builds)
        return builds

    def collect_job(self, job_name):
        job_name, req_status, jenkins_build = self.__latest_build__(job_name)
        if req_status == "ok":
            return { job_name : self.__convert_build__(job_name, jenkins_build)}
        else:
            return { job_name: {"request_status" : req_status }}

    def __latest_build__(self, job_name):
        try:
            return (job_name, "ok", self.jenkins.latest_build(job_name))
        except HTTPError as e:
            # ignore...
            if(e.code == 404): # not found - its OK lets not crash
                logging.warning("No build found for job %s" % job_name)
                return (job_name, "not_found", None)
            else:
                logging.exception("HTTP Error requesting status for job %s" % job_name)
                return (job_name, "error", None)
        except URLError as e:
            logging.exception("URL Error requesting status for job %s" % job_name)
            return (job_name, "error", None)


    def __convert_build__(self, job_name, jenkins_build_result):
        build = {"request_status" : "ok"}
        build["building"] = jenkins_build_result["building"]
        build["result"] = self.__convert_store_fill_job_result__(job_name, jenkins_build_result["result"])
        build["number"] = jenkins_build_result["number"]
        build["timestamp"] = datetime.fromtimestamp(jenkins_build_result["timestamp"]/1000.0)
        logging.debug("Converted Build result", build)
        return build

    def __convert_store_fill_job_result__(self, job_name, jenkins_result):
        if jenkins_result:
            result = jenkins_result.lower() if jenkins_result in ("SUCCESS", "UNSTABLE", "FAILURE") else "other" # ABORTED or NOT_BUILT
            self.last_results[job_name] = result
            return result
        else:
            return self.last_results[job_name] if job_name in self.last_results else "other"

    def collect_view(self, view_name):
        view = self.__view__(view_name)
        if view:
            return self.__extract_job__status__(view)
        else:
            return { "all" : {"request_status" : "error"} }

    def __extract_job__status__(self, view):
        builds = {}
        for job in view["jobs"]:
            if "color" in job:
                color_status_building = job["color"].split("_") if job["color"] else (None,)
                if color_status_building[0] in self.colors_to_result:
                    builds[job["name"]] = {"request_status" : "ok",
                                           "result" : self.colors_to_result[color_status_building[0]],
                                           "building" : len(color_status_building) > 1 and color_status_building[1] == "anime"}
                else:
                    builds[job["name"]] = {"request_status" : "ok",
                                           "result" : "other",
                                           "building" : False }
            else:
                builds[job["name"]] = {"request_status" : "not_found"}
        return builds

    def __view__(self, view_name):
        try:
            return self.jenkins.view(view_name)
        except:
            # ignore...
            logging.exception("Error occured requesting info for view %s" % view_name)

class JenkinsClient():
    """ copied and simplifed from jenkinsapi by Willow Garage in order to ensure singe requests for latest build
        as oposed to multiple requests and local status"""
    def __init__(self, http_client):
        self.http_client = http_client

    def latest_build(self, job_name):
        return json.loads(self.http_client.open_and_read("/job/%s/lastBuild/api/json?depth=0" % job_name))

    def view(self, view_name):
        return json.loads(self.http_client.open_and_read("/view/%s/api/json?depth=0" % view_name))


if  __name__ =='__main__':
    base_url = sys.argv[1]
    build = sys.argv[2]

    if not base_url or not build:
        print("Usage: python3 jenkinscollectory.py <base_url> <build>")
        exit(42)

    """smoke test"""
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    collector = JenkinsCollector(base_url,
                                 job_names = [build],
                                 view_names = [])
    print(collector.collect())
