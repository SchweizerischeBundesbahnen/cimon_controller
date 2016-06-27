__author__ = 'florianseidl'

import env
from output import *
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock

class AbstractBuildAmpelTest(TestCase):

    def test_not_found_is_no_output(self):
        ampel = self.__create_ampel__(signal_error_threshold=0)
        ampel.on_update({"build" : {"job.a" :{"request_status" : "not_found"}}})
        self.assertEqual(ampel.signal.call_count, 0)

    def test_failture_is_red(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "failure"}}}, red=True, yellow=False, green=False)

    def test_unstable_is_yellow(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "unstable"}}}, red=False, yellow=True, green=False)

    def test_success_is_green(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"}}}, red=False, yellow=False, green=True)

    def test_ok_but_no_result_is_key_error(self):
        # misses the required parameter in the map and therefore raises a key error (invalid build status map)
        with self.assertRaises(KeyError):
            self.__do_test__({"build" : {"job.a" :{"request_status" : "ok"}}}, red=False, yellow=False, green=False)

    def test_2_success_1_failture_is_red(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"},
                                     "job.b" :{"request_status" : "ok", "result" : "failure"},
                                     "job.c" :{"request_status" : "ok", "result" : "success"}}}, red=True, yellow=False, green=False)

    def test_success_failture__unstable_is_red(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"},
                                     "job.b" :{"request_status" : "ok", "result" : "failure"},
                                     "job.c" :{"request_status" : "ok", "result" : "unstable"}}}, red=True, yellow=False, green=False)

    def test_2_success_2_unstable_is_yellow(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"},
                                     "job.b" :{"request_status" : "ok", "result" : "unstable"},
                                     "job.c" :{"request_status" : "ok", "result" : "success"}}}, red=False, yellow=True, green=False)


    def test_2_success_1_error_is_all_on(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"},
                                     "job.b" :{"request_status" : "error"},
                                     "job.c" :{"request_status" : "ok", "result" : "success"}}}, red=True, yellow=True, green=True)

    def test_2_success_1_not_found_is_green(self):
        self.__do_test__({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"},
                                     "job.b" :{"request_status" : "not_found"},
                                     "job.c" :{"request_status" : "ok", "result" : "success"}}}, red=False, yellow=False, green=True)

    def test_unknown_status_no_output(self):
        ampel = self.__create_ampel__(signal_error_threshold=0)
        ampel.on_update({"someunkownstatus" : {"job.a" :{"request_status" : "ok", "result" : "success"}}})
        self.assertEqual(ampel.signal.call_count, 0)

    def test_error_no_previous_status_is_all_on(self):
        # first error (no previous status) is error
        self.__do_test__({"build" : {"job.a" :{"request_status" : "error"}}}, red=True, yellow=True, green=True)

    def test_error_threshold_below(self):
        self.__do_test_error__(1, 2, False)

    def test_error_threshold_equal(self):
        self.__do_test_error__(2, 2, False)

    def test_error_threshold_above(self):
        self.__do_test_error__(3, 2, True)

    def test_error_threshold_0_above(self):
        self.__do_test_error__(1, 0, True)

    def test_error_threshold_0_0(self):
        self.__do_test_error__(0, 0, False)

    def __do_test__(self, status, red, yellow, green):
        ampel = self.__create_ampel__(signal_error_threshold=3) # threshold is pointless here as no previosu status exists
        ampel.on_update(status)
        ampel.signal.assert_called_once_with(red=red, yellow=yellow, green=green)

    def __do_test_error__(self, nr_errors, signal_error_threshold, expect_error_signal):
        ampel = self.__create_ampel__(signal_error_threshold)
        # requires a previous state - in this case all is OK before (green=True, yellow=False, red=False)
        ampel.on_update({"build" : {"job.a" :{"request_status" : "ok", "result" : "success"}}})
        status = {"build" : {"job.a" :{"request_status" : "error"}}}
        for i in range(nr_errors):
            ampel.signal.assert_called_once_with(red=False, yellow=False, green=True)
            ampel.signal.reset_mock()
            ampel.on_update(status)
        if expect_error_signal:
            ampel.signal.assert_called_once_with(red=True, yellow=True, green=True)
        else:
            ampel.signal.assert_called_once_with(red=False, yellow=False, green=True)

    def __create_ampel__(self,signal_error_threshold):
        ampel = AbstractBuildAmpel(signal_error_threshold=signal_error_threshold)
        ampel.signal = Mock(spec=(""))
        return ampel

if __name__ == '__main__':
    main()