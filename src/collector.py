# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

from base64 import b64encode
from urllib.request import urlopen, HTTPError, URLError, ContentTooShortError, Request
from urllib.parse import unquote
from time import sleep
from threading import Condition
import logging
import ssl
import sys

logger = logging.getLogger(__name__)

def create_http_client(base_url, username = None, password = None, jwt_login_url= None, saml_login_url=None, verify_ssl=True):
    if jwt_login_url:
        return HttpClient(base_url=base_url,
                          authentication_handler=JwtAuthenticationHandler(username=username, password=password, jwt_login_url=jwt_login_url, verify_ssl=verify_ssl),
                          verify_ssl=verify_ssl)
    elif saml_login_url:
        return HttpClient(base_url=base_url,
                          authentication_handler=SamlAuthenticationHandler(username=username, password=password, saml_login_url=saml_login_url, verify_ssl=verify_ssl),
                          verify_ssl=verify_ssl)
    elif username:
        return HttpClient(base_url=base_url,
                          authentication_handler=BasicAuthenticationHandler(username=username, password=password),
                          verify_ssl=verify_ssl)
    else:
        return HttpClient(base_url=base_url, verify_ssl=verify_ssl)

# Base classes to build collectors.
#
# Currently includes a HTTP Client with handlers for different kinds of authentication
#
class EmptyAuthenticationHandler:
    """ Implement no authentication so HttpClient is not forced to check for the presence of an authentication handler """
    def request_headers(self):
        return {}

    def handle_forbidden(self, request_headers, status_code):
        return False # does not authenticate

class BasicAuthenticationHandler():
    """ Authenticate using RFC  """

    def __init__(self, username, password):
        # basic authentication
        self.auth = b'Basic ' + b64encode(('%s:%s' % (username, password)).encode('utf-8'))

    def request_headers(self):
        return { "Authorization" : self.auth }

    def handle_forbidden(self, request_headers, status_code):
        return True # retry

class TokenBasedAuthenticationHandler():
    """ Authenticate via a Token drawn from a configured login url """

    def __init__(self, username, password, login_url, verify_ssl=True):
        self.login_http_client = HttpClient(login_url, BasicAuthenticationHandler(username, password), verify_ssl=verify_ssl)
        self.token = None
        self.is_renewing = False
        self.renewing = Condition()

    def request_headers(self):
        if self.is_renewing: # avoid lock at the cost of sometimes missing, sending mutiple requests and getting more than one 40x
            with self.renewing:
                # wait for one thread to renew the lock
                while self.is_renewing:
                    self.renewing.wait()
        if not self.token:
            self.login({})
        return { self.request_header_name : self.token if self.token else "no token received" }

    def handle_forbidden(self, request_headers, status_code):
        self.login(request_headers)
        # retry whether there is a new token or not....
        return True

    def login(self, request_headers):
        # only one of the threads will get the jwt token
        with self.renewing:
            # check if another thread as allready set the cookie to a different value
            if self.token == request_headers.get(self.request_header_name, None):
                try:
                    self.is_renewing = True
                    self.token = self.__renew_token__()
                finally:
                    self.is_renewing = False
                    self.renewing.notify_all()

    def __renew_token__(self):
        # looks as if we have to aquire a (new) JWT Token....
        logger.debug("Requesting new Token from %s...", self.login_http_client.base_url)
        response = self.login_http_client.open()
        token = response.getheader(self.response_header_name)
        if token:
            logger.info("Received new Token")
            logger.debug("New Token: '%s...'", token[:42]) # log only start in order to avoid leak
            return token
        else:
            logger.error("Failed to renew Token, did not receive an %s header" % self.response_header_name)
            return self.token # try with old token, will try another login if token is invalid....

