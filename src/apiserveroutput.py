__author__ = 'florianseidl'
# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from http.server import HTTPServer, BaseHTTPRequestHandler
import re
import json
import logging
import sys
from threading import Thread, RLock
from time import sleep
from datetime import datetime
from output import BuildFilter

# Template for an output. For ampel type output with 3 or less lights or signals, use myampeloutput template instead.
# copy and add your functionality

logger = logging.getLogger(__name__)

default_host = "localhost"
default_port = 8080
default_views = {"all" : BuildFilter(".*")}

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    global host, port, created, views
    if created: # safeguard against double creation since we use global variables
        raise ValueError("There is allready one API server configured, only one is allwowed")
    host = configuration.get("host", default_host)
    port = configuration.get("port", default_port)
    views_from_config = configuration.get("views", {}) # view: pattern
    for view_name, pattern in views_from_config.items():
        views[view_name] =  BuildFilter(pattern) if pattern else BuildFilter(".*")
    created = True
    return ApiServerOutput()

created = False
host = default_host
port = default_port
__shared_status__ = {}
server = None
server_lock = RLock()
views=default_views

def start_http_server_if_not_started():
    global server_lock
    try:
        server_lock.acquire()
        global server
        if not server:
            server = HTTPServer((host, port), ApiServerRequestHandler)
            logger.info("Starting http server at %s:%d", host, port)
            Thread(target=server.serve_forever).start()
    finally:
        server_lock.release()

def stop_http_server():
    try:
        server_lock.acquire()
        global server # ignore race conditions as they should not apply (server is only acessed here in cimon loop and on start)
        if server:
            server.shutdown()
            logger.info("Stopped http server")
        server = None
    finally:
        server_lock.release()

def set_shared_status(status):
    global __shared_status__
    __shared_status__ = status

def get_shared_status():
    return __shared_status__.copy()

class ApiServerOutput():
    """Template for your own output device."""

    def on_update(self, status):
        """Display the given status.
        Status is a dict of status type, for instance { 'build' : {"<job_name_1>": {"request_status" : "error" | "not_found" | "ok", "result" : "failure" | "unstable" | "other" | "success"},
                                                                    "<job_name_2>": {...},
                                                                    ...}
                                                       }
        """
        start_http_server_if_not_started()
        set_shared_status(status)

    def close(self):
        stop_http_server()

class ApiServer():
    """ A delegate to the delegate (HTTPRequestHander) as is easy to test """

    job_request_pattern = re.compile("/job/([\w\.-]*)/lastBuild/api/json.*")
    view_request_pattern = re.compile("/view/([\w\.-\/]*)/api/json.*")

    result_to_color = {"failure" : "red",
                        "unstable" : "yellow",
                        "success" : "blue"}


    def handle_get(self, path):
        try:
            status = get_shared_status()
            if "build" in status:
                if "all" in status["build"] and status["build"]["all"]["request_status"] == "error":
                   return (500, "Error requesting any job")
                else:
                    job_match = self.job_request_pattern.match(path)
                    if job_match and len(job_match.groups()) > 0:
                        return self.handle_job(job=job_match.group(1), build_status=status["build"])
                    else:
                        view_match = self.view_request_pattern.match(path)
                        if view_match and len(view_match.groups()) > 0:
                            return self.handle_view(view=view_match.group(1), build_status=status["build"])
                        else:
                            return (404, 'Path "%s" is not handled.' % path)
            else:
                return (500, "No build status available at all (maybe this is cimon does not collect build status?)")
        except Exception:
            logging.error("Error handing HTTP Request", exc_info=True)
            return (500, str(sys.exc_info()))

    def handle_job(self, job, build_status):
        if job in build_status and build_status[job]["request_status"] == "ok":
            return (200, self.__to_jenkins_job_result__(build_status[job]))
        elif job in build_status and build_status[job]["request_status"] == "error":
            return (500, 'Error requesting job "%s"' % job)
        elif job in build_status and build_status[job]["request_status"] == "not_found":
            return (404, "Request status %s" % build_status[job]["request_status"])
        else:
            return (404, 'Unkonwn build job "%s"' % job)

    def handle_view(self, view, build_status):
        if view in views:
            return (200, self.__to_jenkins_view_result__(views[view].filter_build_status(build_status)))
        else:
            return (404, 'Unknown view "%s"' % view)

    def __to_jenkins_job_result__(self, build_result):
        jenkins_response = {
            "result" : build_result["result"].upper() if build_result["result"] in ("success", "failure", "unstable") else None,
            "building" : build_result["building"] if "building" in build_result else False
        }
        if "number" in build_result:
            jenkins_response["number"] = build_result["number"]
        if "timestamp" in build_result and build_result["timestamp"]:
            jenkins_response["timestamp"] = build_result["timestamp"].timestamp() * 1000
        if "culprits" in build_result:
            jenkins_response["culprits"] = [{"fullName" : culprit} for culprit in build_result["culprits"]]
        return jenkins_response

    def __to_jenkins_view_result__(self, build_status):
        jenkins_view = {
            "description": None,
            "jobs" : []
        }
        for job in build_status:
            jenkins_view["jobs"].append({"name" : job, "color" : self.__to_color__(build_status[job])})
        return jenkins_view

    def __to_color__(self, job_status):
        if "result" in job_status and job_status["result"] in self.result_to_color:
            color=self.result_to_color[job_status["result"]]
            if "building" in job_status and job_status["building"]:
                color += "_anime"
            return color
        else:
            return "disabled"


class ApiServerRequestHandler(BaseHTTPRequestHandler):
    """ A shallow adapter to the Python http request handler as it is hard to test"""
    api_server = ApiServer()

    def do_GET(self):
        try:
            result = self.api_server.handle_get(self.path)
            if(200 <= result[0] < 300):
                logging.debug('Response to "%s" http status code %d: %s' % (self.path, result[0], str(result[1])))
                self.send_ok(code=result[0], jenkins_response=result[1])
            else: # some kind of error....
                logging.log(logging.INFO if result[0] < 500 else logging.WARNING, 'Error requesting "%s" http status code %d: %s' % (self.path, result[0], str(result[1])))
                self.send_error(code=result[0], message=result[1])
        finally:
            self.wfile.flush()

    def send_ok(self, code, jenkins_response):
        self.send_response(code)
        self.send_header("Content-type","application/json;charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(jenkins_response).encode("utf-8"))

if  __name__ =='__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.info("test: starting server for manual tests, available job: 'job.a'")
    o = ApiServerOutput()
    o.on_update({"build" : {"job.a" :{"request_status" : "ok", "result" : "success", "number" : 42, "timestamp" : datetime.fromtimestamp(1467131487.090)}}})
    logging.info("test: serving for 30 seconds")
    sleep(30)
    stop_http_server()
    logging.info("test: stopped server")

