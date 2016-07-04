import env
from unittest import TestCase
from clewareampeloutput import *
from unittest.mock import MagicMock, Mock, patch, call
from time import sleep

class TestClewareAmpel(TestCase):

    def setUp(self):
        self.ampel = self.create_cleware_ampel()

    def tearDown(self):
        if self.ampel:
            self.ampel.stop()

    def test_output_called(self):
        self.ampel.display()
        sleep(0.5) # make sure it waits after just one output
        self.assertEqual(self.ampel.__output_to_cleware__.call_count, 1)

    def test_output_called_all_off(self):
        self.ampel.display()
        sleep(0.2)
        self.ampel.__output_to_cleware__.assert_has_calls([call(red=False, yellow=False, green=False)])

    def test_output_called_display_green(self):
        self.ampel.display(green=True)
        sleep(0.2)
        self.ampel.__output_to_cleware__.assert_has_calls([call(red=False, yellow=False, green=True)])

    def test_flash(self):
        self.ampel.display(green=True, flash=True)
        sleep(1) # allow for many flashes...
        print(self.ampel.__output_to_cleware__.call_count)
        # should be 9 or 10 calls depending on computing time... usually 10
        self.assertTrue(self.ampel.__output_to_cleware__.call_count in (9,10))

    def test_flash_on_off(self):
        self.ampel.display(green=True, flash=True)
        sleep(0.15) # allow for 1 flashes (on-off)
        self.assertEqual(self.ampel.__output_to_cleware__.call_count, 2)
        self.ampel.__output_to_cleware__.assert_has_calls([call(red=False, yellow=False, green=True),
                                                           call(red=False, yellow=False, green=False)])

    def test_flash_on_off_on_off(self):
        self.ampel.display(green=True, flash=True)
        sleep(0.35) # allow for 1 flashes (on-off)
        self.assertEqual(self.ampel.__output_to_cleware__.call_count, 4)
        self.ampel.__output_to_cleware__.assert_has_calls([call(red=False, yellow=False, green=True),
                                                           call(red=False, yellow=False, green=False),
                                                           call(red=False, yellow=False, green=True),
                                                           call(red=False, yellow=False, green=False)])

    def test_output_called_display_green_then_red(self):
        self.ampel.display(green=True)
        sleep(0.1)
        self.ampel.display(red=True)
        sleep(0.2)
        self.ampel.__output_to_cleware__.assert_has_calls([call(red=False, yellow=False, green=True),
                                                           call(red=True, yellow=False, green=False)])

    def create_cleware_ampel(self):
        ampel = ClewareAmpel(flash_interval=0.1)
        ampel.__output_to_cleware__ = MagicMock(spec=(""))
        return ampel

