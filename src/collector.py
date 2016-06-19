# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'u206123'

from base64 import b64encode
from urllib.request import urlopen, HTTPError, Request
from time import sleep
import logging
import ssl

def create_http_client(username = None, password = None, saml_login_url=None, verify_ssl=True):
    if saml_login_url:
        return HttpClient(authentication_handler=SamlAuthenticationHandler(username=username, password=password, saml_login_url=saml_login_url, verify_ssl=verify_ssl),
                                      verify_ssl=verify_ssl)
    elif username:
        return HttpClient(authentication_handler=BasicAuthenticationHandler(username=username, password=password),
                                      verify_ssl=verify_ssl)
    else:
        return HttpClient(verify_ssl=verify_ssl)

# Base classes to build collectors.
#
# Currently includes a HTTP Client with handlers for different kinds of authentication
#
class EmptyAuthenticationHandler:
    """ Implement no authentication so HttpClient is not forced to check for the presence of an authentication handler """
    def add_header(self, request):
        pass

    def handle_forbidden(self, http_error):
        return False # does not authenticate

class BasicAuthenticationHandler():
    """ Authenticate using RFC  """

    def __init__(self, username, password):
        # basic authentication
        self.auth = b'Basic ' + b64encode(('%s:%s' % (username, password)).encode('utf-8'))

    def add_header(self, request):
        request.add_header("Authorization", self.auth)

    def handle_forbidden(self, http_error):
        return True # retry


class SamlAuthenticationHandler():
    """ Authenticate via SAML Cookies as implemented in SBB WSG """

    def __init__(self, username, password, saml_login_url, verify_ssl=True):
        self.login_http_client = HttpClient(BasicAuthenticationHandler(username, password), verify_ssl=verify_ssl)
        self.saml_login_url = saml_login_url
        self.saml_cookie = None

    def add_header(self, request):
        if self.saml_cookie:
            request.add_header("Cookie", self.saml_cookie)

    def handle_forbidden(self, http_error):
        return self.saml_login()

    def saml_login(self):
        # looks as if we have to aquire a (new) SAML Token....
        logging.debug("Requesting new SAML Cookie from %s...", self.login_http_client)
        response = self.login_http_client.open(self.saml_login_url)
        saml_cookie = response.getheader("Set-Cookie")
        if saml_cookie:
            logging.info("Received new SAML Cookie")
            logging.debug("New SAML Cookie: '%s'", saml_cookie)
            self.saml_cookie = saml_cookie
            return True # ok na
        else:
            logging.error("Failed to renew SAML Cookie, did not receive Set-Cookie")
            return True # ok anyway na, will try another login if cookie is missing....

class HttpClient:
    """ A HttpClient able to do authentication via
    - Retry: Retry for instance 401 as this does sometimes help (Bug in SBB eBiz/LDAP)
    - BasicAuthentication: Username/Password - Use for instance from within SBB LAN. Also supports retry.
    - SamlAuthentication: SAML using a specific Login URL and HTTP Set-Cookie and Cookie Headers for use with SBB Webservice Gateway (WSG) - access from outside SBB LAN
    Will retry status code 5xx and if told so by authentication handler max_retries times (default 3 times)"""

    def __init__(self, authentication_handler=EmptyAuthenticationHandler(), max_retries=3, retry_delay_sec=3, verify_ssl=True):
        self.authentication_handler = authentication_handler
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        ctx = ssl.create_default_context()
        if not verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.ctx = ctx

    def open_and_read(self, request_url):
        response = self.open(request_url)
        return response.readall().decode(response.headers.get_content_charset() or "utf-8")

    def open(self, request_url, retry=0):
        try:
            request = Request(request_url)
            logging.debug("Request to %s" % request_url)
            self.authentication_handler.add_header(request)
            logging.debug("Request headers: %s" % request.headers)
            return self.__open__(request)
        except HTTPError as e:
            if e.code in (401,402,403,407,408) and retry < self.max_retries and self.authentication_handler.handle_forbidden(e): # maybe authentication issue
                # authentication handler did its job and said retry
                logging.info("Potential authentication status code %s requesting %s, retry %s", str(e.code), request_url, retry)
                sleep(retry *  self.retry_delay_sec) # back off after first time
                return self.open(request_url, retry + 1)
            elif e.code >= 500 and retry < self.max_retries: # retry server side error (may be temporary), max 3 attempts
                logging.warning("Temporary error requesting %s, retry %s: %s", request_url, retry, str(e))
                sleep((retry + 1) *  self.retry_delay_sec) # back off starting from the first time
                return self.open(request_url, retry + 1)
            else:
                raise e

    def __open__(self, request):
        return urlopen(request, context=self.ctx)