class JwtAuthenticationHandler(TokenBasedAuthenticationHandler):
    """ Authenticate via JWT Tokens as implemented in SBB WSG """
    def __init__(self, username, password, jwt_login_url, verify_ssl=True):
        super().__init__(username=username, password=password, login_url=jwt_login_url, verify_ssl=verify_ssl)
        self.request_header_name="Authorization"
        self.response_header_name="Authorization"

class SamlAuthenticationHandler(TokenBasedAuthenticationHandler):
    """ Authenticate via SAML Cookies as implemented in SBB WSG """
    def __init__(self, username, password, saml_login_url, verify_ssl=True):
        super().__init__(username=username, password=password, login_url=saml_login_url, verify_ssl=verify_ssl)
        self.request_header_name="Cookie"
        self.response_header_name="Set-Cookie"

class HttpClient:
    """ A HttpClient able to do authentication via
    - Retry: Retry for instance 401 as this does sometimes help (Bug in SBB eBiz/LDAP)
    - BasicAuthentication: Username/Password - Use for instance from within SBB LAN. Also supports retry.
    - JWTAuthentication: JWT using a specific Login URL and HTTP Authorization Headers for use with SBB Webservice Gateway (WSG) - access from outside SBB LAN
    - SamlAuthentication: SAML using a specific Login URL and HTTP Set-Cookie and Cookie Headers for use with SBB Webservice Gateway (WSG) - access from outside SBB LAN
    Will retry status code 5xx and if told so by authentication handler max_retries times (default 3 times)"""

    def __init__(self, base_url, authentication_handler=EmptyAuthenticationHandler(), max_retries=3, retry_delay_sec=3, verify_ssl=True):
        self.base_url = base_url
        self.authentication_handler = authentication_handler
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        # the feature urlopen with ssl context is only supported from python 3.4.3 onwards
        if not verify_ssl:
            if sys.version_info >= (3,4,3):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self.ctx = ctx
            else:
                logger.warning("Disabling verify ssl is not supported in python version below 3.4.3. Ignoring configuration, ssl verfication is enabled")
                self.ctx = None
        else:
            # verification activated, default will be fine
            self.ctx = None

    def open_and_read(self, request_path=None):
        response = self.open(request_path)
        return response.readall().decode(response.headers.get_content_charset() or "utf-8")

    def open(self, request_path=None, retry=0):
        request_headers = self.authentication_handler.request_headers()
        try:
            request = Request(self.__request_url__(request_path))
            logger.debug("Request to %s", self.__request_url__(request_path))
            for key, value in request_headers.items():
                request.add_header(key, value)
            logger.debug("Request headers: %s" % request.headers.keys()) # do not log contents to avoid leak
            return self.__open__(request)
        except HTTPError as e:
            if e.code in (401,402,403,407,408) and retry < self.max_retries and self.authentication_handler.handle_forbidden(request_headers, e.code): # maybe authentication issue
                return self.__retry__("Potential authentication status code %d" % e.code, request_path, retry);
            elif e.code >= 500 and retry < self.max_retries: # retry server side error (may be temporary), max 3 attempts
                return self.__retry__("Temporary error %d %s" % (e.code, e.reason), request_path, retry);
            else:
                self.__try__log_contents__(e)
                raise e
        except (URLError, ContentTooShortError) as e:
            if retry < self.max_retries:
                return self.__retry__("Error %s" % str(e), request_path, retry)
            else:
                raise e

    def __retry__(self, text, request_path, retry):
        logger.info("%s requesting %s, retry %s", text, self.__request_url__(request_path), retry)
        sleep(retry *  self.retry_delay_sec) # back off after first time
        return self.open(request_path, retry + 1)

    def __request_url__(self, request_path):
        if request_path:
            return self.base_url + request_path
        else:
            return self.base_url

    def __open__(self, request):
        if self.ctx:
            return urlopen(request, context=self.ctx)
        else:
            return urlopen(request)


    def __try__log_contents__(self, e):
        try:
            logger.info("Response heades: %s" % str(e.headers))
            logger.info("Response contents %s" % e.file.read())
        except:
            pass # ignore
