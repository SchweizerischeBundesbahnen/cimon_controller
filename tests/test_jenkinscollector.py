__author__ = 'florianseidl'

import os
import re
from datetime import datetime
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError, URLError

from cimon import Health, RequestStatus
from collector import HttpClient
from jenkinscollector import JenkinsClient, JenkinsCollector


def read(file_name):
    with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name), encoding='utf-8') as f:
        return f.read()


def to_filename(name):
    return name.replace("/", "__")


class TestJenkinsClient(TestCase):
    json_str = '{ "foo": "bar" }'

    def test_json_decode(self):
        c = JenkinsClient(HttpClient("http://foo.bar"))
        c.http_client.open_and_read = MagicMock(spec=(""), return_value=self.json_str)
        res = c.latest_build("myjob")
        self.assertEqual(res, {"foo": "bar"})
        c.http_client.open_and_read.assert_called_with("/job/myjob/lastBuild/api/json?depth=0")

    def test_http_exception_500(self):
        c = JenkinsClient(HttpClient("http://foo.bar"))
        c.http_client.open_and_read = Mock(spec=(""), return_value=self.json_str)
        c.http_client.open_and_read.side_effect = HTTPError("http://foo.bar", 500, None, None, None)
        with self.assertRaises(HTTPError):
            c.latest_build("myjob")
        self.assertEqual(1, c.http_client.open_and_read.call_count)


