__author__ = 'florianseidl'

import env
from output import *
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock
from cimon import JobStatus,RequestStatus,Health

class AbstractBuildAmpelTest(TestCase):

    def test_not_found_is_no_output(self):
        ampel = self.__create_ampel__(signal_error_threshold=0)
        ampel.on_update({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.NOT_FOUND)})
        self.assertEqual(ampel.signal.call_count, 0)

    def test_failture_is_red(self):
        self.__do_test__({("ci.sbb.ch","job.a") : JobStatus(RequestStatus.OK, Health.SICK)}, red=True, yellow=False, green=False)

    def test_unstable_is_yellow(self):
        self.__do_test__({("ci.sbb.ch","job.a") : JobStatus(RequestStatus.OK, Health.UNWELL)}, red=False, yellow=True, green=False)

    def test_success_is_green(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY)}, red=False, yellow=False, green=True)

    def test_2_success_1_failture_is_red(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY),
                          ("ci.sbb.ch","job.b") : JobStatus(RequestStatus.OK, Health.SICK),
                          ("ci.sbb.ch","job.c") :JobStatus(RequestStatus.OK, Health.HEALTHY)}, red=True, yellow=False, green=False)

    def test_success_failture__unstable_is_red(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY),
                          ("ci.sbb.ch","job.b") : JobStatus(RequestStatus.OK, Health.SICK),
                          ("ci.sbb.ch","job.c") : JobStatus(RequestStatus.OK, Health.UNWELL)}, red=True, yellow=False, green=False)

    def test_2_success_2_unstable_is_yellow(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY),
                          ("ci.sbb.ch","job.b") :JobStatus(RequestStatus.OK, Health.UNWELL),
                          ("ci.sbb.ch","job.c") :JobStatus(RequestStatus.OK, Health.HEALTHY)}, red=False, yellow=True, green=False)


    def test_2_success_1_error_is_all_on(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY),
                          ("ci.sbb.ch","job.b") :JobStatus(RequestStatus.ERROR),
                          ("ci.sbb.ch","job.c") :JobStatus(RequestStatus.OK, Health.HEALTHY)}, red=True, yellow=True, green=True)

    def test_2_success_1_not_found_is_green(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY),
                          ("ci.sbb.ch","job.b") :JobStatus(RequestStatus.NOT_FOUND),
                          ("ci.sbb.ch","job.c") :JobStatus(RequestStatus.OK, Health.HEALTHY)}, red=False, yellow=False, green=True)

    def test_error_no_previous_status_is_all_on(self):
        # first error (no previous status) is error
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.ERROR)}, red=True, yellow=True, green=True)

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

    def test_is_buiding_success(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY, True)}, red=False, yellow=False, green=True, flash=True)

    def test_is_not_buiding_success(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY, False)}, red=False, yellow=False, green=True, flash=False)

    def test_is_buiding_failure(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.SICK, True)}, red=True, yellow=False, green=False, flash=True)

    def test_is_buiding_unstable(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.UNWELL, True)}, red=False, yellow=True, green=False, flash=True)

    def test_is_buiding_other(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.OTHER, True)}, red=False, yellow=True, green=False, flash=True)

    def test_is_buiding_error(self):
        self.__do_test__({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.ERROR),
                          ("ci.sbb.ch","job.b") :JobStatus(RequestStatus.OK, Health.OTHER, False)},
                         red=True, yellow=True, green=True, flash=False)

    def test_error_with_all(self):
        ampel = self.__create_ampel__(0)
        ampel.on_update({("ci.sbb.ch",'all'): JobStatus(RequestStatus.ERROR)})
        ampel.signal.assert_called_once_with(red=True, yellow=True, green=True, flash=False)

    def __do_test__(self, status, red, yellow, green, flash=False):
        ampel = self.__create_ampel__(signal_error_threshold=3) # threshold is pointless here as no previosu status exists
        ampel.on_update(status)
        ampel.signal.assert_called_once_with(red=red, yellow=yellow, green=green, flash=flash)

    def __do_test_error__(self, nr_errors, signal_error_threshold, expect_error_signal):
        ampel = self.__create_ampel__(signal_error_threshold)
        # requires a previous state - in this case all is OK before (green=True, yellow=False, red=False)
        ampel.on_update({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY)})
        status = {("ci.sbb.ch","job.a") :JobStatus(RequestStatus.ERROR)}
        for i in range(nr_errors):
            ampel.signal.assert_called_once_with(red=False, yellow=False, green=True, flash=False)
            ampel.signal.reset_mock()
            ampel.on_update(status)
        if expect_error_signal:
            ampel.signal.assert_called_once_with(red=True, yellow=True, green=True, flash=False)
        else:
            ampel.signal.assert_called_once_with(red=False, yellow=False, green=True, flash=False)


    def test_filter_ok(self):
        filter = NameFilter("job\.\w*")
        status = {("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY)}
        self.assertEqual(status, filter.filter_status(status))

    def test_filter_ok_many(self):
        filter = NameFilter("job\.\w*")
        status = {("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY), ("ci.sbb.ch", "job.b") :JobStatus(RequestStatus.NOT_FOUND)}
        self.assertEqual(status, filter.filter_status(status))

    def test_filter_filtered(self):
        filter = NameFilter("job\.\w*")
        status = {"another.a" :JobStatus(RequestStatus.OK, Health.HEALTHY)}
        self.assertEqual({}, filter.filter_status(status))

    def test_filter_nofilter(self):
        filter = NameFilter()
        status = {"another.a" : {("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY)}}
        self.assertEqual(status, filter.filter_status(status))

    def test_filter_with_ampel(self):
        ampel = self.__create_ampel__(signal_error_threshold=1, build_filter_pattern="bla.*") # threshold is pointless here as no previosu status exists
        ampel.on_update({("ci.sbb.ch","job.a") :JobStatus(RequestStatus.OK, Health.HEALTHY)})
        self.assertFalse(ampel.signal.called)

    def test_filter_with_ampel_one_filtered(self):
        ampel = self.__create_ampel__(signal_error_threshold=1, build_filter_pattern="bla.*") # threshold is pointless here as no previosu status exists
        ampel.on_update({("ci.sbb.ch","job.a") : JobStatus(RequestStatus.OK, Health.SICK), ("ci.sbb.ch", "bla.b") : JobStatus(RequestStatus.OK, Health.HEALTHY)})
        ampel.signal.assert_called_once_with(red=False, yellow=False, green=True, flash=False)

    def __create_ampel__(self,signal_error_threshold, build_filter_pattern=None):
        ampel = AbstractBuildAmpel(signal_error_threshold=signal_error_threshold, build_filter_pattern=build_filter_pattern)
        ampel.signal = Mock(spec=(""))
        return ampel

if __name__ == '__main__':
    main()