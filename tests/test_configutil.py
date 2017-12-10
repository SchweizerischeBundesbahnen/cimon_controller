__author__ = 'florianseidl'

import env
from configutil import *
from unittest import TestCase
from unittest.mock import Mock, patch
import os

@patch("os.path.expanduser", Mock(spec=(""), return_value="home"))
class ConfigUtilTest(TestCase):
    filename="bilbla_42_foobar_gibitsnicht_sowieso.blo"
    key = b'\n\xb5\x86\x92%\x97A.[\xea-A\x1f\xfcW\x9cEQ\xf0\x81\xaa\x8a\xaf`3\xa2\x0f\xae&\xf7\x88\x8f'
    passwordEncrypted = "6qcvb0Kt0FSU"
    passwordDecrypted = "topsecret"

    def setUp(self):
        self.isfile_method = os.path.isfile

    def tearDown(self):
        os.path.isfile = self.isfile_method

    def test_encrypt(self):
        self.assertEqual(encrypt(self.passwordDecrypted, self.key), self.passwordEncrypted)

    def test_decrypt(self):
        self.assertEqual(decrypt(self.passwordEncrypted, self.key), self.passwordDecrypted)

    def test_encrypt_decrypt(self):
        self.assertEqual(decrypt(encrypt(self.passwordDecrypted, self.key),self.key), self.passwordDecrypted)

    def test_find_config_in_path_directly(self):
        self.mock_os_isfile(True)
        self.assertEqual(self.filename, find_config_file_path(self.filename))

    def test_find_config_in_path(self):
        os.path.isfile=Mock(spec=(""), side_effect=[False, True])
        self.assertEqual("home/cimon/%s" % self.filename, find_config_file_path(self.filename).replace("\\", "/"))

    def test_find_config_not_in_path_mandatory(self):
        self.mock_os_isfile(False)
        with self.assertRaises(Exception):
            find_config_file_path(self.filename)

    def test_find_config_not_in_path_optional(self):
        self.mock_os_isfile(False)
        self.assertIsNone(find_config_file_path(self.filename, optional=True))

    def mock_os_isfile(self, found):
        os.path.isfile = Mock(spec=(""), return_value=found)

if __name__ == '__main__':
    main()