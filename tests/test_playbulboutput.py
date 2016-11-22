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
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display()
        self.ampel.__call_gatttool__.assert_has_calls([call('gatttool -b dummy --char-write -a color_reg -n 00000000')])

    def test_output_called_display_green(self):
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display(green=True)
        self.ampel.__call_gatttool__.assert_has_calls([call('gatttool -b dummy --char-write -a color_reg -n green')])

    def test_flash(self):
        self.ampel = self.create_playbulb_ampel()
        self.ampel.display(green=True, flash=True)
        self.ampel.__call_gatttool__.assert_has_calls([call('gatttool -b dummy --char-write -a flash_reg -n greenflash')])


    def create_playbulb_ampel(self, device='dummy', color_reg = 'color_reg', flash_reg = 'flash_reg', flash = 'flash', red_color = 'red', green_color='green', yellow_color = 'yellow', retval=True):
        ampel = PlaybulbAmpel(device, color_reg, flash_reg, flash, red_color, green_color, yellow_color)
        ampel.__call_gatttool__ = MagicMock(spec=(""), return_value=retval)
        return ampel
