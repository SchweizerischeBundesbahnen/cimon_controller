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
        c = JenkinsClient(HttpClient("http://foo.bar"))
        c.http_client.open_and_read = MagicMock(spec=(""), return_value=self.json_str)
        res = c.latest_build("myjob")
        self.assertEquals(res, {"foo" : "bar"})
        c.http_client.open_and_read.assert_called_with("/job/myjob/lastBuild/api/json?depth=0")


    def test_http_exception_500(self):
        c = JenkinsClient(HttpClient("http://foo.bar"))
        c.http_client.open_and_read = Mock(spec=(""), return_value=self.json_str)
        c.http_client.open_and_read.side_effect = HTTPError("http://foo.bar", 500, None, None, None)
        with self.assertRaises(HTTPError):
            c.latest_build("myjob")
        self.assertEqual(1, c.http_client.open_and_read.call_count)

class TestJenkinsCollector(TestCase):
    job_name_success = "mvp.mct.vermittler-produkt.continuous"
    job_name_failed = "mvp.mct.vermittler-orchestrierung_commons.continuous"
    job_name_unstable = "kd.esta.integrate.template.was3.it"
    job_name_building = "kd.sid.sid-library-ios.continuous"
    view_name_1 = "mvp/view/mct-new/view/mct-develop/view/continuous"
    view_name_2 = "kd/view/esta.integrate"
    view_name_3 = "pz/view/tip/view/tip-all"
    view_name_building = "kd_view_sid"
    url = "https://ci.sbb.ch"

    def read(self, file_name):
        with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name)) as f:
            return f.read()

    def do_collect_jobs(self, job_name):
        col = JenkinsCollector(self.url, job_names= (job_name, ))
        retval = self.read(job_name)
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value=retval)
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
        self.assertEqual("ok", status[self.job_name_success]["request_status"])

    def test_build_result_successs(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual("success", status[self.job_name_success]["result"])

    def test_building(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertFalse(status[self.job_name_success]["building"])

    def test_number(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(515, status[self.job_name_success]["number"])

    def test_timestamp(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(datetime(2016, 3, 19, 23, 16, 22, 182000), status[self.job_name_success]["timestamp"])

    def test_build_result_failed(self):
        status = self.do_collect_jobs(self.job_name_failed)
        self.assertEqual("failure", status[self.job_name_failed]["result"])

    def test_build_result_unstable(self):
        status = self.do_collect_jobs(self.job_name_unstable)
        self.assertEqual("unstable", status[self.job_name_unstable]["result"])

    def test_build_request_status_error(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 500, None, None, None))
        self.assertEqual("error", status["foo"]["request_status"])

    def test_build_request_status_not_found(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 404, None, None, None))
        self.assertEqual("not_found", status["foo"]["request_status"])

    def test_build_request_status_url_error(self):
        # for instance host not found
        status = self.do_collect_jobs_error("foo", URLError("kaputt"))
        self.assertEqual("error", status["foo"]["request_status"])

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
        self.assertEquals(4, len([k for (k, v) in build.items() if "result" in v and v["result"] == "failure"]))

    def test_collect_views_count_success(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        self.assertEquals(62, len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]))

    def test_collect_views_count_unstabe(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        self.assertEquals(4, len([k for (k, v) in build.items() if "result" in v and v["result"] == "unstable"]))

    def test_collect_views_count_success_2(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        self.assertEquals(5, len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]))

    def test_collect_views_count_disabled(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        self.assertEquals(1, len([k for (k, v) in build.items() if v["request_status"] == "not_found"]))

    def test_collect_views_count_success_3(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        self.assertEquals(9, len([k for (k, v) in build.items() if "result" in v and v["result"] == "success"]))

    def test_collect_jobs_and_views(self):
        col = JenkinsCollector(self.url, job_names= (self.job_name_success, self.job_name_failed), view_names=(self.view_name_2, ))
        content_by_key = {
                            self.job_name_success : self.read(self.job_name_success),
                            self.job_name_failed : self.read(self.job_name_failed),
                            self.view_name_2 : self.read(self.view_name_2.replace("/", "__"))
        }
        col.jenkins.http_client.open_and_read = Mock(spec=(""), side_effect=lambda x : [content_by_key[k] for k in content_by_key if k in x][0])
        status = col.collect()
        self.assertEquals(11, len(status))


    def test_build_request_status_http_error(self):
        status = self.do_collect_views(1, "foo", HTTPError("", 500, "kaputt", None, None))
        self.assertEqual(status["all"]["request_status"], "error")

    def test_build_result_not_building(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertFalse(status[self.job_name_success]["building"])

    def test_build_result_view_not_building(self):
        build = self.do_collect_views(22, view_name=self.view_name_building)
        self.assertEquals(0, len([k for (k, v) in build.items() if "buidling" in v and v["building"]]))

    def test_build_result_building(self):
        status = self.do_collect_jobs(self.job_name_building)
        self.assertTrue(status[self.job_name_building]["building"])

    def test_collect_view_building(self):
        build = self.do_collect_views(22, view_name=self.view_name_building)
        self.assertEquals(6, len([k for (k, v) in build.items() if "building" in v and v["building"]]))

    def test_build_result_building_no_result(self):
        status = self.do_collect_jobs(self.job_name_building)
        self.assertEquals("other", status[self.job_name_building]["result"])

    def test_build_job_first_success_then_building(self):
        col = JenkinsCollector(self.url, job_names= (self.job_name_building, ))
        filter=lambda x : x.replace("\"building\":true", "\"building\":false").replace("\"result\":null", "\"result\":\"SUCCESS\"")
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value = filter(self.read(self.job_name_building)))
        # first request - not building yet
        status = col.collect()
        self.assertEquals("success", status[self.job_name_building]["result"])
        self.assertFalse(status[self.job_name_building]["building"])

        # second request - building now
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value = self.read(self.job_name_building))
        status = col.collect()
        self.assertEquals("success", status[self.job_name_building]["result"])
        self.assertTrue(status[self.job_name_building]["building"])
        return col

    def test_build_job_first_success_then_building_then_falied(self):
        col = self.test_build_job_first_success_then_building()

        # third request - failed
        filter=lambda x : x.replace("\"building\":true", "\"building\":false").replace("\"result\":null", "\"result\":\"FAILURE\"")
        col.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value = filter(self.read(self.job_name_building)))
        status = col.collect()
        self.assertEquals("failure", status[self.job_name_building]["result"])
        self.assertFalse(status[self.job_name_building]["building"])

if __name__ == '__main__':
    main()