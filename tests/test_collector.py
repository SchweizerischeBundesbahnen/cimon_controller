__author__ = 'florianseidl'

import env
from collector import *
from urllib.request import HTTPError, URLError
from unittest import TestCase, main
from unittest.mock import MagicMock, Mock, DEFAULT
from types import SimpleNamespace
import os
from datetime import datetime


class TestHttpClient(TestCase):
    json_str = '{ "foo": "bar" }'

    def test_ok(self):
        h = self.create_http_client("foobar42")
        self.assertEquals(h.open_and_read("http://irgendw.as"), "foobar42")
        self.assertEqual(h.__open__.call_count, 1)

    def test_http_exception_500(self):
        h = self.create_http_client(http_error_codes=[500]*99)
        with self.assertRaises(HTTPError):
            h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 4)

    def test_http_exception_500_then_OK(self):
        h = self.create_http_client(http_error_codes=[500, None])
        h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 2)

    def test_http_exception_500_2times_OK(self):
        h = self.create_http_client(http_error_codes=[500, 500, None])
        h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 3)

    def test_http_exception_500_3times_OK(self):
        h = self.create_http_client(http_error_codes=[500, 500, 500, None])
        h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 4)

    def test_http_exception_401_no_retry(self):
        h = self.create_http_client(http_error_codes=[401]*99)
        with self.assertRaises(HTTPError):
            h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 1)

    def test_basic_auth(self):
        h = self.create_http_client(authentication_handler=BasicAuthenticationHandler("bla", "blo"))
        h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 1)
        request = self.__get_request__(h.__open__)
        self.assertTrue(request.has_header("Authorization"))

    def test_basic_auth_http_exception_401_retry_ok(self):
        h = self.create_http_client(http_error_codes=(401,None), authentication_handler=BasicAuthenticationHandler("bla", "blo"))
        h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 2)

    def test_basic_auth_http_exception_401_retry_fail(self):
        h = self.create_http_client(http_error_codes=[401]*99, authentication_handler=BasicAuthenticationHandler("bla", "blo"))
        with self.assertRaises(HTTPError):
            h.open_and_read("http://irgendw.as")
        self.assertEqual(h.__open__.call_count, 4)

    def test_saml(self):
        saml = SamlAuthenticationHandler("irgendwer", "geheim", "http://log.in")
        saml.login_http_client = self.create_http_client(cookie_header="bla")
        h = self.create_http_client(http_error_codes=(401,None), response_str="hallo", authentication_handler=saml)
        h.open_and_read("http://irgendwas")
        self.assertEqual(h.__open__.call_count, 2)
        self.assertEqual(saml.login_http_client.__open__.call_count, 1)
        request = self.__get_request__(h.__open__)
        self.assertEquals(request.get_header("Cookie"), "bla")

    def test_saml_http_exception_401_saml_no_cookie_sent(self):
        saml = SamlAuthenticationHandler("irgendwer", "geheim", "http://log.in")
        saml.login_http_client = self.create_http_client()
        h = self.create_http_client(http_error_codes=[401]*99, authentication_handler=saml)
        with self.assertRaises(HTTPError):
            h.open_and_read("http://irgendwas")
        self.assertEqual(h.__open__.call_count, 4)
        self.assertEqual(saml.login_http_client.__open__.call_count, 3)

    def create_http_client(self, response_str="", http_error_codes=None, authentication_handler=EmptyAuthenticationHandler(), cookie_header=None):
        h = HttpClient(authentication_handler, retry_delay_sec=0)
        response = SimpleNamespace()
        response.readall = Mock(spec=(""), return_value=response_str.encode("UTF-8"))
        response.headers = SimpleNamespace()
        response.headers.get_content_charset= Mock(spec=(""), return_value="UTF-8")
        response.getheader = Mock(spec=(""), return_value=cookie_header)

        side_effects = [HTTPError("http://foo.bar", code, None, None, None) if code else DEFAULT for code in http_error_codes] if http_error_codes else None

        h.__open__ = Mock(spec=(""),
                          return_value=response,
                          side_effect=side_effects)
        return h

    def __get_request__(self, open):
        return open.call_args[0][0]