__author__ = 'florianseidl'

import env
from newreliccollector import NewRelicApplicationsCollector, NewRelicAlertsCollector
from urllib.request import HTTPError, URLError
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock
import os
import json
from cimon import JobStatus,Health,RequestStatus

def read(file_name):
    with open("%s/testdata/%s" % (os.path.dirname(__file__), file_name), encoding='utf-8') as f:
        return f.read()

class TestAlertsCollector(TestCase):
    result_file = "alerts.json"
    url = "https://api.newrelic.com"

    def do_collect_alerts(self, policy_name_pattern=None, condition_name_pattern=None, overrideById={}):
        col = NewRelicAlertsCollector(base_url=self.url,
                                      api_key="sometoken",
                                      policy_name_pattern=policy_name_pattern,
                                      condition_name_pattern=condition_name_pattern)
        self.jsonStr = self.__override__(read("alerts_violations.json"), overrideById)
        col.new_relic_client.http_client.open_and_read = self.mock_open_and_read
        return col.collect()

    def __override__(self, jsonStr, overrideById):
        parsedJson = json.loads(jsonStr)
        if parsedJson["violations"]:
            parsedJson["violations"] = [self.__merge__(alert, overrideById) for alert in parsedJson["violations"]]
        return json.dumps(parsedJson)

    def __merge__(self, alert, overrideById):
        if alert["id"] in overrideById:
            alert.update(overrideById[alert["id"]])
        return alert

    def do_collect_jobs_error(self, error):
        col = NewRelicAlertsCollector(base_url=self.url, api_key="sometoken")
        col.new_relic_client.http_client.open_and_read = MagicMock(spec=(""),side_effect=error)
        return col.collect()

    def mock_open_and_read(self, request_path):
        return self.jsonStr

    def test_request_status_ok(self):
        status = self.do_collect_alerts()
        self.assertEqual(RequestStatus.OK, status[("api.newrelic.com", "touri-tour_dev-monitor")].request_status)

    def test_health_sick(self):
        status = self.do_collect_alerts()
        self.assertEqual(Health.SICK, status[("api.newrelic.com", "touri-tour_dev-monitor")].health)

    def test_health_unwell(self):
        status = self.do_collect_alerts()
        self.assertEqual(Health.UNWELL, status[("api.newrelic.com", "Heap memory usage (High)")].health)

    def test_health_info(self):
        status = self.do_collect_alerts(overrideById={53962109:{"priority": "Info"}})
        self.assertEqual(Health.HEALTHY, status[("api.newrelic.com", "touri-lidi_dev-monitor")].health)

    def test_only_last_event_valid(self):
        status = self.do_collect_alerts(overrideById={53962210:{"priority": "Info"}})
        self.assertEqual(Health.SICK, status[("api.newrelic.com", "touri-cus-ftp_prod-monitor")].health)

    def test_only_last_event_valid_all(self):
        status = self.do_collect_alerts(overrideById={53962210:{"priority": "Info"},53962212:{"priority": "Info"}})
        self.assertEqual(Health.HEALTHY, status[("api.newrelic.com", "touri-cus-ftp_prod-monitor")].health)

    def test_only_priorty_wins_over_last(self):
        status = self.do_collect_alerts(overrideById={53962212:{"priority": "Info"}})
        self.assertEqual(Health.SICK, status[("api.newrelic.com", "touri-cus-ftp_prod-monitor")].health)

    def test_fiter_policy(self):
        status = self.do_collect_alerts(policy_name_pattern="touri-team_alert-policy_prod")
        self.assertNotIn(("api.newrelic.com", "touri-tour_dev-monitor"), status)
        self.assertIn(("api.newrelic.com", "touri-cus-ftp_prod-monitor"), status)

    def test_fiter_policy_regex(self):
        status = self.do_collect_alerts(policy_name_pattern=".*_prod")
        self.assertNotIn(("api.newrelic.com", "touri-tour_dev-monitor"), status)
        self.assertIn(("api.newrelic.com", "touri-cus-ftp_prod-monitor"), status)

    def test_fiter_condition_app_name(self):
        status = self.do_collect_alerts(condition_name_pattern=".*cus-ftp_prod.*")
        self.assertNotIn(("api.newrelic.com", "touri-tour_dev-monitor"), status)
        self.assertIn(("api.newrelic.com", "touri-cus-ftp_prod-monitor"), status)

    def test_fiter_condition_stage(self):
        status = self.do_collect_alerts(condition_name_pattern=".*_prod-.*")
        self.assertNotIn(("api.newrelic.com", "touri-tour_dev-monitor"), status)
        self.assertIn(("api.newrelic.com", "touri-cus-ftp_prod-monitor"), status)

