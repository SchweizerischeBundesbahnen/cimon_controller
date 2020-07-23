# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
from webbrowser import get

#
# supplies a list of available job-names under http://localhost:8080/jobs
# supplies data for a job under http://localhost:8080/job/<job-name>/lastBuild/api/json
#

__author__ = 'florianseidl'

from http.server import HTTPServer, BaseHTTPRequestHandler
import re
import json
import logging
import sys
from threading import Thread, RLock
from time import sleep
from datetime import datetime
from output import NameFilter
from cimon import JobStatus,RequestStatus,Health

logger = logging.getLogger(__name__)

default_host = "localhost"
default_port = 8080
default_views = {"all" : re.compile(r'.*')}

def create(configuration, key=None):
    """Create an instance (called by cimon.py)"""
    global host, port, created, views, collector_filter
    if created: # safeguard against double creation since we use global variables
        raise ValueError("There is allready one API server configured, only one is allwowed")
    host = configuration.get("host", default_host)
    port = configuration.get("port", default_port)
    build_filter_pattern=configuration.get("buildFilterPattern", None),
    collector_filter = NameFilter(configuration["collectorFilterPattern"]) if "collectorFilterPattern" in configuration else NameFilter()
    views_from_config = configuration.get("views", {}) # view: pattern
    for view_name, pattern in views_from_config.items():
        views[view_name] =  re.compile(pattern if pattern else r'.*')
    created = True
    set_shared_config(configuration.get("web", {}))
    return ApiServerOutput()

created = False
host = default_host
port = default_port
__shared_status__ = {}
__shared_config__ = {}
server = None
server_lock = RLock()
collector_filter=NameFilter()
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

def set_shared_config(config):
    global __shared_config__
    __shared_config__ = config

def get_shared_config():
    return __shared_config__.copy()

class ApiServerOutput():
    """Template for your own output device."""

    def on_update(self, status):
        start_http_server_if_not_started()
        set_shared_status(self.filter_status_by_collector(status))

    def filter_status_by_collector(self, status):
        filtered = collector_filter.filter_status(status)
        return {k[1]:v for k,v in filtered.items()}

    def close(self):
        stop_http_server()

class ApiServer():
    """ A delegate to the delegate (HTTPRequestHander) as is easy to test """

    job_request_pattern = re.compile("/job/([\w\.\-/_]*)/lastBuild/api/json.*")

    result_to_color = {Health.SICK  : "red",
                       Health.UNWELL : "yellow",
                       Health.HEALTHY      : "blue"}

    health_to_jenkins_status = {Health.SICK  : "FAILURE",
                                Health.UNWELL : "UNSTABLE",
                                Health.HEALTHY      : "SUCCESS"}

    def handle_get(self, path):
        try:
            if(path == "/config"):
                return self.handle_config()
            if(path == "/jobs"):
                status = get_shared_status()
                return self.list_all_jobs(status=status)
            status = get_shared_status()
            logger.info("handle_get: %s", path)
            if "all" in status and status["all"].request_status == RequestStatus.ERROR:
               return (500, "Error requesting any job")
            else:
                job_match = self.job_request_pattern.match(path)
                if job_match and len(job_match.groups()) > 0:
                    logger.info("job_match value=%s", job_match.group(1))
                    return self.handle_job(job=job_match.group(1), status=status)
                else:
                    logger.info("no job_match")
                    return (404, 'Path "%s" is not handled.' % path)
        except Exception:
            logging.error("Error handling HTTP Request", exc_info=True)
            return (500, str(sys.exc_info()))

    def list_all_jobs(self, status):
        return (200, self.__to_jenkins_job_list__(status.keys()))

    def __to_jenkins_job_list__(selfself, keys):
        jenkins_response = [key for key in keys]
        #logging.info("job list", jenkins_response)
        return jenkins_response
    
    def handle_job(self, job, status):
        jobWithSlash=job+'/'
        # config can contain job name with or without terminating slash; regexp always delivers job name without terminating slash
        if job in status:
            job_status=status[job]
            logging.debug("handle_job: match for job=%s" % job)
        elif jobWithSlash in status:
            job_status=status[jobWithSlash]
            logging.debug("handle_job: match for job=%" %jobWithSlash)
        else:
            job_status = None
            logging.warning("handle_job: no match for job=%" % job)
        
        if job_status and job_status.request_status == RequestStatus.OK:
            return (200, self.__to_jenkins_job_result__(job_status))
        elif job_status and job_status.request_status == RequestStatus.ERROR:
            return (500, 'Error requesting job "%s"' % job)
        elif job_status and job_status.request_status == RequestStatus.NOT_FOUND:
            return (404, "Not found for job %s" % job)
        else:
            return (404, 'Unkonwn build job "%s"' % job)

    def handle_view(self, view, status):
        if view in views:
            filteredView = {k: v for k, v in status.items() if views[view].match(k)}
            return (200, self.__to_jenkins_view_result__(filteredView))
        else:
            return (404, 'Unknown view "%s"' % view)

    def handle_config(self):
        return (200, get_shared_config())

    def __to_jenkins_job_result__(self, job_status):
        jenkins_response = {
            "result" : self.health_to_jenkins_status[job_status.health] if job_status.health in self.health_to_jenkins_status else None,
            "building" : job_status.active
        }
        if job_status.number:
            jenkins_response["number"] = job_status.number
        if job_status.timestamp:
            jenkins_response["timestamp"] = job_status.timestamp.timestamp() * 1000
        if job_status.names:
            jenkins_response["culprits"] = [{"fullName" : name} for name in job_status.names]
        if job_status.duration:
            jenkins_response["duration"] = job_status.duration
        if job_status.fullDisplayName:
            jenkins_response["fullDisplayName"] = job_status.fullDisplayName
        if job_status.url:
            jenkins_response["url"] = job_status.url
        if job_status.builtOn:
            jenkins_response["builtOn"] = job_status.builtOn
        if job_status.cause:
            jenkins_response["actions"] = [{"causes": [{"shortDescription": job_status.cause}]}]
        return jenkins_response

    def __to_jenkins_view_result__(self, jobs_status):
        jenkins_view = {
            "description": None,
            "jobs" : []
        }
        for job in jobs_status:
            jenkins_view["jobs"].append({"name" : job, "color" : self.__to_color__(jobs_status[job])})
        return jenkins_view

    def __to_color__(self, job_status):
        if job_status.health in self.result_to_color:
            color=self.result_to_color[job_status.health]
            if job_status.active:
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

