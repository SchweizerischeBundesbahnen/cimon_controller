import env
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch, call
from energenieoutput import *
from types import SimpleNamespace

class TestEnergenieBuildAmpel(TestCase):

    def test_signal_all_on(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=True, green=True, flash=False)
        e.energenie.switch.assert_called_once_with(socket_1=True, socket_2=True, socket_3=True, socket_4=True)

    def test_signal_all_on_ignore_flash(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=True, green=True, flash=True)
        e.energenie.switch.assert_called_once_with(socket_1=True, socket_2=True, socket_3=True, socket_4=True)


    def test_signal_all_off(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with(socket_1=False, socket_2=False, socket_3=False, socket_4=False)

    def test_signal_red(self):
        e = self.create_ampel()
        e.signal(red=True, yellow=False, green=False, flash=False)
        e.energenie.switch.assert_called_once_with(socket_1=True, socket_2=False, socket_3=False, socket_4=True)

    def test_signal_yellow(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=True, green=False, flash=False)
        e.energenie.switch.assert_called_once_with(socket_1=False, socket_2=True, socket_3=False, socket_4=False)

    def test_signal_green(self):
        e = self.create_ampel()
        e.signal(red=False, yellow=False, green=True, flash=False)
        e.energenie.switch.assert_called_once_with(socket_1=False, socket_2=False, socket_3=True, socket_4=False)

    def create_ampel(self):
        a = EnergenieBuildAmpel()
        a.energenie = SimpleNamespace()
        a.energenie.switch = MagicMock(spec=(""))
        return a

class EnergenieTest(TestCase):

    def test_all_on(self):
        e = self.create_energenie()
        e.switch(socket_1=True, socket_2=True, socket_3=True, socket_4=True)
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, True), (3, True), (4, True))

    def test_1_on(self):
        e = self.create_energenie()
        e.switch(socket_1=True, socket_2=False, socket_3=False, socket_4=False)
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, False), (3, False), (4, False))

    def test_2_on(self):
        e = self.create_energenie()
        e.switch(socket_1=False, socket_2=True, socket_3=False, socket_4=False)
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, True), (3, False), (4, False))

    def test_3_on(self):
        e = self.create_energenie()
        e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, True), (4, False))

    def test_4_on(self):
        e = self.create_energenie()
        e.switch(socket_1=False, socket_2=False, socket_3=False, socket_4=True)
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, False), (4, True))

    def test_1_4_on(self):
        e = self.create_energenie()
        e.switch(socket_1=True, socket_2=False, socket_3=False, socket_4=True)
        e.__call_sispmctl__.assert_called_once_with((1, True),(2, False), (3, False), (4, True))

    def test_two_same_calls(self):
        e = self.create_energenie()
        for i in range(0,2):
            e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.__call_sispmctl__.assert_called_once_with((1, False),(2, False), (3, True), (4, False))
        self.assertEquals(1, e.__call_sispmctl__.call_count)

    def test_two_different_calls(self):
        e = self.create_energenie()
        e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.switch(socket_1=False, socket_2=True, socket_3=False, socket_4=False)
        e.__call_sispmctl__.assert_called_with((1, False),(2, True), (3, False), (4, False))
        self.assertEquals(2, e.__call_sispmctl__.call_count)

    def test_four_same_calls(self):
        e = self.create_energenie()
        for i in range(0,4):
            e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.__call_sispmctl__.assert_called_with((1, False),(2, False), (3, True), (4, False))
        self.assertEquals(2, e.__call_sispmctl__.call_count)

    def test_seven_same_calls(self):
        e = self.create_energenie()
        for i in range(0,7):
            e.switch(socket_1=False, socket_2=True, socket_3=False, socket_4=False)
        e.__call_sispmctl__.assert_called_with((1, False),(2, True), (3, False), (4, False))
        self.assertEquals(3, e.__call_sispmctl__.call_count)

    def test_three_different_calls(self):
        e = self.create_energenie()
        e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.switch(socket_1=False, socket_2=True, socket_3=False, socket_4=False)
        e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        e.__call_sispmctl__.assert_called_with((1, False),(2, False), (3, True), (4, False))
        self.assertEquals(3, e.__call_sispmctl__.call_count)

    def test_two_same_calls_repeat_every_time_0(self):
        self.do_two_same_calls_repeat_every_time(0)

    def test_two_same_calls_repeat_every_time_1(self):
        self.do_two_same_calls_repeat_every_time(1)

    def test_two_same_calls_repeat_every_time_minus_1(self):
        self.do_two_same_calls_repeat_every_time(-1)

    def do_two_same_calls_repeat_every_time(self, repeat_every):
        e = self.create_energenie(repeat_every=repeat_every)
        for i in range(0,2):
            e.switch(socket_1=False, socket_2=False, socket_3=True, socket_4=False)
        self.assertEquals(2, e.__call_sispmctl__.call_count)

    def create_energenie(self, repeat_every=3):
        e = Energenie(repeat_every=repeat_every)
        e.__call_sispmctl__ = MagicMock(spec=(""))
        return e