class TestNewRelicApplicationsCollector(TestCase):
    result_file = "application.json"
    url = "https://api.newrelic.com"

    def do_collect_health(self, application_name_pattern=None):
        col = NewRelicApplicationsCollector(base_url=self.url, api_key="sometoken", application_name_pattern=application_name_pattern)
        col.new_relic_client.http_client.open_and_read = self.mock_open_and_read
        return col.collect()

    def do_collect_jobs_error(self, error):
        col = NewRelicApplicationsCollector(base_url=self.url, api_key="sometoken", application_name_pattern=r'.*')
        col.new_relic_client.http_client.open_and_read = MagicMock(spec=(""),side_effect=error)
        return col.collect()

    def mock_open_and_read(self, request_path):
        jsonStr = read("application.json")
        if not '?' in request_path:
            return jsonStr
        ids = request_path.split("?")[1].split("=")[1].split(",")
        parsedJson = json.loads(jsonStr)
        filteredApps = [app for app in parsedJson["applications"] if str(app["id"]) in ids]
        parsedJson["applications"] = filteredApps
        return json.dumps(parsedJson)

    def test_request_status_ok(self):
        status = self.do_collect_health(r'.*')
        self.assertEqual(RequestStatus.OK, status[("api.newrelic.com", "touri-archiv_prod")].request_status)

    def test_filter(self):
        status = self.do_collect_health( "touri-archiv_prod")
        self.assertEqual(1, len(status))

    def test_health_healthy(self):
        status = self.do_collect_health(r'.*')
        self.assertEqual(Health.HEALTHY, status[("api.newrelic.com", "touri-tour_prod")].health)

    def test_health_unkown(self):
        status = self.do_collect_health(r'.*')
        self.assertEqual(Health.UNDEFINED, status[("api.newrelic.com", "touri-sap-pm-leveldb_dev")].health)

    def test_health_unwell(self):
        status = self.do_collect_health(r'.*')
        self.assertEqual(Health.SICK, status[("api.newrelic.com", "touri-zug_dev")].health)

    def test_health_sick(self):
        status = self.do_collect_health(r'.*')
        self.assertEqual(Health.UNWELL, status[("api.newrelic.com", "touri-zug_e2e")].health)

    def test_filter_all_dev(self):
        status = self.do_collect_health( ".*_dev")
        self.assertEqual(20, len(status))

    def test_http_500(self):
        status = self.do_collect_jobs_error(HTTPError(self.url, 500, None, None, None))
        self.assertEqual(RequestStatus.ERROR, status[("api.newrelic.com", "all")].request_status)

    def test_http_404(self):
        status = self.do_collect_jobs_error(HTTPError(self.url, 404, None, None, None))
        self.assertEqual(RequestStatus.NOT_FOUND, status[("api.newrelic.com", "all")].request_status)

    def test_http_url_error(self):
        status = self.do_collect_jobs_error(URLError("kaputt"))
        self.assertEqual(RequestStatus.ERROR, status[("api.newrelic.com", "all")].request_status)

if __name__ == '__main__':
    main()