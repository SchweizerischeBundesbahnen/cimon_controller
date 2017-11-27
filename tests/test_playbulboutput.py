import env
from unittest import TestCase
from playbulboutput import *
from unittest.mock import MagicMock, call

class TestPlaybulbAmpel(TestCase):

    def test_output_called(self):
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display()
        self.assertEqual(self.ampel.__call_gatttool__.call_count, 1)

    def test_output_called_all_off(self):
        self.output_called_display_color(colorString='off')

    def test_output_called_display_green(self):
        self.output_called_display_color(colorString='green',green=True)

    def test_output_called_display_red(self):
        self.output_called_display_color(colorString='yellow', yellow=True)

    def test_output_called_display_red(self):
        self.output_called_display_color(colorString='red', red=True)

    def test_output_called_display_all(self):
        self.output_called_display_color(colorString='all', red=True, yellow=True, green=True)

    def test_output_called_display_red_priority(self):
        self.output_called_display_color(colorString='red', red=True, yellow=True)

    def test_output_called_display_yellow_priority(self):
        self.output_called_display_color(colorString='yellow', yellow=True, green=True)

    def output_called_display_color(self, colorString, red=False, yellow=False, green=False):
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display(red=red, yellow=yellow,green=green)
        self.ampel.__call_gatttool__.assert_has_calls([call('gatttool -b dummy --char-write -a color_reg -n %s' % colorString)])

    def test_flash(self):
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display(green=True, flash=True)
        self.ampel.__call_gatttool__.assert_has_calls([call('gatttool -b dummy --char-write -a flash_reg -n greenflash')])

    def create_playbulb_ampel(self):
        ampel = PlaybulbAmpel(device='dummy',
                              color_reg='color_reg',
                              flash_reg='flash_reg',
                              flash='flash',
                              red_color='red',
                              green_color='green',
                              yellow_color='yellow',
                              all_color='all',
                              off_color='off')
        ampel.__call_gatttool__ = MagicMock(spec=(""), return_value=True)
        return ampel
