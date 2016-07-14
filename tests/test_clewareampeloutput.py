import env
from unittest import TestCase
from clewareampeloutput import *
from unittest.mock import MagicMock, Mock, patch, call
from time import sleep


class TestClewarecontrolClewareAmpel(TestCase):
    red = 0
    yellow = 1
    green = 2

    def tearDown(self):
        if self.ampel:
            self.ampel.stop()

    def test_output_called(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display()
        sleep(0.5) # make sure it waits after just one output
        self.assertEqual(self.ampel.__call_clewarecontrol__.call_count, 1)

    def test_output_called_all_off(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display()
        sleep(0.2)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,False))])

    def test_output_called_display_green(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True)
        sleep(0.2)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True))])

    def test_flash(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True, flash=True)
        sleep(1) # allow for many flashes...
        # should be 9 or 10 calls depending on computing time... usually 10
        self.assertTrue(self.ampel.__call_clewarecontrol__.call_count in (9,10))

    def test_flash_on_off(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True, flash=True)
        sleep(0.19) # allow for 1 flashes (on-off)
        self.assertEqual(self.ampel.__call_clewarecontrol__.call_count, 2)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True)),
                                                           call((self.green,False))])

    def test_flash_on_off_on_off(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True, flash=True)
        sleep(0.42) # allow for 1 flashes (on-off)
        self.assertEqual(self.ampel.__call_clewarecontrol__.call_count, 4)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True)),
                                                             call((self.green,False)),
                                                             call((self.green,True)),
                                                             call((self.green,False))])

    def test_output_called_display_green_then_red(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True)
        sleep(0.1)
        self.ampel.display(red=True)
        sleep(0.2)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True)),
                                                           call((self.red,True), (self.green,False))])

    def test_no_flash_negative_interval(self):
        self.ampel = self.create_cleware_ampel(flash_interval_sec=-1)
        self.ampel.display(green=True, flash=True)
        sleep(0.9) # allow for many flashes...
        # should be 9 or 10 calls depending on computing time... usually 10
        self.assertEquals(self.ampel.__call_clewarecontrol__.call_count, 1)

    def test_output_called_display_green_twice(self):
        self.ampel = self.create_cleware_ampel()
        for i in range(0,2):
            self.ampel.display(green=True)
            sleep(0.2)
        self.assertEquals(1, self.ampel.__call_clewarecontrol__.call_count)
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True))])

    def test_output_called_display_green_three_times(self):
        self.ampel = self.create_cleware_ampel()
        for i in range(0,3):
            self.ampel.display(green=True)
            sleep(0.2)
        self.assertEquals(1, self.ampel.__call_clewarecontrol__.call_count)

    def test_flash_on_off_on_off_no_flash_but_same(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True, flash=True)
        sleep(0.42) # allow for 1 flashes (on-off)
        self.ampel.display(green=True, flash=False)
        # last display is not shown because it is the same value
        self.assertEqual(self.ampel.__call_clewarecontrol__.call_count, 4)

    def test_output_called_display_green_ten_times(self):
        self.ampel = self.create_cleware_ampel(absoulte_every_sec=1)
        for i in range(0,2):
            self.ampel.display(green=True)
            sleep(1)
        self.assertEquals(2, self.ampel.__call_clewarecontrol__.call_count)

    def test_output_called_display_green_twice_absolute_every(self):
        self.ampel = self.create_cleware_ampel(absoulte_every_sec=0)
        for i in range(0,2):
            self.ampel.display(green=True)
            sleep(0.2)
        self.assertEquals(2, self.ampel.__call_clewarecontrol__.call_count)

    def test_wait_for_display(self):
        self.ampel = self.create_cleware_ampel()
        self.ampel.display(green=True)
        self.ampel.wait_for_display()
        self.ampel.__call_clewarecontrol__.assert_has_calls([call((self.red,False), (self.yellow,False), (self.green,True))])

    def create_cleware_ampel(self, flash_interval_sec=0.2, retval=True, absoulte_every_sec=42):
        ampel = ClewarecontrolClewareAmpel(flash_interval_sec=flash_interval_sec, absoulte_every_sec=absoulte_every_sec)
        ampel.__call_clewarecontrol__ = MagicMock(spec=(""), return_value=retval)
        return ampel