class TestJenkinsCollectorJobs(TestCase):
    job_name_success = "mvp.mct.vermittler-produkt.continuous"
    job_name_failed = "mvp.mct.vermittler-orchestrierung_commons.continuous"
    job_name_unstable = "kd.esta.integrate.template.was3.it"
    job_name_building = "kd.sid.sid-library-ios.continuous"
    job_name_noname = 'pt.cisi.orga_common_check_develop'
    url = "https://ci.sbb.ch"

    def do_collect_jobs(self, job_name, mock_open_and_read=None):
        col = JenkinsCollector(mock_jenkins_client(self.url, mock_open_and_read if mock_open_and_read != None else self.mock_open_and_read),
                               self.url,
                               job_names=(job_name,))
        status = col.collect()
        self.assertIsNotNone(status[("ci.sbb.ch", job_name)])
        return status

    def do_collect_jobs_error(self, job_name, error):
        return self.do_collect_jobs(job_name=job_name, mock_open_and_read=MagicMock(spec=(""), side_effect=error))

    def mock_open_and_read(self, request_path, folder=""):
        match = re.match("/job/(.*)/lastBuild/api/json", request_path)
        return read(folder + to_filename(match.group(1).strip("/")))

    def test_request_status_ok(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(RequestStatus.OK, status[("ci.sbb.ch", self.job_name_success)].request_status)

    def test_build_result_successs(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(Health.HEALTHY, status[("ci.sbb.ch", self.job_name_success)].health)

    def test_building(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertFalse(status[("ci.sbb.ch", self.job_name_success)].active)

    def test_number(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertEqual(515, status[("ci.sbb.ch", self.job_name_success)].number)

    def test_timestamp(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertAlmostEquals(datetime(2016, 3, 19, 23, 16, 22, 182000).timestamp(),
                                status[("ci.sbb.ch", self.job_name_success)].timestamp.timestamp(),
                                places=3)

    def test_culprits(self):
        status = self.do_collect_jobs(self.job_name_failed)
        self.assertEqual(["Diacon Gilles"], status[("ci.sbb.ch", self.job_name_failed)].names)

    def test_build_result_failed(self):
        status = self.do_collect_jobs(self.job_name_failed)
        self.assertEqual(Health.SICK, status[("ci.sbb.ch", self.job_name_failed)].health)

    def test_build_result_unstable(self):
        status = self.do_collect_jobs(self.job_name_unstable)
        self.assertEqual(Health.UNWELL, status[("ci.sbb.ch", self.job_name_unstable)].health)

    def test_build_request_status_error(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 500, None, None, None))
        self.assertEqual(RequestStatus.ERROR, status[("ci.sbb.ch", "foo")].request_status)

    def test_build_request_status_not_found(self):
        status = self.do_collect_jobs_error("foo", HTTPError(self.url, 404, None, None, None))
        self.assertEqual(RequestStatus.NOT_FOUND, status[("ci.sbb.ch", "foo")].request_status)

    def test_build_request_status_url_error(self):
        # for instance host not found
        status = self.do_collect_jobs_error("foo", URLError("kaputt"))
        self.assertEqual(RequestStatus.ERROR, status[("ci.sbb.ch", "foo")].request_status)

    def test_build_result_not_building(self):
        status = self.do_collect_jobs(self.job_name_success)
        self.assertFalse(status[("ci.sbb.ch", self.job_name_success)].active)

    def test_build_result_building(self):
        status = self.do_collect_jobs(self.job_name_building)
        self.assertTrue(status[("ci.sbb.ch", self.job_name_building)].active)

    def test_build_result_building_no_result(self):
        status = self.do_collect_jobs(self.job_name_building)
        self.assertEqual(Health.OTHER, status[("ci.sbb.ch", self.job_name_building)].health)

    def test_build_job_first_success_then_building(self):
        filter = lambda x: x.replace("\"building\":true", "\"building\":false").replace("\"result\":null",
                                                                                        "\"result\":\"SUCCESS\"")
        col = JenkinsCollector(mock_jenkins_client(self.url, MagicMock(spec=(""), return_value=filter(read(self.job_name_building)))),
                               self.url,
                               job_names=(self.job_name_building,))
        # first request - not building yet
        status = col.collect()
        self.assertEqual(Health.HEALTHY, status[("ci.sbb.ch", self.job_name_building)].health)
        self.assertFalse(status[("ci.sbb.ch", self.job_name_building)].active)

        # second request - building now
        col.job_reader.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value = read(self.job_name_building))
        status = col.collect()
        self.assertEqual(Health.HEALTHY, status[("ci.sbb.ch", self.job_name_building)].health)
        self.assertTrue(status[("ci.sbb.ch", self.job_name_building)].active)
        return col

    def test_build_job_first_success_then_building_then_falied(self):
        col = self.test_build_job_first_success_then_building()

        # third request - failed
        filter = lambda x: x.replace("\"building\":true", "\"building\":false").replace("\"result\":null",
                                                                                        "\"result\":\"FAILURE\"")
        col.job_reader.jenkins.http_client.open_and_read = MagicMock(spec=(""), return_value=filter(read(self.job_name_building)))
        status = col.collect()
        self.assertEqual(Health.SICK, status[("ci.sbb.ch", self.job_name_building)].health)
        self.assertFalse(status[("ci.sbb.ch", self.job_name_building)].active)

    def test_job_name_from_url(self):
        col = JenkinsCollector(mock_jenkins_client(self.url, self.mock_open_and_read),
                               self.url,
                               job_names=(self.job_name_noname,),
                               job_name_from_url_pattern='https://ci.sbb.ch/job/(.+)/\d+/')
        status = col.collect()
        self.assertIsNotNone(status[("ci.sbb.ch", 'pt.cisi.orga/job/common-check/job/develop')])


class TestJenkinsCollectorViews(TestCase):
    view_name_1 = "mvp/view/mct-new/view/mct-develop/view/continuous"
    view_name_2 = "kd/view/esta.integrate"
    view_name_3 = "pz/view/tip/view/tip-all"
    view_name_building = "kd/view/sid"
    view_name_depth_2 = "pz/view/touri"
    view_name_noname = "pt.view.cisi/view/01-build/view/91_xfd"
    url = "https://ci.sbb.ch"

    def do_collect_views(self, expected_nr_jobs, view_name, mock_open_and_read=None):
        col = JenkinsCollector(jenkins=mock_jenkins_client(self.url, mock_open_and_read if mock_open_and_read != None else self.mock_open_and_read),
                               base_url=self.url,
                               view_names=(view_name,))
        builds = col.collect()
        self.assertEqual(len(builds), expected_nr_jobs)
        return builds

    def do_collect_views_error(self, expected_nr_jobs, view_name, error):
        return self.do_collect_views(expected_nr_jobs=expected_nr_jobs,
                                     view_name=view_name,
                                     mock_open_and_read=MagicMock(spec=(""), side_effect=error))

    def mock_open_and_read(self, request_path, folder=""):
        match = re.match("/view/(.*)/api/json", request_path)
        return read(folder + to_filename(match.group(1).strip("/")))

    def test_collect_views_count(self):
        self.do_collect_views(66, view_name=self.view_name_1)

    def test_collect_views_http_error(self):
        self.do_collect_views_error(1, view_name=self.view_name_1, error=HTTPError(self.url, 500, None, None, None))

    def test_collect_views_url_error(self):
        self.do_collect_views_error(1, view_name=self.view_name_1, error=URLError("kaputt"))

    def test_collect_views_count_failure(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        self.assertEqual(4, len([k for (k, v) in build.items() if v.health == Health.SICK]))

    def test_collect_views_count_success(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        self.assertEqual(62, len([k for (k, v) in build.items() if v.health == Health.HEALTHY]))

    def test_collect_views_count_unstabe(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        self.assertEqual(4, len([k for (k, v) in build.items() if v.health == Health.UNWELL]))

    def test_collect_views_count_success_2(self):
        build = self.do_collect_views(9, view_name=self.view_name_2)
        self.assertEqual(5, len([k for (k, v) in build.items() if v.health == Health.HEALTHY]))

    def test_collect_views_count_disabled(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        self.assertEqual(1, len([k for (k, v) in build.items() if v.request_status == RequestStatus.NOT_FOUND]))

    def test_collect_views_count_success_3(self):
        build = self.do_collect_views(10, view_name=self.view_name_3)
        self.assertEqual(9, len([k for (k, v) in build.items() if v.health == Health.HEALTHY]))

    def test_build_request_status_http_error(self):
        status = self.do_collect_views_error(1, "foo", HTTPError("", 500, "kaputt", None, None))
        self.assertEqual(status[("ci.sbb.ch", "foo")].request_status, RequestStatus.ERROR)

    def test_collect_view_building(self):
        build = self.do_collect_views(22, view_name=self.view_name_building)
        self.assertEqual(6, len([k for (k, v) in build.items() if v.active]))

    def test_collect_view_with_numbers(self):
        build = self.do_collect_views(6, view_name=self.view_name_depth_2)
        self.assertEqual(4, len([k for (k, v) in build.items() if v.number]))

    def test_collect_view_with_timestamp(self):
        build = self.do_collect_views(6, view_name=self.view_name_depth_2)
        self.assertEqual(4, len([k for (k, v) in build.items() if v.timestamp]))

    def test_collect_view_with_culprits(self):
        build = self.do_collect_views(6, view_name=self.view_name_depth_2)
        self.assertEqual(3, len([k for (k, v) in build.items() if v.names]))

    def test_collect_view_without_numbers(self):
        build = self.do_collect_views(66, view_name=self.view_name_1)
        self.assertEqual(0, len([k for (k, v) in build.items() if v.number]))

    def test_build_result_view_not_building(self):
        build = self.do_collect_views(22, view_name=self.view_name_building)
        self.assertEqual(6, len([k for (k, v) in build.items() if v.active]))

    def test_job_name_from_url(self):
        col = JenkinsCollector(mock_jenkins_client(self.url, self.mock_open_and_read),
                               self.url,
                               view_names=(self.view_name_noname,),
                               job_name_from_url_pattern='https://ci.sbb.ch/job/(.+)')
        builds = col.collect()
        print(str(builds))


class TestJenkinsCollectorNestedViews(TestCase):
    view_name_nested = "mvp/view/zvs-drittgeschaeft"
    view_name_nested_loop = "mvp/view/zvs-drittgeschaeft-fake-broken-with-loop"

    def setUp(self):
        self.testViews = TestJenkinsCollectorViews()

    def mock_open_and_read_for_nested_view(self, request_path):
        return self.testViews.mock_open_and_read(request_path, folder="nested_view/")

    def test_nested_view(self):
        self.testViews.do_collect_views(124, view_name=self.view_name_nested,
                                        mock_open_and_read=self.mock_open_and_read_for_nested_view)

    def test_nested_view_loop(self):
        self.testViews.do_collect_views(124, view_name=self.view_name_nested_loop,
                                        mock_open_and_read=self.mock_open_and_read_for_nested_view)


class TestJenkinsCollectorJobsAndViews(TestCase):

    def setUp(self):
        self.testJobs = TestJenkinsCollectorJobs()
        self.testViews = TestJenkinsCollectorViews()

    def test_collect_jobs_and_views(self):
        content_by_key = {
            self.testJobs.job_name_success: read(to_filename(self.testJobs.job_name_success)),
            self.testJobs.job_name_failed: read(to_filename(self.testJobs.job_name_failed)),
            self.testViews.view_name_2: read(to_filename(self.testViews.view_name_2))
        }
        col = JenkinsCollector(jenkins=mock_jenkins_client(self.testJobs.url, Mock(spec=(""), side_effect=lambda x:
        [content_by_key[k] for k in content_by_key if k in x][0])),
                               base_url=self.testJobs.url,
                               job_names=(self.testJobs.job_name_success, self.testJobs.job_name_failed),
                               view_names=(self.testViews.view_name_2,))
        status = col.collect()
        self.assertEqual(11, len(status))


class TestJenkinsCollectorFolders(TestCase):
    folder_name_1 = "PN_ES"
    folder_name_2 = "pt.cisi.orga"
    url = "https://ci.sbb.ch"

    def test_collect_folder(self):
        build = self.do_collect_folder(self.folder_name_1)
        self.assertEqual(101 + 41, len(build))

    def test_collect_folder_healthy(self):
        build = self.do_collect_folder(self.folder_name_1)
        self.assertEqual(Health.HEALTHY, build[("ci.sbb.ch", "PN_ES/aps-boot/master")].health)

    def test_collect_folder_request_status(self):
        build = self.do_collect_folder(self.folder_name_1)
        self.assertEqual(RequestStatus.OK, build[("ci.sbb.ch", "PN_ES/aps-boot/master")].request_status)

    def test_collect_folder_sick(self):
        build = self.do_collect_folder(self.folder_name_1)
        self.assertEqual(Health.SICK,
                         build[("ci.sbb.ch", "PN_ES/aps-safety-logic/feature/refactorocs_attempt1")].health)

    def test_collect_folder_active(self):
        build = self.do_collect_folder(self.folder_name_1)
        self.assertTrue(build[("ci.sbb.ch", "PN_ES/aps-safety-logic/feature/refactorocs_attempt1")].active)
        self.assertFalse(build[("ci.sbb.ch", "PN_ES/aps-safety-logic/master")].active)

    def test_collect_folder_number(self):
        build = self.do_collect_folder(self.folder_name_2)
        self.assertEqual(55, build[("ci.sbb.ch", "pt.cisi.orga/angebot/develop")].number)

    def test_collect_folder_duration(self):
        build = self.do_collect_folder(self.folder_name_2)
        self.assertEqual(1209369, build[("ci.sbb.ch", "pt.cisi.orga/angebot/develop")].duration)

    def test_collect_folder_timestamp(self):
        build = self.do_collect_folder(self.folder_name_2)
        self.assertEqual(datetime.fromtimestamp(1592443260.226),
                         build[("ci.sbb.ch", "pt.cisi.orga/angebot/develop")].timestamp)

    def do_collect_folder(self, folder_name):
        col = JenkinsCollector(mock_jenkins_client(self.url, self.mock_open_and_read),
                               self.url,
                               folder_names=(folder_name,))
        return col.collect()

    def mock_open_and_read(self, request_path):
        match = re.match("/job/(.*)/api/json", request_path)
        return read("folder/" + to_filename(match.group(1).strip("/")))


class TestJenkinsCollectorMultibranch(TestCase):
    multibranch_pipeline_name = 'mvp.bats.vermittler-automat-tvm.ui-tests'
    url = "https://ci.sbb.ch"

    def test_collect_multibranch_pipeline(self):
        build = self.do_collect_multibranch_pipeline(self.multibranch_pipeline_name)
        self.assertEqual(2, len(build))

    def test_collect_multibranch_pipeline_healthy(self):
        build = self.do_collect_multibranch_pipeline(self.multibranch_pipeline_name)
        self.assertEqual(Health.HEALTHY,
                         build[("ci.sbb.ch", "mvp.bats.vermittler-automat-tvm.ui-tests/develop")].health)

    def test_collect_multibranch_pipeline_request_status(self):
        build = self.do_collect_multibranch_pipeline(self.multibranch_pipeline_name)
        self.assertEqual(RequestStatus.OK,
                         build[("ci.sbb.ch", "mvp.bats.vermittler-automat-tvm.ui-tests/develop")].request_status)

    def test_collect_multibranch_pipeline_active(self):
        build = self.do_collect_multibranch_pipeline(self.multibranch_pipeline_name)
        self.assertFalse(build[("ci.sbb.ch", "mvp.bats.vermittler-automat-tvm.ui-tests/bugfix/20.1.3")].active)

    def do_collect_multibranch_pipeline(self, multibranch_pipeline_name):
        col = JenkinsCollector(mock_jenkins_client(self.url, self.mock_open_and_read),
                               self.url,
                               multibranch_pipeline_names=(multibranch_pipeline_name,))
        return col.collect()

    def mock_open_and_read(self, request_path):
        match = re.match("/job/(.*)/api/json", request_path)
        return read("multibranch/" + to_filename(match.group(1).strip("/")))


def mock_jenkins_client(base_url, mock_open_and_read):
    jenkins = JenkinsClient(http_client=HttpClient(base_url=base_url))
    jenkins.http_client.open_and_read = mock_open_and_read
    return jenkins


if __name__ == '__main__':
    main()
