__author__ = 'florianseidl'

import env
from jenkinscollector import JenkinsClient, JenkinsCollector
from collector import HttpClient
from urllib.request import HTTPError, URLError
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock
import os
from datetime import datetime

class TestJenkinsClient(TestCase):
    json_str = '{ "foo": "bar" }'

    def test_json_decode(self):
        c = JenkinsClient("http://foo.bar", HttpClient())
        c.http_client.open_and_read = MagicMock(spec=(""), return_value=self.json_str)
        res = c.latest_build("myjob")
        self.assertEquals(res, {"foo" : "bar"}, res)
        c.http_client.open_and_read.assert_called_with("http://foo.bar/job/myjob/lastBuild/api/json?depth=0")


    def test_http_exception_500(self):
        c = JenkinsClient("http://foo.bar", HttpClient())
        c.http_client.open_and_read = Mock(spec=(""), return_value=self.json_str)
        c.http_client.open_and_read.side_effect = HTTPError("http://foo.bar", 500, None, None, None)
        with self.assertRaises(HTTPError):
            c.latest_build("myjob")
        self.assertEqual(c.http_client.open_and_read.call_count, 1)

class TestJenkinsCollector(TestCase):
    job_name_success = "mvp.mct.vermittler-produkt.continuous"
    job_name_failed = "mvp.mct.vermittler-orchestrierung_commons.continuous"
    job_name_unstable = "kd.esta.integrate.template.was3.it"
    view_name_1 = "mvp/view/mct-new/view/mct-develop/view/continuous"
    view_name_2 = "kd/view/esta.integrate"
    view_name_3 = "pz/view/tip/view/tip-all"
    url = "https://ci.sbb.ch"

    def read(self, file_name):
        with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name)) as f:
            return f.read()

    def do_collect_jobs(self, job_name):
        col = JenkinsCollector(self.url, job_names= (job_name, ))
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value=self.read(job_name))
        status = col.collect()
        self.assertIsNotNone(status[job_name])
        return status

    def do_collect_jobs_error(self, job_name, error):
        col = JenkinsCollector(self.url, job_names= (job_name, ))
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""),side_effect=error)
        status = col.collect()
        self.assertIsNotNone(status[job_name])
        return status

    def test_request_status_ok(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(status[self.job_name_success]["request_status"], "ok")

    def test_build_result_successs(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(status[self.job_name_success]["result"], "success")

    def test_building(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(status[self.job_name_success]["building"], False)

    def test_number(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(status[self.job_name_success]["number"], 515)

    def test_timestamp(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(status[self.job_name_success]["timestamp"], datetime(2016, 3, 19, 23, 16, 22, 182000))

    def test_build_result_failed(self):
        status = self.do_collect_jobs(self.job_name_failed)
        self.assertEqual(status[self.job_name_failed]["result"], "failure")

    def test_build_result_unstable(self):
        status = self.do_collect_jobs(self.job_name_unstable)
        self.assertEqual(status[self.job_name_unstable]["result"], "unstable")

    def test_build_request_status_error(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 500, None, None, None))
        self.assertEqual(status["foo"]["request_status"], "error")

    def test_build_request_status_not_found(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 404, None, None, None))
        self.assertEqual(status["foo"]["request_status"], "not_found")

    def test_build_request_status_url_error(self):
        # for instance host not found
        status = self.do_collect_jobs_error("foo", URLError("kaputt"))
        self.assertEqual(status["foo"]["request_status"], "error")

    def do_collect_views(self, expected_nr_jobs, view_name, error=None):
        col = JenkinsCollector(self.url, view_names = (view_name, ))
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""),
                                                return_value= self.read(view_name.replace("/", "__")) if not error else None,
                                                side_effect = error)
        build = col.collect()
        self.assertEqual(len(build), expected_nr_jobs)
        return build

    def test_collect_views_count(self):
        self.do_collect_views(66, view_name=self.view_name_1)

    def test_collect_views_http_error(self):
        self.do_collect_views(1, view_name=self.view_name_1, error=HTTPError(self.url, 500, None, None, None))

    def test_collect_views_url_error(self):
        self.do_collect_views(1, view_name=self.view_name_1, error=URLError("kaputt"))

    def test_collect_views_count_failure(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "failure"]), 4)

    def test_collect_views_count_success(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]), 62)

    def test_collect_views_count_unstabe(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "unstable"]), 4)

    def test_collect_views_count_success_2(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]), 5)

    def test_collect_views_count_other(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "other"]), 1)

    def test_collect_views_count_success_3(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        print (build)
        self.assertEquals(len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]), 9)

    def test_collect_jobs_and_views(self):
        col = JenkinsCollector(self.url, job_names= (self.job_name_success, self.job_name_failed), view_names=(self.view_name_2, ))
        col.jenkins.http_client.open_and_read = Mock(spec=(""), side_effect=[self.read(self.view_name_2.replace("/", "__")),
                                                                    self.read(self.job_name_success),
                                                                    self.read(self.job_name_failed)])
        status = col.collect()
        self.assertEquals(len(status), 11)

    def test_build_request_status_http_error(self):
        status = self.do_collect_views(1, "foo", HTTPError("", 500, "kaputt", None, None))
        print(status)
        self.assertEqual(status["all"]["request_status"], "error")

if __name__ == '__main__':
    main()