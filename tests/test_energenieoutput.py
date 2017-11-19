import env
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch, call
from energenieoutput import *
from types import SimpleNamespace

class TestEnergenieBuildAmpel(TestCase):

    def test_signal_all_on(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=True, green=True, flash=False)
        e.energenie.switch.assert_called_once_with([(1,True), (2,True), (3,True), (4,True)])

    def test_signal_all_on_ignore_flash(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=True, green=True, flash=True)
        e.energenie.switch.assert_called_once_with([(1,True), (2,True), (3,True), (4,True)])

    def test_signal_all_off(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([(1,False), (2,False), (3,False), (4,False)])

    def test_signal_red(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([(1,True), (2,False), (3,False), (4,True)])

    def test_signal_yellow(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=True, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([(1,False), (2,True), (3,False), (4,False)])

    def test_signal_green(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=False, green=True, flash=False)
        e.energenie.switch.assert_called_once_with([(1,False), (2,False), (3,True), (4,False)])

    def test_signal_green_on_2(self):
        e = self.create_ampel({1: "yellow", 2 : "green", 3: "red"})
        e.signal(red=False, yellow=False, green=True, flash=False)
        e.energenie.switch.assert_called_once_with([(1,False), (2,True), (3,False)])

    def test_signal_red_on_3_yellow_on_1(self):
        e = self.create_ampel({1: "yellow", 2 : "green", 3: "red"})
        e.signal(red=True, yellow=True, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([(1,True), (2,False), (3,True)])

    def test_signal_red_not_configured(self):
        e = self.create_ampel({3: "yellow", 4 : "green"})
        e.signal(red=True, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([(3,False), (4,False)])

    def test_signal_nothing_empty_config(self):
        e = self.create_ampel()
        e.colors = {}
        e.signal(red=True, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with([])

    def create_ampel(self, colors=None):
        a = EnergenieBuildAmpel(colors=colors) if colors else EnergenieBuildAmpel()
        a.energenie = SimpleNamespace()
        a.energenie.switch = MagicMock(spec=(""))
        return a

class EnergenieTest(TestCase):

    def test_all_on(self):
        e = self.create_energenie()
        e.switch([(1, True), (2,True), (3,True), (4,True)])
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, True), (3, True), (4, True))

    def test_1_on(self):
        e = self.create_energenie()
        e.switch([(1,True), (2,False), (3,False), (4,False)])
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, False), (3, False), (4, False))

    def test_2_on(self):
        e = self.create_energenie()
        e.switch([(1,False), (2,True), (3,False), (4,False)])
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, True), (3, False), (4, False))

    def test_3_on(self):
        e = self.create_energenie()
        e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, True), (4, False))

    def test_4_on(self):
        e = self.create_energenie()
        e.switch([(1,False), (2,False), (3,False), (4,True)])
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, False), (4, True))

    def test_1_4_on(self):
        e = self.create_energenie()
        e.switch([(1,True), (2,False), (3,False), (4,True)])
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, False), (3, False), (4, True))

    def test_all_on_partial(self):
        e = self.create_energenie()
        e.switch([(1, True), (2,True), (3,True)])
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, True), (3, True))

    def test_all_on_only_one(self):
        e = self.create_energenie()
        e.switch([(3,True)])
        e.__call_sispmctl__.assert_called_once_with((3, True))

    def test_no_command(self):
        e = self.create_energenie()
        e.switch([])
        self.assertEqual(0, e.__call_sispmctl__.call_count)

    def test_two_same_calls(self):
        e = self.create_energenie()
        for i in range(0,2):
            e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, True), (4, False))
        self.assertEqual(1, e.__call_sispmctl__.call_count)

    def test_two_different_calls(self):
        e = self.create_energenie()
        e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.switch([(1,False), (2,True), (3,False), (4,False)])
        e.__call_sispmctl__.assert_called_with((1, False),(2, True), (3, False), (4, False))
        self.assertEqual(2, e.__call_sispmctl__.call_count)

    def test_four_same_calls(self):
        e = self.create_energenie()
        for i in range(0,4):
            e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.__call_sispmctl__.assert_called_with((1, False),(2, False), (3, True), (4, False))
        self.assertEqual(2, e.__call_sispmctl__.call_count)

    def test_seven_same_calls(self):
        e = self.create_energenie()
        for i in range(0,7):
            e.switch([(1,False), (2,True), (3,False), (4,False)])
        e.__call_sispmctl__.assert_called_with((1, False),(2, True), (3, False), (4, False))
        self.assertEqual(3, e.__call_sispmctl__.call_count)

    def test_three_different_calls(self):
        e = self.create_energenie()
        e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.switch([(1,False), (2,True), (3,False), (4,False)])
        e.switch([(1,False), (2,False), (3,True), (4,False)])
        e.__call_sispmctl__.assert_called_with((1, False),(2, False), (3, True), (4, False))
        self.assertEqual(3, e.__call_sispmctl__.call_count)

    def test_two_same_calls_repeat_every_time_0(self):
        self.do_two_same_calls_repeat_every_time(0)

    def test_two_same_calls_repeat_every_time_1(self):
        self.do_two_same_calls_repeat_every_time(1)

    def test_two_same_calls_repeat_every_time_minus_1(self):
        self.do_two_same_calls_repeat_every_time(-1)

    def do_two_same_calls_repeat_every_time(self, repeat_every):
        e = self.create_energenie(repeat_every=repeat_every)
        for i in range(0,2):
            e.switch([(1,False), (2,False), (3,True), (4,False)])
        self.assertEqual(2, e.__call_sispmctl__.call_count)

    def create_energenie(self, repeat_every=3):
        e = Energenie(repeat_every=repeat_every)
        e.__call_sispmctl__ = MagicMock(spec=(""))
        return e

