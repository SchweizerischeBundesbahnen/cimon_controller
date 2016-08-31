__author__ = 'florianseidl'

import env
from apiserveroutput import *
import apiserveroutput
from output import BuildFilter
from unittest import TestCase
from unittest.mock import MagicMock, Mock
from types import SimpleNamespace
from datetime import datetime
import yaml
import os
import collections
import json

class TestApiServerOutput(TestCase):
    job_name_success = "mvp.mct.vermittler-produkt.continuous"
    job_name_failed = "mvp.mct.vermittler-orchestrierung_commons.continuous"
    job_name_unstable = "kd.esta.integrate.template.was3.it"
    job_name_building = "kd.sid.sid-library-ios.continuous"
    view_name_3 = "pz/view/tip/view/tip-all"

    def setUp(self):
        apiserveroutput.server = SimpleNamespace() # pretend there is an http server to avioid starting one
        apiserveroutput.set_shared_status({})
        apiserveroutput.views = apiserveroutput.default_views

    def create(self):
        return ApiServerOutput(), ApiServer()

    def read(self, file_name):
        with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name), encoding='utf-8') as f:
            return json.load(f)

    def do_test_query_jobs_from_api(self, job_name, values):
        out, api = self.create()
        out.on_update({"build" :  { job_name : values }})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0" % job_name)
        self.assertEquals(result[0], 200)
        self.assert_all_in_original_job(job_name, result[1])

    def assert_all_in_original_job(self, job_name, api_response):
        original_jenkins_response = self.read(job_name)
        self.__assert_all_in_original_recursive__(api_response, original_jenkins_response)

    def assert_all_in_original_view(self, view_name, api_response):
        original_jenkins_response = self.read(view_name.replace("/", "__"))
        self.__assert_all_in_original_recursive__(api_response, original_jenkins_response)

    def __assert_all_in_original_recursive__(self, api_response_part, original_part):
        if isinstance(api_response_part, dict):
            self.assertIsInstance(original_part, dict)
            for key in api_response_part:
                self.assertIn(key, original_part)
                self.__assert_all_in_original_recursive__(api_response_part[key], original_part[key])
        elif isinstance(api_response_part, collections.Sequence) and not isinstance(api_response_part, str):
            self.assertIsInstance(original_part, collections.Sequence)
            self.assertNotIsInstance(original_part, str)
            for value in api_response_part:
                if(isinstance(value, dict)):
                   self.assertTrue(self.__find_partial_dict_in_list__(value, original_part))
                else:
                    self.assertIn(value, original_part)
        else:
            self.assertEquals(api_response_part, original_part)

    def __find_partial_dict_in_list__(self, partial, list_of_dicts):
        for d in list_of_dicts:
            if isinstance(d, dict):
                for k in partial:
                    if k in d and partial[k] == d[k]:
                        return True
        return False

    def test_request_status_ok(self):
        self.do_test_query_jobs_from_api(self.job_name_success, {"request_status" : "ok", "result" : "success"})

    def test_request_status_failed(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, {"request_status" : "ok", "result" : "failure"})

    def test_request_status_unstable(self):
        self.do_test_query_jobs_from_api(self.job_name_unstable, {"request_status" : "ok", "result" : "unstable"})

    def test_request_building_false(self):
        self.do_test_query_jobs_from_api(self.job_name_success, {"request_status" : "ok", "result" : "success", "building" : False})

    def test_request_building_true(self):
        self.do_test_query_jobs_from_api(self.job_name_building, {"request_status" : "ok", "result" : None, "building" : True})

    def test_request_number(self):
        self.do_test_query_jobs_from_api(self.job_name_success, {"request_status" : "ok", "result" : "success", "number" : 515})

    def test_request_culprits(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, {"request_status" : "ok", "result" : "failure", "culprits" : ["Diacon Gilles"]})

    def test_request_timestamp(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, {"request_status" : "ok", "result" : "failure", "timestamp": datetime.fromtimestamp(1458426704.059) })

    def test_request_all(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, {"request_status" : "ok", "result" : "failure", "building" : False, "culprits" : ["Diacon Gilles"], "timestamp": datetime.fromtimestamp(1458426704.059), "number" : 554})

    def test_not_found(self):
        out, api = self.create()
        out.on_update({"build" :  { self.job_name_success : {"request_status" : "ok", "result" : "success", "building" : False} }})
        result = api.handle_get("/job/gibtsgarnicht/lastBuild/api/json?depth=0" )
        self.assertEquals(result[0], 404)

    def test_not_found_in_result(self):
        out, api = self.create()
        out.on_update({"build" :  { self.job_name_success : {"request_status" : "not_found" } }})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEquals(result[0], 404)

    def test_error_in_result(self):
        out, api = self.create()
        out.on_update({"build" :  { self.job_name_success : {"request_status" : "error"} }})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEquals(result[0], 500)

    def test_error_in_result_all(self):
        out, api = self.create()
        out.on_update({"build" :  { "all" : {"request_status" : "error"} }})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEquals(result[0], 500)

    def test_view_all(self):
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(1, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_all_2_builds(self):
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"},
                                    "pz.tip.app.nightly" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(2, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_not_found(self):
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/gibtsgarnicht/api/json?depth=0")
        self.assertEquals(result[0], 404)

    def test_view_error_job(self):
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "error" } }})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(result[1], {'description': None, 'jobs': [{'name': 'pz.tip.app.continuous', 'color': 'disabled'}]})

    def test_view_no_job(self):
        out, api = self.create()
        out.on_update({"build" :  {} } )
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(0, len(result[1]["jobs"]))

    def test_view_all_error(self):
        out, api = self.create()
        out.on_update({"build" :  { "all" : {"request_status" : "error" } }})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 500)

    def test_view_configured_2_builds(self):
        apiserveroutput.views.update({"confiview" : BuildFilter(".*\.nightly")})
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"},
                                    "pz.tip.app.nightly" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(1, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_configured_2_builds_match_none(self):
        apiserveroutput.views.update({"confiview" : BuildFilter("hotzenplotz") })
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"},
                                    "pz.tip.app.nightly" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(0, len(result[1]["jobs"]))

    def test_view_configured_2_builds_and_all(self):
        apiserveroutput.views.update({"confiview" : BuildFilter(".*\.nightly")})
        out, api = self.create()
        out.on_update({"build" :  { "pz.tip.app.continuous" : {"request_status" : "ok", "result" : "success"},
                                    "pz.tip.app.nightly" : {"request_status" : "ok", "result" : "success"} }})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(1, len(result[1]["jobs"]))
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEquals(result[0], 200)
        self.assertEquals(2, len(result[1]["jobs"]))
