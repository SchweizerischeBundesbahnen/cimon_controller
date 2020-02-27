__author__ = 'florianseidl'

import collections
import os
from types import SimpleNamespace
from unittest import TestCase

import apiserveroutput
from apiserveroutput import *

class TestApiServerOutput(TestCase):
    job_name_success = "mvp.mct.vermittler-produkt.continuous"
    job_name_failed = "mvp.mct.vermittler-orchestrierung_commons.continuous"
    job_name_unstable = "kd.esta.integrate.template.was3.it"
    job_name_building = "kd.sid.sid-library-ios.continuous"
    view_name_3 = "pz/view/tip/view/tip-all"

    def setUp(self):
        apiserveroutput.server = SimpleNamespace() # pretend there is an http server to avioid starting one
        set_shared_status({})

    def create(self):
        return ApiServerOutput(), ApiServer()

    def read(self, file_name):
        with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name), encoding='utf-8') as f:
            return json.load(f)

    def do_test_query_jobs_from_api(self, job_name, values):
        out, api = self.create()
        out.on_update({ ("ci.sbb.ch", job_name) : values })
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0" % job_name)
        self.assertEqual(result[0], 200)
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
            self.assertEqual(api_response_part, original_part)

    def __find_partial_dict_in_list__(self, partial, list_of_dicts):
        for d in list_of_dicts:
            if isinstance(d, dict):
                for k in partial:
                    if k in d and partial[k] == d[k]:
                        return True
        return False

    def test_request_status_ok(self):
        JobStatus(RequestStatus.OK, Health.HEALTHY)
        self.do_test_query_jobs_from_api(self.job_name_success, JobStatus(RequestStatus.OK, Health.HEALTHY))

    def test_request_status_failed(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, JobStatus(RequestStatus.OK, Health.SICK))

    def test_request_status_unstable(self):
        self.do_test_query_jobs_from_api(self.job_name_unstable, JobStatus(RequestStatus.OK, Health.UNWELL))

    def test_request_building_true(self):
        self.do_test_query_jobs_from_api(self.job_name_building, JobStatus(RequestStatus.OK, Health.OTHER, True))

    def test_request_number(self):
        self.do_test_query_jobs_from_api(self.job_name_success, JobStatus(RequestStatus.OK, Health.HEALTHY, number=515))

    def test_request_culprits(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, JobStatus(RequestStatus.OK, Health.SICK, names=["Diacon Gilles"]))

    def test_request_timestamp(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, JobStatus(RequestStatus.OK, Health.SICK, timestamp=datetime.fromtimestamp(1458426704.059)))

    def test_request_all(self):
        self.do_test_query_jobs_from_api(self.job_name_failed, JobStatus(RequestStatus.OK, Health.SICK, active=False, names=["Diacon Gilles"], timestamp=datetime.fromtimestamp(1458426704.059), number=554))

    def test_not_found(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch",self.job_name_success) : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/job/gibtsgarnicht/lastBuild/api/json?depth=0" )
        self.assertEqual(result[0], 404)

    def test_not_found_in_result(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch",self.job_name_success) : JobStatus(RequestStatus.NOT_FOUND)})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEqual(result[0], 404)

    def test_error_in_result(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch",self.job_name_success) : JobStatus(RequestStatus.ERROR)})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEqual(result[0], 500)

    def test_error_in_result_all(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","all") : JobStatus(RequestStatus.ERROR)})
        result = api.handle_get("/job/%s/lastBuild/api/json?depth=0"% self.job_name_success )
        self.assertEqual(result[0], 500)

    def test_view_all(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(1, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_all_2_builds(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY),
                       ("ci.sbb.ch","pz.tip.app.nightly") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(2, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_not_found(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/gibtsgarnicht/api/json?depth=0")
        self.assertEqual(result[0], 404)

    def test_view_error_job(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.ERROR)})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1], {'description': None, 'jobs': [{'name': 'pz.tip.app.continuous', 'color': 'disabled'}]})

    def test_view_no_job(self):
        out, api = self.create()
        out.on_update({})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(0, len(result[1]["jobs"]))

    def test_view_all_error(self):
        out, api = self.create()
        out.on_update({("ci.sbb.ch","all") : JobStatus(RequestStatus.ERROR)})
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 500)

    def test_view_configured_2_builds(self):
        views.update({"confiview" : re.compile(".*\.nightly")})
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY),
                       ("ci.sbb.ch","pz.tip.app.nightly") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(1, len(result[1]["jobs"]))
        self.assert_all_in_original_view(self.view_name_3, result[1])

    def test_view_configured_2_builds_match_none(self):
        views.update({"confiview" : re.compile("hotzenplotz")})
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY),
                       ("ci.sbb.ch","pz.tip.app.nightly") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(0, len(result[1]["jobs"]))

    def test_view_configured_2_builds_and_all(self):
        views.update({"confiview" : re.compile(".*\.nightly")})
        out, api = self.create()
        out.on_update({("ci.sbb.ch","pz.tip.app.continuous") : JobStatus(RequestStatus.OK, Health.HEALTHY),
                       ("ci.sbb.ch","pz.tip.app.nightly") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        result = api.handle_get("/view/confiview/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(1, len(result[1]["jobs"]))
        result = api.handle_get("/view/all/api/json?depth=0")
        self.assertEqual(result[0], 200)
        self.assertEqual(2, len(result[1]["jobs"]))
