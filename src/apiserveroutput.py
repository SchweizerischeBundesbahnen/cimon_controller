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

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    global host, port
    host = configuration.get("host", default_host)
    port = configuration.get("port", None)
    return ApiServerOutput()

host = default_host
port = 8080
__shared_status__ = {}
server = None
server_lock = RLock()

def start_http_server_if_not_started():
    try:
        server_lock.acquire()
        global server
        if not server:
            server = HTTPServer((host, port), ApiServer)
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

class ApiServer(BaseHTTPRequestHandler):

    job_request_pattern = re.compile("/job/([\w\.]*)/lastBuild/api/json.*")

    def do_GET(self):
        try:
            match = self.job_request_pattern.match(self.path)
            if match and len(match.groups()) > 0:
                job = match.group(1)
                status = get_shared_status()
                if "build" in status and job in status["build"] and status["build"][job]["request_status"] == "ok":
                    self.send_jenkins_response_to_last_build_request(job, status)
                elif "build" in status and job in status["build"]:
                    self.send_not_found("Request status %s" % status["build"][job]["request_status"])
                elif "build" in status:
                    self.send_not_found('Unkonwn build job "%s"' % job)
                else:
                    self.send_not_found("No build status available at all (maybe this is cimon does not collect build status?)")
            else:
                self.send_not_found('Path "%s" is not handled.' % self.path)
        except Exception:
            logging.error("Error handing HTTP Request", exc_info=True)
            self.send_error(500, str(sys.exc_info()))
        finally:
            self.wfile.flush()

    def send_not_found(self, reason):
        self.send_error(404, "Not found: %s" % reason)

    # act as if we where jenkins
    def send_jenkins_response_to_last_build_request(self, job, status):
        build_result = status["build"][job]
        self.send_response(200)
        self.send_header("Content-type","application/json")
        self.end_headers()
        jenkins_response = self.__to_jenkins_result__(build_result)
        self.wfile.write(json.dumps(jenkins_response).encode("utf-8"))

    def __to_jenkins_result__(self, build_result):
        jenkins_response = {
            "result" : build_result["result"] if build_result["result"] else "null",
            "building" : build_result["building"] if "building" in build_result else False
        }
        if "number" in build_result:
            jenkins_response["number"] = build_result["number"]
        if "timestamp" in build_result and build_result["timestamp"]:
            jenkins_response["timestamp"] = build_result["timestamp"].timestamp() * 1000
        if "culprits" in build_result:
            jenkins_response["culprits"] = [{"fullName" : culprit} for culprit in build_result["culprits"]]
        return jenkins_response

if  __name__ =='__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.info("test: starting server for manual tests, available job: 'job.a'")
    o = ApiServerOutput()
    o.on_update({"build" : {"job.a" :{"request_status" : "ok", "result" : "success", "number" : 42, "timestamp" : datetime.fromtimestamp(1467131487.090)}}})
    logging.info("test: serving for 30 seconds")
    sleep(30)
    stop_http_server()
    logging.info("test: stopped server")

